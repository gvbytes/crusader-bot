"""Everyday commands: help, info, avatars and reminders."""

import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils import channel_link, is_staff, load_json, parse_duration, save_json

REMINDERS_FILE = "reminders.json"   # [ {user, channel, text, due, created}, ... ]
MAX_REMINDER = 30 * 86400           # 30 days
MAX_REMINDERS_PER_USER = 10

# Order and titles for the /help sections
HELP_SECTIONS = {
    "Utility": "🧰 Utility",
    "Community": "🤝 Community",
    "CTF": "🚩 CTF",
    "AI News": "🧠 AI news",
    "Moderation": "🛡️ Staff only",
}


class Utility(commands.Cog):
    """General commands everyone can use."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminders = load_json(REMINDERS_FILE, [])
        self.check_reminders.start()

    async def cog_unload(self):
        self.check_reminders.cancel()

    # --- /help ----------------------------------------------------------------
    @commands.hybrid_command(description="Show everything CrusaderBot can do")
    async def help(self, ctx: commands.Context):
        # Built from the commands themselves, so it never goes out of date.
        embed = discord.Embed(title="⚔️ CrusaderBot commands",
                              description=f"Use `/command` or `{config.PREFIX}command`.",
                              color=config.COLOR_MAIN)
        staff = is_staff(ctx.author)
        for cog_name, title in HELP_SECTIONS.items():
            cog = self.bot.get_cog(cog_name)
            if not cog or (cog_name == "Moderation" and not staff):
                continue
            lines = [f"`/{c.name}` {c.description}" for c in cog.get_commands() if not c.hidden]
            if lines:
                embed.add_field(name=title, value="\n".join(lines), inline=False)
        embed.add_field(name="🚩 Report a message",
                        value="Right-click a message → **Apps** → **Report to staff**", inline=False)
        if ctx.guild:
            embed.add_field(name="🎭 Roles", value=f"Pick your roles in {channel_link(ctx.guild, 'roles')}",
                            inline=False)
        await ctx.send(embed=embed, ephemeral=True)

    # --- /ping ----------------------------------------------------------------
    @commands.hybrid_command(description="Check if the bot is responsive")
    async def ping(self, ctx: commands.Context):
        await ctx.send(f"⚡ Pong! `{round(self.bot.latency * 1000)}ms`")

    # --- /rules ---------------------------------------------------------------
    @commands.hybrid_command(description="Quick summary of the server rules")
    @commands.guild_only()
    async def rules(self, ctx: commands.Context):
        embed = discord.Embed(
            title="📜 Server rules (summary)",
            description=("1. Respect everyone\n"
                         "2. Keep topics in the right channels\n"
                         "3. Security research is for learning only: no attacks on real targets\n"
                         "4. No spam or unsolicited DMs\n\n"
                         f"Full rules: {channel_link(ctx.guild, 'rules')}"),
            color=config.COLOR_WARN,
        )
        await ctx.send(embed=embed)

    # --- /serverinfo ----------------------------------------------------------
    @commands.hybrid_command(description="Stats about this server")
    @commands.guild_only()
    async def serverinfo(self, ctx: commands.Context):
        g = ctx.guild
        humans = sum(not m.bot for m in g.members)
        embed = discord.Embed(title=g.name, color=config.COLOR_MAIN)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="Members", value=f"{humans} people, {g.member_count - humans} bots")
        embed.add_field(name="Channels", value=f"{len(g.text_channels)} text, {len(g.voice_channels)} voice")
        embed.add_field(name="Roles", value=str(len(g.roles) - 1))
        embed.add_field(name="Owner", value=g.owner.mention if g.owner else "Unknown")
        embed.add_field(name="Created", value=f"<t:{int(g.created_at.timestamp())}:D>")
        embed.add_field(name="Boosts", value=f"Level {g.premium_tier} ({g.premium_subscription_count})")
        await ctx.send(embed=embed)

    # --- /userinfo ------------------------------------------------------------
    @commands.hybrid_command(description="Info about a member")
    @app_commands.describe(member="Who to look up (leave empty for yourself)")
    @commands.guild_only()
    async def userinfo(self, ctx: commands.Context, member: discord.Member | None = None):
        m = member or ctx.author
        roles = [r.mention for r in reversed(m.roles) if r != ctx.guild.default_role]
        embed = discord.Embed(title=m.display_name, description=m.mention, color=m.color or config.COLOR_MAIN)
        embed.set_thumbnail(url=m.display_avatar.url)
        embed.add_field(name="Username", value=str(m))
        embed.add_field(name="Joined server", value=f"<t:{int(m.joined_at.timestamp())}:R>" if m.joined_at else "?")
        embed.add_field(name="Account created", value=f"<t:{int(m.created_at.timestamp())}:R>")
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:15]) or "None", inline=False)
        await ctx.send(embed=embed)

    # --- /avatar --------------------------------------------------------------
    @commands.hybrid_command(description="Show someone's avatar in full size")
    @app_commands.describe(member="Whose avatar (leave empty for yours)")
    async def avatar(self, ctx: commands.Context, member: discord.Member | None = None):
        m = member or ctx.author
        embed = discord.Embed(title=f"{m.display_name}'s avatar", color=config.COLOR_MAIN)
        embed.set_image(url=m.display_avatar.with_size(1024).url)
        await ctx.send(embed=embed)

    # --- /remind --------------------------------------------------------------
    @commands.hybrid_command(description="Set a reminder, e.g. /remind 2h submit the assignment")
    @app_commands.describe(when="How long from now, e.g. 10m, 2h, 1d12h", text="What to remind you about")
    async def remind(self, ctx: commands.Context, when: str, *, text: str):
        seconds = parse_duration(when)
        if not seconds or seconds > MAX_REMINDER:
            return await ctx.send("⚠️ Use a time like `10m`, `2h` or `1d12h` (max 30 days).", ephemeral=True)
        mine = [r for r in self.reminders if r["user"] == ctx.author.id]
        if len(mine) >= MAX_REMINDERS_PER_USER:
            return await ctx.send(f"⚠️ You already have {MAX_REMINDERS_PER_USER} reminders. "
                                  "Wait for some to finish first.", ephemeral=True)
        due = int(time.time()) + seconds
        self.reminders.append({"user": ctx.author.id, "channel": ctx.channel.id,
                               "text": text[:500], "due": due, "created": int(time.time())})
        save_json(REMINDERS_FILE, self.reminders)
        await ctx.send(f"⏰ Got it. I'll remind you <t:{due}:R>.", ephemeral=True)

    @commands.hybrid_command(description="List your upcoming reminders")
    async def reminders(self, ctx: commands.Context):
        mine = sorted((r for r in self.reminders if r["user"] == ctx.author.id), key=lambda r: r["due"])
        if not mine:
            return await ctx.send("You have no reminders.", ephemeral=True)
        lines = [f"• <t:{r['due']}:R>: {r['text']}" for r in mine]
        await ctx.send("⏰ **Your reminders**\n" + "\n".join(lines), ephemeral=True)

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        now = time.time()
        due = [r for r in self.reminders if r["due"] <= now]
        if not due:
            return
        self.reminders = [r for r in self.reminders if r["due"] > now]
        save_json(REMINDERS_FILE, self.reminders)
        for r in due:
            text = f"⏰ <@{r['user']}> reminder (set <t:{r['created']}:R>): {r['text']}"
            # DM first so reminders stay private; fall back to the original channel.
            try:
                user = await self.bot.fetch_user(r["user"])
                await user.send(text)
                continue
            except discord.HTTPException:
                pass
            channel = self.bot.get_channel(r["channel"])
            if channel:
                try:
                    await channel.send(text, allowed_mentions=discord.AllowedMentions(users=True))
                except discord.HTTPException:
                    pass

    @check_reminders.before_loop
    async def before_reminders(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
