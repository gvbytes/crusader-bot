#!/usr/bin/env python3
"""
Crusaders 24/7 Discord Community Bot Service & Active Guardrails
Configured for Cloud Deployment (Render, Railway, Fly.io, VPS)
"""

import sys
import os
import ssl
import certifi
import re
import time
from collections import defaultdict

os.environ["SSL_CERT_FILE"] = certifi.where()
ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

import asyncio
import discord
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
if not TOKEN and len(sys.argv) > 1:
    TOKEN = sys.argv[1].strip()

ROLE_MAP = {
    "🚀": "🚀 Builder",
    "🚩": "🚩 CTF / Cyber",
    "🎮": "🎮 Gamer",
    "✅": "⚔️ Crusader"
}

MALICIOUS_DOMAINS = [
    "grabify.link", "iplogger.org", "2no.co", "yip.su", "iplis.ru",
    "discord-nitro", "free-nitro", "dlscord", "discorcl", "steamcommunitu",
    "steamcomminuty", "gift-discord"
]

DANGEROUS_EXTENSIONS = [".exe", ".bat", ".vbs", ".scr", ".cmd", ".pif"]
USER_MESSAGE_LOG = defaultdict(list)

@bot.event
async def on_ready():
    print("=" * 60, flush=True)
    print(f"🛡️ Crusaders Security Guardrails & Bot LIVE: {bot.user}", flush=True)
    print("=" * 60, flush=True)

    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="Crusaders Security • gvbytes.com"
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)

    for guild in bot.guilds:
        await sync_existing_reactions(guild)

async def sync_existing_reactions(guild):
    roles_ch = discord.utils.get(guild.text_channels, name="🎭・roles")
    if not roles_ch:
        return

    try:
        async for message in roles_ch.history(limit=10):
            for reaction in message.reactions:
                emoji_str = str(reaction.emoji.name if hasattr(reaction.emoji, 'name') else reaction.emoji)
                if emoji_str in ROLE_MAP:
                    target_role_name = ROLE_MAP[emoji_str]
                    target_role = discord.utils.get(guild.roles, name=target_role_name)
                    if not target_role:
                        continue

                    async for user in reaction.users():
                        if user.bot:
                            continue
                        member = guild.get_member(user.id)
                        if member and target_role not in member.roles:
                            try:
                                await member.add_roles(target_role)
                                print(f"  [+] Synced role '{target_role_name}' to {member.display_name}", flush=True)
                            except Exception:
                                pass
    except Exception as e:
        print(f"  [!] Sync error in #roles: {e}", flush=True)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    member = message.author
    content_lower = message.content.lower()

    is_leader = False
    if hasattr(member, 'roles'):
        for r in member.roles:
            if r.name == "👑 Leader":
                is_leader = True
                break

    if not is_leader:
        for domain in MALICIOUS_DOMAINS:
            if domain in content_lower:
                try:
                    await message.delete()
                    warn = await message.channel.send(
                        f"🛡️ **Security Alert**: Suspicious link detected from {member.mention}. Message automatically removed."
                    )
                    await asyncio.sleep(6)
                    await warn.delete()
                    return
                except Exception:
                    pass

        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in DANGEROUS_EXTENSIONS):
                try:
                    await message.delete()
                    warn = await message.channel.send(
                        f"🛡️ **Security Alert**: Executable files (`.exe`, `.scr`, `.bat`) are restricted to prevent malware. Removed file from {member.mention}."
                    )
                    await asyncio.sleep(6)
                    await warn.delete()
                    return
                except Exception:
                    pass

        now = time.time()
        timestamps = USER_MESSAGE_LOG[member.id]
        timestamps = [t for t in timestamps if now - t < 3.0]
        timestamps.append(now)
        USER_MESSAGE_LOG[member.id] = timestamps

        if len(timestamps) >= 5:
            try:
                await message.delete()
                warn = await message.channel.send(
                    f"⚠️ {member.mention} **Slow down!** You are sending messages too fast (Anti-Spam Guardrail)."
                )
                await asyncio.sleep(4)
                await warn.delete()
                return
            except Exception:
                pass

        if len(message.mentions) > 4:
            try:
                await message.delete()
                warn = await message.channel.send(
                    f"⚠️ {member.mention} Mass-mentions are blocked by server security protocols."
                )
                await asyncio.sleep(5)
                await warn.delete()
                return
            except Exception:
                pass

        if ("discord.gg/" in content_lower or "discord.com/invite/" in content_lower):
            if message.channel.name != "🚀・showcase":
                try:
                    await message.delete()
                    warn = await message.channel.send(
                        f"📌 {member.mention} Discord invites are only allowed in <#🚀・showcase>. Message removed."
                    )
                    await asyncio.sleep(6)
                    await warn.delete()
                    return
                except Exception:
                    pass

    if bot.user in message.mentions:
        embed = discord.Embed(
            title="⚔️ CrusaderBot Online & Guardrails Active",
            description=(
                f"Hey {message.author.mention}! Server security & guardrails are **100% Operational**.\n\n"
                "• **Role Picker**: <#🎭・roles>\n"
                "• **Server Protocols**: <#📜・rules-and-info>\n"
                "• **Showcase**: <#🚀・showcase>\n"
                "• **Founder Portfolio**: [gvbytes.com](https://gvbytes.com)\n\n"
                "Type `!help` or `!ping` for utilities!"
            ),
            color=discord.Color.from_rgb(245, 158, 11)
        )
        embed.set_footer(text=f"Latency: {round(bot.latency * 1000)}ms • CrusaderBot")
        await message.channel.send(embed=embed)
        return

    await bot.process_commands(message)

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"⚡ **Pong!** Latency: `{latency}ms` • All Guardrails Operational.")

