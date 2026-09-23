# Crusaders Discord Bot ⚔️

24/7 Discord Community Bot & Automated Security Guardrails for **Crusaders** ([gvbytes.com](https://gvbytes.com)).
Made using Antigravity.

## Features

- **🛡️ Active Security Guardrails**:
  - Anti-Toxicity & Harassment Filter
  - Anti-Malware / Phishing / IP Logger / Executable Upload Block
  - Anti-Flood Rate Limiter & Mass-Mention Shield
  - Discord Invite Link Shield (Restricted to `#showcase`)
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
