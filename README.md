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
  - Anti-toxicity & harassment: deletes messages with harassment phrases ("kys", "kill yourself", "go die", "nobody likes you"…), including simple disguises like `K.Y.S`, `kyyys` or `k1ll y0urself`. Three strikes within 10 minutes gives a 10-minute timeout. Add your own phrases with the `EXTRA_BLOCKED_PHRASES` environment variable (comma-separated). It is keyword-based, so it won't understand context and can miss spaced-out letters like `f u c k`.
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


