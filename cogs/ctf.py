"""Upcoming CTF competitions from CTFtime.org."""

import datetime as dt
import time

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils import channel_link, find_channel

CTFTIME_API = "https://ctftime.org/api/v1/events/"
CACHE_SECONDS = 30 * 60          # CTFtime asks bots not to hammer the API
DIGEST_MARKER = "CTF digest"     # footer text that identifies the bot's scheduled posts
DIGEST_DAYS_AHEAD = 7            # a digest lists CTFs starting in the next week


def to_unix(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso).timestamp())


def ctf_embed(events: list, title: str, footer: str = "Data from CTFtime.org") -> discord.Embed:
    embed = discord.Embed(title=title, url="https://ctftime.org/event/list/upcoming",
                          color=config.COLOR_BAD)
    if not events:
        embed.description = "No CTFs found in this period. Check back soon!"
    for e in events:
        start, finish = to_unix(e["start"]), to_unix(e["finish"])
        where = "🌐 Online" if not e.get("onsite") else f"📍 {e.get('location') or 'On-site'}"
        weight = f" · weight {e['weight']:.1f}" if e.get("weight") else ""
        embed.add_field(
            name=f"{e['title']}"[:256],
            value=(f"{e.get('format') or 'CTF'} · {where}{weight}\n"
                   f"🕒 <t:{start}:f> → <t:{finish}:f> (starts <t:{start}:R>)\n"
                   f"[CTFtime]({e['ctftime_url']})" + (f" · [Website]({e['url']})" if e.get("url") else "")),
            inline=False,
        )
    embed.set_footer(text=f"{footer} · times shown in your timezone")
    return embed


class CTF(commands.Cog):
    """Upcoming CTF competitions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache: list = []
        self.cache_time = 0.0
        self.last_digest: dict[int, int] = {}   # guild id -> unix time of the last digest
        if config.CTF_POST_EVERY_DAYS:
            self.digest_loop.start()

    async def cog_unload(self):
        self.digest_loop.cancel()

    async def upcoming(self, days: int = 14) -> list:
        """Fetch upcoming CTFs (cached for 30 minutes)."""
        if self.cache and time.time() - self.cache_time < CACHE_SECONDS:
            return self.cache
        now = int(time.time())
        params = {"limit": 50, "start": now, "finish": now + days * 86400}
        async with self.bot.http_session.get(CTFTIME_API, params=params,
                                             timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            events = await resp.json(content_type=None)
        self.cache = sorted(events, key=lambda e: e["start"])
        self.cache_time = time.time()
        return self.cache

    # --- /ctf -----------------------------------------------------------------
    @commands.hybrid_command(description="Show upcoming CTF competitions from CTFtime")
    @app_commands.describe(count="How many to show (1-10)", online_only="Hide on-site events")
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def ctf(self, ctx: commands.Context, count: commands.Range[int, 1, 10] = 5,
                  online_only: bool = False):
        await ctx.defer()
        try:
            events = await self.upcoming()
        except (aiohttp.ClientError, TimeoutError):
            return await ctx.send("⚠️ Couldn't reach CTFtime right now. Try again in a few minutes.")
        if online_only:
            events = [e for e in events if not e.get("onsite")]
        await ctx.send(embed=ctf_embed(events[:count], "🚩 Upcoming CTFs"))

    # --- Scheduled digest -----------------------------------------------------
    async def post_digest(self, channel: discord.TextChannel) -> bool:
        """Post the CTF digest in a channel. Returns True if it was sent."""
        try:
            events = await self.upcoming()
        except (aiohttp.ClientError, TimeoutError) as e:
            print(f"  [!] CTF digest: CTFtime unreachable ({e!r})", flush=True)
            return False
        cutoff = time.time() + DIGEST_DAYS_AHEAD * 86400
        soon = [e for e in events if to_unix(e["start"]) < cutoff][:10]
        every = config.CTF_POST_EVERY_DAYS
        embed = ctf_embed(soon, "🚩 CTFs coming up this week",
                          footer=f"{DIGEST_MARKER} · posted every {every} days · data from CTFtime.org")
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as e:
            print(f"  [!] CTF digest: can't post in #{channel.name} ({e})", flush=True)
            return False
        self.last_digest[channel.guild.id] = int(time.time())
        print(f"  [+] CTF digest posted in #{channel.name} ({len(soon)} CTFs)", flush=True)
        return True

    async def last_digest_time(self, channel: discord.TextChannel) -> int | None:
        """When the bot last posted a digest in this channel, read from the channel itself,
        so the schedule survives restarts without saving anything to disk."""
        since = discord.utils.utcnow() - dt.timedelta(days=config.CTF_POST_EVERY_DAYS)
        async for msg in channel.history(after=since, oldest_first=False, limit=500):
            if msg.author == self.bot.user and any(
                    DIGEST_MARKER in (e.footer.text or "") for e in msg.embeds):
                return int(msg.created_at.timestamp())
        return None

    @tasks.loop(hours=1)
    async def digest_loop(self):
        period = config.CTF_POST_EVERY_DAYS * 86400
        for guild in self.bot.guilds:
            channel = find_channel(guild, "ctf")
            if not channel:
                continue
            last = self.last_digest.get(guild.id)
            if last is None or time.time() - last >= period:
                try:
                    last = await self.last_digest_time(channel)
                except discord.HTTPException as e:
                    print(f"  [!] CTF digest: can't read #{channel.name} ({e})", flush=True)
                    continue
                if last:
                    self.last_digest[guild.id] = last
            if last is None or time.time() - last >= period:
                await self.post_digest(channel)

    @digest_loop.before_loop
    async def before_digest(self):
        await self.bot.wait_until_ready()

    # --- /ctfpost (staff) -----------------------------------------------------
    @commands.hybrid_command(description="Staff: post the CTF digest in the CTF channel now")
    @app_commands.default_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def ctfpost(self, ctx: commands.Context):
        channel = find_channel(ctx.guild, "ctf")
        if not channel:
            return await ctx.send(f"⚠️ I can't find {channel_link(ctx.guild, 'ctf')}. "
                                  "Create it or change `CHANNELS['ctf']` in config.py.", ephemeral=True)
        await ctx.defer(ephemeral=True)
        if await self.post_digest(channel):
            await ctx.send(f"✅ Posted in {channel.mention}. The next automatic post is in "
                           f"{config.CTF_POST_EVERY_DAYS} days.", ephemeral=True)
        else:
            await ctx.send(f"⚠️ Couldn't post in {channel.mention}. Check that I can send messages "
                           "and embed links there, and that CTFtime is up.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CTF(bot))
