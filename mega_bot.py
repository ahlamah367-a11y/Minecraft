import os
import sqlite3
import json
import asyncio
import random
import time
import re
import threading
from datetime import datetime, timedelta, timezone
from flask import Flask

import discord
from discord.ext import commands, tasks
from discord import app_commands

# --- إعداد خادم الويب الوهمي لإرضاء منصة Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# تشغيل السيرفر في خلفية البوت
threading.Thread(target=run_flask, daemon=True).start()
# ---------------------------------------------

# ==================================
# إعداد البوت
# ==================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.guild_messages = True
intents.reactions = True
intents.voice_states = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

# ==================================
# الملفات وقواعد البيانات
# ==================================

WELCOME_CONFIG_FILE = "welcome_config.json"
LOGS_CONFIG_FILE = "logs_config.json"
MOD_CONFIG_FILE = "mod_roles.json"
WARNINGS_FILE = "warnings.json"
CONFIG_FILE = "config.json"
ERROR_LOG_FILE = "error_logs.json"
PROTECTION_FILE = "protection_config.json"
SUGGESTIONS_FILE = "suggestions.json"
SUGGESTION_CONFIG_FILE = "suggestion_config.json"
XP_FILE = "xp.json"
AFK_FILE = "afk.json"
REACTION_ROLES_FILE = "reaction_roles.json"
ANTI_CONFIG_FILE = "anti_config.json"
BAD_WORDS_FILE = "bad_words.json"
PANELS_FILE = "panels.json"
MEMBER_COUNT_FILE = "member_count.json"

# ملفات نظام التقديمات
APPLICATIONS_FILE = "applications_data.json"
APPLICATION_CONFIG_FILE = "applications_config.json"
APPLICATION_TYPES_FILE = "application_types.json"
APPLICATION_QUESTIONS_FILE = "application_questions.json"
APPLICATION_DECISIONS_FILE = "application_decisions.json"
APPLICATION_COOLDOWN_FILE = "application_cooldowns.json"

# ملف نظام البانلات العامة
GENERAL_PANELS_FILE = "general_panels.json"

# ==================================
# دوال التحميل والحفظ العامة
# ==================================

def load_json(filename, default=None):
    if default is None:
        default = {}
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return default
    return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def save_error(error):
    logs = load_json(ERROR_LOG_FILE, [])
    logs.append({
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "error": str(error)
    })
    save_json(ERROR_LOG_FILE, logs)

def parse_hex_color(hex_str, default_color=discord.Color.blurple()):
    if not hex_str:
        return default_color
    hex_str = hex_str.strip().lstrip('#').replace('0x', '')
    try:
        return discord.Color(int(hex_str, 16))
    except ValueError:
        return default_color

welcome_config = load_json(WELCOME_CONFIG_FILE, {})
mod_roles = load_json(MOD_CONFIG_FILE, {})
protection_config = load_json(PROTECTION_FILE, {})
suggestions = load_json(SUGGESTIONS_FILE, {})
suggestion_config = load_json(SUGGESTION_CONFIG_FILE, {})
xp_data = load_json(XP_FILE, {})
afk_users = load_json(AFK_FILE, {})
reaction_roles = load_json(REACTION_ROLES_FILE, {})
anti_config = load_json(ANTI_CONFIG_FILE, {})
bad_words = load_json(BAD_WORDS_FILE, [])
persistent_panels = load_json(PANELS_FILE, [])

applications_data = load_json(APPLICATIONS_FILE, {})
application_config = load_json(APPLICATION_CONFIG_FILE, {})
application_types = load_json(APPLICATION_TYPES_FILE, {})
application_questions = load_json(APPLICATION_QUESTIONS_FILE, {})
application_decisions = load_json(APPLICATION_DECISIONS_FILE, {})
application_cooldowns = load_json(APPLICATION_COOLDOWN_FILE, {})

general_panels = load_json(GENERAL_PANELS_FILE, [])

def save_general_panels():
    save_json(GENERAL_PANELS_FILE, general_panels)

def save_persistent():
    save_json(PANELS_FILE, persistent_panels)

def save_application_types():
    save_json(APPLICATION_TYPES_FILE, application_types)

def save_all_applications():
    save_json(APPLICATIONS_FILE, applications_data)
    save_json(APPLICATION_CONFIG_FILE, application_config)
    save_json(APPLICATION_TYPES_FILE, application_types)
    save_json(APPLICATION_QUESTIONS_FILE, application_questions)
    save_json(APPLICATION_DECISIONS_FILE, application_decisions)
    save_json(APPLICATION_COOLDOWN_FILE, application_cooldowns)

def save_member_count(data):
    save_json(MEMBER_COUNT_FILE, data)

def load_member_count():
    return load_json(MEMBER_COUNT_FILE, {})

def save_suggestions_config():
    save_json(SUGGESTION_CONFIG_FILE, suggestion_config)

# ==================================
# نظام AFK المتكامل
# ==================================

def save_afk():
    save_json(AFK_FILE, afk_users)

def format_afk_duration(seconds: float):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = []
    if days: parts.append(f"{days} يوم")
    if hours: parts.append(f"{hours} ساعة")
    if minutes: parts.append(f"{minutes} دقيقة")
    if seconds and not parts: parts.append(f"{seconds} ثانية")

    return " و".join(parts) if parts else "أقل من ثانية"

def get_guild_afk(guild_id):
    guild_id = str(guild_id)
    if guild_id not in afk_users:
        afk_users[guild_id] = {}
    return afk_users[guild_id]

def get_user_afk(guild_id, user_id):
    guild_data = get_guild_afk(guild_id)
    return guild_data.get(str(user_id))

def remove_user_afk(guild_id, user_id):
    guild_id = str(guild_id)
    user_id = str(user_id)
    if guild_id not in afk_users:
        return None
    data = afk_users[guild_id].pop(user_id, None)
    if not afk_users[guild_id]:
        afk_users.pop(guild_id, None)
    if data:
        save_afk()
    return data

