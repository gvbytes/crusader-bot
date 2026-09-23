# crusader bot

discord bot for the crusaders server. handles basic moderation, reaction roles, and automated security guardrails.

## setup and install

1. install the requirements:
```bash
pip install -r requirements.txt
```

2. set your bot token:
```bash
export DISCORD_BOT_TOKEN="your_bot_token"
```

## how to run

start the bot:
```bash
python bot.py
```

## features

- link blocklist: removes known ip-logger and fake-nitro links
- file-type block: blocks dangerous executable uploads
- rate limit: basic spam protection
- mass-mention limit: blocks messages mentioning too many members

## deployment

deploy as background worker or cloud container:
- set DISCORD_BOT_TOKEN in environment
- runs 24/7 on render, railway or fly.io
