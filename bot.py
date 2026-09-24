#!/usr/bin/env python3
"""
CrusaderBot: community, moderation and CTF bot for the Crusaders Discord server.

This file only starts things up. Each feature lives in its own file in cogs/:
    guardrails.py   automatic filters (bad links, spam, harassment...)
    moderation.py   staff commands (/warn, /timeout, /purge...)
    community.py    welcome, reaction roles, /poll, /suggest, /report
    utility.py      /help, /ping, /rules, /serverinfo, /userinfo, /remind...
    ctf.py          upcoming CTFs from CTFtime.org
    ai_news.py      daily AI news from trusted sources
"""

import asyncio
import os
import ssl
import sys

import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

import aiohttp
import discord
from aiohttp import web
from discord.ext import commands

import config

COGS = ["guardrails", "moderation", "community", "utility", "ctf", "ai_news"]


class CrusaderBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=config.PREFIX,
            intents=discord.Intents.all(),
            help_command=None,  # we provide our own /help
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
        )
        self.http_session: aiohttp.ClientSession | None = None
        self.synced_guilds: set[int] = set()

    async def setup_hook(self):
        # Runs once, before the bot connects.
        # Give the web session certifi's certificates explicitly, so HTTPS to CTFtime
        # works on every system, whatever order the libraries were imported in.
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.http_session = aiohttp.ClientSession(
            headers={"User-Agent": "CrusaderBot/2.0 (Discord bot)"},
            connector=aiohttp.TCPConnector(ssl=ssl_context),
        )
        for cog in COGS:
            await self.load_extension(f"cogs.{cog}")
            print(f"  [+] Loaded cogs/{cog}.py", flush=True)

    async def on_ready(self):
        print("=" * 60, flush=True)
        print(f"⚔️ CrusaderBot online as {self.user} in {len(self.guilds)} server(s)", flush=True)
        print("=" * 60, flush=True)
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching, name="over Crusaders • /help"))

        # Register slash commands per server: this makes them appear instantly.
        for guild in self.guilds:
            if guild.id in self.synced_guilds:
                continue
            self.tree.copy_global_to(guild=guild)
            try:
                synced = await self.tree.sync(guild=guild)
                self.synced_guilds.add(guild.id)
                print(f"  [+] Synced {len(synced)} slash commands to {guild.name}", flush=True)
            except discord.HTTPException as e:
                print(f"  [!] Slash sync failed in {guild.name}: {e}", flush=True)

    async def close(self):
        if self.http_session:
            await self.http_session.close()
        await super().close()


bot = CrusaderBot()


# --- Friendly error messages for every command -------------------------------
@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    error = getattr(error, "original", error)
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        msg = "⛔ You don't have permission to use this command."
    elif isinstance(error, commands.BotMissingPermissions):
        needed = ", ".join(p.replace("_", " ").title() for p in error.missing_permissions)
        msg = f"⚠️ I'm missing a permission for this: **{needed}**."
    elif isinstance(error, commands.MissingRequiredArgument):
        msg = f"⚠️ Missing `{error.param.name}`. Try `/help` to see how to use `{ctx.command}`."
    elif isinstance(error, (commands.BadArgument, commands.MemberNotFound)):
        msg = f"⚠️ {error}"
    elif isinstance(error, commands.CommandOnCooldown):
        msg = f"⏳ Slow down. Try again in {error.retry_after:.0f}s."
    elif isinstance(error, commands.NoPrivateMessage):
        msg = "This command only works inside the server."
    else:
        print(f"  [!] Error in {ctx.command}: {error!r}", flush=True)
        msg = "❌ Something went wrong running that command."
    try:
        await ctx.send(msg, ephemeral=True)
    except discord.HTTPException:
        pass


# --- Health check web server (Render and uptime monitors ping this) ----------
async def handle_health_check(request):
    ready = bot.is_ready()
    return web.json_response({
        "status": "online",
        "service": "CrusaderBot",
        "version": os.environ.get("RENDER_GIT_COMMIT", "local")[:7],
        "bot_user": str(bot.user) if bot.user else None,
        "bot_status": "ready" if ready else "connecting",
        "latency_ms": round(bot.latency * 1000) if ready else 0,
        "last_ctf_post": max(ctf.last_digest.values(), default=None) if (ctf := bot.get_cog("CTF")) else None,
        "last_ai_post": max(ai.last_digest.values(), default=None) if (ai := bot.get_cog("AI News")) else None,
    })


async def start_health_server():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    app.router.add_get("/health", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", config.PORT).start()
    print(f"🌐 Health check server listening on port {config.PORT}", flush=True)


async def main():
    if not config.TOKEN:
        print("❌ DISCORD_BOT_TOKEN is not set. Add it as an environment variable.", flush=True)
        sys.exit(1)
    await start_health_server()
    async with bot:
        await bot.start(config.TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shut down.", flush=True)
