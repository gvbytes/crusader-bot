"""Automatic filters that run on every message from non-staff members."""

import asyncio
import re
import time
from collections import defaultdict
from datetime import timedelta

import discord
from discord.ext import commands

import config
from utils import channel_link, is_staff, mod_log

# --- Harassment detection ------------------------------------------------------
LEET_MAP = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
                          "7": "t", "@": "a", "$": "s", "!": "i"})


def normalize_text(text: str) -> str:
    """Lowercase, undo simple leetspeak, drop symbols and squash repeated letters
    so that 'K.Y.S', 'kyyys' and 'k1ll y0urself' are all caught."""
    text = text.lower().translate(LEET_MAP)
    text = re.sub(r"[^a-z\s]", "", text)       # 'k.y.s' -> 'kys'
    text = re.sub(r"(.)\1+", r"\1", text)      # 'kyyys' -> 'kys', 'kill' -> 'kil'
    return " ".join(text.split())


# Phrases are normalized the same way, then matched as whole words only,
# so 'skills' or 'stfuzzy' never trigger a false alarm.
TOXIC_REGEXES = [
    re.compile(r"\b" + r"\s*".join(re.escape(w) for w in normalize_text(p).split()) + r"\b")
    for p in config.TOXIC_PHRASES if normalize_text(p)
]


def is_toxic(text: str) -> bool:
    cleaned = normalize_text(text)
    return any(rx.search(cleaned) for rx in TOXIC_REGEXES)


class Guardrails(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_times = defaultdict(list)   # member id -> recent message timestamps
        self.toxic_strikes = defaultdict(list)   # member id -> recent strike timestamps

    async def remove(self, message: discord.Message, notice: str, log_title: str, seconds: int = 6):
        """Delete a message, post a short-lived notice, and record it in #mod-log."""
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        await mod_log(
            message.guild, log_title,
            f"**Member:** {message.author.mention} (`{message.author.id}`)\n"
            f"**Channel:** {message.channel.mention}\n"
            f"**Message:** {message.content[:900] or '*(attachment only)*'}",
        )
        try:
            await message.channel.send(notice, delete_after=seconds)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        member = message.author
        content = message.content.lower()

        if not is_staff(member):
            # 1. Known IP-logger / fake-Nitro links
            if any(domain in content for domain in config.MALICIOUS_DOMAINS):
                return await self.remove(message,
                    f"🛡️ Suspicious link from {member.mention} removed.", "🔗 Suspicious link removed")

            # 2. Executable file uploads
            if any(a.filename.lower().endswith(tuple(config.DANGEROUS_EXTENSIONS)) for a in message.attachments):
                return await self.remove(message,
                    f"🛡️ {member.mention} executable files aren't allowed here. File removed.",
                    "📎 Executable upload removed")

            # 3. Spam: too many messages too fast
            now = time.time()
            recent = [t for t in self.message_times[member.id] if now - t < config.SPAM_SECONDS]
            recent.append(now)
            self.message_times[member.id] = recent
            if len(recent) >= config.SPAM_MESSAGES:
                return await self.remove(message,
                    f"⚠️ {member.mention} slow down, you're sending messages too fast.",
                    "💨 Spam removed", seconds=4)

            # 4. Mass mentions
            if len(message.mentions) > config.MAX_MENTIONS:
                return await self.remove(message,
                    f"⚠️ {member.mention} please don't mention that many people at once.",
                    "📣 Mass mention removed")

            # 5. Invite links outside #showcase
            if "discord.gg/" in content or "discord.com/invite/" in content:
                showcase = channel_link(message.guild, "showcase")
                if not message.channel.name.endswith(config.CHANNELS["showcase"]):
                    return await self.remove(message,
                        f"📌 {member.mention} Discord invites are only allowed in {showcase}.",
                        "✉️ Invite link removed")

            # 6. Harassment, with strikes and an automatic timeout
            if is_toxic(message.content):
                return await self.handle_toxic(message)

        # Someone @mentioned the bot: point them to the right places
        if self.bot.user in message.mentions and not message.reference:
            g = message.guild
            embed = discord.Embed(
                title="⚔️ Hi, I'm CrusaderBot",
                description=(
                    f"Hey {member.mention}! Here's where to go:\n\n"
                    f"• **Pick your roles:** {channel_link(g, 'roles')}\n"
                    f"• **Server rules:** {channel_link(g, 'rules')}\n"
                    f"• **Show your projects:** {channel_link(g, 'showcase')}\n\n"
                    "Type `/help` to see everything I can do."
                ),
                color=config.COLOR_WARN,
            )
            await message.channel.send(embed=embed)

    async def handle_toxic(self, message: discord.Message):
        member = message.author
        now = time.time()
        strikes = [t for t in self.toxic_strikes[member.id] if now - t < config.TOXIC_STRIKE_WINDOW]
        strikes.append(now)
        self.toxic_strikes[member.id] = strikes

        if len(strikes) >= config.TOXIC_STRIKES_FOR_TIMEOUT:
            self.toxic_strikes[member.id] = []
            try:
                await member.timeout(timedelta(minutes=config.TOXIC_TIMEOUT_MINUTES),
                                     reason="Repeated harassment (CrusaderBot auto-mod)")
                notice = (f"🔇 {member.mention} has been timed out for "
                          f"{config.TOXIC_TIMEOUT_MINUTES} minutes for repeated harassment.")
            except discord.HTTPException:
                notice = f"⛔ {member.mention} keeps posting harassment. Staff, please review."
            await self.remove(message, notice, "🔇 Harassment: strike 3, timeout", seconds=10)
        else:
            left = config.TOXIC_STRIKES_FOR_TIMEOUT - len(strikes)
            await self.remove(message,
                f"⚠️ {member.mention} harassment isn't allowed here. Message removed. "
                f"({left} more and you'll be timed out.)",
                f"🚫 Harassment removed (strike {len(strikes)})", seconds=8)


async def setup(bot: commands.Bot):
    await bot.add_cog(Guardrails(bot))
