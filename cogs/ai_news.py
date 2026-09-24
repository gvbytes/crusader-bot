"""Daily AI news digest from official AI lab blogs and established tech outlets."""

import asyncio
import datetime as dt
import email.utils
import html
import re
import time
import xml.etree.ElementTree as ET

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils import channel_link, find_channel, read_limited

DIGEST_MARKER = "AI digest"       # footer text that identifies the bot's daily posts
CACHE_SECONDS = 30 * 60
FEED_MAX_BYTES = 3_000_000
MAX_ITEMS = 10
MAX_PER_SOURCE = 2
MAX_LAB_ITEMS = 6                 # leave room for at least 4 news stories
MAX_PER_NAME = 2                  # at most 2 stories about the same company/product on busy days
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"
KIND_EMOJI = {"lab": "🔬", "news": "📰"}
# For sources marked "ai_only" (company blogs that also post about hiring, gaming...),
# keep only posts whose title is about AI.
AI_TITLE = re.compile(r"\b(ai|a\.i\.|llms?|gpt[\w.-]*|gemini|claude|models?|agents?|agentic|robot\w*|"
                      r"inference|training|generative|machine learning|neural|deep learning|reasoning|"
                      r"transformers?|diffusion|chatbots?|copilot|omniverse|cuda|datasets?)\b", re.I)
# Words that don't identify a story, even when capitalised in a headline
COMMON = {"the", "how", "why", "what", "new", "this", "with", "for", "and", "from", "its", "you", "your",
          "now", "after", "into", "about", "more", "will", "can", "our", "all", "here", "just", "says",
          "that", "are", "has", "have", "who", "when", "top", "best", "ai", "update", "updates"}


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def post_time(now: dt.datetime) -> dt.datetime:
    """The scheduled time (e.g. 09:00 IST) on the IST calendar day of `now`, in UTC."""
    local = now.astimezone(IST)
    return local.replace(hour=config.AI_NEWS_HOUR_IST, minute=0, second=0, microsecond=0).astimezone(dt.timezone.utc)


# --- Reading RSS / Atom feeds ------------------------------------------------------
def parse_date(text: str | None) -> float | None:
    if not text:
        return None
    text = text.strip()
    try:
        return email.utils.parsedate_to_datetime(text).timestamp()      # RSS: "Tue, 23 Sep 2026 10:00:00 GMT"
    except (TypeError, ValueError):
        pass
    try:
        d = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))     # Atom: "2026-09-23T10:00:00Z"
        return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).timestamp()
    except ValueError:
        return None


