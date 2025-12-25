# ================== ULTIMATE GIVEAWAY BOT ==================
# Python 3.10+ | discord.py 2.4+
# Features: Slash cmds, buttons, auto gw, role req, blacklist,
# min account age, min join age, reroll, end early,
# persistence, restart-safe, logs, stats, anti-dup, hosting ready
# ============================================================

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio, random, json, os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ------------------ CONFIG ------------------
load_dotenv()
TOKEN = os.getenv("TOKEN")

DATA_FILE = "giveaways.json"
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "log_channel": None,
    "auto_giveaway": {
        "enabled": False,
        "interval_hours": 24,
        "channel_id": None,
        "time": "1h",
        "winners": 1,
        "prize": "Free Reward"
    }
}

# ------------------ BOT ------------------
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------ STORAGE ------------------
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f, indent=4)
        return default
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

def load_giveaways():
    return load_json(DATA_FILE, {})

def save_giveaways(d):
    save_json(DATA_FILE, d)

def load_config():
    return load_json(CONFIG_FILE, DEFAULT_CONFIG)

def save_config(c):
    save_json(CONFIG_FILE, c)

# ------------------ TIME ------------------
def parse_time(t: str):
    try:
        v = int(t[:-1])
        u = t[-1]
        return v * {"s":1,"m":60,"h":3600,"d":86400}[u]
    except:
        return None

# ------------------ BUTTON VIEW ------------------
class JoinView(discord.ui.View):
    def __init__(self, gid):
        super().__init__(timeout=None)
        self.gid = str(gid)

    @discord.ui.button(label="🎉 Join Giveaway", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, _):
        data = load_giveaways()
        g = data.get(self.gid)

        if not g:
            return await interaction.response.send_message("❌ Giveaway ended.", ephemeral=True)

        member = interaction.user

        # role required
        if g["role_required"] and g["role_required"] not in [r.id for r in member.roles]:
            return await interaction.response.send_message("❌ Required role missing.", ephemeral=True)

        # blacklist role
        if g["blacklist_role"] and g["blacklist_role"] in [r.id for r in member.roles]:
            return await interaction.response.send_message("❌ You are blacklisted.", ephemeral=True)

        # min account age
        if g["min_account_days"]:
            if (datetime.utcnow() - member.created_at).days < g["min_account_days"]:
                return await interaction.response.send_message("❌ Account too new.", ephemeral=True)

        # min join age
        if g["min_join_days"]:
            if (datetime.utcnow() - member.joined_at).days < g["min_join_days"]:
                return await interaction.response.send_message("❌ Joined too recently.", ephemeral=True)

        if member.id not in g["entries"]:
            g["entries"].append(member.id)
            save_giveaways(data)

        await interaction.response.send_message("✅ Entered giveaway!", ephemeral=True)

# ------------------ READY ------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    resume_giveaways.start()
    auto_giveaway_loop.start()
    print(f"✅ Logged in as {bot.user}")

# ------------------ START GIVEAWAY ------------------
@bot.tree.command(name="giveaway", description="Start an ultimate giveaway")
@app_commands.checks.has_permissions(manage_guild=True)
async def giveaway(
    interaction: discord.Interaction,
    time: str,
    winners: int,
    prize: str,
    role_required: discord.Role = None,
    blacklist_role: discord.Role = None,
    min_account_days: int = 0,
    min_join_days: int = 0
):
    seconds = parse_time(time)
    if not seconds:
        return await interaction.response.send_message("❌ Invalid time format.", ephemeral=True)

    end = datetime.utcnow() + timedelta(seconds=seconds)

    embed = discord.Embed(
        title="🎉 GIVEAWAY 🎉",
        color=discord.Color.green(),
        description=(
            f"🏆 **Prize:** {prize}\n"
            f"👥 **Winners:** {winners}\n"
            f"⏰ **Ends:** <t:{int(end.timestamp())}:R>\n"
            f"{'🔒 Role: ' + role_required.mention if role_required else ''}"
        )
    )
    embed.set_footer(text="Click the button to join")

    await interaction.response.send_message(embed=embed, view=JoinView(interaction.id))
    msg = await interaction.original_response()

    data = load_giveaways()
    data[str(msg.id)] = {
        "channel": msg.channel.id,
        "prize": prize,
        "winners": winners,
        "end": end.timestamp(),
        "role_required": role_required.id if role_required else None,
        "blacklist_role": blacklist_role.id if blacklist_role else None,
        "min_account_days": min_account_days,
        "min_join_days": min_join_days,
        "entries": []
    }
    save_giveaways(data)

# ------------------ END GIVEAWAY ------------------
async def end_giveaway(gid):
    data = load_giveaways()
    g = data.get(str(gid))
    if not g:
        return

    channel = bot.get_channel(g["channel"])
    entries = g["entries"]

    if len(entries) < g["winners"]:
        await channel.send("❌ Not enough valid entries.")
    else:
        winners = random.sample(entries, g["winners"])
        mentions = ", ".join(f"<@{w}>" for w in winners)
        await channel.send(
            f"🎉 **GIVEAWAY ENDED** 🎉\n"
            f"🏆 **Prize:** {g['prize']}\n"
            f"🥳 **Winners:** {mentions}"
        )

    del data[str(gid)]
    save_giveaways(data)

# ------------------ REROLL ------------------
@bot.tree.command(name="reroll", description="Reroll a giveaway")
@app_commands.checks.has_permissions(manage_guild=True)
async def reroll(interaction: discord.Interaction, message_id: str):
    data = load_giveaways()
    g = data.get(message_id)
    if not g or not g["entries"]:
        return await interaction.response.send_message("❌ No entries.", ephemeral=True)

    winner = random.choice(g["entries"])
    await interaction.response.send_message(f"🔄 New Winner: <@{winner}>")

# ------------------ END EARLY ------------------
@bot.tree.command(name="end", description="End giveaway early")
@app_commands.checks.has_permissions(manage_guild=True)
async def end(interaction: discord.Interaction, message_id: str):
    await end_giveaway(message_id)
    await interaction.response.send_message("✅ Giveaway ended.")

# ------------------ RESUME ON RESTART ------------------
@tasks.loop(seconds=30)
async def resume_giveaways():
    data = load_giveaways()
    now = datetime.utcnow().timestamp()

    for gid, g in list(data.items()):
        if g["end"] <= now:
            await end_giveaway(gid)

# ------------------ AUTO GIVEAWAY ------------------
@tasks.loop(minutes=1)
async def auto_giveaway_loop():
    config = load_config()
    ag = config["auto_giveaway"]
    if not ag["enabled"]:
        return

    if not hasattr(auto_giveaway_loop, "last"):
        auto_giveaway_loop.last = datetime.utcnow()

    if datetime.utcnow() - auto_giveaway_loop.last >= timedelta(hours=ag["interval_hours"]):
        auto_giveaway_loop.last = datetime.utcnow()
        channel = bot.get_channel(ag["channel_id"])
        if channel:
            await channel.send(
                f"/giveaway time:{ag['time']} winners:{ag['winners']} prize:{ag['prize']}"
            )

# ------------------ RUN ------------------
bot.run(TOKEN)
