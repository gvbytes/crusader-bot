"""Staff-only commands. Each one checks Discord permissions and logs to #mod-log."""

import time
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import can_moderate, load_json, mod_log, parse_duration, save_json

WARNINGS_FILE = "warnings.json"   # {"guild_id": {"member_id": [ {reason, by, at}, ... ]}}
MAX_TIMEOUT = 28 * 86400          # Discord's limit: 28 days


class Moderation(commands.Cog):
    """Staff tools. Only visible to members with the right permissions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warnings = load_json(WARNINGS_FILE, {})

    def member_warnings(self, member: discord.Member) -> list:
        return self.warnings.setdefault(str(member.guild.id), {}).setdefault(str(member.id), [])

    # --- /warn ---------------------------------------------------------------
    @commands.hybrid_command(description="Warn a member and DM them the reason")
    @app_commands.describe(member="Who to warn", reason="Why they are being warned")
    @app_commands.default_permissions(moderate_members=True)
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        if problem := can_moderate(ctx.author, member):
            return await ctx.send(f"⚠️ {problem}", ephemeral=True)

        warns = self.member_warnings(member)
        warns.append({"reason": reason, "by": ctx.author.id, "at": int(time.time())})
        save_json(WARNINGS_FILE, self.warnings)

        try:
            await member.send(f"⚠️ You were warned in **{ctx.guild.name}**: {reason}")
            dm_note = ""
        except discord.HTTPException:
            dm_note = " (couldn't DM them)"

        await ctx.send(f"⚠️ {member.mention} has been warned. They now have **{len(warns)}** warning(s){dm_note}.")
        await mod_log(ctx.guild, "⚠️ Member warned",
                      f"**Member:** {member.mention}\n**By:** {ctx.author.mention}\n"
                      f"**Reason:** {reason}\n**Total warnings:** {len(warns)}")

    # --- /warnings -----------------------------------------------------------
    @commands.hybrid_command(description="Show a member's warnings")
    @app_commands.describe(member="Whose warnings to show")
    @app_commands.default_permissions(moderate_members=True)
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, member: discord.Member):
        warns = self.member_warnings(member)
        if not warns:
            return await ctx.send(f"✅ {member.display_name} has no warnings.", ephemeral=True)
        lines = [f"**{i}.** <t:{w['at']}:d> by <@{w['by']}>: {w['reason']}"
                 for i, w in enumerate(warns[-10:], start=max(1, len(warns) - 9))]
        embed = discord.Embed(title=f"Warnings for {member.display_name} ({len(warns)})",
                              description="\n".join(lines), color=config.COLOR_WARN)
        await ctx.send(embed=embed, ephemeral=True)

    # --- /clearwarnings ------------------------------------------------------
    @commands.hybrid_command(description="Remove all of a member's warnings")
    @app_commands.describe(member="Whose warnings to clear")
    @app_commands.default_permissions(moderate_members=True)
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def clearwarnings(self, ctx: commands.Context, member: discord.Member):
        count = len(self.member_warnings(member))
        self.warnings[str(ctx.guild.id)].pop(str(member.id), None)
        save_json(WARNINGS_FILE, self.warnings)
        await ctx.send(f"🧹 Cleared {count} warning(s) for {member.mention}.")
        await mod_log(ctx.guild, "🧹 Warnings cleared",
                      f"**Member:** {member.mention}\n**By:** {ctx.author.mention}\n**Removed:** {count}",
                      color=config.COLOR_OK)

    # --- /timeout ------------------------------------------------------------
    @commands.hybrid_command(description="Time out a member (they can't talk for a while)")
    @app_commands.describe(member="Who to time out", duration="How long, e.g. 10m, 2h, 1d",
                           reason="Why (optional)")
    @app_commands.default_permissions(moderate_members=True)
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def timeout(self, ctx: commands.Context, member: discord.Member, duration: str, *,
                      reason: str = "No reason given"):
        if problem := can_moderate(ctx.author, member):
            return await ctx.send(f"⚠️ {problem}", ephemeral=True)
        seconds = parse_duration(duration)
        if not seconds or seconds > MAX_TIMEOUT:
            return await ctx.send("⚠️ Use a duration like `10m`, `2h` or `1d` (max 28 days).", ephemeral=True)

        await member.timeout(timedelta(seconds=seconds), reason=f"{ctx.author}: {reason}")
        until = int(time.time()) + seconds
        await ctx.send(f"🔇 {member.mention} is timed out until <t:{until}:f>.")
        await mod_log(ctx.guild, "🔇 Member timed out",
                      f"**Member:** {member.mention}\n**By:** {ctx.author.mention}\n"
                      f"**Duration:** {duration}\n**Reason:** {reason}")

    # --- /untimeout ----------------------------------------------------------
    @commands.hybrid_command(description="Remove a member's timeout")
    @app_commands.describe(member="Who to un-mute")
    @app_commands.default_permissions(moderate_members=True)
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def untimeout(self, ctx: commands.Context, member: discord.Member):
        if not member.is_timed_out():
            return await ctx.send(f"{member.display_name} isn't timed out.", ephemeral=True)
        await member.timeout(None, reason=f"Timeout removed by {ctx.author}")
        await ctx.send(f"🔊 {member.mention} can talk again.")
        await mod_log(ctx.guild, "🔊 Timeout removed",
                      f"**Member:** {member.mention}\n**By:** {ctx.author.mention}", color=config.COLOR_OK)

    # --- /purge --------------------------------------------------------------
    @commands.hybrid_command(description="Bulk-delete recent messages in this channel")
    @app_commands.describe(amount="How many messages to check (1-100)",
                           member="Only delete messages from this member (optional)")
    @app_commands.default_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    @commands.guild_only()
    async def purge(self, ctx: commands.Context, amount: commands.Range[int, 1, 100],
                    member: discord.Member | None = None):
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
        else:
            await ctx.message.delete()  # don't count the "!purge" message itself

        check = (lambda m: m.author == member) if member else (lambda m: True)
        # Discord can only bulk-delete messages newer than 14 days.
        deleted = await ctx.channel.purge(limit=amount, check=check, bulk=True,
                                          reason=f"/purge by {ctx.author}")
        who = f" from {member.mention}" if member else ""
        await ctx.send(f"🧹 Deleted {len(deleted)} message(s){who}.", ephemeral=True,
                       delete_after=None if ctx.interaction else 5)
        await mod_log(ctx.guild, "🧹 Messages purged",
                      f"**Channel:** {ctx.channel.mention}\n**By:** {ctx.author.mention}\n"
                      f"**Deleted:** {len(deleted)}{who}")

    # --- /slowmode -----------------------------------------------------------
    @commands.hybrid_command(description="Set slowmode for this channel (0 turns it off)")
    @app_commands.describe(seconds="Seconds between messages per member (0-21600)")
    @app_commands.default_permissions(manage_channels=True)
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def slowmode(self, ctx: commands.Context, seconds: commands.Range[int, 0, 21600]):
        await ctx.channel.edit(slowmode_delay=seconds, reason=f"Slowmode set by {ctx.author}")
        text = "turned off" if seconds == 0 else f"set to {seconds}s"
        await ctx.send(f"🐢 Slowmode {text} in {ctx.channel.mention}.")
        await mod_log(ctx.guild, "🐢 Slowmode changed",
                      f"**Channel:** {ctx.channel.mention}\n**By:** {ctx.author.mention}\n**Now:** {text}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