def clean(text: str | None, limit: int = 180) -> str:
    """Plain text from an HTML snippet, cut at a word boundary."""
    text = " ".join(html.unescape(re.sub(r"(?s)<[^>]+>", " ", text or "")).split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def parse_feed(raw: bytes, source: dict) -> list[dict]:
    """Turn an RSS or Atom feed into a list of {title, link, published, summary, source, kind}."""
    root = ET.fromstring(raw)
    items = []
    for node in root.iter():
        if node.tag == "item":                       # RSS
            link = (node.findtext("link") or "").strip()
            date = node.findtext("pubDate") or node.findtext(f"{DC}date")
            summary = node.findtext("description")
        elif node.tag == f"{ATOM}entry":             # Atom
            link_el = next((l for l in node.findall(f"{ATOM}link") if l.get("rel", "alternate") == "alternate"),
                           node.find(f"{ATOM}link"))
            link = (link_el.get("href") if link_el is not None else "") or ""
            date = node.findtext(f"{ATOM}published") or node.findtext(f"{ATOM}updated")
            summary = node.findtext(f"{ATOM}summary") or node.findtext(f"{ATOM}content")
        else:
            continue
        title = clean(node.findtext("title") or node.findtext(f"{ATOM}title"), 250)
        published = parse_date(date)
        if source.get("ai_only") and not AI_TITLE.search(title):
            continue
        if title and link.startswith("http") and published:
            items.append({"title": title, "link": link, "published": published,
                          "summary": clean(summary), "source": source["name"], "kind": source["kind"]})
    return items


# --- Choosing what to post -----------------------------------------------------------
def words(title: str) -> set[str]:
    """Meaningful words in a headline (no filler like 'the', 'its', 'new')."""
    return {w for w in re.findall(r"[a-z0-9]+", title.lower()) if len(w) > 2 and w not in COMMON}


def names(title: str) -> set[str]:
    """Distinctive words in a headline: names and versions like 'Meta', 'Muse', 'GPT-6'."""
    return {w.lower() for w in re.findall(r"[A-Za-z0-9][\w.\-]*", title)
            if (w[0].isupper() or any(ch.isdigit() for ch in w)) and len(w) >= 3 and w.lower() not in COMMON}


def same_story(a: str, b: str) -> bool:
    """Two outlets covering the same news share most title words, or at least two names
    ('Meta made a wearable for its Muse AI agent' / 'Meta is making a standalone Muse AI gadget')."""
    wa, wb = words(a), words(b)
    shared = len(wa & wb)
    # "Meta introduces camera-free AI glasses" / "Meta ditches the camera on its newest smart glasses":
    # 3 of the shorter headline's 5 meaningful words are shared.
    if shared >= 3 and shared / min(len(wa), len(wb)) >= 0.6:
        return True
    return len(names(a) & names(b)) >= 2


def pick(items: list[dict], since: float, now: float) -> list[dict]:
    """Newest items since `since`: lab announcements first, max 2 per source, no duplicates."""
    fresh = [i for i in items if since <= i["published"] <= now + 300]
    fresh.sort(key=lambda i: (i["kind"] != "lab", -i["published"]))
    chosen, per_source, links = [], {}, set()
    for item in fresh:
        if item["link"] in links or per_source.get(item["source"], 0) >= MAX_PER_SOURCE:
            continue
        if item["kind"] == "lab" and sum(c["kind"] == "lab" for c in chosen) >= MAX_LAB_ITEMS:
            continue
        # Only compare with other outlets: two posts from the same blog are different posts.
        if any(c["source"] != item["source"] and same_story(item["title"], c["title"]) for c in chosen):
            continue
        # Keep variety: on a big launch day, don't let one company fill the whole post.
        topics = {n for n in names(item["title"]) if not n.replace(".", "").isdigit()}
        if any(sum(t in names(c["title"]) for c in chosen) >= MAX_PER_NAME for t in topics):
            continue
        chosen.append(item)
        links.add(item["link"])
        per_source[item["source"]] = per_source.get(item["source"], 0) + 1
        if len(chosen) >= MAX_ITEMS:
            break
    return chosen


def news_embed(items: list[dict], title: str, footer: str) -> discord.Embed:
    embed = discord.Embed(title=title, color=config.COLOR_MAIN)
    if not items:
        embed.description = "No new AI updates from the trusted sources in the last day."
    else:
        labs = sum(i["kind"] == "lab" for i in items)
        embed.description = (f"🔬 **{labs}** from AI labs · 📰 **{len(items) - labs}** from tech news\n"
                             "*Straight from the sources below; open the link for the full story.*")
    for i in items:
        value = f"**{i['source']}** · <t:{int(i['published'])}:R>\n"
        if i["summary"] and i["summary"].lower() != i["title"].lower():
            value += f"{i['summary']}\n"
        value += f"[Read more]({i['link']})"
        embed.add_field(name=f"{KIND_EMOJI[i['kind']]} {i['title']}"[:256], value=value[:1024], inline=False)
    embed.set_footer(text=footer[:2048])
    while len(embed) > 5900 and embed.fields:   # Discord's limit is 6000 characters per embed
        embed.remove_field(-1)
    return embed


class AINews(commands.Cog, name="AI News"):
    """Daily AI news from trusted sources."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache: list[dict] = []
        self.cache_time = 0.0
        self.feed_status: dict[str, str] = {}      # source name -> "ok" or the error
        self.last_good: dict[str, list[dict]] = {} # source name -> items from its last successful fetch
        self.last_digest: dict[int, int] = {}      # guild id -> unix time of the last digest
        if config.AI_NEWS_DAILY:
            self.daily_loop.start()

    async def cog_unload(self):
        self.daily_loop.cancel()

    async def fetch_source(self, source: dict) -> list[dict]:
        """Fetch one feed, retrying once. If it still fails, reuse its last good copy."""
        name = source["name"]
        for attempt in (1, 2):
            try:
                async with self.bot.http_session.get(source["url"], timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    resp.raise_for_status()
                    raw = await read_limited(resp, FEED_MAX_BYTES)
                items = parse_feed(raw, source)
                self.feed_status[name] = "ok"
                self.last_good[name] = items
                return items
            except (aiohttp.ClientError, TimeoutError, ET.ParseError, ValueError) as e:
                error = e
                if attempt == 1:
                    await asyncio.sleep(3)
        self.feed_status[name] = f"{type(error).__name__} (using last good copy)" if name in self.last_good \
            else type(error).__name__
        print(f"  [!] AI news: {name} feed failed twice ({error!r})", flush=True)
        return self.last_good.get(name, [])

    async def all_items(self) -> list[dict]:
        """Every item from every source (cached for 30 minutes)."""
        if self.cache and time.time() - self.cache_time < CACHE_SECONDS:
            return self.cache
        results = await asyncio.gather(*(self.fetch_source(s) for s in config.AI_NEWS_SOURCES))
        self.cache = [item for items in results for item in items]
        self.cache_time = time.time()
        return self.cache

    async def todays_items(self) -> list[dict]:
        now = time.time()
        items = await self.all_items()
        chosen = pick(items, now - 86400, now)
        if len(chosen) < 3:                       # quiet day: look back two days instead
            chosen = pick(items, now - 2 * 86400, now)
        return chosen

    def footer(self) -> str:
        names = ", ".join(s["name"] for s in config.AI_NEWS_SOURCES)
        return f"{DIGEST_MARKER} · daily at {config.AI_NEWS_HOUR_IST}:00 IST · Sources: {names}"

    # --- Daily post ---------------------------------------------------------------
    async def post_digest(self, channel: discord.TextChannel) -> bool:
        items = await self.todays_items()
        today = utcnow().astimezone(IST).strftime("%d %b %Y")
        try:
            await channel.send(embed=news_embed(items, f"🧠 Daily AI update · {today}", self.footer()))
        except discord.HTTPException as e:
            print(f"  [!] AI news: can't post in #{channel.name} ({e})", flush=True)
            return False
        self.last_digest[channel.guild.id] = int(utcnow().timestamp())
        print(f"  [+] AI digest posted in #{channel.name} ({len(items)} items)", flush=True)
        return True

    async def posted_since(self, channel: discord.TextChannel, since: dt.datetime) -> int | None:
        """When the bot last posted a digest here after `since`, read from the channel itself,
        so the schedule survives restarts without saving anything."""
        async for msg in channel.history(after=since - dt.timedelta(seconds=1), oldest_first=False, limit=500):
            if msg.author == self.bot.user and any(DIGEST_MARKER in (e.footer.text or "") for e in msg.embeds):
                return int(msg.created_at.timestamp())
        return None

    @tasks.loop(minutes=15)
    async def daily_loop(self):
        now = utcnow()
        due = post_time(now)
        if now < due:
            return                                # not 9:00 IST yet today
        for guild in self.bot.guilds:
            channel = find_channel(guild, "ai")
            if not channel:
                continue
            last = self.last_digest.get(guild.id)
            if last and last >= due.timestamp():
                continue                          # already posted today (remembered)
            try:
                last = await self.posted_since(channel, due)
            except discord.HTTPException as e:
                print(f"  [!] AI news: can't read #{channel.name} ({e})", flush=True)
                continue
            if last:
                self.last_digest[guild.id] = last
            else:
                await self.post_digest(channel)

    @daily_loop.before_loop
    async def before_daily(self):
        await self.bot.wait_until_ready()

    # --- Commands -------------------------------------------------------------------
    @commands.hybrid_command(description="Latest AI news from official labs and trusted tech outlets")
    @commands.cooldown(1, 30, commands.BucketType.channel)
    async def ainews(self, ctx: commands.Context):
        await ctx.defer()
        items = await self.todays_items()
        await ctx.send(embed=news_embed(items, "🧠 Latest AI news",
                                        "Sources: " + ", ".join(s["name"] for s in config.AI_NEWS_SOURCES)))

    @commands.hybrid_command(description="Staff: post today's AI update in the AI channel now")
    @app_commands.default_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def ainewspost(self, ctx: commands.Context):
        channel = find_channel(ctx.guild, "ai")
        if not channel:
            return await ctx.send(f"⚠️ I can't find {channel_link(ctx.guild, 'ai')}. "
                                  "Create it or change `CHANNELS['ai']` in config.py.", ephemeral=True)
        await ctx.defer(ephemeral=True)
        if await self.post_digest(channel):
            await ctx.send(f"✅ Posted in {channel.mention}.", ephemeral=True)
        else:
            await ctx.send(f"⚠️ Couldn't post in {channel.mention}. Check that I can send messages and "
                           "embed links there.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AINews(bot))