async def handle_afk_message(message):
    if not message.guild or message.author.bot:
        return

    guild_id = str(message.guild.id)
    author_id = str(message.author.id)

    own_afk = get_user_afk(guild_id, author_id)
    if own_afk:
        removed = remove_user_afk(guild_id, author_id)
        if removed:
            started = removed.get("started_at", time.time())
            duration = max(0, time.time() - float(started))
            embed = discord.Embed(
                title="👋 أهلًا بعودتك!",
                description=(
                    f"{message.author.mention} رجعت من وضع **AFK**.\n\n"
                    f"⏱️ **مدة الغياب:** `{format_afk_duration(duration)}`"
                ),
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.set_footer(text="تم إلغاء حالة AFK تلقائيًا")
            try:
                await message.channel.send(embed=embed, delete_after=8)
            except Exception:
                pass

    notified = set()
    for member in message.mentions:
        if member.bot or member.id in notified:
            continue
        notified.add(member.id)
        data = get_user_afk(guild_id, member.id)
        if not data:
            continue

        reason = data.get("reason", "لم يتم تحديد سبب")
        started = data.get("started_at", time.time())
        duration = max(0, time.time() - float(started))

        embed = discord.Embed(
            title="💤 هذا العضو في وضع AFK",
            description=(
                f"👤 **العضو:** {member.mention}\n"
                f"💬 **السبب:** {reason}\n"
                f"⏱️ **منذ:** `{format_afk_duration(duration)}`"
            ),
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="قد يكون العضو غير متواجد حاليًا")
        try:
            await message.channel.send(embed=embed, delete_after=10)
        except Exception:
            pass

# ==================================
# مجموعة أوامر AFK
# ==================================

afk_group = app_commands.Group(
    name="afk",
    description="إدارة وضع AFK"
)

@afk_group.command(name="set", description="تفعيل وضع AFK")
@app_commands.describe(reason="سبب الغياب - اختياري")
async def afk(interaction: discord.Interaction, reason: str = "غير متوفر"):
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)
    guild_data = get_guild_afk(guild_id)

    if user_id in guild_data:
        old_data = guild_data[user_id]
        old_reason = old_data.get("reason", "غير متوفر")
        embed = discord.Embed(
            title="💤 أنت بالفعل AFK",
            description=(
                f"أنت حاليًا في وضع **AFK**.\n\n"
                f"💬 **السبب الحالي:** {old_reason}\n\n"
                f"يمكنك فقط إرسال رسالة في الشات للعودة تلقائيًا."
            ),
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    now = time.time()
    guild_data[user_id] = {
        "reason": reason,
        "started_at": now,
        "started_at_text": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    }
    save_afk()

    embed = discord.Embed(
        title="💤 تم تفعيل وضع AFK",
        description=(
            f"👤 **العضو:** {interaction.user.mention}\n\n"
            f"💬 **السبب:** {reason}\n"
            f"🕐 **وقت التفعيل:** <t:{int(now)}:F>\n"
            f"⏱️ **منذ:** <t:{int(now)}:R>\n\n"
            f"📌 سيتم إلغاء AFK تلقائيًا عند إرسال رسالة."
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text=f"AFK • {interaction.guild.name}")
    await interaction.response.send_message(embed=embed)

@afk_group.command(name="status", description="عرض حالة AFK لعضو")
@app_commands.describe(member="العضو المراد فحص حالته")
async def afk_status(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    data = get_user_afk(interaction.guild.id, member.id)

    if not data:
        embed = discord.Embed(
            title="🟢 العضو غير AFK",
            description=f"{member.mention} ليس في وضع **AFK** حاليًا.",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    started = float(data.get("started_at", time.time()))
    duration = max(0, time.time() - started)
    reason = data.get("reason", "غير متوفر")

    embed = discord.Embed(
        title="💤 حالة AFK",
        description=f"{member.mention} حاليًا في وضع **AFK**.",
        color=discord.Color.orange()
    )
    embed.add_field(name="💬 السبب", value=reason, inline=False)
    embed.add_field(name="⏱️ مدة الغياب", value=format_afk_duration(duration), inline=True)
    embed.add_field(name="🕐 بدأ AFK", value=f"<t:{int(started)}:R>", inline=True)
    embed.add_field(name="📅 الوقت", value=f"<t:{int(started)}:F>", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="نظام AFK")
    await interaction.response.send_message(embed=embed)

@afk_group.command(name="list", description="عرض جميع الأعضاء الموجودين في وضع AFK")
async def afk_list(interaction: discord.Interaction):
    guild_data = get_guild_afk(interaction.guild.id)
    if not guild_data:
        embed = discord.Embed(
            title="💤 قائمة AFK",
            description="لا يوجد أي عضو في وضع AFK حاليًا.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        return

    lines = []
    for user_id, data in list(guild_data.items()):
        member = interaction.guild.get_member(int(user_id))
        if not member:
            continue

        started = float(data.get("started_at", time.time()))
        duration = max(0, time.time() - started)
        reason = data.get("reason", "غير متوفر")
        lines.append(f"👤 {member.mention}\n💬 `{reason}` • ⏱️ `{format_afk_duration(duration)}`")

    if not lines:
        embed = discord.Embed(
            title="💤 قائمة AFK",
            description="لا يوجد أي عضو في وضع AFK حاليًا.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        return

    text = "\n\n".join(lines[:20])
    if len(lines) > 20:
        text += f"\n\n📌 وهناك `{len(lines) - 20}` عضو آخر."

    embed = discord.Embed(
        title="💤 أعضاء AFK",
        description=text,
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text=f"إجمالي AFK: {len(lines)}")
    await interaction.response.send_message(embed=embed)

@afk_group.command(name="remove", description="إزالة AFK عن عضو يدويًا")
@app_commands.describe(member="العضو المراد إزالة AFK عنه")
@app_commands.checks.has_permissions(manage_messages=True)
async def afk_remove(interaction: discord.Interaction, member: discord.Member):
    data = get_user_afk(interaction.guild.id, member.id)
    if not data:
        embed = discord.Embed(
            title="⚠️ العضو ليس AFK",
            description=f"{member.mention} ليس في وضع AFK حاليًا.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    started = float(data.get("started_at", time.time()))
    duration = max(0, time.time() - started)
    remove_user_afk(interaction.guild.id, member.id)

    embed = discord.Embed(
        title="✅ تم إزالة AFK",
        description=(
            f"👤 **العضو:** {member.mention}\n"
            f"⏱️ **مدة AFK:** `{format_afk_duration(duration)}`\n"
            f"👮 **بواسطة:** {interaction.user.mention}"
        ),
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc)
    )
    await interaction.response.send_message(embed=embed)

bot.tree.add_command(afk_group)

# ==================================
# نظام البانلات العامة الديناميكية (المطورة)
# ==================================

STYLE_MAP = {
    "أزرق": discord.ButtonStyle.primary,
    "blue": discord.ButtonStyle.primary,
    "primary": discord.ButtonStyle.primary,
    "رمادي": discord.ButtonStyle.secondary,
    "grey": discord.ButtonStyle.secondary,
    "gray": discord.ButtonStyle.secondary,
    "secondary": discord.ButtonStyle.secondary,
    "أخضر": discord.ButtonStyle.success,
    "green": discord.ButtonStyle.success,
    "success": discord.ButtonStyle.success,
    "أحمر": discord.ButtonStyle.danger,
    "red": discord.ButtonStyle.danger,
    "danger": discord.ButtonStyle.danger,
}

class GeneralPanelButton(discord.ui.Button):
    def __init__(self, panel_id, button_data):
        self.panel_id = panel_id
        self.button_data = button_data

        label = button_data.get("name", "زر")
        emoji = button_data.get("emoji")
        style_key = str(button_data.get("style", "secondary")).lower()
        style = STYLE_MAP.get(style_key, discord.ButtonStyle.secondary)

        super().__init__(
            label=label[:80],
            emoji=emoji if emoji else None,
            style=style,
            custom_id=f"general_panel:{panel_id}:{button_data.get('id')}"
        )

    async def callback(self, interaction: discord.Interaction):
        data = general_panels
        panel = next((p for p in data if isinstance(p, dict) and p.get("id") == self.panel_id), None)

        if not panel:
            await interaction.response.send_message("❌ هذا البانل لم يعد موجودًا.", ephemeral=True)
            return

        button = next((b for b in panel.get("buttons", []) if b.get("id") == self.button_data.get("id")), None)

        if not button:
            await interaction.response.send_message("❌ هذا الزر لم يعد موجودًا.", ephemeral=True)
            return

        embed_color = parse_hex_color(panel.get("color"), discord.Color.blurple())
        embed = discord.Embed(
            title=button.get("title", "بدون عنوان"),
            description=button.get("description", "بدون وصف"),
            color=embed_color,
            timestamp=datetime.now(timezone.utc)
        )

        image_url = button.get("image")
        if image_url:
            embed.set_image(url=image_url)

        for field in button.get("fields", []):
            name = field.get("name")
            value = field.get("value")
            if name and value:
                embed.add_field(name=name, value=value, inline=field.get("inline", False))

        await interaction.response.send_message(embed=embed, ephemeral=True)


class GeneralPanelView(discord.ui.View):
    def __init__(self, panel):
        super().__init__(timeout=None)
        panel_id = panel.get("id")
        for button_data in panel.get("buttons", []):
            self.add_item(GeneralPanelButton(panel_id, button_data))


class OpenNextModalView(discord.ui.View):
    def __init__(self, panel_data, current_button, total_buttons):
        super().__init__(timeout=180)
        self.panel_data = panel_data
        self.current_button = current_button
        self.total_buttons = total_buttons

    @discord.ui.button(label="⚙️ متابعة إعداد الأزرار", style=discord.ButtonStyle.primary)
    async def open_modal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            GeneralButtonModal(self.panel_data, self.current_button, self.total_buttons)
        )
        self.stop()


class GeneralButtonModal(discord.ui.Modal):
    def __init__(self, panel_data, button_number, total_buttons):
        super().__init__(title=f"إعداد الزر {button_number}/{total_buttons}")
        self.panel_data = panel_data
        self.button_number = button_number
        self.total_buttons = total_buttons

        self.button_name = discord.ui.TextInput(label="اسم الزر", placeholder="مثال: شرح الرتب", max_length=80)
        self.button_emoji = discord.ui.TextInput(label="إيموجي الزر", placeholder="مثال: 📋", required=False, max_length=100)
        self.button_style = discord.ui.TextInput(
            label="لون الزر",
            placeholder="أزرق / رمادي / أخضر / أحمر (الافتراضي: رمادي)",
            required=False,
            max_length=20
        )
        self.embed_title = discord.ui.TextInput(label="عنوان الـ Embed عند الضغط", placeholder="مثال: شرح الرتب", max_length=256)
        self.embed_description = discord.ui.TextInput(
            label="وصف الـ Embed + رابط الصورة اختيارياً",
            placeholder="اكتب وصف الرسالة التي تظهر عند النقر...",
            style=discord.TextStyle.paragraph,
            max_length=4000
        )

        self.add_item(self.button_name)
        self.add_item(self.button_emoji)
        self.add_item(self.button_style)
        self.add_item(self.embed_title)
        self.add_item(self.embed_description)

    async def on_submit(self, interaction: discord.Interaction):
        # البحث عن رابط صورة داخل الوصف تلقائيًا إذا وُجد
        desc_text = self.embed_description.value
        button_image = None
        urls = re.findall(r'https?://\S+\.(?:png|jpg|jpeg|gif|webp)', desc_text, re.IGNORECASE)
        if urls:
            button_image = urls[0]

        button_data = {
            "id": str(random.randint(100000, 999999)),
            "name": self.button_name.value,
            "emoji": self.button_emoji.value or None,
            "style": self.button_style.value or "secondary",
            "title": self.embed_title.value,
            "description": desc_text,
            "image": button_image,
            "fields": []
        }

        self.panel_data["buttons"].append(button_data)

        if len(self.panel_data["buttons"]) < self.total_buttons:
            next_number = len(self.panel_data["buttons"]) + 1
            await interaction.response.send_message(
                f"✅ تم حفظ بيانات الزر {self.button_number}. اضغط للبدء في الزر {next_number}:",
                view=OpenNextModalView(self.panel_data, next_number, self.total_buttons),
                ephemeral=True
            )
            return

        panel_id = str(random.randint(100000000, 999999999))
        self.panel_data["id"] = panel_id
        self.panel_data["created_at"] = time.time()

        general_panels.append(self.panel_data)
        save_general_panels()

        view = GeneralPanelView(self.panel_data)
        panel_color = parse_hex_color(self.panel_data.get("color"), discord.Color.blurple())

        embed = discord.Embed(
            title=self.panel_data["title"],
            description=self.panel_data["description"],
            color=panel_color
        )
        if self.panel_data.get("image"):
            embed.set_image(url=self.panel_data["image"])

        await interaction.response.send_message("✅ تم إنشاء البانل بنجاح!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)
        bot.add_view(view)


class GeneralPanelModal(discord.ui.Modal):
    def __init__(self, button_count):
        super().__init__(title="إنشاء بانل عام")
        self.button_count = button_count

        self.panel_title = discord.ui.TextInput(label="عنوان البانل", placeholder="مثال: معلومات السيرفر", max_length=256)
        self.panel_description = discord.ui.TextInput(
            label="وصف البانل",
            placeholder="اكتب وصف البانل هنا...",
            style=discord.TextStyle.paragraph,
            max_length=4000
        )
        self.panel_color = discord.ui.TextInput(
            label="لون البانل (Hex Code)",
            placeholder="مثال: #3498db أو ff0000 (اختياري)",
            required=False,
            max_length=10
        )
        self.panel_image = discord.ui.TextInput(
            label="رابط صورة البانل (Image URL)",
            placeholder="https://example.com/image.png (اختياري)",
            required=False,
            max_length=500
        )

        self.add_item(self.panel_title)
        self.add_item(self.panel_description)
        self.add_item(self.panel_color)
        self.add_item(self.panel_image)

    async def on_submit(self, interaction: discord.Interaction):
        panel_data = {
            "id": None,
            "title": self.panel_title.value,
            "description": self.panel_description.value,
            "color": self.panel_color.value or None,
            "image": self.panel_image.value or None,
            "buttons": []
        }
        await interaction.response.send_message(
            "✅ تم حفظ تفاصيل البانل! اضغط الزر أدناه للبدء بتعيين إعدادات الأزرار:",
            view=OpenNextModalView(panel_data, 1, self.button_count),
            ephemeral=True
        )


@bot.tree.command(name="general-panel", description="إنشاء بانل عام بأزرار قابلة للتخصيص والألوان والصور")
@app_commands.describe(buttons="عدد الأزرار التي تريدها من 1 إلى 5")
@app_commands.choices(
    buttons=[
        app_commands.Choice(name="1 زر", value=1),
        app_commands.Choice(name="2 أزرار", value=2),
        app_commands.Choice(name="3 أزرار", value=3),
        app_commands.Choice(name="4 أزرار", value=4),
        app_commands.Choice(name="5 أزرار", value=5)
    ]
)
@app_commands.checks.has_permissions(administrator=True)
async def general_panel(interaction: discord.Interaction, buttons: app_commands.Choice[int]):
    await interaction.response.send_modal(GeneralPanelModal(buttons.value))


# ==================================
# البانل السريع (Single-Button Panel)
# ==================================

class LegacyGeneralPanelView(discord.ui.View):
    def __init__(self, button_name, button_emoji, button_description, color=None):
        super().__init__(timeout=None)

        button = discord.ui.Button(
            label=button_name,
            emoji=button_emoji,
            style=discord.ButtonStyle.primary,
            custom_id=f"general_panel_{button_name[:30]}"
        )
        button.callback = self.button_callback
        self.add_item(button)

        self.button_label = button_name
        self.button_description = button_description
        self.color = parse_hex_color(color, discord.Color.blurple())

    async def button_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=self.button_label,
            description=self.button_description,
            color=self.color
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="panel", description="إنشاء بانل عام سريع مع تحديد الألوان والصورة")
@app_commands.describe(
    channel="الروم المراد الإرسال إليه",
    description="وصف البانل",
    button_name="اسم الزر",
    button_emoji="إيموجي الزر",
    button_description="الوصف الظاهر بعد الضغط على الزر",
    image="رابط صورة البانل - اختياري",
    color="كود اللون Hex - اختياري (مثال: #ff0000)"
)
@app_commands.checks.has_permissions(administrator=True)
async def panel(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    description: str,
    button_name: str,
    button_emoji: str,
    button_description: str,
    image: str = None,
    color: str = None
):
    embed_color = parse_hex_color(color, discord.Color.blurple())
    embed = discord.Embed(title="📌 Panel", description=description, color=embed_color)
    if image:
        embed.set_image(url=image)

    view = LegacyGeneralPanelView(button_name, button_emoji, button_description, color)
    msg = await channel.send(embed=embed, view=view)

    general_panels.append({
        "guild_id": interaction.guild.id,
        "channel_id": channel.id,
        "message_id": msg.id,
        "button_name": button_name,
        "button_emoji": button_emoji,
        "button_description": button_description,
        "color": color
    })

    save_general_panels()
    await interaction.response.send_message("✅ تم إنشاء البانل وحفظه بنجاح", ephemeral=True)

# ==================================
# نظام السجلات (Logs System)
# ==================================

async def send_log(guild, title, description, color):
    config = load_json(LOGS_CONFIG_FILE, {})
    log_channel_id = config.get(str(guild.id))
    if log_channel_id:
        channel = guild.get_channel(log_channel_id)
        if channel:
            embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc))
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

# ==================================
# مجموعة أوامر السجلات
# ==================================

logs_group = app_commands.Group(
    name="logs",
    description="إدارة نظام السجلات"
)

@logs_group.command(name="set", description="تحديد روم السجلات (Logs)")
@app_commands.describe(channel="روم السجلات")
@app_commands.checks.has_permissions(administrator=True)
async def set_logs(interaction: discord.Interaction, channel: discord.TextChannel):
    config = load_json(LOGS_CONFIG_FILE, {})
    config[str(interaction.guild.id)] = channel.id
    save_json(LOGS_CONFIG_FILE, config)
    await interaction.response.send_message(f"✅ تم ضبط روم السجلات بنجاح في {channel.mention}", ephemeral=True)

@logs_group.command(name="remove", description="إلغاء وتفريغ إعداد روم السجلات")
@app_commands.checks.has_permissions(administrator=True)
async def remove_logs(interaction: discord.Interaction):
    config = load_json(LOGS_CONFIG_FILE, {})
    gid = str(interaction.guild.id)
    if gid in config:
        del config[gid]
        save_json(LOGS_CONFIG_FILE, config)
        await interaction.response.send_message("❌ تم إلغاء روم السجلات بنجاح.", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ روم السجلات غير مفعل أساساً.", ephemeral=True)

bot.tree.add_command(logs_group)

# ==================================
# نظام الترحيب والعداد
# ==================================

@bot.tree.command(name="set-welcome", description="تعداد وتخصيص رسالة الترحيب وأعضاء السيرفر")
@app_commands.describe(
    channel="روم الترحيب",
    message="نص رسالة الترحيب (يمكن استخدام المتغيرات)",
    show_user="هل تريد منشن العضو؟",
    show_count="هل تريد إظهار العدد؟"
)
@app_commands.choices(
    show_user=[
        app_commands.Choice(name="نعم", value="yes"),
        app_commands.Choice(name="لا", value="no")
    ],
    show_count=[
        app_commands.Choice(name="نعم", value="yes"),
        app_commands.Choice(name="لا", value="no")
    ]
)
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str,
    show_user: str,
    show_count: str
):
    guild_id = str(interaction.guild.id)
    welcome_config[guild_id] = {
        "channel_id": channel.id,
        "message": message,
        "show_user": (show_user == "yes"),
        "show_count": (show_count == "yes")
    }
    save_json(WELCOME_CONFIG_FILE, welcome_config)
    await interaction.response.send_message(f"✅ تم حفظ إعدادات الترحيب بنجاح في روم {channel.mention}!", ephemeral=True)

@bot.tree.command(name="welcome-test", description="تجربة رسالة الترحيب")
@app_commands.checks.has_permissions(administrator=True)
async def welcome_test(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    if guild_id not in welcome_config:
        await interaction.response.send_message("❌ لم يتم إعداد الترحيب بعد.", ephemeral=True)
        return
    data = welcome_config[guild_id]
    channel = interaction.guild.get_channel(data.get("channel_id"))
    if not channel:
        await interaction.response.send_message("❌ روم الترحيب غير موجود.", ephemeral=True)
        return
    message = data.get("message", "أهلاً بك {user} في السيرفر!").replace("{user}", interaction.user.mention)
    embed = discord.Embed(title="👋 تجربة ترحيب", description=message, color=discord.Color.green())
    await channel.send(content=interaction.user.mention, embed=embed)
    await interaction.response.send_message("✅ تم إرسال تجربة الترحيب.", ephemeral=True)

@bot.tree.command(name="welcome-remove", description="حذف إعداد الترحيب")
@app_commands.checks.has_permissions(administrator=True)
async def welcome_remove(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    if guild_id in welcome_config:
        del welcome_config[guild_id]
        save_json(WELCOME_CONFIG_FILE, welcome_config)
        await interaction.response.send_message("✅ تم حذف نظام الترحيب.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ نظام الترحيب غير مفعل.", ephemeral=True)

@bot.tree.command(name="member-count-setup", description="إعداد عداد الأعضاء")
@app_commands.checks.has_permissions(administrator=True)
async def member_count_setup(interaction: discord.Interaction, channel: discord.VoiceChannel, name: str = "👥 الأعضاء: {count}"):
    data = load_member_count()
    data[str(interaction.guild.id)] = {"channel_id": channel.id, "name": name}
    save_member_count(data)
    count = interaction.guild.member_count
    await channel.edit(name=name.replace("{count}", str(count)))
    await interaction.response.send_message(f"✅ تم إعداد عداد الأعضاء الحالي: `{count}`", ephemeral=True)

@bot.tree.command(name="member-count-remove", description="حذف عداد الأعضاء")
@app_commands.checks.has_permissions(administrator=True)
async def member_count_remove(interaction: discord.Interaction):
    data = load_member_count()
    guild_id = str(interaction.guild.id)
    if guild_id in data:
        del data[guild_id]
        save_member_count(data)
        await interaction.response.send_message("✅ تم حذف عداد الأعضاء.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ لا يوجد عداد أعضاء مفعل.", ephemeral=True)

async def update_member_count(guild):
    data = load_member_count()
    guild_id = str(guild.id)
    if guild_id not in data:
        return
    channel = guild.get_channel(data[guild_id]["channel_id"])
    if channel:
        try:
            await channel.edit(name=data[guild_id]["name"].replace("{count}", str(guild.member_count)))
        except Exception:
            pass

# ==================================
# التحقق من الصلاحيات والأحداث الأساسية
# ==================================

def has_mod_permission(member):
    if member.guild_permissions.administrator or member.guild_permissions.manage_messages:
        return True
    role_id = mod_roles.get(str(member.guild.id))
    if role_id:
        role = member.guild.get_role(role_id)
        if role and role in member.roles:
            return True
    return False

@bot.event
async def on_member_join(member):
    guild = member.guild
    guild_id = str(guild.id)

    if guild_id in welcome_config:
        data = welcome_config[guild_id]
        channel = guild.get_channel(data.get("channel_id"))
        if channel:
            raw_message = data.get("message", "أهلاً بك {user} في السيرفر!")
            show_user = data.get("show_user", True)
            count = guild.member_count

            formatted_message = raw_message.replace("{count}", str(count))\
                                          .replace("{user}", member.mention if show_user else member.name)\
                                          .replace("{username}", member.name)\
                                          .replace("{server}", guild.name)

            embed = discord.Embed(title="👋 عضو جديد!", description=formatted_message, color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
            embed.set_thumbnail(url=member.display_avatar.url)
            try:
                await channel.send(content=member.mention if show_user else None, embed=embed)
            except Exception:
                pass

    cfg = load_json(CONFIG_FILE, {})
    role_id = cfg.get(guild_id, {}).get("autorole_id")
    if role_id:
        role = guild.get_role(role_id)
        if role:
            try: await member.add_roles(role)
            except Exception: pass

    await update_member_count(guild)
    await send_log(guild, "📥 دخول عضو", f"العضو: {member.mention} (`{member.id}`)", discord.Color.green())

@bot.event
async def on_member_remove(member):
    guild_id = str(member.guild.id)
    user_id = str(member.id)

    if guild_id in afk_users:
        if user_id in afk_users[guild_id]:
            del afk_users[guild_id][user_id]
            if not afk_users[guild_id]:
                del afk_users[guild_id]
            save_afk()

    await update_member_count(member.guild)

    await send_log(
        member.guild,
        "📤 خروج عضو",
        f"العضو: {member.mention} (`{member.id}`)",
        discord.Color.dark_red()
    )

# ==================================
# فحص الحماية المتقدم (Anti Check)
# ==================================

async def anti_check(message):
    if (
        not message.guild
        or message.author.bot
        or has_mod_permission(message.author)
    ):
        return False

    config = anti_config.get(str(message.guild.id), {})
    content = message.content.lower()
    prot = protection_config.get(str(message.guild.id), {})

    if config.get("massmention") and message.mention_everyone:
        try:
            await message.delete()
            await message.author.timeout(timedelta(minutes=5), reason="Mass Mention")
        except Exception:
            pass
        return True

    if config.get("mention") and len(message.mentions) >= 5:
        try:
            await message.delete()
            await message.author.timeout(timedelta(minutes=3), reason="Spam Mentions")
        except Exception:
            pass
        return True

    if config.get("badwords"):
        for word in bad_words:
            if word in content:
                try:
                    await message.delete()
                    await message.author.timeout(timedelta(minutes=2), reason="Bad Words")
                except Exception:
                    pass
                return True

    if (prot.get("anti_links") or prot.get("links")) and re.findall(r"https?://\S+", content):
        try:
            await message.delete()
            await message.author.timeout(timedelta(minutes=2), reason="رابط ممنوع")
        except Exception:
            pass
        return True

    if (prot.get("anti_invite") or prot.get("invites")) and ("discord.gg/" in content or "discord.com/invite/" in content):
        try:
            await message.delete()
            await message.author.timeout(timedelta(minutes=5), reason="دعوة ديسكورد")
        except Exception:
            pass
        return True

    return False


async def welcome_on_message(message):
    if message.author.bot or not message.guild:
        return

    if await anti_check(message):
        return

    await handle_afk_message(message)

    guild_id = str(message.guild.id)
    user_id_str = str(message.author.id)

    if guild_id not in xp_data:
        xp_data[guild_id] = {}

    if user_id_str not in xp_data[guild_id]:
        xp_data[guild_id][user_id_str] = {"xp": 0, "level": 1}

    xp_data[guild_id][user_id_str]["xp"] += 1

    current_xp = xp_data[guild_id][user_id_str]["xp"]
    current_level = xp_data[guild_id][user_id_str]["level"]

    if current_xp >= current_level * 100:
        xp_data[guild_id][user_id_str]["level"] += 1
        new_level = xp_data[guild_id][user_id_str]["level"]
        try:
            await message.channel.send(f"🎉 مبروك {message.author.mention} وصلت للمستوى `{new_level}`!")
        except Exception:
            pass

    save_json(XP_FILE, xp_data)
    await bot.process_commands(message)

# ==================================
# نظام التقديمات المتطور
# ==================================

def has_application(guild_id, user_id):
    for app in applications_data.get(str(guild_id), []):
        if app["user_id"] == user_id and app["status"] == "pending":
            return True
    return False

class ApplicationSelectView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = str(guild_id)

        types = application_types.get(self.guild_id, [])

        if isinstance(types, dict):
            options = []
            for name, data in types.items():
                description = data.get("description", "بدون وصف") if isinstance(data, dict) else "بدون وصف"
                options.append(discord.SelectOption(label=str(name)[:100], description=str(description)[:100], value=str(name)))
        else:
            options = []
            for app_type in types:
                if not isinstance(app_type, dict) or not app_type.get("enabled", True):
                    continue
                name = app_type.get("name", "تقديم")
                description = app_type.get("description", "بدون وصف")
                options.append(discord.SelectOption(label=str(name)[:100], description=str(description)[:100], value=str(name)))

        options = options[:25]
        if not options:
            options.append(discord.SelectOption(label="لا توجد أنواع تقديم", description="لم تتم إضافة أي نوع تقديم بعد", value="none"))

        select = discord.ui.Select(
            placeholder="📋 اختر نوع التقديم",
            options=options,
            custom_id=f"application_select_{self.guild_id}"
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_type = interaction.data["values"][0]

        if selected_type == "none":
            await interaction.response.send_message("❌ لا توجد أنواع تقديم متاحة حاليًا.", ephemeral=True)
            return

        if has_application(interaction.guild.id, interaction.user.id):
            await interaction.response.send_message("❌ لديك تقديم قيد المراجعة بالفعل.", ephemeral=True)
            return

        await interaction.response.send_modal(ApplyModal(interaction.guild.id, selected_type))


class ApplyModal(discord.ui.Modal):
    def __init__(self, guild_id, app_type):
        super().__init__(title=f"تقديم {app_type}")
        self.guild_id = str(guild_id)
        self.app_type = app_type

        type_questions = application_questions.get(self.guild_id, {}).get(
            app_type, ["اسمك؟", "عمرك؟", "خبرتك؟", "لماذا تريد الانضمام؟", "أي معلومات إضافية؟"]
        )

        self.inputs = []
        for q in type_questions[:5]:
            if q and q != "اختياري":
                item = discord.ui.TextInput(label=str(q)[:45], style=discord.TextStyle.paragraph, required=False)
                self.inputs.append(item)
                self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)

        if has_application(interaction.guild.id, interaction.user.id):
            await interaction.response.send_message("❌ لديك تقديم قيد المراجعة بالفعل.", ephemeral=True)
            return

        app_id = random.randint(100000, 999999)
        answers = [item.value or "لم يكتب" for item in self.inputs]

        if gid not in applications_data:
            applications_data[gid] = []

        applications_data[gid].append({
            "id": app_id,
            "user_id": interaction.user.id,
            "type": self.app_type,
            "answers": answers,
            "status": "pending",
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        })

        save_all_applications()

        config = application_config.get(gid, {})
        result_channel_id = config.get("results_channel") or config.get("channel")
        result_channel = interaction.guild.get_channel(result_channel_id) if result_channel_id else None

        if result_channel:
            embed = discord.Embed(title="📩 تقديم جديد", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
            embed.add_field(name="👤 العضو", value=interaction.user.mention, inline=False)
            embed.add_field(name="📌 النوع", value=self.app_type, inline=False)

            type_questions = application_questions.get(gid, {}).get(
                self.app_type, ["السؤال 1", "السؤال 2", "السؤال 3", "السؤال 4", "السؤال 5"]
            )

            for i, answer in enumerate(answers):
                q_name = type_questions[i] if i < len(type_questions) else f"السؤال {i + 1}"
                embed.add_field(name=str(q_name)[:256], value=str(answer)[:1024], inline=False)

            embed.add_field(name="📌 الحالة", value="🟡 **قيد المراجعة**", inline=False)
            await result_channel.send(embed=embed, view=ApplicationControlView(interaction.user.id, app_id))

        await interaction.response.send_message("✅ تم إرسال التقديم بنجاح.", ephemeral=True)


class ApplicationControlView(discord.ui.View):
    def __init__(self, user_id: int = 0, app_id: int = 0):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.app_id = app_id

        if app_id and user_id:
            self.accept_btn.custom_id = f"app_accept:{app_id}:{user_id}"
            self.reject_btn.custom_id = f"app_reject:{app_id}:{user_id}"

    @discord.ui.button(label="قبول", emoji="✅", style=discord.ButtonStyle.green, custom_id="app_accept_default")
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        parts = button.custom_id.split(":")
        if len(parts) == 3:
            app_id = int(parts[1])
            user_id = int(parts[2])
        else:
            app_id = self.app_id
            user_id = self.user_id

        gid = str(interaction.guild.id)
        application = next((app for app in applications_data.get(gid, []) if app.get("id") == app_id), None)

        if not application:
            await interaction.response.send_message("❌ لم يتم العثور على التقديم.", ephemeral=True)
            return

        if application.get("status") != "pending":
            await interaction.response.send_message("⚠️ تم اتخاذ قرار بشأن هذا التقديم مسبقًا.", ephemeral=True)
            return

        application["status"] = "accepted"
        application["decision_by"] = interaction.user.id
        application["decision_time"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        save_all_applications()

        member = interaction.guild.get_member(user_id)
        app_type = application.get("type")

        if member:
            types = application_types.get(gid, [])
            if isinstance(types, dict):
                types = [{"name": name, **(data if isinstance(data, dict) else {})} for name, data in types.items()]

            for app_type_data in types:
                if not isinstance(app_type_data, dict) or app_type_data.get("name") != app_type:
                    continue
                role_id = app_type_data.get("role_id")
                if role_id:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        try:
                            await member.add_roles(role, reason="قبول التقديم")
                        except Exception as e:
                            print(f"Role error: {e}")
                break

            try:
                await member.send(f"🎉 تم قبول تقديمك!\n📋 نوع التقديم: `{app_type}`")
            except Exception:
                pass

        if interaction.message and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            status_text = f"🟢 **مقبول**\n👮 بواسطة: {interaction.user.mention}\n🕐 الوقت: {application['decision_time']}"

            found = False
            for i, field in enumerate(embed.fields):
                if field.name == "📌 الحالة":
                    embed.set_field_at(i, name="📌 الحالة", value=status_text, inline=False)
                    found = True
                    break

            if not found:
                embed.add_field(name="📌 الحالة", value=status_text, inline=False)

            for item in self.children:
                item.disabled = True

            await interaction.message.edit(embed=embed, view=self)

        await interaction.response.send_message("✅ تم قبول التقديم وتحديث البانل.", ephemeral=True)

    @discord.ui.button(label="رفض", emoji="❌", style=discord.ButtonStyle.red, custom_id="app_reject_default")
    async def reject_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        parts = button.custom_id.split(":")
        if len(parts) == 3:
            app_id = int(parts[1])
            user_id = int(parts[2])
        else:
            app_id = self.app_id
            user_id = self.user_id

        gid = str(interaction.guild.id)
        application = next((app for app in applications_data.get(gid, []) if app.get("id") == app_id), None)

        if not application:
            await interaction.response.send_message("❌ لم يتم العثور على التقديم.", ephemeral=True)
            return

        if application.get("status") != "pending":
            await interaction.response.send_message("⚠️ تم اتخاذ قرار بشأن هذا التقديم مسبقًا.", ephemeral=True)
            return

        application["status"] = "rejected"
        application["decision_by"] = interaction.user.id
        application["decision_time"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        save_all_applications()

        member = interaction.guild.get_member(user_id)
        if member:
            try:
                await member.send(f"❌ تم رفض تقديمك.\n📋 نوع التقديم: `{application.get('type')}`")
            except Exception:
                pass

        if interaction.message and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            status_text = f"🔴 **مرفوض**\n👮 بواسطة: {interaction.user.mention}\n🕐 الوقت: {application['decision_time']}"

            found = False
            for i, field in enumerate(embed.fields):
                if field.name == "📌 الحالة":
                    embed.set_field_at(i, name="📌 الحالة", value=status_text, inline=False)
                    found = True
                    break

            if not found:
                embed.add_field(name="📌 الحالة", value=status_text, inline=False)

            for item in self.children:
                item.disabled = True

            await interaction.message.edit(embed=embed, view=self)

        await interaction.response.send_message("❌ تم رفض التقديم وتحديث البانل.", ephemeral=True)

# ================================
# أوامر نظام التقديمات (Slash Commands)
# ================================

@bot.tree.command(name="application-panel", description="إنشاء بانل تقديم متطور")
@app_commands.checks.has_permissions(administrator=True)
async def application_panel(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    results_channel: discord.TextChannel,
    title: str,
    description: str,
    image: str = None
):
    gid = str(interaction.guild.id)
    config = application_config.get(gid, {})
    config.update({
        "channel": channel.id,
        "results_channel": results_channel.id,
        "title": title,
        "description": description,
        "image": image
    })
    application_config[gid] = config
    save_all_applications()

    embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
    if image:
        embed.set_image(url=image)

    msg = await channel.send(embed=embed, view=ApplicationSelectView(interaction.guild.id))

    persistent_panels.append({
        "type": "application",
        "guild_id": interaction.guild.id,
        "channel_id": channel.id,
        "message_id": msg.id
    })
    save_persistent()

    await interaction.response.send_message("✅ تم إنشاء بانل التقديم بنجاح.", ephemeral=True)

@bot.tree.command(name="application-add-type", description="إضافة نوع تقديم مع رتبة خاصة وتحديث البانل تلقائياً")
@app_commands.checks.has_permissions(administrator=True)
async def application_add_type(interaction: discord.Interaction, name: str, role: discord.Role, description: str = "بدون وصف"):
    gid = str(interaction.guild.id)
    if gid not in application_types:
        application_types[gid] = []

    if isinstance(application_types[gid], dict):
        converted_list = []
        for k, v in application_types[gid].items():
            desc = v.get("description", "بدون وصف") if isinstance(v, dict) else "بدون وصف"
            r_id = v.get("role_id") if isinstance(v, dict) else None
            converted_list.append({"name": k, "description": desc, "role_id": r_id, "enabled": True})
        application_types[gid] = converted_list

    for app_type in application_types[gid]:
        if app_type["name"] == name:
            await interaction.response.send_message("❌ هذا النوع موجود مسبقاً.", ephemeral=True)
            return

    application_types[gid].append({
        "name": name,
        "description": description,
        "role_id": role.id,
        "enabled": True
    })
    save_application_types()

    updated = 0
    for panel in persistent_panels:
        if panel.get("type") != "application" or str(panel.get("guild_id")) != gid:
            continue
        try:
            channel = interaction.guild.get_channel(panel["channel_id"])
            if not channel:
                continue
            message = await channel.fetch_message(panel["message_id"])
            cfg = application_config.get(gid, {})

            embed = discord.Embed(
                title=cfg.get("title", "📋 التقديم"),
                description=cfg.get("description", "اختر نوع التقديم"),
                color=discord.Color.blurple()
            )
            if cfg.get("image"):
                embed.set_image(url=cfg["image"])

            await message.edit(embed=embed, view=ApplicationSelectView(gid))
            updated += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Panel update error: {e}")

    await interaction.response.send_message(
        f"✅ تمت إضافة نوع التقديم: `{name}`\n🎭 الرتبة: {role.mention}\n🔄 تم تحديث {updated} بانل تلقائياً.",
        ephemeral=True
    )

@bot.tree.command(name="application-remove-type", description="حذف نوع تقديم")
@app_commands.checks.has_permissions(administrator=True)
async def application_remove_type(interaction: discord.Interaction, name: str):
    gid = str(interaction.guild.id)
    types = application_types.get(gid, [])

    if isinstance(types, dict):
        if name in types:
            del types[name]
            save_all_applications()
            await interaction.response.send_message("✅ تم حذف النوع.", ephemeral=True)
            return
    elif isinstance(types, list):
        for i, t in enumerate(types):
            if isinstance(t, dict) and t.get("name") == name:
                types.pop(i)
                save_all_applications()
                await interaction.response.send_message("✅ تم حذف النوع.", ephemeral=True)
                return

    await interaction.response.send_message("❌ النوع غير موجود.", ephemeral=True)

@bot.tree.command(name="application-set-questions", description="تحديد أسئلة نوع تقديم")
@app_commands.checks.has_permissions(administrator=True)
async def application_set_questions(
    interaction: discord.Interaction,
    app_type: str,
    q1: str,
    q2: str,
    q3: str,
    q4: str = "اختياري",
    q5: str = "اختياري"
):
    gid = str(interaction.guild.id)
    if gid not in application_questions:
        application_questions[gid] = {}

    application_questions[gid][app_type] = [q1, q2, q3, q4, q5]
    save_all_applications()
    await interaction.response.send_message("✅ تم حفظ الأسئلة.", ephemeral=True)

@bot.tree.command(name="application-set-role", description="تحديد رتبة المقبولين العامة في التقديمات")
@app_commands.checks.has_permissions(administrator=True)
async def application_set_role(interaction: discord.Interaction, role: discord.Role):
    gid = str(interaction.guild.id)
    if gid not in application_config:
        application_config[gid] = {}
    application_config[gid]["accepted_role"] = role.id
    save_all_applications()
    await interaction.response.send_message(f"✅ سيتم إعطاء رتبة {role.mention} للمقبولين تلقائياً (عام)", ephemeral=True)

@bot.tree.command(name="application-description", description="تعديل وصف بانل التقديم")
@app_commands.checks.has_permissions(administrator=True)
async def application_description(interaction: discord.Interaction, description: str):
    gid = str(interaction.guild.id)
    application_config.setdefault(gid, {})
    application_config[gid]["description"] = description
    save_all_applications()
    await interaction.response.send_message("✅ تم تعديل الوصف.", ephemeral=True)

@bot.tree.command(name="application-list", description="عرض التقديمات الحالية")
@app_commands.checks.has_permissions(administrator=True)
async def application_list(interaction: discord.Interaction):
    apps = applications_data.get(str(interaction.guild.id), [])
    if not apps:
        await interaction.response.send_message("❌ لا يوجد تقديمات حالية", ephemeral=True)
        return
    embed = discord.Embed(title="📝 قائمة التقديمات", color=discord.Color.blue())
    for app in apps[:10]:
        embed.add_field(name=f"#{app['id']} - {app['type']}", value=f"👤 <@{app['user_id']}>\n📌 الحالة: {app['status']}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="reset-panels", description="إزالة الأزرار من البانلات القديمة بأمان")
@app_commands.checks.has_permissions(administrator=True)
async def reset_panels(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    count = 0
    checked = 0

    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                async for msg in channel.history(limit=50):
                    checked += 1
                    if msg.author != bot.user or not msg.components:
                        continue
                    try:
                        await msg.edit(view=None)
                        count += 1
                        await asyncio.sleep(0.5)
                    except discord.HTTPException as e:
                        if e.status == 429:
                            await asyncio.sleep(5)
                        else:
                            print(f"Panel edit error: {e}")
            except discord.Forbidden:
                continue
            except Exception as e:
                print(f"Reset error in #{channel.name}: {e}")

    await interaction.followup.send(f"♻️ تم Reset عدد `{count}` بانل.\n🔎 تم فحص `{checked}` رسالة.", ephemeral=True)

# ==================================
# Reaction Roles System
# ==================================

class ReactionRoleView(discord.ui.View):
    def __init__(self, role_id: int):
        super().__init__(timeout=None)
        self.role_id = role_id

    @discord.ui.button(label="✅ أخذ الرتبة", style=discord.ButtonStyle.green, custom_id="take_role_btn")
    async def take_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("❌ الرتبة غير موجودة", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("⚠️ أنت تملك هذه الرتبة بالفعل", ephemeral=True)
            return

        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ تم إعطاؤك رتبة {role.mention}", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ ليس لدي صلاحيات لإعطائك هذه الرتبة", ephemeral=True)

    @discord.ui.button(label="❌ إزالة الرتبة", style=discord.ButtonStyle.red, custom_id="remove_role_btn")
    async def remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("❌ الرتبة غير موجودة", ephemeral=True)
            return

        if role not in interaction.user.roles:
            await interaction.response.send_message("⚠️ أنت لا تملك هذه الرتبة", ephemeral=True)
            return

        try:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"❌ تم إزالة رتبة {role.mention}", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ ليس لدي صلاحيات لإزالة هذه الرتبة", ephemeral=True)

    @discord.ui.button(label="👥 عرض الأعضاء", style=discord.ButtonStyle.blurple, custom_id="show_role_members_btn")
    async def show_members(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("❌ الرتبة غير موجودة", ephemeral=True)
            return

        members = role.members
        if not members:
            text = "لا يوجد أحد يملك هذه الرتبة."
        else:
            text = "\n".join([f"• {member.mention}" for member in members[:50]])
            if len(members) > 50:
                text += f"\n\nو {len(members) - 50} أعضاء آخرين..."

        embed = discord.Embed(title=f"👥 أعضاء رتبة {role.name}", description=text, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="reaction-role", description="إنشاء بانل أخذ/إزالة رتبة عبر الأزرار")
@app_commands.describe(
    channel="الروم المراد إرسال البانل إليه",
    role="الرتبة المراد إعطاؤها للعضو",
    title="عنوان الرسالة (Embed)",
    description="وصف الرسالة (Embed)"
)
@app_commands.checks.has_permissions(administrator=True)
async def reaction_role(interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role, title: str, description: str):
    embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
    view = ReactionRoleView(role.id)
    msg = await channel.send(embed=embed, view=view)

    persistent_panels.append({
        "type": "reaction_role",
        "guild_id": interaction.guild.id,
        "channel_id": channel.id,
        "message_id": msg.id,
        "role_id": role.id
    })
    save_persistent()

    await interaction.response.send_message(f"✅ تم إنشاء بانل الرتبة بنجاح في {channel.mention} لرتبة {role.mention}", ephemeral=True)

# ==================================
# أوامر الإدارة والعقوبات (Moderation)
# ==================================

@bot.tree.command(name="ban", description="حظر عضو")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "لا يوجد سبب"):
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 تم حظر {member.mention}")
        await send_log(interaction.guild, "🔨 Ban", f"العضو: {member.mention}\nالسبب: {reason}", discord.Color.red())
    except Exception:
        await interaction.response.send_message("❌ لا أمتلك الصلاحيات الكافية لحظر هذا العضو.", ephemeral=True)

@bot.tree.command(name="kick", description="طرد عضو")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "لا يوجد سبب"):
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 تم طرد {member.mention}")
    except Exception:
        await interaction.response.send_message("❌ لا أمتلك الصلاحيات الكافية لطرد هذا العضو.", ephemeral=True)

@bot.tree.command(name="mute", description="كتم عضو (Timeout)")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "لا يوجد سبب"):
    try:
        await member.timeout(timedelta(minutes=minutes), reason=reason)
        await interaction.response.send_message(f"🔇 تم كتم {member.mention} لمدة {minutes} دقيقة.")
    except Exception:
        await interaction.response.send_message("❌ لا أمتلك الصلاحيات الكافية لكتم هذا العضو.", ephemeral=True)

@bot.tree.command(name="unmute", description="فك كتم عضو")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.timeout(None, reason="فك الكتم")
        await interaction.response.send_message(f"🔊 تم فك الكتم عن {member.mention}")
    except Exception:
        await interaction.response.send_message("❌ لا أمتلك الصلاحيات الكافية لفك كتم هذا العضو.", ephemeral=True)

@bot.tree.command(name="warn", description="تحذير عضو")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    warnings = load_json(WARNINGS_FILE, {})
    gid, uid = str(interaction.guild.id), str(member.id)
    if gid not in warnings: warnings[gid] = {}
    if uid not in warnings[gid]: warnings[gid][uid] = []
    warnings[gid][uid].append({"reason": reason, "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")})
    save_json(WARNINGS_FILE, warnings)
    await interaction.response.send_message(f"⚠️ تم تحذير {member.mention}")

@bot.tree.command(name="clear", description="مسح الرسائل")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"✅ تم حذف {len(deleted)} رسالة.", ephemeral=True)

# ==================================
# الإدارة المتقدمة
# ==================================

START_TIME = datetime.now(timezone.utc)

@bot.tree.command(name="move", description="نقل عضو إلى روم صوتي")
@app_commands.checks.has_permissions(move_members=True)
async def move(interaction: discord.Interaction, member: discord.Member, channel: discord.VoiceChannel):
    if member.voice:
        try:
            await member.move_to(channel)
            await interaction.response.send_message(f"✅ تم نقل {member.mention} إلى {channel.mention}")
        except Exception:
            await interaction.response.send_message("❌ لا يملك البوت الصلاحيات لنقل العضو.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ العضو ليس في روم صوتي.", ephemeral=True)

@bot.tree.command(name="deafen", description="تغميض صوت عضو")
@app_commands.checks.has_permissions(deafen_members=True)
async def deafen(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.edit(deafen=True)
        await interaction.response.send_message(f"🔇 تم تغميض {member.mention}")
    except Exception:
        await interaction.response.send_message("❌ لا أملك صلاحية تغميض العضو.", ephemeral=True)

@bot.tree.command(name="undeafen", description="إلغاء تغميض صوت عضو")
@app_commands.checks.has_permissions(deafen_members=True)
async def undeafen(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.edit(deafen=False)
        await interaction.response.send_message(f"🔊 تم إلغاء تغميض {member.mention}")
    except Exception:
        await interaction.response.send_message("❌ لا أملك صلاحية إلغاء تغميض العضو.", ephemeral=True)

@bot.tree.command(name="timeout", description="إعطاء تايم اوت لعضو")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int):
    try:
        await member.timeout(timedelta(minutes=minutes))
        await interaction.response.send_message(f"⏳ تم إعطاء {member.mention} تايم اوت لمدة {minutes} دقيقة")
    except Exception:
        await interaction.response.send_message("❌ فشل إعطاء تايم اوت للعضو.", ephemeral=True)

@bot.tree.command(name="rolelist", description="عرض رتب السيرفر")
async def rolelist(interaction: discord.Interaction):
    roles = interaction.guild.roles[1:]
    text = "\n".join([f"{r.mention}" for r in roles[:50]])
    embed = discord.Embed(title="📋 رتب السيرفر", description=text or "لا توجد رتب.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="channelinfo", description="معلومات الروم الحالي")
async def channelinfo(interaction: discord.Interaction):
    channel = interaction.channel
    embed = discord.Embed(title="📢 معلومات الروم")
    embed.add_field(name="الاسم", value=channel.name)
    embed.add_field(name="ID", value=channel.id)
    embed.add_field(name="النوع", value=str(channel.type))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="botinfo", description="معلومات البوت")
async def botinfo(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 معلومات البوت")
    embed.add_field(name="الاسم", value=bot.user.name)
    embed.add_field(name="السيرفرات", value=len(bot.guilds))
    embed.add_field(name="الأعضاء", value=sum(g.member_count for g in bot.guilds))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="uptime", description="مدة تشغيل البوت")
async def uptime(interaction: discord.Interaction):
    delta = datetime.now(timezone.utc) - START_TIME
    await interaction.response.send_message(f"⏱️ البوت يعمل منذ: `{delta}`")

@bot.tree.command(name="stats", description="إحصائيات السيرفر")
async def stats(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title="📊 إحصائيات السيرفر")
    embed.add_field(name="الأعضاء", value=guild.member_count)
    embed.add_field(name="الرومات", value=len(guild.channels))
    embed.add_field(name="الرتب", value=len(guild.roles))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="autorole", description="تحديد رتبة تلقائية")
@app_commands.checks.has_permissions(administrator=True)
async def autorole(interaction: discord.Interaction, role: discord.Role):
    config = load_json(CONFIG_FILE, {})
    gid = str(interaction.guild.id)
    if gid not in config: config[gid] = {}
    config[gid]["autorole_id"] = role.id
    save_json(CONFIG_FILE, config)
    await interaction.response.send_message(f"✅ تم تحديد الرتبة التلقائية {role.mention}")

@bot.tree.command(name="set-mod-role", description="تحديد رتبة الإدارة")
@app_commands.checks.has_permissions(administrator=True)
async def set_mod_role(interaction: discord.Interaction, role: discord.Role):
    mod_roles[str(interaction.guild.id)] = role.id
    save_json(MOD_CONFIG_FILE, mod_roles)
    await interaction.response.send_message(f"✅ تم تحديد رتبة الإدارة: {role.mention}")

@bot.tree.command(name="rules", description="إرسال القوانين")
@app_commands.checks.has_permissions(administrator=True)
async def rules(interaction: discord.Interaction, text: str):
    embed = discord.Embed(title="📜 القوانين", description=text, color=discord.Color.blue())
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ تم إرسال القوانين", ephemeral=True)

@bot.tree.command(name="poll", description="إنشاء تصويت")
async def poll(interaction: discord.Interaction, question: str):
    embed = discord.Embed(title="📊 تصويت", description=question)
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await interaction.response.send_message("✅ تم إنشاء التصويت", ephemeral=True)

@bot.tree.command(name="nickname", description="تغيير اسم عضو")
@app_commands.checks.has_permissions(manage_nicknames=True)
async def nickname(interaction: discord.Interaction, member: discord.Member, name: str):
    try:
        await member.edit(nick=name)
        await interaction.response.send_message(f"✅ تم تغيير اسم {member.mention} إلى `{name}`")
    except Exception:
        await interaction.response.send_message("❌ لا أستطيع تغيير الاسم", ephemeral=True)

@bot.tree.command(name="addrole", description="إعطاء رتبة لعضو")
@app_commands.checks.has_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    try:
        await member.add_roles(role)
        await interaction.response.send_message(f"✅ تم إعطاء {member.mention} رتبة {role.mention}")
    except Exception:
        await interaction.response.send_message("❌ لا أستطيع إعطاء هذه الرتبة", ephemeral=True)

@bot.tree.command(name="removerole", description="إزالة رتبة من عضو")
@app_commands.checks.has_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    try:
        await member.remove_roles(role)
        await interaction.response.send_message(f"❌ تم إزالة رتبة {role.mention} من {member.mention}")
    except Exception:
        await interaction.response.send_message("❌ لا أستطيع إزالة هذه الرتبة", ephemeral=True)

@bot.tree.command(name="createrole", description="إنشاء رتبة جديدة")
@app_commands.checks.has_permissions(manage_roles=True)
async def createrole(interaction: discord.Interaction, name: str):
    try:
        role = await interaction.guild.create_role(name=name)
        await interaction.response.send_message(f"✅ تم إنشاء الرتبة {role.mention}")
    except Exception:
        await interaction.response.send_message("❌ فشل إنشاء الرتبة.", ephemeral=True)

@bot.tree.command(name="roleall", description="إعطاء رتبة لكل أعضاء السيرفر")
@app_commands.checks.has_permissions(administrator=True)
async def roleall(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer(ephemeral=True)
    count = 0
    for member in interaction.guild.members:
        if not member.bot:
            try:
                await member.add_roles(role)
                count += 1
            except Exception:
                pass
    await interaction.followup.send(f"✅ تم إعطاء الرتبة {role.mention} لـ {count} عضو")

@bot.tree.command(name="dm", description="إرسال رسالة خاصة لعضو")
@app_commands.checks.has_permissions(administrator=True)
async def dm(interaction: discord.Interaction, member: discord.Member, message: str):
    try:
        await member.send(message)
        await interaction.response.send_message("✅ تم إرسال الرسالة", ephemeral=True)
    except Exception:
        await interaction.response.send_message("❌ لا يمكن إرسال رسالة لهذا العضو", ephemeral=True)

@bot.tree.command(name="announce", description="إرسال إعلان Embed")
@app_commands.checks.has_permissions(administrator=True)
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, title: str, description: str):
    embed = discord.Embed(title=title, description=description, color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
    embed.set_footer(text=f"إعلان بواسطة {interaction.user}")
    await channel.send(embed=embed)
    await interaction.response.send_message("✅ تم إرسال الإعلان", ephemeral=True)

@bot.tree.command(name="clearwarns", description="مسح تحذيرات عضو")
@app_commands.checks.has_permissions(administrator=True)
async def clearwarns(interaction: discord.Interaction, member: discord.Member):
    warnings = load_json(WARNINGS_FILE, {})
    gid = str(interaction.guild.id)
    if gid in warnings and str(member.id) in warnings[gid]:
        del warnings[gid][str(member.id)]
        save_json(WARNINGS_FILE, warnings)
    await interaction.response.send_message("✅ تم مسح التحذيرات")

# ==================================
# إدارة الرومات (Channels)
# ==================================

@bot.tree.command(name="lock", description="قفل الروم")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 تم قفل الروم.")

@bot.tree.command(name="unlock", description="فتح الروم")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("🔓 تم فتح الروم.")

@bot.tree.command(name="slowmode", description="تحديد سرعة الرسائل")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"🐌 تم تعيين Slowmode إلى {seconds} ثانية.")

@bot.tree.command(name="hide", description="إخفاء الروم")
@app_commands.checks.has_permissions(manage_channels=True)
async def hide(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, view_channel=False)
    await interaction.response.send_message("🙈 تم إخفاء الروم.")

@bot.tree.command(name="unhide", description="إظهار الروم")
@app_commands.checks.has_permissions(manage_channels=True)
async def unhide(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, view_channel=True)
    await interaction.response.send_message("👁️ تم إظهار الروم.")

# ==================================
# نظام الاقتراحات (Suggestions)
# ==================================

@bot.tree.command(name="suggestion-setup", description="إعداد روم الاقتراحات")
@app_commands.checks.has_permissions(administrator=True)
async def suggestion_setup(interaction: discord.Interaction, channel: discord.TextChannel):
    suggestion_config[str(interaction.guild.id)] = channel.id
    save_suggestions_config()
    await interaction.response.send_message(f"✅ تم تعيين روم الاقتراحات {channel.mention}", ephemeral=True)

@bot.tree.command(name="suggest", description="إرسال اقتراح")
async def suggest(interaction: discord.Interaction, suggestion: str):
    channel_id = suggestion_config.get(str(interaction.guild.id))
    if not channel_id:
        await interaction.response.send_message("❌ لم يتم إعداد روم الاقتراحات", ephemeral=True)
        return
    channel = interaction.guild.get_channel(channel_id)
    if not channel:
        await interaction.response.send_message("❌ الروم غير موجود", ephemeral=True)
        return

    embed = discord.Embed(title="💡 اقتراح جديد", description=suggestion, color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
    embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)

    msg = await channel.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await interaction.response.send_message("✅ تم إرسال اقتراحك", ephemeral=True)

# ==================================
# أوامر الحماية (Anti System)
# ==================================

@bot.tree.command(name="anti-links", description="منع الروابط")
@app_commands.checks.has_permissions(administrator=True)
async def anti_links(interaction: discord.Interaction, status: bool):
    gid = str(interaction.guild.id)
    if gid not in protection_config: protection_config[gid] = {}
    protection_config[gid]["anti_links"] = status
    save_json(PROTECTION_FILE, protection_config)
    await interaction.response.send_message(f"🔗 منع الروابط: {'مفعل ✅' if status else 'متوقف ❌'}", ephemeral=True)

@bot.tree.command(name="anti-invite", description="منع دعوات السيرفرات")
@app_commands.checks.has_permissions(administrator=True)
async def anti_invite(interaction: discord.Interaction, status: bool):
    gid = str(interaction.guild.id)
    if gid not in protection_config: protection_config[gid] = {}
    protection_config[gid]["anti_invite"] = status
    save_json(PROTECTION_FILE, protection_config)
    await interaction.response.send_message(f"🚫 منع الدعوات: {'مفعل ✅' if status else 'متوقف ❌'}", ephemeral=True)

@bot.tree.command(name="badword-add", description="إضافة كلمة ممنوعة")
@app_commands.checks.has_permissions(administrator=True)
async def badword_add(interaction: discord.Interaction, word: str):
    if word.lower() not in bad_words:
        bad_words.append(word.lower())
        save_json(BAD_WORDS_FILE, bad_words)
    await interaction.response.send_message(f"✅ تمت إضافة الكلمة `{word}`", ephemeral=True)

# ==================================
# أوامر المعلومات (Information)
# ==================================

@bot.tree.command(name="avatar", description="عرض صورة العضو")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"🖼️ صورة {member.name}", color=discord.Color.blue())
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="عرض معلومات العضو")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"👤 معلومات {member}", color=discord.Color.blurple())
    embed.add_field(name="🆔 ID", value=member.id, inline=False)
    embed.add_field(name="📅 دخل السيرفر", value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "غير معروف", inline=False)
    embed.add_field(name="🎭 الرتب", value=" ".join([r.mention for r in member.roles[1:]]) or "لا يوجد", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="عرض معلومات السيرفر")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"🏠 معلومات {guild.name}", color=discord.Color.green())
    embed.add_field(name="👥 الأعضاء", value=guild.member_count)
    embed.add_field(name="📁 الرومات", value=len(guild.channels))
    embed.add_field(name="🎭 الرتب", value=len(guild.roles))
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await interaction.response.send_message(embed=embed)

# ==================================
# أوامر الرسائل (Say & Embed)
# ==================================

@bot.tree.command(name="say", description="جعل البوت يرسل رسالة")
@app_commands.checks.has_permissions(administrator=True)
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("✅ تم الإرسال", ephemeral=True)
    await interaction.channel.send(message)

@bot.tree.command(name="embed", description="إرسال رسالة Embed من البوت")
@app_commands.checks.has_permissions(administrator=True)
async def embed_command(interaction: discord.Interaction, title: str, description: str):
    embed = discord.Embed(title=title, description=description, color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
    await interaction.response.send_message("✅ تم إرسال الـ Embed", ephemeral=True)
    await interaction.channel.send(embed=embed)

# ==================================
# أوامر المساعدة (Help)
# ==================================

@bot.tree.command(name="ping", description="سرعة استجابة البوت")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! `{latency}ms`")

@bot.tree.command(name="help", description="عرض قائمة الأوامر")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 أوامر البوت", description="قائمة الأوامر المتاحة", color=discord.Color.blurple())
    embed.add_field(name="🛡️ الإدارة", value="/ban, /kick, /mute, /warn, /clear, /lock, /unlock, /say, /embed", inline=False)
    embed.add_field(name="👑 إدارة الرتب والأعضاء", value="/addrole, /removerole, /createrole, /roleall, /nickname, /dm, /announce", inline=False)
    embed.add_field(name="📊 المعلومات", value="/avatar, /userinfo, /serverinfo, /ping", inline=False)
    embed.add_field(name="📝 التقديمات والترحيب", value="/application-panel, /application-add-type, /application-remove-type, /application-set-questions, /set-welcome, /member-count-setup", inline=False)
    embed.add_field(name="🔘 البانلات العامة", value="/general-panel, /panel", inline=False)
    embed.add_field(name="🛡️ الحماية", value="/anti-links, /anti-invite, /badword-add", inline=False)
    embed.add_field(name="💤 نظام الـ AFK", value="/afk, /afk-status, /afk-list, /afk-remove", inline=False)
    await interaction.response.send_message(embed=embed)

# ==================================
# تشغيل البوت والأحداث العامة
# ==================================

_welcome_views_registered = False

async def welcome_on_ready():
    global _welcome_views_registered
    print(f"🤖 Bot Online: {bot.user}")

    if _welcome_views_registered:
        return

    # إضافة Persistent View الخاصة بأزرار قبول/رفض التقديمات عامة
    bot.add_view(ApplicationControlView())

    # استعادة البانلات المعتادة للتقديمات والتفاعل
    for panel_item in persistent_panels:
        try:
            ptype = panel_item.get("type")
            if ptype == "application":
                bot.add_view(ApplicationSelectView(panel_item["guild_id"]), message_id=panel_item["message_id"])
            elif ptype == "reaction_role":
                bot.add_view(ReactionRoleView(panel_item["role_id"]), message_id=panel_item["message_id"])
        except Exception as e:
            print(f"Failed persistent view: {e}")

    # استعادة البانلات العامة (القديمة والديناميكية)
    for panel_item in general_panels:
        try:
            if isinstance(panel_item, dict):
                if "button_name" in panel_item:
                    bot.add_view(
                        LegacyGeneralPanelView(
                            panel_item["button_name"],
                            panel_item["button_emoji"],
                            panel_item["button_description"],
                            panel_item.get("color")
                        ),
                        message_id=panel_item.get("message_id")
                    )
                elif "id" in panel_item and "buttons" in panel_item:
                    bot.add_view(GeneralPanelView(panel_item))
        except Exception as e:
            print(f"Failed panel view restoration: {e}")

    # المزامنة مع سيرفرات الديسكورد
    try:
        await bot.tree.sync()
        print("✅ Synced Slash Commands successfully.")
    except Exception as e:
        print(f"Sync error: {e}")

    _welcome_views_registered = True

# ===================== TICKETS (PRESERVED ORIGINAL SYSTEM) =====================
# ==================================
# إعداد البوت
# ==================================

GUILD_ID = int(os.getenv("GUILD_ID", "1532326696714240062"))



# 


def default_ticket():

    return {
        "name": "تذكرة جديدة",
        "description": "اضغط لفتح التذكرة",
        "panel_description": "اضغط لفتح التذكرة",
        "emoji": "🎫",
        "name_format": "{emoji}・{count}",
        "color": "blue",
        "welcome_message": "أهلاً {user} 👋\nسيتم الرد عليك قريباً.",
        "ticket_image": None,
        "image": None,
        "open_category": None,
        "close_category": None,
        "staff_roles": [],
        "blocked_roles": [],
        "blocked_role": None,
        "open_logs": None,
        "close_logs": None,
        "rating_room": None,
        "claim": True,
        "rating": True,
        "transcript": True,
        "ask_reason": False,
        "max_tickets": 1,
        "prevent_same_type": True,
        "counter": 0,
        "opened": 0,
        "closed": 0,
        "ratings": [],
        "priority": "normal",
        "auto_close": False,
        "auto_close_time": 24,
        "notes": [],
        "added_members": [],
        "last_activity": None
    }



def default_database():

    return {
        "tickets": {},
        "panel": {
            "title": "🎫 نظام التذاكر",
            "description": "اختر نوع التذكرة من القائمة بالأسفل",
            "image": None,
            "channel": None,
            "message_id": None
        },
        "panels": {},
        "open_tickets": {},
        "closed_today": 0,
        "stats": {
            "total_opened": 0,
            "total_closed": 0,
            "tickets_today": 0,
            "daily_opened": {},
            "daily_closed": {},
            "ratings": [],
            "staff": {},
            "logs": [],
            "permissions": {
                "managers": [],
                "setup_admins": []
            }
        },
        "auto_setup": {},
        "log_channels": {"open": None, "claim": None, "close": None, "rating": None, "note": None, "admin": None}
    }


DATABASE_FILE = "database.json"
BACKUP_FILE = "database_backup.json"

def save_database():
    with open(DATABASE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            database,
            file,
            indent=4,
            ensure_ascii=False
        )



def load_database():

    if not os.path.exists(DATABASE_FILE):
        return default_database()

    with open(DATABASE_FILE, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except:
            return default_database()



try:
    database = load_database()
except:
    database = default_database()
    save_database()

# دعم البانلات المتعددة وربط كل بانل بتذاكره الخاصة
if "panels" not in database:
    database["panels"] = {}

if "log_channels" not in database:
    database["log_channels"] = {"open": None, "claim": None, "close": None, "rating": None, "note": None, "admin": None}
else:
    for _log_key in ("open", "claim", "close", "rating", "note", "admin"):
        if _log_key not in database["log_channels"]:
            database["log_channels"][_log_key] = None
    database["log_channels"].pop("ticket", None)

for panel_id, panel in database["panels"].items():
    if "tickets" not in panel:
        panel["tickets"] = []

# دعم الإعداد الجديد للتذاكر القديمة
for ticket_type, ticket_settings in database["tickets"].items():
    if "name_format" not in ticket_settings:
        ticket_settings["name_format"] = "{emoji}・{count}"
    if "counter" not in ticket_settings:
        ticket_settings["counter"] = 0

save_database()



# ==================================
# أدوات مساعدة وتصميم موحد
# ==================================

def make_embed(title, description, color=discord.Color.blue()):

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now()
    )

    embed.set_footer(
        text="🎫 Professional Ticket System"
    )

    return embed



async def send_ticket_log(
    guild,
    log_type,
    title,
    description="",
    color=discord.Color.blue(),
    fields=None,
    file_path=None
):
    """إرسال اللوق إلى الروم المخصص لنوع الحدث."""
    log_id = database.get("log_channels", {}).get(log_type)
    if not log_id:
        return

    log = guild.get_channel(log_id)
    if not log:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now()
    )

    if fields:
        for name, value, inline in fields:
            embed.add_field(
                name=name,
                value=str(value)[:1024],
                inline=inline
            )

    embed.set_footer(text=f"🎫 Ticket Logs • {log_type.upper()}")

    try:
        if file_path and os.path.exists(file_path):
            await log.send(
                embed=embed,
                file=discord.File(file_path)
            )
        else:
            await log.send(embed=embed)
    except Exception as e:
        print(f"Ticket {log_type} log error: {e}")


async def log_ticket_action(
    interaction,
    action,
    details="",
    color=discord.Color.blue(),
    log_type="admin"
):
    """إجراءات الإدارة تذهب دائماً إلى روم لوق الإدارة."""
    ticket = get_ticket_from_channel(interaction.channel.id)
    if not ticket:
        return

    settings = database["tickets"].get(ticket.get("type"))

    await send_ticket_log(
        interaction.guild,
        log_type,
        f"📝 {action}",
        fields=[
            ("🎫 صاحب التذكرة", f"<@{ticket.get('owner')}>", False),
            (
                "🎟️ النوع",
                settings.get("name", "غير معروف") if settings else "غير معروف",
                True
            ),
            ("👤 الإداري", interaction.user.mention, True),
            ("📌 التفاصيل", details or "—", False),
            (
                "📅 الوقت",
                f"<t:{int(datetime.now().timestamp())}:F>",
                False
            ),
        ],
        color=color
    )


def is_manager(user):
    if user.guild_permissions.administrator:
        return True
    return user.id in database["stats"]["permissions"]["managers"]



def create_ticket_id():

    number = len(database["tickets"]) + 1
    return f"ticket_{number}"



def get_ticket(ticket_id):

    return database["tickets"].get(ticket_id)



def get_ticket_from_channel(channel_id):

    return database["open_tickets"].get(str(channel_id))



def check_staff(interaction):

    ticket = get_ticket_from_channel(interaction.channel.id)

    if not ticket:
        return False

    settings = database["tickets"].get(ticket["type"])

    if not settings:
        return False

    staff_roles = settings.get("staff_roles", [])
    
    if is_manager(interaction.user):
        return True

    user_roles = [role.id for role in interaction.user.roles]

    for role in staff_roles:
        if role in user_roles:
            return True

    return False


print("✅ الأجزاء الأساسية وقواعد البيانات جاهزة")


# ==================================
# إنشاء أنواع التذاكر والأوامر الإدارية (مع حماية المشرفين)
# ==================================

@bot.tree.command(
    name="reload-data",
    description="إعادة تحميل قاعدة البيانات"
)
async def reload_data(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ للمشرفين فقط",
            ephemeral=True
        )
        return

    global database
    database = load_database()

    await interaction.response.send_message(
        "✅ تم تحديث البيانات",
        ephemeral=True
    )



@bot.tree.command(
    name="backup-tickets",
    description="عمل نسخة احتياطية"
)
async def backup_tickets(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ للمشرفين فقط",
            ephemeral=True
        )
        return

    filename = f"backup-{datetime.now().strftime('%Y-%m-%d')}.json"

    with open(filename,"w",encoding="utf-8") as f:
        json.dump(
            database,
            f,
            indent=4,
            ensure_ascii=False
        )

    await interaction.response.send_message(
        "✅ تم إنشاء نسخة احتياطية",
        file=discord.File(filename),
        ephemeral=True
    )



@bot.tree.command(
    name="restore-backup",
    description="استرجاع نسخة احتياطية"
)
async def restore_backup(interaction:discord.Interaction):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ للمشرفين فقط",
            ephemeral=True
        )
        return

    global database

    if not os.path.exists(BACKUP_FILE):
        await interaction.response.send_message(
            "❌ لا يوجد نسخة احتياطية",
            ephemeral=True
        )
        return

    with open(BACKUP_FILE, "r", encoding="utf-8") as file:
        database = json.load(file)

    await interaction.response.send_message(
        embed=make_embed(
            "✅ تم الاسترجاع",
            "تم استرجاع قاعدة بيانات التذاكر بنجاح.",
            discord.Color.green()
        ),
        ephemeral=True
    )



@bot.tree.command(
    name="add-manager",
    description="إضافة مدير لنظام التذاكر"
)
@app_commands.describe(
    member="العضو"
)
async def add_manager(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ للمشرفين فقط",
            ephemeral=True
        )
        return

    database["stats"]["permissions"]["managers"].append(
        member.id
    )

    save_database()

    database["stats"]["logs"].append({
        "user": str(interaction.user.id),
        "action": f"أضاف المدير {member.id}",
        "time": str(datetime.now())
    })

    await interaction.response.send_message(
        embed=make_embed(
            "👑 تم إضافة مدير",
            f"{member.mention} أصبح مدير نظام التذاكر.",
            discord.Color.green()
        )
    )



@bot.tree.command(
    name="ticket-auto-setup",
    description="إعداد نظام التذاكر تلقائياً"
)
async def ticket_auto_setup(
    interaction: discord.Interaction
):

    if not is_manager(interaction.user):
        await interaction.response.send_message(
            "❌ لا تملك صلاحية",
            ephemeral=True
        )
        return

    guild = interaction.guild

    open_category = await guild.create_category(
        "🎫 التذاكر المفتوحة"
    )

    close_category = await guild.create_category(
        "🔒 التذاكر المغلقة"
    )

    logs = await guild.create_text_channel(
        "📜-ticket-logs"
    )

    database["panel"]["channel"] = logs.id

    database["auto_setup"] = {
        "open_category": open_category.id,
        "close_category": close_category.id,
        "logs": logs.id
    }

    save_database()

    await interaction.response.send_message(
        embed=make_embed(
            "✅ تم الإعداد",
            "تم إنشاء نظام التذاكر بالكامل.",
            discord.Color.green()
        ),
        ephemeral=True
    )



@bot.tree.command(
    name="ticket-system-info",
    description="معلومات النظام"
)
async def ticket_system_info(
    interaction: discord.Interaction
):

    embed = make_embed(
        "🤖 حالة النظام",
        ""
    )

    embed.add_field(
        name="🎫 أنواع التذاكر",
        value=str(len(database["tickets"]))
    )

    embed.add_field(
        name="📂 التذاكر المفتوحة",
        value=str(len(database["open_tickets"]))
    )

    embed.add_field(
        name="👑 المدراء",
        value=str(len(database["stats"]["permissions"]["managers"]))
    )

    await interaction.response.send_message(
        embed=embed
    )



@bot.tree.command(
    name="dashboard",
    description="لوحة إحصائيات التذاكر"
)
async def dashboard(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ للمشرفين فقط",
            ephemeral=True
        )
        return

    stats = database["stats"]

    embed = discord.Embed(
        title="📊 لوحة التحكم",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="🎫 إجمالي الفتح",
        value=str(stats["total_opened"])
    )

    embed.add_field(
        name="🔒 إجمالي الإغلاق",
        value=str(stats["total_closed"])
    )

    embed.add_field(
        name="👑 عدد الإداريين",
        value=str(len(stats["staff"]))
    )

    embed.set_footer(
        text="Ticket System Professional"
    )

    await interaction.response.send_message(
        embed=embed
    )



@bot.tree.command(
    name="ticket-create",
    description="إنشاء نوع تذكرة جديد"
)
@app_commands.describe(
    name="اسم التذكرة",
    description="وصف التذكرة في البانل",
    name_format="صيغة اسم الروم، استخدم {count} للعداد و {emoji} للإيموجي"
)
async def ticket_create(
    interaction: discord.Interaction,
    name: str,
    description: str,
    name_format: str = "{emoji}・{count}"
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط", ephemeral=True)
        return

    ticket_id = create_ticket_id()

    database["tickets"][ticket_id] = default_ticket()
    database["tickets"][ticket_id]["name"] = name
    database["tickets"][ticket_id]["description"] = description
    database["tickets"][ticket_id]["panel_description"] = description
    database["tickets"][ticket_id]["name_format"] = name_format.strip() or "{emoji}・{count}"

    save_database()

    await interaction.response.send_message(
        f"✅ تم إنشاء نوع تذكرة جديد\n🎫 الاسم: {name}\n🆔 المعرف: `{ticket_id}`",
        ephemeral=True
    )



@bot.tree.command(
    name="ticket-delete",
    description="حذف نوع تذكرة"
)
@app_commands.describe(
    ticket_id="معرف التذكرة"
)
async def ticket_delete(
    interaction: discord.Interaction,
    ticket_id: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط", ephemeral=True)
        return

    if ticket_id not in database["tickets"]:
        await interaction.response.send_message("❌ هذا النوع غير موجود", ephemeral=True)
        return

    del database["tickets"][ticket_id]

    # إزالة التذكرة من جميع البانلات التي كانت تحتوي عليها
    for panel_id, panel in database.get("panels", {}).items():
        if ticket_id in panel.get("tickets", []):
            panel["tickets"].remove(ticket_id)
            try:
                await refresh_panel_message(interaction.guild, panel_id)
            except:
                pass

    save_database()

    await interaction.response.send_message("✅ تم حذف نوع التذكرة", ephemeral=True)



@bot.tree.command(
    name="tickets-list",
    description="عرض أنواع التذاكر"
)
async def tickets_list(
    interaction: discord.Interaction
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط", ephemeral=True)
        return

    if not database["tickets"]:
        await interaction.response.send_message("❌ لا يوجد أنواع تذاكر حالياً", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 أنواع التذاكر",
        color=discord.Color.blue()
    )

    for ticket_id, data in database["tickets"].items():
        embed.add_field(
            name=f"{data['emoji']} {data['name']}",
            value=f"🆔 `{ticket_id}`\n📜 {data.get('description', data.get('panel_description', ''))}",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)



@bot.tree.command(
    name="ticket-copy",
    description="نسخ إعدادات تذكرة موجودة بالكامل"
)
@app_commands.describe(
    ticket_id="معرف التذكرة المراد نسخها"
)
async def ticket_copy(
    interaction: discord.Interaction,
    ticket_id: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط", ephemeral=True)
        return

    original_ticket = get_ticket(ticket_id)
    if not original_ticket:
        await interaction.response.send_message("❌ التذكرة المراد نسخها غير موجودة", ephemeral=True)
        return

    new_id = create_ticket_id()
    copied_data = json.loads(json.dumps(original_ticket))
    copied_data["name"] = f"{copied_data['name']} (نسخة)"
    copied_data["counter"] = 0
    copied_data["opened"] = 0
    copied_data["closed"] = 0
    copied_data["ratings"] = []

    database["tickets"][new_id] = copied_data
    save_database()

    await interaction.response.send_message(f"✅ تم نسخ التذكرة بنجاح!\n🆔 المعرف الجديد: `{new_id}`", ephemeral=True)



@bot.tree.command(
    name="ticket-rename-type",
    description="تغيير اسم نوع التذكرة"
)
@app_commands.describe(
    ticket_id="معرف التذكرة",
    new_name="الاسم الجديد"
)
async def ticket_rename_type(
    interaction: discord.Interaction,
    ticket_id: str,
    new_name: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط", ephemeral=True)
        return

    ticket = get_ticket(ticket_id)

    if not ticket:
        await interaction.response.send_message("❌ التذكرة غير موجودة", ephemeral=True)
        return

    ticket["name"] = new_name
    save_database()

    await interaction.response.send_message("✅ تم تغيير الاسم", ephemeral=True)


# ==================================
# إعدادات البانل والمودال (البانلات المتعددة)
# ==================================

@bot.tree.command(
    name="add-ticket-panel",
    description="إنشاء بانل تذاكر جديد"
)
@app_commands.describe(
    title="عنوان البانل",
    description="وصف البانل",
    image="رابط صورة البانل - اختياري"
)
async def add_ticket_panel(
    interaction: discord.Interaction,
    title: str,
    description: str,
    image: str = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    panel_number = 1
    while f"panel_{panel_number}" in database["panels"]:
        panel_number += 1

    panel_id = f"panel_{panel_number}"

    database["panels"][panel_id] = {
        "title": title,
        "description": description,
        "image": image,
        "channel": interaction.channel.id,
        "message_id": None,
        "created_by": interaction.user.id,
        "created_at": str(datetime.now()),
        "tickets": []
    }

    save_database()

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue()
    )

    if image:
        embed.set_image(url=image)

    message = await interaction.channel.send(
        embed=embed,
        view=TicketPanel(panel_id)
    )

    database["panels"][panel_id]["message_id"] = message.id
    save_database()
    await send_ticket_log(interaction.guild, "admin", "🖥️ إنشاء بانل", fields=[
        ("🖥️ البانل", panel_id, True), ("👤 بواسطة", interaction.user.mention, True),
        ("📌 الروم", interaction.channel.mention, True), ("🏷️ العنوان", title, False)
    ], color=discord.Color.green())

    await interaction.followup.send(
        embed=make_embed(
            "✅ تم إنشاء البانل",
            f"تم إنشاء البانل بنجاح.\n\n"
            f"🆔 **المعرف:** `{panel_id}`\n"
            f"📌 **البانل:** {message.jump_url}\n\n"
            f"🎫 حالياً لا توجد تذاكر داخل هذا البانل.\n"
            f"استخدم `/panel-add-ticket` لإضافة تذكرة إليه.",
            discord.Color.green()
        ),
        ephemeral=True
    )



@bot.tree.command(
    name="panels-list",
    description="عرض جميع بانلات التذاكر"
)
async def panels_list(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط",
            ephemeral=True
        )
        return

    if not database.get("panels"):
        await interaction.response.send_message(
            "❌ لا يوجد أي بانلات حالياً",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🖥️ جميع بانلات التذاكر",
        color=discord.Color.blue()
    )

    for panel_id, panel in database["panels"].items():
        channel = interaction.guild.get_channel(panel.get("channel"))
        channel_text = channel.mention if channel else "❌ الروم غير موجود"

        embed.add_field(
            name=f"🆔 {panel_id}",
            value=(
                f"📌 **العنوان:** {panel.get('title', 'بدون عنوان')}\n"
                f"📜 **الوصف:** {panel.get('description', 'بدون وصف')}\n"
                f"📍 **الروم:** {channel_text}\n"
                f"🔗 [فتح البانل](https://discord.com/channels/"
                f"{interaction.guild.id}/"
                f"{panel.get('channel')}/"
                f"{panel.get('message_id')})"
            ),
            inline=False
        )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )



@bot.tree.command(
    name="delete-ticket-panel",
    description="حذف بانل تذاكر معين"
)
@app_commands.describe(
    panel_id="معرف البانل مثل panel_1"
)
async def delete_ticket_panel(
    interaction: discord.Interaction,
    panel_id: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط",
            ephemeral=True
        )
        return

    panel = database["panels"].get(panel_id)

    if not panel:
        await interaction.response.send_message(
            "❌ لم يتم العثور على هذا البانل",
            ephemeral=True
        )
        return

    channel = interaction.guild.get_channel(panel.get("channel"))

    if channel:
        try:
            message = await channel.fetch_message(panel.get("message_id"))
            await message.delete()
        except:
            pass

    del database["panels"][panel_id]
    save_database()
    await send_ticket_log(interaction.guild, "admin", "🗑️ حذف بانل", fields=[
        ("🖥️ البانل", panel_id, True), ("👤 بواسطة", interaction.user.mention, True)
    ], color=discord.Color.red())

    await interaction.response.send_message(
        f"✅ تم حذف البانل `{panel_id}` بنجاح",
        ephemeral=True
    )


# ==================================
# ربط التذاكر بالبانلات
# ==================================

async def refresh_panel_message(guild, panel_id):
    panel = database["panels"].get(panel_id)
    if not panel:
        return False

    channel = guild.get_channel(panel.get("channel"))
    if not channel:
        return False

    try:
        message = await channel.fetch_message(panel.get("message_id"))
        await message.edit(view=TicketPanel(panel_id))
        return True
    except Exception as e:
        print(f"Panel refresh error: {e}")
        return False


@bot.tree.command(
    name="panel-add-ticket",
    description="إضافة نوع تذكرة إلى بانل معين"
)
@app_commands.describe(
    panel_id="معرف البانل مثل panel_1",
    ticket_id="معرف نوع التذكرة مثل ticket_1"
)
async def panel_add_ticket(
    interaction: discord.Interaction,
    panel_id: str,
    ticket_id: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط.",
            ephemeral=True
        )
        return

    panel = database["panels"].get(panel_id)
    if not panel:
        await interaction.response.send_message(
            f"❌ البانل `{panel_id}` غير موجود.",
            ephemeral=True
        )
        return

    ticket = database["tickets"].get(ticket_id)
    if not ticket:
        await interaction.response.send_message(
            f"❌ نوع التذكرة `{ticket_id}` غير موجود.",
            ephemeral=True
        )
        return

    if ticket_id in panel.get("tickets", []):
        await interaction.response.send_message(
            f"⚠️ التذكرة **{ticket['name']}** موجودة بالفعل داخل `{panel_id}`.",
            ephemeral=True
        )
        return

    panel.setdefault("tickets", [])
    panel["tickets"].append(ticket_id)
    save_database()
    await send_ticket_log(interaction.guild, "admin", "➕ إضافة نوع تذكرة إلى بانل", fields=[
        ("🖥️ البانل", panel_id, True), ("🎫 التذكرة", ticket["name"], True),
        ("👤 بواسطة", interaction.user.mention, True)
    ], color=discord.Color.green())

    updated = await refresh_panel_message(interaction.guild, panel_id)

    await interaction.response.send_message(
        embed=make_embed(
            "✅ تمت إضافة التذكرة",
            f"🎫 **التذكرة:** {ticket['name']}\n"
            f"🆔 **المعرف:** `{ticket_id}`\n\n"
            f"🖥️ **البانل:** `{panel_id}`\n\n"
            f"{'🔄 تم تحديث البانل مباشرة.' if updated else '⚠️ تمت الإضافة لكن تعذر تحديث رسالة البانل.'}",
            discord.Color.green()
        ),
        ephemeral=True
    )


@bot.tree.command(
    name="panel-remove-ticket",
    description="إزالة نوع تذكرة من بانل معين"
)
@app_commands.describe(
    panel_id="معرف البانل",
    ticket_id="معرف نوع التذكرة"
)
async def panel_remove_ticket(
    interaction: discord.Interaction,
    panel_id: str,
    ticket_id: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط.",
            ephemeral=True
        )
        return

    panel = database["panels"].get(panel_id)
    if not panel:
        await interaction.response.send_message(
            f"❌ البانل `{panel_id}` غير موجود.",
            ephemeral=True
        )
        return

    if ticket_id not in panel.get("tickets", []):
        await interaction.response.send_message(
            "❌ هذه التذكرة غير موجودة داخل هذا البانل.",
            ephemeral=True
        )
        return

    panel["tickets"].remove(ticket_id)
    save_database()
    await send_ticket_log(interaction.guild, "admin", "➖ إزالة نوع تذكرة من بانل", fields=[
        ("🖥️ البانل", panel_id, True), ("🎫 التذكرة", ticket_id, True),
        ("👤 بواسطة", interaction.user.mention, True)
    ], color=discord.Color.red())

    updated = await refresh_panel_message(interaction.guild, panel_id)
    ticket = database["tickets"].get(ticket_id)
    ticket_name = ticket["name"] if ticket else ticket_id

    await interaction.response.send_message(
        embed=make_embed(
            "✅ تمت إزالة التذكرة",
            f"🎫 **التذكرة:** {ticket_name}\n"
            f"🆔 **المعرف:** `{ticket_id}`\n"
            f"🖥️ **البانل:** `{panel_id}`\n\n"
            f"{'🔄 تم تحديث البانل.' if updated else '⚠️ تمت الإزالة لكن تعذر تحديث البانل.'}",
            discord.Color.green()
        ),
        ephemeral=True
    )


@bot.tree.command(
    name="panel-tickets",
    description="عرض التذاكر الموجودة داخل بانل معين"
)
@app_commands.describe(
    panel_id="معرف البانل مثل panel_1"
)
async def panel_tickets(
    interaction: discord.Interaction,
    panel_id: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط.",
            ephemeral=True
        )
        return

    panel = database["panels"].get(panel_id)
    if not panel:
        await interaction.response.send_message(
            f"❌ البانل `{panel_id}` غير موجود.",
            ephemeral=True
        )
        return

    ticket_ids = panel.get("tickets", [])
    if not ticket_ids:
        await interaction.response.send_message(
            f"📭 البانل `{panel_id}` لا يحتوي على أي تذاكر.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"🎫 تذاكر {panel_id}",
        color=discord.Color.blue()
    )

    text = ""
    for ticket_id in ticket_ids:
        ticket = database["tickets"].get(ticket_id)
        if ticket:
            text += (
                f"{ticket.get('emoji', '🎫')} "
                f"**{ticket['name']}**\n"
                f"🆔 `{ticket_id}`\n\n"
            )

    if not text:
        text = "❌ لا توجد تذاكر صالحة."

    embed.description = text
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================================
# القوائم والبانل الموحد
# ==================================

class TicketSelect(discord.ui.Select):

    def __init__(self, panel_id):
        self.panel_id = panel_id
        panel = database["panels"].get(panel_id)
        options = []

        if panel:
            panel_tickets = panel.get("tickets", [])
            for ticket_id in panel_tickets:
                data = database["tickets"].get(ticket_id)
                if not data:
                    continue

                options.append(
                    discord.SelectOption(
                        label=data["name"][:100],
                        value=ticket_id,
                        description=data.get(
                            "panel_description",
                            data.get("description", "فتح تذكرة")
                        )[:100],
                        emoji=data.get("emoji", "🎫")
                    )
                )

        if not options:
            options.append(
                discord.SelectOption(
                    label="لا توجد تذاكر",
                    value="none",
                    description="لا توجد تذاكر مضافة لهذا البانل",
                    emoji="❌"
                )
            )

        options.append(
            discord.SelectOption(
                label="تحديث القائمة",
                value="refresh_menu",
                description="إعادة تحميل أنواع التذاكر",
                emoji="🔄"
            )
        )

        super().__init__(
            placeholder="🎫 اختر نوع التذكرة",
            options=options,
            custom_id=f"ticket_select_{panel_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]

        if ticket_type == "refresh_menu":
            await interaction.response.edit_message(
                view=TicketPanel(self.panel_id)
            )
            return

        if ticket_type == "none":
            await interaction.response.send_message(
                "❌ لا توجد تذاكر مضافة لهذا البانل حالياً.",
                ephemeral=True
            )
            return

        user_id = interaction.user.id
        ticket_settings = database["tickets"].get(ticket_type)

        if not ticket_settings:
            await interaction.response.send_message(
                "❌ نوع التذكرة لم يعد موجوداً.",
                ephemeral=True
            )
            return

        for t in database["open_tickets"].values():
            if t.get("owner") == user_id:
                await interaction.response.send_message(
                    "❌ لديك تذكرة مفتوحة بالفعل.",
                    ephemeral=True
                )
                return

        if ticket_settings.get("ask_reason"):
            await interaction.response.send_modal(
                TicketFormModal(ticket_type, self.panel_id)
            )
            return

        await create_ticket(
            interaction,
            ticket_type,
            None,
            self.panel_id
        )



# ==================================
# View البانل
# ==================================

class TicketPanel(discord.ui.View):

    def __init__(self, panel_id):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        self.add_item(
            TicketSelect(panel_id)
        )


# ==================================
# نظام نماذج التذاكر (Ticket Forms)
# ==================================

class TicketFormModal(discord.ui.Modal):

    def __init__(self, ticket_type, panel_id=None):
        super().__init__(title="معلومات فتح التذكرة")
        self.ticket_type = ticket_type
        self.panel_id = panel_id

        self.question1 = discord.ui.TextInput(
            label="ماذا تريد؟",
            placeholder="اكتب طلبك بالتفصيل",
            required=True,
            max_length=300
        )

        self.question2 = discord.ui.TextInput(
            label="التفاصيل الإضافية",
            placeholder="اكتب أي معلومات تساعد الإدارة",
            required=False,
            max_length=300
        )

        self.add_item(self.question1)
        self.add_item(self.question2)


    async def on_submit(self, interaction: discord.Interaction):

        reason = (
            f"📜 الطلب:\n{self.question1.value}\n\n"
            f"📌 التفاصيل:\n{self.question2.value}"
        )

        await create_ticket(
            interaction,
            self.ticket_type,
            reason,
            self.panel_id
        )



@bot.tree.command(
    name="ticket-form",
    description="تفعيل نموذج أسئلة لنوع تذكرة"
)
@app_commands.describe(
    ticket_id="معرف نوع التذكرة"
)
async def ticket_form(
    interaction: discord.Interaction,
    ticket_id: str
):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط",
            ephemeral=True
        )
        return


    if ticket_id not in database["tickets"]:
        await interaction.response.send_message(
            "❌ نوع التذكرة غير موجود",
            ephemeral=True
        )
        return


    database["tickets"][ticket_id]["ask_reason"] = True

    save_database()


    await interaction.response.send_message(
        embed=make_embed(
            "✅ تم تفعيل النموذج",
            f"تم تفعيل أسئلة الفتح لنوع التذكرة:\n🎫 {database['tickets'][ticket_id]['name']}",
            discord.Color.green()
        ),
        ephemeral=True
    )


# ==================================
# نظام فتح التذاكر والترانسكريبت
# ==================================

async def create_transcript(channel):
    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        author = f"{message.author.name}#{message.author.discriminator}" if message.author.discriminator != "0" else message.author.name
        avatar = message.author.display_avatar.url
        content = message.content or ""
        
        embeds_html = ""
        for embed in message.embeds:
            embeds_html += f"""
            <div style="background-color: #2f3136; border-left: 4px solid #7289da; padding: 10px; margin-top: 5px; border-radius: 4px;">
                <b style="color: #ffffff;">{embed.title or ''}</b>
                <p style="color: #dcddde; white-space: pre-wrap;">{embed.description or ''}</p>
            </div>
            """

        attachments_html = ""
        for att in message.attachments:
            attachments_html += f'<br><a href="{att.url}" target="_blank" style="color: #00b0f4;">📎 {att.filename}</a>'

        messages.append(f"""
        <div style="display: flex; margin-bottom: 15px; font-family: Arial, sans-serif;">
            <img src="{avatar}" style="width: 40px; height: 40px; border-radius: 50%; margin-right: 15px;">
            <div>
                <div><b>{author}</b> <span style="font-size: 11px; color: #72767d; margin-left: 5px;">{timestamp}</span></div>
                <div style="color: #dcddde; white-space: pre-wrap; margin-top: 2px;">{content}</div>
                {embeds_html}
                {attachments_html}
            </div>
        </div>
        """)

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Transcript - {channel.name}</title>
    </head>
    <body style="background-color: #36393f; color: #dcddde; padding: 20px;">
        <h2 style="color: #ffffff; border-bottom: 1px solid #4f545c; padding-bottom: 10px;">📜 سجل التذكرة: {channel.name}</h2>
        {"".join(messages)}
    </body>
    </html>
    """

    filename = f"transcript-{channel.id}.html"
    with open(filename, "w", encoding="utf-8") as file:
        file.write(html_content)

    return filename



async def send_open_log(interaction, channel, ticket):
    settings = database["tickets"].get(ticket["type"])
    if not settings:
        return
    def fmt(value):
        try: return f"<t:{int(datetime.fromisoformat(value).timestamp())}:F>"
        except Exception: return value or "غير معروف"
    await send_ticket_log(interaction.guild, "open", "🎫 فتح تذكرة", fields=[
        ("👤 صاحب التذكرة", f"<@{ticket['owner']}>", True),
        ("🎟️ النوع", settings.get("name", "غير معروف"), True),
        ("📌 الروم", channel.mention, True),
        ("🖥️ البانل", ticket.get("panel_id", "غير محدد"), True),
        ("📅 وقت الفتح", fmt(ticket.get("created")), True),
        ("👑 المستلم", f"<@{ticket['claimed']}>" if ticket.get("claimed") else "لم يتم الاستلام بعد", True),
        ("📜 سبب الفتح", ticket.get("reason") or "بدون سبب", False),
    ], color=discord.Color.green())


async def send_claim_log(interaction, channel, ticket):
    settings = database["tickets"].get(ticket.get("type"))
    def fmt(value):
        try: return f"<t:{int(datetime.fromisoformat(value).timestamp())}:F>"
        except Exception: return value or "غير معروف"
    await send_ticket_log(interaction.guild, "claim", "👑 استلام تذكرة", fields=[
        ("👤 صاحب التذكرة", f"<@{ticket.get('owner')}>", True),
        ("🎟️ النوع", settings.get("name", "غير معروف") if settings else "غير معروف", True),
        ("👑 المستلم", interaction.user.mention, True),
        ("📌 الروم", channel.mention, True),
        ("📅 وقت الاستلام", fmt(ticket.get("claimed_at")), True),
        ("⏱️ وقت الفتح", fmt(ticket.get("created")), True),
    ], color=discord.Color.gold())


async def send_close_log(interaction, channel, transcript=None, rating=None, rating_reason=None):
    ticket = database["open_tickets"].get(str(channel.id))
    if not ticket:
        return
    settings = database["tickets"].get(ticket["type"])
    def fmt(value):
        try: return f"<t:{int(datetime.fromisoformat(value).timestamp())}:F>"
        except Exception: return value or "غير معروف"
    notes = "\n".join(f"• <@{n.get('staff')}> — {n.get('note','')}" for n in ticket.get("notes", [])) or "لا توجد ملاحظات"
    await send_ticket_log(interaction.guild, "close", "🔒 إغلاق تذكرة", fields=[
        ("👤 صاحب التذكرة", f"<@{ticket.get('owner')}>", True),
        ("🎟️ النوع", settings.get("name", "غير معروف") if settings else "غير معروف", True),
        ("📌 الروم", f"#{channel.name}", True),
        ("👑 المستلم", f"<@{ticket['claimed']}>" if ticket.get("claimed") else "لا يوجد", True),
        ("🔒 أغلقها", f"<@{ticket.get('closed_by')}>" if ticket.get("closed_by") else interaction.user.mention, True),
        ("📅 وقت الفتح", fmt(ticket.get("created")), True),
        ("👑 وقت الاستلام", fmt(ticket.get("claimed_at")), True),
        ("🔒 وقت الإغلاق", fmt(ticket.get("closed_at")), True),
        ("⭐ التقييم", f"{rating}/5" if rating is not None else "لم يتم التقييم", True),
        ("📝 سبب التقييم المنخفض", rating_reason or "—", False),
        ("📑 الملاحظات", notes, False),
    ], color=discord.Color.red(), file_path=transcript)


async def create_ticket(interaction, ticket_type, reason=None, panel_id=None):
    settings = database["tickets"].get(ticket_type)
    if not settings:
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ نوع التذكرة غير موجود", ephemeral=True)
        return

    category_id = settings.get("open_category")
    category = interaction.guild.get_channel(category_id) if category_id else None

    # عداد مستقل لكل نوع تذكرة، ويتم حفظه في قاعدة البيانات
    settings["counter"] = int(settings.get("counter", 0)) + 1
    number = settings["counter"]

    # استبدال المتغيرات داخل صيغة اسم الروم
    name_format = settings.get("name_format", "{emoji}・{count}")
    replacements = {
        "{count}": str(number),
        "{emoji}": str(settings.get("emoji", "🎫")),
        "{name}": str(settings.get("name", "ticket")),
        "{user}": str(interaction.user.name),
        "{userid}": str(interaction.user.id),
        "{id}": str(number),
    }
    channel_name = name_format
    for placeholder, value in replacements.items():
        channel_name = channel_name.replace(placeholder, value)

    # Discord يفرض حداً أقصى لطول اسم الروم
    channel_name = channel_name.strip()[:100]
    if not channel_name:
        channel_name = f"{settings.get('emoji', '🎫')}・{number}"

    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    }

    for role_id in settings.get("staff_roles", []):
        role = interaction.guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

    channel = await interaction.guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites
    )

    database["open_tickets"][str(channel.id)] = {
        "owner": interaction.user.id,
        "user": str(interaction.user.id),
        "type": ticket_type,
        "created": str(datetime.now()),
        "claimed": None,
        "reason": reason,
        "panel_id": panel_id,
        "closed": False,
        "closed_by": None,
        "closed_at": None,
        "claimed_at": None,
        "rating": None,
        "rating_reason": None,
        "priority": "normal",
        "last_activity": str(datetime.now()),
        "added_members": []
    }

    database["stats"]["total_opened"] += 1
    settings["opened"] += 1
    save_database()

    colors = {
        "blue": discord.Color.blue(),
        "red": discord.Color.red(),
        "green": discord.Color.green(),
        "gold": discord.Color.gold()
    }
    embed_color = colors.get(settings.get("color"), discord.Color.blue())

    welcome_text = settings.get("welcome_message", "أهلاً {user} 👋\nسيتم الرد عليك قريباً.")
    embed = discord.Embed(
        title=f"{settings['emoji']} {settings['name']}",
        description=welcome_text.replace("{user}", interaction.user.mention),
        color=embed_color
    )

    embed.add_field(name="👤 صاحب التذكرة", value=interaction.user.mention, inline=False)
    embed.add_field(name="🔢 رقم التذكرة", value=f"#{number}", inline=False)

    if reason:
        embed.add_field(name="📜 السبب", value=reason, inline=False)

    if settings.get("ticket_image") or settings.get("image"):
        embed.set_image(url=settings.get("ticket_image") or settings.get("image"))

    embed.set_footer(text="نظام التذاكر الاحترافي")

    await channel.send(embed=embed, view=TicketButtons())
    await send_open_log(interaction, channel, database["open_tickets"][str(channel.id)])

    if not interaction.response.is_done():
        await interaction.response.send_message(f"✅ تم فتح التذكرة {channel.mention}", ephemeral=True)


# ==================================
# أزرار وأدوات داخل التذكرة
# ==================================

class TicketButtons(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        emoji="👑",
        style=discord.ButtonStyle.blurple,
        custom_id="claim_button_secure"
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_staff(interaction):
            await interaction.response.send_message("❌ ليس لديك صلاحية لاستلام التذكرة", ephemeral=True)
            return

        ticket = database["open_tickets"].get(str(interaction.channel.id))
        if not ticket:
            await interaction.response.send_message("❌ التذكرة غير موجودة", ephemeral=True)
            return

        if ticket.get("claimed"):
            await interaction.response.send_message(
                "⚠️ هذه التذكرة تم استلامها مسبقاً",
                ephemeral=True
            )
            return

        ticket["claimed"] = interaction.user.id
        ticket["claimed_at"] = str(datetime.now())
        
        staff = str(interaction.user.id)
        if staff not in database["stats"]["staff"]:
            database["stats"]["staff"][staff] = {
                "claimed": 0,
                "closed": 0
            }
        database["stats"]["staff"][staff]["claimed"] += 1

        database["stats"]["logs"].append({
            "user": str(interaction.user.id),
            "action": "استلم التذكرة",
            "time": str(datetime.now())
        })

        save_database()
        await send_claim_log(interaction, interaction.channel, ticket)
        
        button.disabled = True
        await interaction.message.edit(view=self)

        embed = make_embed(
            "👑 تم استلام التذكرة",
            f"الإداري المسؤول الآن:\n{interaction.user.mention}",
            discord.Color.gold()
        )
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message(f"👑 تم استلام التذكرة بنجاح", ephemeral=True)

    @discord.ui.button(
        label="إغلاق",
        emoji="🔒",
        style=discord.ButtonStyle.red,
        custom_id="close_button_secure"
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_staff(interaction):
            await interaction.response.send_message("❌ ليس لديك صلاحية", ephemeral=True)
            return

        channel_id = str(interaction.channel.id)
        if channel_id in database["open_tickets"]:
            database["open_tickets"][channel_id]["closed"] = True
            database["open_tickets"][channel_id]["closed_by"] = interaction.user.id
            database["open_tickets"][channel_id]["closed_at"] = str(datetime.now())
            
            staff = str(interaction.user.id)
            if staff not in database["stats"]["staff"]:
                database["stats"]["staff"][staff] = {"claimed": 0, "closed": 0}
            database["stats"]["staff"][staff]["closed"] += 1

            database["stats"]["logs"].append({
                "user": str(interaction.user.id),
                "action": "أغلِق التذكرة",
                "time": str(datetime.now())
            })

        save_database()

        await interaction.response.send_message(
            "🔒 تم تجهيز إغلاق التذكرة\n⭐ اختر تقييم الخدمة:",
            view=RatingView(interaction.channel.id),
            ephemeral=True
        )


# ==================================
# نظام التقييم والإغلاق
# ==================================

class CloseRatingReasonModal(discord.ui.Modal):
    def __init__(self, ticket_channel_id, stars):
        super().__init__(title="سبب التقييم المنخفض")
        self.ticket_channel_id = ticket_channel_id
        self.stars = stars
        self.reason = discord.ui.TextInput(
            label="سبب التقييم",
            placeholder="اكتب سبب إعطائك أقل من 5 نجوم...",
            required=True, min_length=3, max_length=1000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.reason.value.strip():
            await interaction.response.send_message("❌ يجب كتابة سبب التقييم.", ephemeral=True)
            return
        await RatingView(self.ticket_channel_id).finalize_rating(
            interaction, self.stars, self.reason.value.strip()
        )


class RatingView(discord.ui.View):
    def __init__(self, ticket_channel_id):
        super().__init__(timeout=None)
        self.ticket_channel_id = ticket_channel_id

    async def start_rating(self, interaction, stars):
        ticket = database["open_tickets"].get(str(self.ticket_channel_id))
        if not ticket:
            await interaction.response.send_message("❌ التذكرة غير موجودة.", ephemeral=True)
            return
        if interaction.user.id != ticket.get("owner"):
            await interaction.response.send_message("❌ التقييم مخصص لصاحب التذكرة فقط.", ephemeral=True)
            return
        if stars < 5:
            await interaction.response.send_modal(CloseRatingReasonModal(self.ticket_channel_id, stars))
        else:
            await self.finalize_rating(interaction, stars)

    async def finalize_rating(self, interaction, stars, rating_reason=None):
        ticket = database["open_tickets"].get(str(self.ticket_channel_id))
        if not ticket:
            return
        ticket_settings = database["tickets"].get(ticket["type"])
        if ticket_settings:
            ticket_settings["ratings"].append({
                "user": str(interaction.user.id),
                "stars": stars,
                "staff": ticket.get("claimed"),
                "reason": rating_reason,
                "time": str(datetime.now())
            })

        ticket["rating"] = stars
        ticket["rating_reason"] = rating_reason
        if not ticket.get("closed_by"):
            ticket["closed_by"] = interaction.user.id
        if not ticket.get("closed_at"):
            ticket["closed_at"] = str(datetime.now())

        save_database()
        await send_rating_log(interaction, stars, ticket, rating_reason)

        channel = interaction.channel
        close_cat_id = ticket_settings.get("close_category") if ticket_settings else None
        if close_cat_id:
            close_category = interaction.guild.get_channel(close_cat_id)
            if close_category:
                try:
                    await channel.edit(category=close_category)
                except Exception:
                    pass

        transcript = await create_transcript(channel)
        await send_close_log(interaction, channel, transcript, stars, rating_reason)

        if not interaction.response.is_done():
            await interaction.response.send_message(
                "⭐ تم حفظ تقييمك بنجاح، سيتم حذف الروم خلال 3 ثواني...", ephemeral=True
            )
        await asyncio.sleep(3)
        try:
            await channel.delete()
        except Exception:
            pass

    @discord.ui.button(label="⭐", style=discord.ButtonStyle.gray, custom_id="rating_1_sec")
    async def one(self, interaction, button):
        await self.start_rating(interaction, 1)

    @discord.ui.button(label="⭐⭐⭐", style=discord.ButtonStyle.blurple, custom_id="rating_3_sec")
    async def three(self, interaction, button):
        await self.start_rating(interaction, 3)

    @discord.ui.button(label="⭐⭐⭐⭐", style=discord.ButtonStyle.blurple, custom_id="rating_4_sec")
    async def four(self, interaction, button):
        await self.start_rating(interaction, 4)

    @discord.ui.button(label="⭐⭐⭐⭐⭐", style=discord.ButtonStyle.green, custom_id="rating_5_sec")
    async def five(self, interaction, button):
        await self.start_rating(interaction, 5)


async def send_rating_log(interaction, stars, ticket, rating_reason=None):
    staff = ticket.get("claimed")
    await send_ticket_log(interaction.guild, "rating", "⭐ تقييم تذكرة", fields=[
        ("👤 صاحب التذكرة", f"<@{ticket.get('owner')}>", True),
        ("👑 الإداري المستلم", f"<@{staff}>" if staff else "لا يوجد", True),
        ("⭐ التقييم", f"{stars}/5", True),
        ("📝 السبب", rating_reason or "لا يوجد — التقييم 5/5", False),
    ], color=discord.Color.gold())


# ==================================
# أوامر الإدارة داخل التذكرة
# ==================================

# ==================================
# مجموعة أوامر لوقات التذاكر
# ==================================

ticket_log_group = app_commands.Group(
    name="ticket-log",
    description="إعداد لوقات التذاكر"
)


def _register_ticket_log_command(
    name,
    log_type,
    description,
    success_text
):
    async def command(
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ هذا الأمر مخصص للمشرفين فقط",
                ephemeral=True
            )
            return

        database.setdefault("log_channels", {})[log_type] = channel.id
        save_database()

        await interaction.response.send_message(
            embed=make_embed(
                "📜 تم ضبط روم اللوق",
                success_text.format(
                    channel=channel.mention
                ),
                discord.Color.green()
            ),
            ephemeral=True
        )

    command.__name__ = name.replace("-", "_")

    command = app_commands.describe(
        channel="روم اللوق المخصص لهذا الحدث"
    )(command)

    ticket_log_group.command(
        name=name.replace("ticket-", "").replace("-log", ""),
        description=description
    )(command)


_register_ticket_log_command(
    "ticket-open-log",
    "open",
    "تحديد روم لوق فتح التذاكر",
    "لوق **فتح التذاكر** سيصل إلى {channel}."
)
_register_ticket_log_command(
    "ticket-claim-log",
    "claim",
    "تحديد روم لوق استلام التذاكر",
    "لوق **استلام التذاكر** سيصل إلى {channel}."
)
_register_ticket_log_command(
    "ticket-close-log",
    "close",
    "تحديد روم لوق إغلاق التذاكر",
    "لوق **إغلاق التذاكر** سيصل إلى {channel}."
)
_register_ticket_log_command(
    "ticket-rating-log",
    "rating",
    "تحديد روم لوق تقييم التذاكر",
    "لوق **التقييمات** سيصل إلى {channel}."
)
_register_ticket_log_command(
    "ticket-note-log",
    "note",
    "تحديد روم لوق ملاحظات التذاكر",
    "لوق **الملاحظات** سيصل إلى {channel}."
)
_register_ticket_log_command(
    "ticket-admin-log",
    "admin",
    "تحديد روم لوق إجراءات الإدارة",
    "لوق **إجراءات الإدارة** سيصل إلى {channel}."
)

bot.tree.add_command(ticket_log_group)


@bot.tree.command(name="claim", description="استلام التذكرة")
async def claim_ticket(interaction: discord.Interaction):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ ليس لديك صلاحية لاستلام التذكرة", ephemeral=True)
        return

    ticket = get_ticket_from_channel(interaction.channel.id)
    if not ticket:
        await interaction.response.send_message("❌ التذكرة غير موجودة", ephemeral=True)
        return

    if ticket.get("claimed"):
        await interaction.response.send_message("⚠️ هذه التذكرة تم استلامها مسبقاً", ephemeral=True)
        return

    ticket["claimed"] = interaction.user.id
    ticket["claimed_at"] = str(datetime.now())
    
    staff = str(interaction.user.id)
    if staff not in database["stats"]["staff"]:
        database["stats"]["staff"][staff] = {"claimed": 0, "closed": 0}
    database["stats"]["staff"][staff]["claimed"] += 1

    database["stats"]["logs"].append({
        "user": str(interaction.user.id),
        "action": "استلم التذكرة",
        "time": str(datetime.now())
    })

    save_database()
    await send_claim_log(interaction, interaction.channel, ticket)
    
    embed = make_embed(
        "👑 تم استلام التذكرة",
        f"الإداري المسؤول الآن:\n{interaction.user.mention}",
        discord.Color.gold()
    )
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message(f"👑 تم استلام التذكرة", ephemeral=True)



@bot.tree.command(name="close", description="إغلاق التذكرة")
async def close_ticket(interaction: discord.Interaction):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    channel_id = str(interaction.channel.id)
    if channel_id in database["open_tickets"]:
        database["open_tickets"][channel_id]["closed"] = True
        database["open_tickets"][channel_id]["closed_by"] = interaction.user.id
        database["open_tickets"][channel_id]["closed_at"] = str(datetime.now())
        
        staff = str(interaction.user.id)
        if staff not in database["stats"]["staff"]:
            database["stats"]["staff"][staff] = {"claimed": 0, "closed": 0}
        database["stats"]["staff"][staff]["closed"] += 1

        database["stats"]["logs"].append({
            "user": str(interaction.user.id),
            "action": "أغلِق التذكرة",
            "time": str(datetime.now())
        })

    save_database()
    await interaction.response.send_message("⭐ يرجى تقييم التذكرة قبل الإغلاق", view=RatingView(interaction.channel.id), ephemeral=True)



@bot.tree.command(name="rename", description="تغيير اسم التذكرة")
@app_commands.describe(name="الاسم الجديد")
async def rename_ticket(interaction: discord.Interaction, name: str):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    await interaction.channel.edit(name=name)
    await log_ticket_action(interaction, "تغيير اسم التذكرة", f"الاسم الجديد: `{name}`", discord.Color.blue())
    database["stats"]["logs"].append({
        "user": str(interaction.user.id),
        "action": f"غير اسم التذكرة إلى {name}",
        "time": str(datetime.now())
    })
    save_database()
    await interaction.response.send_message("✅ تم تغيير الاسم")



@bot.tree.command(name="priority", description="تحديد أولوية التذكرة")
@app_commands.choices(
    level=[
        app_commands.Choice(name="عادي", value="normal"),
        app_commands.Choice(name="مهم", value="important"),
        app_commands.Choice(name="عاجل", value="urgent")
    ]
)
async def priority_ticket(interaction: discord.Interaction, level: app_commands.Choice[str]):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    ticket = get_ticket_from_channel(interaction.channel.id)
    ticket["priority"] = level.value
    ticket["last_activity"] = str(datetime.now())
    save_database()
    await log_ticket_action(interaction, "تغيير أولوية", f"الأولوية الجديدة: **{level.name}**", discord.Color.orange())
    await interaction.response.send_message(f"📌 تم تغيير الأولوية إلى: {level.name}")



@bot.tree.command(name="ticket-add", description="إضافة عضو للتذكرة")
async def ticket_add(interaction: discord.Interaction, member: discord.Member):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    await interaction.channel.set_permissions(member, view_channel=True, send_messages=True)
    ticket = get_ticket_from_channel(interaction.channel.id)
    if ticket:
        ticket.setdefault("added_members", []).append(member.id)
        save_database()
    await log_ticket_action(interaction, "إضافة عضو", f"تمت إضافة {member.mention}", discord.Color.green())
    await interaction.response.send_message(f"✅ تمت إضافة {member.mention}")



@bot.tree.command(name="ticket-remove", description="إزالة عضو من التذكرة")
async def ticket_remove(interaction: discord.Interaction, member: discord.Member):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    await interaction.channel.set_permissions(member, overwrite=None)
    ticket = get_ticket_from_channel(interaction.channel.id)
    if ticket:
        ticket.setdefault("added_members", [])
        if member.id in ticket["added_members"]:
            ticket["added_members"].remove(member.id)
        save_database()
    await log_ticket_action(interaction, "إزالة عضو", f"تمت إزالة {member.mention}", discord.Color.red())
    await interaction.response.send_message(f"✅ تمت إزالة {member.mention}")



async def lock_ticket(interaction: discord.Interaction):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await log_ticket_action(interaction, "قفل التذكرة", "تم منع إرسال الرسائل", discord.Color.red())
    await interaction.response.send_message("🔒 تم قفل التذكرة")



async def unlock_ticket(interaction: discord.Interaction):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await log_ticket_action(interaction, "فتح الكتابة", "تم السماح بإرسال الرسائل", discord.Color.green())
    await interaction.response.send_message("🔓 تم فتح التذكرة")



@bot.tree.command(name="reopen", description="إعادة فتح التذكرة")
async def reopen_ticket(interaction: discord.Interaction):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    await interaction.channel.set_permissions(interaction.guild.default_role, view_channel=True)
    ticket = get_ticket_from_channel(interaction.channel.id)
    if ticket:
        ticket["closed"] = False
        ticket["reopened_at"] = str(datetime.now())
        save_database()
    await log_ticket_action(interaction, "إعادة فتح التذكرة", "تمت إعادة التذكرة للحالة المفتوحة", discord.Color.green())
    await interaction.response.send_message("🔄 تم إعادة فتح التذكرة")



@app_commands.describe(category="ID الكاتجوري الجديد")
async def move_ticket(interaction: discord.Interaction, category: str):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    try:
        category_id = int(category)
    except:
        await interaction.response.send_message("❌ ID غير صحيح", ephemeral=True)
        return

    new_category = interaction.guild.get_channel(category_id)
    if not new_category:
        await interaction.response.send_message("❌ لم يتم العثور على الكاتجوري", ephemeral=True)
        return

    old_category = interaction.channel.category.name if interaction.channel.category else "بدون كاتجوري"
    await interaction.channel.edit(category=new_category)
    await log_ticket_action(interaction, "نقل التذكرة", f"من: **{old_category}** إلى: **{new_category.name}**", discord.Color.blue())
    await interaction.response.send_message("🚚 تم نقل التذكرة")



@bot.tree.command(
    name="auto-move",
    description="نقل التذكرة تلقائياً إلى كاتجوري"
)
@app_commands.describe(
    category="ID الكاتجوري"
)
async def auto_move(
    interaction: discord.Interaction,
    category: str
):
    if not check_staff(interaction):
        await interaction.response.send_message(
            "❌ لا تملك صلاحية",
            ephemeral=True
        )
        return

    try:
        category_id = int(category)
    except:
        await interaction.response.send_message(
            "❌ ID غير صحيح",
            ephemeral=True
        )
        return

    new_category = interaction.guild.get_channel(category_id)

    if not new_category:
        await interaction.response.send_message(
            "❌ الكاتجوري غير موجود",
            ephemeral=True
        )
        return

    old_category = interaction.channel.category.name if interaction.channel.category else "بدون كاتجوري"
    await interaction.channel.edit(
        category=new_category
    )
    await log_ticket_action(interaction, "نقل تلقائي", f"من: **{old_category}** إلى: **{new_category.name}**", discord.Color.blue())

    embed = discord.Embed(
        title="🚚 تم نقل التذكرة",
        description=f"تم نقل التذكرة إلى:\n{new_category.name}",
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed
    )



@bot.tree.command(
    name="ticket-info",
    description="عرض معلومات التذكرة الحالية"
)
async def ticket_info(interaction: discord.Interaction):

    ticket = get_ticket_from_channel(interaction.channel.id)

    if not ticket:
        await interaction.response.send_message(
            "❌ هذا الروم ليس تذكرة",
            ephemeral=True
        )
        return

    settings = database["tickets"].get(ticket["type"])

    embed = discord.Embed(
        title="🎫 معلومات التذكرة",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="👤 صاحب التذكرة",
        value=f"<@{ticket['owner']}>",
        inline=False
    )

    embed.add_field(
        name="📌 النوع",
        value=settings["name"] if settings else "غير معروف",
        inline=False
    )

    embed.add_field(
        name="👑 المستلم",
        value=f"<@{ticket['claimed']}>" if ticket["claimed"] else "لا يوجد",
        inline=False
    )

    embed.add_field(
        name="📌 الأولوية",
        value=ticket.get("priority","normal"),
        inline=False
    )

    embed.add_field(
        name="📅 التاريخ",
        value=ticket.get("created","غير معروف"),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )



@bot.tree.command(
    name="ticket-note",
    description="إضافة ملاحظة للتذكرة"
)
@app_commands.describe(
    note="الملاحظة"
)
async def ticket_note(
    interaction: discord.Interaction,
    note: str
):

    if not check_staff(interaction):
        await interaction.response.send_message(
            "❌ ليس لديك صلاحية",
            ephemeral=True
        )
        return

    ticket = get_ticket_from_channel(interaction.channel.id)

    if not ticket:
        await interaction.response.send_message(
            "❌ ليست تذكرة",
            ephemeral=True
        )
        return

    ticket.setdefault("notes", [])

    ticket["notes"].append({
        "staff": interaction.user.id,
        "note": note,
        "time": str(datetime.now())
    })

    save_database()
    await log_ticket_action(interaction, "إضافة ملاحظة", f"📝 {note}", discord.Color.gold(), "note")

    await interaction.response.send_message(
        "✅ تم حفظ الملاحظة",
        ephemeral=True
    )



@bot.tree.command(
    name="ticket-notes",
    description="عرض ملاحظات التذكرة"
)
async def ticket_notes(interaction: discord.Interaction):

    ticket = get_ticket_from_channel(interaction.channel.id)

    if not ticket:
        await interaction.response.send_message(
            "❌ ليست تذكرة",
            ephemeral=True
        )
        return

    notes = ticket.get("notes", [])

    if not notes:
        await interaction.response.send_message(
            "📑 لا يوجد ملاحظات",
            ephemeral=True
        )
        return

    text = ""

    for n in notes:
        text += f"👤 <@{n['staff']}> : {n['note']}\n"

    embed = discord.Embed(
        title="📜 ملاحظات التذكرة",
        description=text,
        color=discord.Color.gold()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )



@bot.tree.command(name="ticket-stats", description="إحصائيات التذاكر")
async def ticket_stats(interaction: discord.Interaction):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    opened = len(database["open_tickets"])
    closed = database.get("closed_today", 0)

    embed = discord.Embed(title="📊 إحصائيات التذاكر", color=discord.Color.blue())
    embed.add_field(name="🎫 المفتوحة", value=str(opened))
    embed.add_field(name="🔒 المغلقة", value=str(closed))
    await interaction.response.send_message(embed=embed)


# ==================================
# إعدادات التذكرة المخصصة
# ==================================

class TicketSettingsModal(discord.ui.Modal):

    def __init__(self, ticket_id, option):
        super().__init__(title="تعديل إعداد التذكرة")
        self.ticket_id = ticket_id
        self.option = option

        self.value = discord.ui.TextInput(
            label="القيمة الجديدة",
            placeholder="اكتب القيمة أو ID هنا",
            required=True,
            max_length=4000
        )
        self.add_item(self.value)

    async def on_submit(self, interaction: discord.Interaction):
        ticket = database["tickets"][self.ticket_id]
        value = self.value.value

        if self.option == "name":
            ticket["name"] = value
        elif self.option == "description":
            ticket["description"] = value
            ticket["panel_description"] = value
        elif self.option == "emoji":
            ticket["emoji"] = value
        elif self.option == "color":
            ticket["color"] = value
        elif self.option == "welcome":
            ticket["welcome_message"] = value
        elif self.option == "image":
            ticket["ticket_image"] = value
            ticket["image"] = value
        elif self.option == "open_category":
            ticket["open_category"] = int(value)
        elif self.option == "close_category":
            ticket["close_category"] = int(value)
        elif self.option == "staff_role":
            ticket["staff_roles"].append(int(value))
        elif self.option == "remove_staff_role":
            role_id = int(value)
            if role_id in ticket["staff_roles"]:
                ticket["staff_roles"].remove(role_id)

        save_database()
        await interaction.response.send_message("✅ تم حفظ التعديل", ephemeral=True)



class TicketSettingsView(discord.ui.View):

    def __init__(self, ticket_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.select(
        placeholder="اختر إعداد للتعديل",
        options=[
            discord.SelectOption(label="اسم التذكرة", value="name", emoji="🏷️"),
            discord.SelectOption(label="وصف البانل", value="description", emoji="📜"),
            discord.SelectOption(label="إيموجي التذكرة", value="emoji", emoji="😀"),
            discord.SelectOption(label="لون التذكرة", value="color", emoji="🎨"),
            discord.SelectOption(label="رسالة الترحيب", value="welcome", emoji="👋"),
            discord.SelectOption(label="صورة داخل التذكرة", value="image", emoji="🖼️"),
            discord.SelectOption(label="كاتجوري الفتح", value="open_category", emoji="📂"),
            discord.SelectOption(label="كاتجوري الإغلاق", value="close_category", emoji="🔒"),
            discord.SelectOption(label="إضافة رتبة إدارة", value="staff_role", emoji="🛡️"),
            discord.SelectOption(label="إزالة رتبة إدارة", value="remove_staff_role", emoji="❌")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.send_modal(TicketSettingsModal(self.ticket_id, select.values[0]))



@bot.tree.command(name="ticket-settings", description="تعديل إعدادات نوع تذكرة")
@app_commands.describe(ticket_id="معرف التذكرة")
async def ticket_settings(interaction: discord.Interaction, ticket_id: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط", ephemeral=True)
        return

    if ticket_id not in database["tickets"]:
        await interaction.response.send_message("❌ نوع التذكرة غير موجود", ephemeral=True)
        return

    embed = discord.Embed(
        title="⚙️ إعدادات التذكرة",
        description=f"تعديل:\n🎫 {database['tickets'][ticket_id]['name']}",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, view=TicketSettingsView(ticket_id), ephemeral=True)


# ==================================
# نظام الحماية و Anti-Spam والخلفيات
# ==================================

spam_users = {}
SPAM_LIMIT = 5
SPAM_TIME = 5


async def anti_spam(message):
    user = message.author.id
    now = asyncio.get_event_loop().time()

    if user not in spam_users:
        spam_users[user] = []

    spam_users[user].append(now)

    spam_users[user] = [
        x for x in spam_users[user]
        if now - x <= SPAM_TIME
    ]

    if len(spam_users[user]) >= SPAM_LIMIT:
        try:
            await message.delete()
        except:
            pass

        embed = discord.Embed(
            title="⚠️ حماية السبام",
            description=f"{message.author.mention} تم منع الإرسال السريع.",
            color=discord.Color.orange()
        )

        await message.channel.send(
            embed=embed,
            delete_after=5
        )

        spam_users[user] = []


AUTO_CLOSE_TIME = 24 * 60 * 60

async def auto_close_checker():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now()
        for channel_id, ticket in list(database["open_tickets"].items()):
            try:
                created = datetime.fromisoformat(ticket["created"])
                if (now - created).total_seconds() >= AUTO_CLOSE_TIME:
                    channel = bot.get_channel(int(channel_id))
                    if channel:
                        embed = discord.Embed(
                            title="🔒 إغلاق تلقائي",
                            description="تم إغلاق التذكرة بسبب عدم النشاط لمدة 24 ساعة.",
                            color=discord.Color.red()
                        )
                        await channel.send(embed=embed)
                        try:
                            await channel.delete()
                        except:
                            pass
                    del database["open_tickets"][channel_id]
                    save_database()
            except:
                pass
        await asyncio.sleep(300)


async def database_backup():
    await bot.wait_until_ready()
    while not bot.is_closed():
        with open(BACKUP_FILE, "w", encoding="utf-8") as file:
            json.dump(
                database,
                file,
                indent=4,
                ensure_ascii=False
            )
        await asyncio.sleep(3600)



async def ticket_on_message(message):
    if message.author.bot or not message.guild:
        return

    channel_id = message.channel.id
    if str(channel_id) in database["open_tickets"]:
        database["open_tickets"][str(channel_id)]["last_activity"] = str(datetime.now())
        save_database()

    await anti_spam(message)
    await bot.process_commands(message)



# ==================================
# تشغيل البوت واستقرار الـ Persistent Views
# ==================================


_ticket_background_tasks_started = False

async def ticket_on_ready():
    print(f"✅ Bot Online: {bot.user}")

    for panel_id in database.get("panels", {}):
        try:
            bot.add_view(TicketPanel(panel_id))
        except Exception as e:
            print(f"❌ Failed to load panel {panel_id}: {e}")

    bot.add_view(TicketButtons())

    for channel_id in database["open_tickets"]:
        bot.add_view(RatingView(int(channel_id)))

    global _ticket_background_tasks_started
    if not _ticket_background_tasks_started:
        asyncio.create_task(auto_close_checker())
        asyncio.create_task(database_backup())
        _ticket_background_tasks_started = True

    # تمت مزامنة Slash Commands في setup_hook عند بدء البوت.


# ===================== POINTS + ROLE SHOP (PRESERVED + ENHANCED) =====================
# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("TOKEN")

POINTS_PER_HOUR = 10
INACTIVITY_MINUTES = 15
TICK_SECONDS = 30

_default_points_db = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "points.db"
)
DB_FILE = os.getenv("POINTS_DB_FILE", _default_points_db)
_db_dir = os.path.dirname(os.path.abspath(DB_FILE))
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.row_factory = sqlite3.Row

db.execute("""
CREATE TABLE IF NOT EXISTS users (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    points INTEGER NOT NULL DEFAULT 0,
    voice_seconds INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    notification_channel_id INTEGER,
    dm_enabled INTEGER NOT NULL DEFAULT 0,
    afk_channel_id INTEGER,
    notification_message TEXT NOT NULL DEFAULT '🎉 حصلت على **{added} نقطة**! - 🎙️ وقتك المحتسب: **{time}** - 🪙 رصيدك الحالي: **{points} نقطة**'
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    amount INTEGER NOT NULL,
    old_points INTEGER NOT NULL,
    new_points INTEGER NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS role_shop (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    price INTEGER NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    UNIQUE(guild_id, role_id)
)
""")
db.commit()


# =========================================================
# DATABASE FUNCTIONS
# =========================================================

def ensure_user(guild_id: int, user_id: int):
    db.execute(
        """
        INSERT OR IGNORE INTO users
        (guild_id, user_id, points, voice_seconds)
        VALUES (?, ?, 0, 0)
        """,
        (guild_id, user_id)
    )
    db.commit()


def get_user(guild_id: int, user_id: int):
    ensure_user(guild_id, user_id)

    return db.execute(
        """
        SELECT *
        FROM users
        WHERE guild_id = ?
        AND user_id = ?
        """,
        (guild_id, user_id)
    ).fetchone()


def update_user(
    guild_id: int,
    user_id: int,
    points=None,
    voice_seconds=None
):
    current = get_user(guild_id, user_id)

    new_points = (
        current["points"]
        if points is None
        else points
    )

    new_seconds = (
        current["voice_seconds"]
        if voice_seconds is None
        else voice_seconds
    )

    db.execute(
        """
        UPDATE users
        SET points = ?,
            voice_seconds = ?
        WHERE guild_id = ?
        AND user_id = ?
        """,
        (
            new_points,
            new_seconds,
            guild_id,
            user_id
        )
    )

    db.commit()


def add_history(
    guild_id,
    user_id,
    action,
    amount,
    old_points,
    new_points,
    reason
):
    db.execute(
        """
        INSERT INTO history (
            guild_id,
            user_id,
            action,
            amount,
            old_points,
            new_points,
            reason,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            guild_id,
            user_id,
            action,
            amount,
            old_points,
            new_points,
            reason,
            datetime.now(timezone.utc).isoformat()
        )
    )

    db.commit()


def get_settings(guild_id: int):
    row = db.execute(
        """
        SELECT *
        FROM guild_settings
        WHERE guild_id = ?
        """,
        (guild_id,)
    ).fetchone()

    if row is None:

        db.execute(
            """
            INSERT INTO guild_settings (
                guild_id
            )
            VALUES (?)
            """,
            (guild_id,)
        )

        db.commit()

        row = db.execute(
            """
            SELECT *
            FROM guild_settings
            WHERE guild_id = ?
            """,
            (guild_id,)
        ).fetchone()

    return row


# =========================================================
# TIME FORMAT
# =========================================================

def format_time(seconds: int):

    seconds = int(seconds)

    days = seconds // 86400
    seconds %= 86400

    hours = seconds // 3600
    seconds %= 3600

    minutes = seconds // 60
    seconds %= 60

    parts = []

    if days:
        parts.append(f"{days} يوم")

    if hours:
        parts.append(f"{hours} ساعة")

    if minutes:
        parts.append(f"{minutes} دقيقة")

    if seconds and not parts:
        parts.append(f"{seconds} ثانية")

    if not parts:
        return "0 دقيقة"

    return " و".join(parts)


# =========================================================
# BOT
# =========================================================

# The single Bot instance is created at the top of this file.
# =========================================================
# VOICE SESSIONS
# =========================================================

voice_sessions = {}


def current_time():
    return datetime.now(timezone.utc)


def is_in_afk(member: discord.Member):

    settings = get_settings(
        member.guild.id
    )

    afk_channel_id = settings[
        "afk_channel_id"
    ]

    if not afk_channel_id:
        return False

    if not member.voice:
        return False

    if not member.voice.channel:
        return False

    return (
        member.voice.channel.id
        == afk_channel_id
    )


def is_active(guild_id, user_id):

    session = voice_sessions.get(
        (guild_id, user_id)
    )

    if not session:
        return False

    inactive_seconds = (
        current_time()
        - session["last_activity"]
    ).total_seconds()

    return (
        inactive_seconds
        < INACTIVITY_MINUTES * 60
    )


# =========================================================
# ACTIVITY
# =========================================================

def register_activity(member: discord.Member):

    if member.bot:
        return

    if not member.voice:
        return

    if not member.voice.channel:
        return

    key = (
        member.guild.id,
        member.id
    )

    if key in voice_sessions:

        voice_sessions[key][
            "last_activity"
        ] = current_time()


# =========================================================
# NOTIFICATIONS
# =========================================================

async def send_point_notification(
    guild: discord.Guild,
    member: discord.Member,
    added: int,
    total_points: int,
    total_seconds: int
):

    settings = get_settings(
        guild.id
    )

    message = settings[
        "notification_message"
    ]

    replacements = {
        "{user}": member.mention,
        "{points}": str(total_points),
        "{added}": str(added),
        "{time}": format_time(total_seconds),
        "{total_time}": format_time(total_seconds)
    }

    for key, value in replacements.items():
        message = message.replace(
            key,
            value
        )

    # -----------------------------------------
    # CHANNEL
    # -----------------------------------------

    channel_id = settings[
        "notification_channel_id"
    ]

    if channel_id:

        channel = guild.get_channel(
            channel_id
        )

        if channel:

            try:
                await channel.send(
                    message
                )

            except Exception as error:
                print(
                    f"[CHANNEL ERROR] {error}"
                )

    # -----------------------------------------
    # DM
    # -----------------------------------------

    if settings["dm_enabled"]:

        try:
            await member.send(
                message
            )

        except Exception as error:
            print(
                f"[DM ERROR] {member}: {error}"
            )


# =========================================================
# PROCESS VOICE
# =========================================================

async def process_voice_member(
    guild: discord.Guild,
    member: discord.Member,
    now_time: datetime
):

    if member.bot:
        return

    if not member.voice:
        return

    if not member.voice.channel:
        return

    key = (
        guild.id,
        member.id
    )

    # -----------------------------------------
    # AFK
    # -----------------------------------------

    if is_in_afk(member):

        if key in voice_sessions:

            voice_sessions[key][
                "last_tick"
            ] = now_time

        return

    # -----------------------------------------
    # NEW SESSION
    # -----------------------------------------

    if key not in voice_sessions:

        voice_sessions[key] = {
            "last_tick": now_time,
            "last_activity": now_time
        }

        return

    session = voice_sessions[key]

    elapsed = (
        now_time
        - session["last_tick"]
    ).total_seconds()

    session["last_tick"] = now_time

    if elapsed <= 0:
        return

    # -----------------------------------------
    # INACTIVITY
    # -----------------------------------------

    if not is_active(
        guild.id,
        member.id
    ):

        session[
            "last_tick"
        ] = now_time

        return

    # -----------------------------------------
    # SAVE TIME
    # -----------------------------------------

    user = get_user(
        guild.id,
        member.id
    )

    old_seconds = user[
        "voice_seconds"
    ]

    new_seconds = (
        old_seconds
        + int(elapsed)
    )

    old_points = user[
        "points"
    ]

    old_hours = (
        old_seconds // 3600
    )

    new_hours = (
        new_seconds // 3600
    )

    gained_hours = (
        new_hours
        - old_hours
    )

    gained_points = (
        gained_hours
        * POINTS_PER_HOUR
    )

    update_user(
        guild.id,
        member.id,
        points=old_points + gained_points,
        voice_seconds=new_seconds
    )

    # -----------------------------------------
    # POINTS REWARD
    # -----------------------------------------

    if gained_points > 0:

        new_points = (
            old_points
            + gained_points
        )

        add_history(
            guild.id,
            member.id,
            "voice",
            gained_points,
            old_points,
            new_points,
            "Voice activity"
        )

        await send_point_notification(
            guild,
            member,
            gained_points,
            new_points,
            new_seconds
        )


# =========================================================
# BACKGROUND LOOP
# =========================================================

@tasks.loop(seconds=TICK_SECONDS)
async def points_loop():

    now_time = current_time()

    for guild in bot.guilds:

        for member in guild.members:

            if member.bot:
                continue

            if not member.voice:
                continue

            try:

                await process_voice_member(
                    guild,
                    member,
                    now_time
                )

            except Exception as error:

                print(
                    f"[POINT LOOP ERROR] "
                    f"{guild.id}/{member.id}: "
                    f"{error}"
                )


@points_loop.before_loop
async def before_points_loop():

    await bot.wait_until_ready()


# =========================================================
# VOICE EVENT
# =========================================================

@bot.event
async def on_voice_state_update(
    member,
    before,
    after
):

    if member.bot:
        return

    key = (
        member.guild.id,
        member.id
    )

    now_time = current_time()

    # -----------------------------------------
    # JOIN
    # -----------------------------------------

    if (
        before.channel is None
        and after.channel is not None
    ):

        voice_sessions[key] = {
            "last_tick": now_time,
            "last_activity": now_time
        }

        return

    # -----------------------------------------
    # LEAVE
    # -----------------------------------------

    if (
        before.channel is not None
        and after.channel is None
    ):

        voice_sessions.pop(
            key,
            None
        )

        return

    # -----------------------------------------
    # MOVE
    # -----------------------------------------

    if (
        before.channel is not None
        and after.channel is not None
        and before.channel.id
        != after.channel.id
    ):

        voice_sessions[key] = {
            "last_tick": now_time,
            "last_activity": now_time
        }


# =========================================================
# MESSAGE ACTIVITY
# =========================================================

async def points_on_message(message):

    if message.author.bot:
        return

    if isinstance(
        message.author,
        discord.Member
    ):

        register_activity(
            message.author
        )

    await bot.process_commands(
        message
    )


# =========================================================
# REACTION ACTIVITY
# =========================================================

@bot.event
async def on_raw_reaction_add(
    payload
):

    if payload.guild_id is None:
        return

    guild = bot.get_guild(
        payload.guild_id
    )

    if not guild:
        return

    member = guild.get_member(
        payload.user_id
    )

    if not member:
        return

    if member.bot:
        return

    register_activity(
        member
    )


# =========================================================
# POINTS COMMAND GROUP
# =========================================================

points_group = app_commands.Group(
    name="points",
    description="نظام النقاط"
)

# =========================================================
# /points
# =========================================================

@points_group.command(
    name="info",
    description="عرض نقاطك ووقت الفويس"
)
async def points(
    interaction: discord.Interaction
):

    data = get_user(
        interaction.guild.id,
        interaction.user.id
    )

    embed = discord.Embed(
        title="🪙 نقاطك",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="🪙 النقاط",
        value=f"**{data['points']}**",
        inline=True
    )

    embed.add_field(
        name="🎙️ وقت الفويس",
        value=format_time(
            data["voice_seconds"]
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# /points-top
# =========================================================

@points_group.command(
    name="top",
    description="عرض أعلى الأعضاء بالنقاط"
)
async def points_top(
    interaction: discord.Interaction
):

    rows = db.execute(
        """
        SELECT user_id, points, voice_seconds
        FROM users
        WHERE guild_id = ?
        ORDER BY points DESC
        LIMIT 10
        """,
        (interaction.guild.id,)
    ).fetchall()

    if not rows:

        return await interaction.response.send_message(
            "❌ لا توجد بيانات بعد.",
            ephemeral=True
        )

    text = ""

    medals = [
        "🥇",
        "🥈",
        "🥉"
    ]

    for index, row in enumerate(
        rows,
        start=1
    ):

        member = interaction.guild.get_member(
            row["user_id"]
        )

        name = (
            member.display_name
            if member
            else f"User {row['user_id']}"
        )

        medal = (
            medals[index - 1]
            if index <= 3
            else f"**{index}.**"
        )

        text += (
            f"{medal} {name} — "
            f"**{row['points']} نقطة**\n"
        )

    embed = discord.Embed(
        title="🏆 Top Points",
        description=text,
        color=discord.Color.gold()
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /points-user
# =========================================================

@points_group.command(
    name="user",
    description="عرض نقاط عضو معين"
)
@app_commands.describe(
    user="العضو"
)
async def points_user(
    interaction,
    user: discord.Member
):

    data = get_user(
        interaction.guild.id,
        user.id
    )

    embed = discord.Embed(
        title=f"🪙 نقاط {user.display_name}",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🪙 النقاط",
        value=str(data["points"]),
        inline=True
    )

    embed.add_field(
        name="🎙️ وقت الفويس",
        value=format_time(
            data["voice_seconds"]
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# ADMIN CHECK
# =========================================================

def admin_only():

    return app_commands.checks.has_permissions(
        administrator=True
    )


# =========================================================
# /points-give
# =========================================================

@points_group.command(
    name="give",
    description="إعطاء نقاط لعضو"
)
@admin_only()
@app_commands.describe(
    user="العضو",
    amount="عدد النقاط",
    reason="سبب العملية"
)
async def points_give(
    interaction,
    user: discord.Member,
    amount: app_commands.Range[int, 1, 1000000],
    reason: str = "بدون سبب"
):

    data = get_user(
        interaction.guild.id,
        user.id
    )

    old = data["points"]
    new = old + amount

    update_user(
        interaction.guild.id,
        user.id,
        points=new
    )

    add_history(
        interaction.guild.id,
        user.id,
        "give",
        amount,
        old,
        new,
        reason
    )

    await interaction.response.send_message(
        f"✅ تم إعطاء {user.mention} "
        f"**{amount} نقطة**.\n"
        f"🪙 رصيده الآن: **{new}**\n"
        f"📝 السبب: {reason}"
    )


# =========================================================
# /points-remove
# =========================================================

@points_group.command(
    name="remove",
    description="خصم نقاط من عضو"
)
@admin_only()
@app_commands.describe(
    user="العضو",
    amount="عدد النقاط",
    reason="سبب العملية"
)
async def points_remove(
    interaction,
    user: discord.Member,
    amount: app_commands.Range[int, 1, 1000000],
    reason: str = "بدون سبب"
):

    data = get_user(
        interaction.guild.id,
        user.id
    )

    old = data["points"]

    new = max(
        0,
        old - amount
    )

    removed = old - new

    update_user(
        interaction.guild.id,
        user.id,
        points=new
    )

    add_history(
        interaction.guild.id,
        user.id,
        "remove",
        removed,
        old,
        new,
        reason
    )

    await interaction.response.send_message(
        f"✅ تم خصم **{removed} نقطة** "
        f"من {user.mention}.\n"
        f"🪙 رصيده الآن: **{new}**\n"
        f"📝 السبب: {reason}"
    )


# =========================================================
# /points-set
# =========================================================

@points_group.command(
    name="set",
    description="تحديد نقاط عضو"
)
@admin_only()
@app_commands.describe(
    user="العضو",
    amount="النقاط الجديدة",
    reason="سبب العملية"
)
async def points_set(
    interaction,
    user: discord.Member,
    amount: app_commands.Range[int, 0, 1000000],
    reason: str = "بدون سبب"
):

    data = get_user(
        interaction.guild.id,
        user.id
    )

    old = data["points"]

    update_user(
        interaction.guild.id,
        user.id,
        points=amount
    )

    add_history(
        interaction.guild.id,
        user.id,
        "set",
        amount - old,
        old,
        amount,
        reason
    )

    await interaction.response.send_message(
        f"✅ تم تغيير نقاط {user.mention} "
        f"من **{old}** إلى **{amount}**."
    )


# =========================================================
# /points-history
# =========================================================

@points_group.command(
    name="history",
    description="عرض سجل النقاط"
)
@app_commands.describe(
    user="عضو معين - اختياري"
)
async def points_history(
    interaction,
    user: discord.Member = None
):

    target = (
        user
        if user
        else interaction.user
    )

    rows = db.execute(
        """
        SELECT *
        FROM history
        WHERE guild_id = ?
        AND user_id = ?
        ORDER BY id DESC
        LIMIT 15
        """,
        (
            interaction.guild.id,
            target.id
        )
    ).fetchall()

    if not rows:

        return await interaction.response.send_message(
            "📜 لا يوجد سجل.",
            ephemeral=True
        )

    text = ""

    for row in rows:

        if row["action"] == "remove":
            symbol = "🔻"

        elif row["action"] == "give":
            symbol = "🔺"

        elif row["action"] == "voice":
            symbol = "🎙️"

        elif row["action"] == "buy":
            symbol = "🛒"

        else:
            symbol = "⚙️"

        text += (
            f"{symbol} **{row['action']}** — "
            f"{row['amount']} نقطة\n"
            f"↳ {row['old_points']} → "
            f"{row['new_points']}\n"
            f"↳ {row['reason'] or 'بدون سبب'}\n\n"
        )

    embed = discord.Embed(
        title=f"📜 سجل {target.display_name}",
        description=text[:4096],
        color=discord.Color.blurple()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# /points-reset
# =========================================================

@points_group.command(
    name="reset",
    description="تصفير نقاط عضو"
)
@admin_only()
@app_commands.describe(
    user="العضو",
    reason="سبب التصفير"
)
async def points_reset(
    interaction,
    user: discord.Member,
    reason: str = "بدون سبب"
):

    data = get_user(
        interaction.guild.id,
        user.id
    )

    old = data["points"]

    update_user(
        interaction.guild.id,
        user.id,
        points=0
    )

    add_history(
        interaction.guild.id,
        user.id,
        "reset",
        -old,
        old,
        0,
        reason
    )

    await interaction.response.send_message(
        f"♻️ تم تصفير نقاط "
        f"{user.mention}.\n"
        f"🪙 كان لديه: **{old} نقطة**."
    )


# =========================================================
# /points-setup
# =========================================================

@points_group.command(
    name="setup",
    description="إعداد نظام النقاط"
)
@admin_only()
@app_commands.describe(
    notification_channel="روم إشعارات النقاط - اختياري",
    dm="إرسال إشعارات DM؟",
    afk_channel="روم AFK المستثنى من الحساب - اختياري"
)
async def points_setup(
    interaction,
    notification_channel: discord.TextChannel = None,
    dm: bool = False,
    afk_channel: discord.VoiceChannel = None
):

    db.execute(
        """
        INSERT INTO guild_settings (
            guild_id,
            notification_channel_id,
            dm_enabled,
            afk_channel_id
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET
            notification_channel_id =
                excluded.notification_channel_id,
            dm_enabled =
                excluded.dm_enabled,
            afk_channel_id =
                excluded.afk_channel_id
        """,
        (
            interaction.guild.id,
            (
                notification_channel.id
                if notification_channel
                else None
            ),
            int(dm),
            (
                afk_channel.id
                if afk_channel
                else None
            )
        )
    )

    db.commit()

    channel_text = (
        notification_channel.mention
        if notification_channel
        else "❌ غير محدد"
    )

    afk_text = (
        afk_channel.mention
        if afk_channel
        else "❌ غير محدد"
    )

    dm_text = (
        "✅ مفعّل"
        if dm
        else "❌ معطل"
    )

    embed = discord.Embed(
        title="⚙️ إعدادات نظام النقاط",
        color=discord.Color.green()
    )

    embed.add_field(
        name="📢 روم الإشعارات",
        value=channel_text,
        inline=False
    )

    embed.add_field(
        name="💌 DM",
        value=dm_text,
        inline=True
    )

    embed.add_field(
        name="💤 AFK",
        value=afk_text,
        inline=True
    )

    embed.add_field(
        name="🎙️ النظام",
        value=(
            "10 نقاط لكل ساعة\n"
            "15 دقيقة بدون نشاط = إيقاف الحساب\n"
            "الميكروفون المغلق لا يمنع احتساب الوقت"
        ),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /points-message
# =========================================================

@points_group.command(
    name="message",
    description="تغيير رسالة إشعار النقاط"
)
@admin_only()
@app_commands.describe(
    message="رسالة الإشعار"
)
async def points_message(
    interaction,
    message: str
):

    if len(message) > 2000:

        return await interaction.response.send_message(
            "❌ الرسالة طويلة جدًا.",
            ephemeral=True
        )

    db.execute(
        """
        UPDATE guild_settings
        SET notification_message = ?
        WHERE guild_id = ?
        """,
        (
            message,
            interaction.guild.id
        )
    )

    db.commit()

    await interaction.response.send_message(
        "✅ تم تغيير رسالة إشعار النقاط."
    )


# =========================================================
# /points-channel
# =========================================================

@points_group.command(
    name="channel",
    description="تحديد روم إشعارات النقاط"
)
@admin_only()
@app_commands.describe(
    channel="الروم - اتركه فارغًا لإلغاء الإشعارات"
)
async def points_channel(
    interaction,
    channel: discord.TextChannel = None
):

    db.execute(
        """
        UPDATE guild_settings
        SET notification_channel_id = ?
        WHERE guild_id = ?
        """,
        (
            channel.id
            if channel
            else None,
            interaction.guild.id
        )
    )

    db.commit()

    if channel:

        text = (
            f"✅ تم تحديد {channel.mention} "
            f"كروم إشعارات."
        )

    else:

        text = (
            "✅ تم إلغاء روم الإشعارات."
        )

    await interaction.response.send_message(
        text
    )



bot.tree.add_command(points_group)

# =========================================================
# SHOP — points rewards + real role shop
# =========================================================
SHOP_ITEMS = {
    "100": "🎁 مكافأة 100 نقطة",
    "500": "⭐ مكافأة 500 نقطة",
    "1000": "💎 مكافأة 1000 نقطة",
    "2500": "👑 مكافأة 2500 نقطة"
}

@bot.tree.command(name="shop", description="عرض متجر النقاط والرتب")
async def shop(interaction: discord.Interaction):
    rows = db.execute("SELECT id, role_id, price, description FROM role_shop WHERE guild_id=? AND enabled=1 ORDER BY price ASC", (interaction.guild.id,)).fetchall()
    lines = ["🛒 **متجر النقاط**", "", "**المكافآت:**", "🎁 `100` نقطة — مكافأة صغيرة", "⭐ `500` نقطة — مكافأة متوسطة", "💎 `1000` نقطة — مكافأة كبيرة", "👑 `2500` نقطة — مكافأة أسطورية"]
    if rows:
        lines += ["", "**🎭 رتب المتجر:**"]
        for r in rows:
            role = interaction.guild.get_role(r[1])
            if role:
                desc = f" — {r[3]}" if r[3] else ""
                lines.append(f"`{r[0]}` • {role.mention} — **{r[2]} نقطة**{desc}")
    else:
        lines += ["", "🎭 لا توجد رتب معروضة في المتجر حاليًا."]
    lines += ["", "استخدم `/buy` مع رقم العنصر للشراء."]
    await interaction.response.send_message("\n".join(lines))

@bot.tree.command(name="buy", description="شراء مكافأة أو رتبة بالنقاط")
@app_commands.describe(item="رقم العنصر من /shop")
async def buy(interaction: discord.Interaction, item: str):
    if item in SHOP_ITEMS:
        price = int(item); label = SHOP_ITEMS[item]
        data = get_user(interaction.guild.id, interaction.user.id)
        if data["points"] < price:
            return await interaction.response.send_message(f"❌ نقاطك غير كافية. رصيدك: **{data['points']}** • السعر: **{price}**", ephemeral=True)
        old=data["points"]; new=old-price
        update_user(interaction.guild.id, interaction.user.id, points=new)
        add_history(interaction.guild.id, interaction.user.id, "buy", -price, old, new, label)
        return await interaction.response.send_message(f"🛒 تم شراء **{label}**\n🪙 رصيدك الجديد: **{new} نقطة**")
    try: shop_id=int(item)
    except ValueError:
        return await interaction.response.send_message("❌ العنصر غير موجود. استخدم `/shop`.", ephemeral=True)
    row=db.execute("SELECT id, role_id, price, description FROM role_shop WHERE id=? AND guild_id=? AND enabled=1",(shop_id,interaction.guild.id)).fetchone()
    if not row:
        return await interaction.response.send_message("❌ عنصر المتجر غير موجود أو غير مفعل.", ephemeral=True)
    role=interaction.guild.get_role(row[1])
    if not role:
        return await interaction.response.send_message("❌ الرتبة المرتبطة بالعنصر لم تعد موجودة.", ephemeral=True)
    if role in interaction.user.roles:
        return await interaction.response.send_message("ℹ️ لديك هذه الرتبة بالفعل.", ephemeral=True)
    data=get_user(interaction.guild.id,interaction.user.id)
    if data["points"] < row[2]:
        return await interaction.response.send_message(f"❌ نقاطك غير كافية. رصيدك: **{data['points']}** • السعر: **{row[2]}**", ephemeral=True)
    try:
        await interaction.user.add_roles(role, reason="Role Shop purchase")
    except discord.Forbidden:
        return await interaction.response.send_message("❌ البوت لا يستطيع إعطاء هذه الرتبة. تأكد أن رتبته أعلى منها.", ephemeral=True)
    old=data["points"]; new=old-row[2]
    update_user(interaction.guild.id,interaction.user.id,points=new)
    add_history(interaction.guild.id,interaction.user.id,"role_shop_buy",-row[2],old,new,f"شراء رتبة {role.name}")
    await interaction.response.send_message(f"🎉 {interaction.user.mention} تم شراء {role.mention} بنجاح مقابل **{row[2]} نقطة**!\n🪙 رصيدك الجديد: **{new} نقطة**")

@bot.tree.command(name="shop-add", description="إضافة رتبة إلى متجر النقاط")
@admin_only()
@app_commands.describe(role="الرتبة", price="السعر بالنقاط", description="وصف اختياري")
async def shop_add(interaction: discord.Interaction, role: discord.Role, price: app_commands.Range[int,1,1000000000], description: str = ""):
    if role.is_default() or role.managed:
        return await interaction.response.send_message("❌ لا يمكن بيع هذه الرتبة.", ephemeral=True)
    if role >= interaction.guild.me.top_role:
        return await interaction.response.send_message("❌ يجب أن تكون رتبة البوت أعلى من الرتبة المعروضة للبيع.", ephemeral=True)
    db.execute("INSERT INTO role_shop(guild_id,role_id,price,description,enabled) VALUES(?,?,?,?,1) ON CONFLICT(guild_id,role_id) DO UPDATE SET price=excluded.price,description=excluded.description,enabled=1",(interaction.guild.id,role.id,int(price),description[:500])); db.commit()
    await interaction.response.send_message(f"✅ تمت إضافة {role.mention} إلى المتجر بسعر **{price} نقطة**.")

@bot.tree.command(name="shop-remove", description="إزالة رتبة من متجر النقاط")
@admin_only()
@app_commands.describe(role="الرتبة المراد إزالتها")
async def shop_remove(interaction: discord.Interaction, role: discord.Role):
    db.execute("DELETE FROM role_shop WHERE guild_id=? AND role_id=?",(interaction.guild.id,role.id)); db.commit()
    await interaction.response.send_message(f"✅ تمت إزالة {role.mention} من المتجر.")

# =========================================================
# /stats
# =========================================================


# =========================================================
# ERROR HANDLER
# =========================================================

@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = (
            "❌ هذا الأمر للإدارة فقط."
        )

    else:

        print(
            f"[COMMAND ERROR] {error}"
        )

        message = (
            "❌ حدث خطأ أثناء تنفيذ الأمر."
        )

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                message,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                message,
                ephemeral=True
            )

    except Exception:
        pass


# =========================================================
# READY
# =========================================================

async def points_on_ready():

    print("=" * 50)
    print(
        f"Logged in as: {bot.user}"
    )
    print(
        f"Bot ID: {bot.user.id}"
    )
    print(
        f"Guilds: {len(bot.guilds)}"
    )
    print("=" * 50)

    if not points_loop.is_running():

        points_loop.start()



# ===================== UNIFIED EVENT PIPELINE =====================
@bot.event
async def on_message(message):
    # Preserve all three original message pipelines without registering duplicate handlers.
    if not message.author.bot and message.guild:
        try: await welcome_on_message(message)
        except Exception as e: print(f"[WELCOME MESSAGE] {e}")
        try: await ticket_on_message(message)
        except Exception as e: print(f"[TICKET MESSAGE] {e}")
        try: await points_on_message(message)
        except Exception as e: print(f"[POINTS MESSAGE] {e}")

async def setup_hook():
    """Register slash commands early and make them available immediately in the main guild."""
    guild = discord.Object(id=GUILD_ID)

    try:
        # Copy all currently registered global commands to the configured guild
        # so they appear immediately instead of waiting for global propagation.
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Guild slash sync: {len(synced)} commands → {GUILD_ID}")
    except Exception as e:
        print(f"❌ Guild slash sync failed: {e}")

    try:
        synced_global = await bot.tree.sync()
        print(f"✅ Global slash sync: {len(synced_global)} commands")
    except Exception as e:
        print(f"❌ Global slash sync failed: {e}")


@bot.event
async def on_ready():
    await welcome_on_ready()
    try: await ticket_on_ready()
    except Exception as e: print(f"[TICKET READY] {e}")
    try: await points_on_ready()
    except Exception as e: print(f"[POINTS READY] {e}")

# The old /move, /lock and /unlock names remain owned by the original Welcome
# commands. Ticket actions keep their original helper implementations and can
# be invoked from ticket UI/buttons or the ticket-specific flows.

TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Token not found!")