@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="⚔️ CRUSADERS BOT & SECURITY GUIDE",
        description="Available server utilities:",
        color=discord.Color.from_rgb(0, 212, 255)
    )
    embed.add_field(name="!ping", value="Check latency & security status.", inline=True)
    embed.add_field(name="!rules", value="View server protocol highlights.", inline=True)
    embed.add_field(name="!links", value="Founder portfolio & GitHub.", inline=True)
    embed.add_field(name="🎭 Roles", value="Grab your tags in <#🎭・roles>.", inline=False)
    embed.set_footer(text="Crusaders Security Core • gvbytes.com")
    await ctx.send(embed=embed)

@bot.command()
async def rules(ctx):
    embed = discord.Embed(
        title="📜 Server Protocols Summary",
        description="1. Respect Everyone\n2. Keep Topics in Designated Channels\n3. Educational Security Research Only\n4. No Spam or Unsolicited DMs\n\nFull details in <#📜・rules-and-info>.",
        color=discord.Color.from_rgb(245, 158, 11)
    )
    await ctx.send(embed=embed)

@bot.command()
async def links(ctx):
    embed = discord.Embed(
        title="🔗 Official Links",
        description="• **Founder Portfolio**: [gvbytes.com](https://gvbytes.com)\n• **GitHub**: [github.com/gvbytes](https://github.com/gvbytes)",
        color=discord.Color.from_rgb(16, 185, 129)
    )
    await ctx.send(embed=embed)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    emoji_str = str(payload.emoji.name if hasattr(payload.emoji, 'name') else payload.emoji)
    if emoji_str in ROLE_MAP:
        role_name = ROLE_MAP[emoji_str]
        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(payload.user_id)
        if role and member:
            try:
                await member.add_roles(role)
                print(f"  [+] Assigned '{role_name}' to {member.display_name}", flush=True)
            except Exception:
                pass

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    emoji_str = str(payload.emoji.name if hasattr(payload.emoji, 'name') else payload.emoji)
    if emoji_str in ROLE_MAP:
        role_name = ROLE_MAP[emoji_str]
        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(payload.user_id)
        if role and member and role in member.roles:
            try:
                await member.remove_roles(role)
                print(f"  [-] Removed '{role_name}' from {member.display_name}", flush=True)
            except Exception:
                pass

@bot.event
async def on_member_join(member):
    print(f"👋 New member joined: {member.display_name}", flush=True)
    crusader_role = discord.utils.get(member.guild.roles, name="⚔️ Crusader")
    if crusader_role:
        try:
            await member.add_roles(crusader_role)
        except Exception:
            pass

    welcome_ch = discord.utils.get(member.guild.text_channels, name="👋・welcome-lounge")
    if welcome_ch:
        embed = discord.Embed(
            title="⚔️ A New Crusader Has Joined!",
            description=f"Welcome {member.mention} to **Crusaders**!\n\n"
                        f"👉 Read the protocols in <#📜・rules-and-info>\n"
                        f"👉 Select your roles in <#🎭・roles>\n"
                        f"👉 Introduce yourself in <#🤝・introductions>",
            color=discord.Color.from_rgb(245, 158, 11)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{member.guild.member_count} • Crusaders")
        try:
            await welcome_ch.send(embed=embed)
        except Exception:
            pass

if __name__ == "__main__":
    bot.run(TOKEN)
