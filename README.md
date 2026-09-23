# Crusaders Discord Bot ⚔️

24/7 Discord Community Bot & Automated Security Guardrails for **Crusaders** ([gvbytes.com](https://gvbytes.com)).
Made using Antigravity.

## Features

- **🛡️ Active Security Guardrails**:
  - Anti-Toxicity & Harassment Filter
  - Anti-Malware / Phishing / IP Logger / Executable Upload Block
  - Anti-Flood Rate Limiter & Mass-Mention Shield
  - Discord Invite Link Shield (Restricted to `#showcase`)
- **🎭 Automated Reaction Roles**: Real-time role assignment on reaction clicks.
- **👋 Member Welcome System**: Custom embed welcome cards for new joiners.
- **💬 Interactive Mentions & Commands**:
  - `@CrusaderBot` — Interactive help & server status
  - `!ping` — Real-time latency probe
  - `!help` — Server navigation shortcuts
  - `!rules` — Protocol summary
  - `!links` — Official website and portfolio links

## Deploy 24/7 to Render / Railway

### Render.com
1. Click **New +** → **Background Worker**
2. Connect this repository (`gvbytes/crusader-bot`)
3. Environment Variables:
   - `DISCORD_BOT_TOKEN`: `YOUR_BOT_TOKEN`
4. Click **Deploy**

### Railway.app
1. Click **New Project** → **Deploy from GitHub repo**
2. Select `crusader-bot`
3. Add Variable `DISCORD_BOT_TOKEN`
4. Deploy!
