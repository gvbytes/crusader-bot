# Crusaders Discord Bot ⚔️

24/7 Discord Community Bot & Automated Security Guardrails for **Crusaders** ([gvbytes.com](https://gvbytes.com)).
Made using Antigravity.

## Features

- **🛡️ Basic Moderation Filters** (simple rules, not full malware or phishing detection):
  - Link blocklist: deletes messages containing a short list of known IP-logger and fake-Nitro domains
  - File-type block: deletes uploads ending in `.exe`, `.bat`, `.vbs`, `.scr`, `.cmd` or `.pif`
  - Rate limit: deletes messages from anyone sending 5 or more within 3 seconds
  - Mass-mention limit: deletes messages that mention more than 4 people
  - Invite links: Discord invites are only allowed in `#showcase`
- **🎭 Automated Reaction Roles**: Real-time role assignment on reaction clicks in `#roles`.
- **👋 Member Welcome System**: Custom embed welcome cards for new joiners in `#welcome-lounge`.
- **💬 Interactive Mentions & Commands**:
  - `@CrusaderBot` — Interactive help & server status
  - `!ping` — Real-time latency probe
  - `!help` — Server navigation shortcuts
  - `!rules` — Protocol summary
  - `!links` — Official website and portfolio links
- **🌐 HTTP Health Check**:
  - Built-in `/health` endpoint for Render, Railway, and uptime pingers.

---

## Deploy 24/7 on Render (Free Tier)

1. Go to [dashboard.render.com](https://dashboard.render.com) and log in with GitHub (`gvbytes`).
2. Click **New +** → Select **Web Service** (Free plan available).
3. Connect repository **`gvbytes/crusader-bot`**.
4. Configure:
   - **Name**: `crusader-bot`
   - **Language**: `Python 3` (or Docker)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
   - **Instance Type**: `Free`
5. Under **Environment Variables**, add:
   - `DISCORD_BOT_TOKEN` = `<your_bot_token>`
6. Click **Deploy Web Service**!
