"""Upcoming CTF competitions from CTFtime.org."""

import asyncio
import collections
import datetime as dt
import html
import ipaddress
import re
import time
from typing import Literal
from urllib.parse import urlparse

import aiohttp
import discord
import yarl
from discord import app_commands
from discord.ext import commands, tasks

import ai_policy
import config
from utils import channel_link, find_channel

CTFTIME_API = "https://ctftime.org/api/v1/events/"
CACHE_SECONDS = 30 * 60          # CTFtime asks bots not to hammer the API
DIGEST_MARKER = "CTF digest"     # footer text that identifies the bot's scheduled posts
DIGEST_DAYS_AHEAD = 7            # a digest lists CTFs starting in the next week
FETCH_DAYS_AHEAD = 30            # how far ahead /ctf looks (few CTFs state an AI policy)
AI_NOTE = "AI policy is read from each CTF's CTFtime page or website. Always check the official rules."
SITE_CACHE_SECONDS = 12 * 3600   # re-read a CTF's website at most twice a day
SITE_MAX_BYTES = 500_000
SITE_PAGES = ("", "/rules")      # the homepage, then /rules


def page_text(raw_html: str) -> str:
    """Visible text of an HTML page (scripts and styles removed)."""
    raw_html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw_html)
    return " ".join(html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw_html)).split())


async def is_public_url(url: str) -> bool:
    """Only fetch normal public websites, never localhost or private network addresses
    (a CTFtime listing is written by strangers, so its link can't be trusted blindly)."""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, parts.port or 443)
    except OSError:
        return False
    return all(ipaddress.ip_address(info[4][0]).is_global for info in infos)

# /ctf ai:<choice> -> which policies to keep
AI_FILTERS = {
    "allowed": {ai_policy.ALLOWED},
    "no_ai": {ai_policy.BANNED},
    "separate": {ai_policy.SEPARATE},
    "stated": {ai_policy.ALLOWED, ai_policy.BANNED, ai_policy.SEPARATE, ai_policy.MIXED},
}
AI_FILTER_NAMES = {"allowed": "AI allowed", "no_ai": "no AI", "separate": "separate AI / human leaderboards",
                   "stated": "a stated AI policy"}


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
            value=(f"{ai_policy.label(e)}\n"
                   f"{e.get('format') or 'CTF'} · {where}{weight}\n"
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
        self.site_policy: dict[int, tuple[str, float]] = {}   # event id -> (policy, when checked)
        if config.CTF_POST_EVERY_DAYS:
            self.digest_loop.start()

    async def cog_unload(self):
        self.digest_loop.cancel()

    async def upcoming(self, days: int = FETCH_DAYS_AHEAD) -> list:
        """Fetch upcoming CTFs (cached for 30 minutes)."""
        if self.cache and time.time() - self.cache_time < CACHE_SECONDS:
            return self.cache
        now = int(time.time())
        params = {"limit": 100, "start": now, "finish": now + days * 86400}
        async with self.bot.http_session.get(CTFTIME_API, params=params,
                                             timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            events = await resp.json(content_type=None)
        events = sorted(events, key=lambda e: e["start"])
        await self.check_websites(events)
        self.cache = events
        self.cache_time = time.time()
        return self.cache

    # --- AI policy from CTF websites -------------------------------------------
    async def check_websites(self, events: list):
        """For CTFs whose CTFtime description doesn't state an AI policy, look on their website."""
        todo = [e for e in events if ai_policy.classify_text(
            f"{e.get('description') or ''} {e.get('restrictions') or ''}") == ai_policy.NOT_STATED]
        limit = asyncio.Semaphore(6)

        async def one(e):
            cached = self.site_policy.get(e["id"])
            if cached and time.time() - cached[1] < SITE_CACHE_SECONDS:
                policy = cached[0]
            else:
                async with limit:
                    policy = await self.website_policy((e.get("url") or "").strip())
                self.site_policy[e["id"]] = (policy, time.time())
            e["_ai_policy_website"] = policy

        await asyncio.gather(*(one(e) for e in todo))

    async def fetch_page(self, url: str) -> str | None:
        """Download a public web page's text. Redirects are followed by hand so that
        every hop is checked, and a public site can't bounce the bot to a private address."""
        for _ in range(4):
            if not await is_public_url(url):
                return None
            try:
                async with self.bot.http_session.get(url, allow_redirects=False,
                                                     timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status in (301, 302, 303, 307, 308) and resp.headers.get("Location"):
                        url = str(resp.url.join(yarl.URL(resp.headers["Location"])))
                        continue
                    if resp.status != 200 or "html" not in resp.headers.get("Content-Type", ""):
                        return None
                    raw = await resp.content.read(SITE_MAX_BYTES)
                    return page_text(raw.decode("utf-8", errors="ignore"))
            except (aiohttp.ClientError, TimeoutError, UnicodeError, ValueError):
                return None
        return None

    async def website_policy(self, url: str) -> str:
        for page in SITE_PAGES:
            text = await self.fetch_page(url.rstrip("/") + page if page else url)
            policy = ai_policy.classify_text(text) if text else ai_policy.NOT_STATED
            if policy != ai_policy.NOT_STATED:
                return policy
        return ai_policy.NOT_STATED

    # --- /ctf -----------------------------------------------------------------
    @commands.hybrid_command(description="Show upcoming CTFs, optionally filtered by their AI policy")
    @app_commands.describe(count="How many to show (1-10)", online_only="Hide on-site events",
                           ai="Only show CTFs with this AI policy")
    @app_commands.choices(ai=[
        app_commands.Choice(name="🤖 AI allowed", value="allowed"),
        app_commands.Choice(name="🚫 No AI", value="no_ai"),
        app_commands.Choice(name="⚖️ Separate AI / human leaderboards", value="separate"),
        app_commands.Choice(name="Any stated AI policy", value="stated"),
    ])
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def ctf(self, ctx: commands.Context, count: commands.Range[int, 1, 10] = 5,
                  online_only: bool = False,
                  ai: Literal["allowed", "no_ai", "separate", "stated"] | None = None):
        await ctx.defer()
        try:
            events = await self.upcoming()
        except (aiohttp.ClientError, TimeoutError):
            return await ctx.send("⚠️ Couldn't reach CTFtime right now. Try again in a few minutes.")
        if online_only:
            events = [e for e in events if not e.get("onsite")]
        title = "🚩 Upcoming CTFs"
        if ai:
            events = [e for e in events if ai_policy.classify(e) in AI_FILTERS[ai]]
            title = f"🚩 Upcoming CTFs with {AI_FILTER_NAMES[ai]}"
            if not events:
                return await ctx.send(
                    f"No CTFs in the next {FETCH_DAYS_AHEAD} days say they have {AI_FILTER_NAMES[ai]} "
                    "on CTFtime or their website. Most CTFs don't state an AI policy publicly, "
                    "so check each event's own rules.")
        embed = ctf_embed(events[:count], title, footer=f"Data from CTFtime.org · {AI_NOTE}")
        await ctx.send(embed=embed)

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
        if soon:
            counts = collections.Counter(ai_policy.classify(e) for e in soon)
            parts = [f"{ai_policy.LABELS[k]}: {counts[k]}" for k in
                     (ai_policy.ALLOWED, ai_policy.BANNED, ai_policy.SEPARATE, ai_policy.MIXED, ai_policy.NOT_STATED)
                     if counts[k]]
            embed.description = ("**AI rules:** " + " · ".join(parts) +
                                 f"\n*{AI_NOTE} Use `/ctf ai:` to filter.*")
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
