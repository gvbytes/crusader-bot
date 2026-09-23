"""Upcoming CTF competitions from CTFtime.org."""

import datetime as dt
import time

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils import find_channel

CTFTIME_API = "https://ctftime.org/api/v1/events/"
CACHE_SECONDS = 30 * 60          # CTFtime asks bots not to hammer the API
MONDAY_9AM_IST = dt.time(hour=3, minute=30, tzinfo=dt.timezone.utc)


def to_unix(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso).timestamp())


def ctf_embed(events: list, title: str) -> discord.Embed:
    embed = discord.Embed(title=title, url="https://ctftime.org/event/list/upcoming",
                          color=config.COLOR_BAD)
    if not events:
        embed.description = "No CTFs found in the next two weeks."
        return embed
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
    embed.set_footer(text="Data from CTFtime.org · times shown in your timezone")
    return embed


class CTF(commands.Cog):
    """Upcoming CTF competitions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache: list = []
        self.cache_time = 0.0
        if config.CTF_WEEKLY_POST:
            self.weekly_post.start()

    async def cog_unload(self):
        self.weekly_post.cancel()

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

    @tasks.loop(time=MONDAY_9AM_IST)
    async def weekly_post(self):
        if dt.datetime.now(dt.timezone.utc).weekday() != 0:   # only on Mondays
            return
        try:
            events = await self.upcoming(days=7)
        except (aiohttp.ClientError, TimeoutError):
            return
        events = [e for e in events if to_unix(e["start"]) < time.time() + 7 * 86400][:10]
        for guild in self.bot.guilds:
            channel = find_channel(guild, "ctf")
            if channel:
                try:
                    await channel.send(embed=ctf_embed(events, "🚩 CTFs this week"))
                except discord.HTTPException:
                    pass

    @weekly_post.before_loop
    async def before_weekly(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(CTF(bot))
