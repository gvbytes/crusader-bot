# crusader bot

discord bot for the crusaders server. handles basic moderation, reaction roles, ctf updates from ctftime, and runs a small health check server on $PORT.

all commands work both as slash commands and with prefix (!).

## files

- bot.py : entry point, starts the client, loads cogs, and runs the health check server
- config.py : bot settings, roles, channels, and blocked keyword lists
- utils.py : shared helpers for channel lookups, mod-logs, and file storage
- cogs/guardrails.py : basic filters (spam, bad links, mass mentions, harassment)
- cogs/moderation.py : staff commands (warn, timeout, purge, slowmode)
- cogs/community.py : welcome messages, reaction roles, polls, suggestions
- cogs/utility.py : ping, help, rules, reminders
- cogs/ctf.py : ctftime integration and upcoming ctfs
- requirements.txt : dependencies (discord.py, aiohttp, certifi)

## setup and install

1. install the requirements:
```bash
pip install -r requirements.txt
```

2. set your bot token:
```bash
export DISCORD_BOT_TOKEN="your_bot_token"
```

3. (optional) additional environment variables:
```bash
export PORT=8080
export EXTRA_BLOCKED_PHRASES="phrase1,phrase2"
```

## how to run

start the bot:
```bash
python bot.py
```

## permissions and discord setup

- enable Server Members and Message Content intents in discord developer portal
- bot role needs: Manage Messages, Manage Roles, Timeout Members, Manage Channels
- bot role must sit above regular member roles in server settings to time people out

## features

### moderation
- link blocklist: removes known ip-logger and fake-nitro links
- file-type block: blocks .exe, .bat, .vbs, .scr, .cmd, .pif uploads
- rate limit: deletes messages from anyone sending 5+ within 3 seconds
- mass-mention limit: blocks messages mentioning more than 4 members
- invite links: discord invites are only allowed in #showcase
- harassment filter: keyword matching on abusive phrases with leetspeak normalization. 3 strikes in 10 minutes gives a 10-minute timeout

### staff commands
- /warn, /warnings, /clearwarnings
- /timeout, /untimeout
- /purge
- /slowmode

### community and utility
- welcome messages in #welcome-lounge with automatic role assignment
- reaction roles in #roles
- /poll, /suggest, /report
- /ping, /help, /rules, /serverinfo, /remind

### ctf tracking
- /ctf : upcoming ctfs from ctftime with timezone conversion
