"""
All the settings for CrusaderBot live here, so you can change the bot's
behaviour without digging through the feature code.
"""

import os

# --- Secrets & hosting (read from the environment, never hardcoded) ---
TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
PORT = int(os.environ.get("PORT", 8080))
PREFIX = "!"

# --- Channels ---
# The bot finds channels by the part of the name after the "・", so
# "🎭・roles" and a plain "roles" channel both match "roles".
CHANNELS = {
    "roles": "roles",
    "rules": "rules-and-info",
    "showcase": "showcase",
    "welcome": "welcome-lounge",
    "intro": "introductions",
    "suggestions": "suggestions",
    "mod_log": "mod-log",
    "ctf": "ctf-news",
}

# --- Roles ---
STAFF_ROLE = "👑 Leader"        # exempt from the auto-filters
MEMBER_ROLE = "⚔️ Crusader"     # given to everyone who joins

# Reaction roles: emoji in #roles -> role name
ROLE_MAP = {
    "🚀": "🚀 Builder",
    "🚩": "🚩 CTF / Cyber",
    "🎮": "🎮 Gamer",
    "✅": "⚔️ Crusader",
}

# --- Auto-moderation ---
MALICIOUS_DOMAINS = [
    "grabify.link", "iplogger.org", "2no.co", "yip.su", "iplis.ru",
    "discord-nitro", "free-nitro", "dlscord", "discorcl", "steamcommunitu",
    "steamcomminuty", "gift-discord",
]
DANGEROUS_EXTENSIONS = [".exe", ".bat", ".vbs", ".scr", ".cmd", ".pif"]

SPAM_MESSAGES = 5        # this many messages...
SPAM_SECONDS = 3.0       # ...within this many seconds counts as spam
MAX_MENTIONS = 4

# Phrases aimed at hurting another member. Add your own with the
# EXTRA_BLOCKED_PHRASES environment variable (comma-separated).
TOXIC_PHRASES = [
    "kill yourself", "kys", "go die", "hope you die", "you should die",
    "neck yourself", "end yourself", "unalive yourself", "drink bleach",
    "nobody likes you", "everyone hates you", "no one would miss you",
    "fuck you", "fuck off", "stfu",
]
TOXIC_PHRASES += [p.strip() for p in os.environ.get("EXTRA_BLOCKED_PHRASES", "").split(",") if p.strip()]
TOXIC_STRIKE_WINDOW = 600      # strikes older than 10 minutes are forgotten
TOXIC_STRIKES_FOR_TIMEOUT = 3
TOXIC_TIMEOUT_MINUTES = 10

# --- CTF feed ---
CTF_WEEKLY_POST = True   # post upcoming CTFs to #ctf-news every Monday, 9:00 IST

# --- Saved data (warnings, reminders) ---
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# --- Colours ---
COLOR_MAIN = 0x00D4FF
COLOR_WARN = 0xF59E0B
COLOR_OK = 0x10B981
COLOR_BAD = 0xEF4444
