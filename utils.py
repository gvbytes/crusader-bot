"""Small helpers shared by every cog."""

import json
import os
import re
from datetime import datetime, timezone

import discord

import config


CHANNEL_SLUG_RE = re.compile(r"[a-z0-9-]+$")


def channel_slug(name: str) -> str:
    """The plain part at the end of a channel name: '🎭・roles', '🎭•roles'
    and 'roles' all give 'roles', whatever decoration comes first."""
    match = CHANNEL_SLUG_RE.search(name.lower())
    return match.group(0).strip("-") if match else ""


def find_channel(guild: discord.Guild, key: str):
    """Find a text channel by its config key, e.g. find_channel(guild, "roles")."""
    wanted = config.CHANNELS.get(key, key)
    for ch in guild.text_channels:
        if channel_slug(ch.name) == wanted:
            return ch
    return None


def channel_link(guild: discord.Guild, key: str) -> str:
    """A clickable #channel link. Discord needs the channel ID for this,
    which is why writing a channel's name inside <#...> showed up as plain text."""
    ch = find_channel(guild, key)
    return ch.mention if ch else f"#{config.CHANNELS.get(key, key)}"


def is_staff(member) -> bool:
    if not isinstance(member, discord.Member):
        return False
    perms = member.guild_permissions
    return (
        perms.administrator
        or perms.manage_messages
        or any(r.name == config.STAFF_ROLE for r in member.roles)
    )


async def mod_log(guild: discord.Guild, title: str, description: str,
                  color=config.COLOR_WARN, important: bool = False) -> bool:
    """Post an entry in #mod-log. Returns True if staff received it.

    If #mod-log doesn't exist, routine entries are skipped, but important ones
    (like member reports) are sent to the server owner by DM instead."""
    embed = discord.Embed(title=title, description=description, color=color,
                          timestamp=datetime.now(timezone.utc))
    ch = find_channel(guild, "mod_log")
    if ch:
        try:
            await ch.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            return True
        except discord.HTTPException:
            pass
    if important and guild.owner:
        embed.set_footer(text=f"{guild.name} has no #mod-log channel, so this was sent to you. "
                              "Create a staff-only #mod-log to receive these there.")
        try:
            await guild.owner.send(embed=embed)
            return True
        except discord.HTTPException:
            pass
    return False


def can_moderate(actor: discord.Member, target: discord.Member) -> str | None:
    """Return a reason why `actor` may not act on `target`, or None if it's fine."""
    if target == actor:
        return "You can't use this on yourself."
    if target.bot:
        return "You can't use this on a bot."
    if target == target.guild.owner:
        return "You can't use this on the server owner."
    if actor != actor.guild.owner and target.top_role >= actor.top_role:
        return "That member's role is equal to or higher than yours."
    if target.top_role >= target.guild.me.top_role:
        return "That member's role is higher than mine. Move my role up in Server Settings → Roles."
    return None


DURATION_RE = re.compile(r"(\d+)\s*(d|h|m|s)")
UNIT_SECONDS = {"d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_duration(text: str) -> int | None:
    """Turn '1h30m', '2d' or '45m' into seconds. Returns None if it can't."""
    text = text.lower().replace(" ", "")
    parts = DURATION_RE.findall(text)
    if not parts or "".join(n + u for n, u in parts) != text:
        return None
    return sum(int(n) * UNIT_SECONDS[u] for n, u in parts)


# --- Tiny JSON "database" -----------------------------------------------------
# Note: on hosts with a temporary disk (like Render's free tier) this file is
# wiped on every redeploy.

def load_json(name: str, default):
    path = os.path.join(config.DATA_DIR, name)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(name: str, data) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    path = os.path.join(config.DATA_DIR, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)  # write-then-rename, so a crash never leaves half a file
