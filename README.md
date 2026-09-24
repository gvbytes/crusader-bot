# Crusaders Discord Bot ⚔️

Community, moderation and CTF bot for the **Crusaders** Discord server.
Made using Antigravity and Claude.

Every command works as a slash command (`/ping`) and with the `!` prefix (`!ping`).

## Features

### 🛡️ Automatic moderation
Runs on every message from non-staff members. Every removal is recorded in `#mod-log`.
These are simple rules, not full malware or phishing detection.
- **Link blocklist:** deletes messages containing a short list of known IP-logger and fake-Nitro domains
- **File-type block:** deletes uploads ending in `.exe`, `.bat`, `.vbs`, `.scr`, `.cmd` or `.pif`
- **Rate limit:** deletes messages from anyone sending 5 or more within 3 seconds
- **Mass-mention limit:** deletes messages that mention more than 4 people
- **Invite links:** Discord invites are only allowed in `#showcase`
- **Harassment filter:** deletes messages with harassment phrases ("kys", "kill yourself", "go die", "nobody likes you"…), including simple disguises like `K.Y.S`, `kyyys` or `k1ll y0urself`. Three strikes within 10 minutes gives a 10-minute timeout. It is keyword-based, so it won't understand context and can miss spaced-out letters like `f u c k`.

### 🧑‍⚖️ Staff commands
Only visible to members with the matching Discord permission.
| Command | What it does | Permission |
|---|---|---|
| `/warn @member reason` | Warns and DMs the member; warnings are saved | Timeout Members |
| `/warnings @member` | Lists a member's warnings | Timeout Members |
| `/clearwarnings @member` | Removes all of a member's warnings | Timeout Members |
| `/timeout @member 2h reason` | Times out a member (up to 28 days) | Timeout Members |
| `/untimeout @member` | Removes a timeout | Timeout Members |
| `/purge 50 [@member]` | Bulk-deletes up to 100 recent messages | Manage Messages |
| `/slowmode 10` | Sets channel slowmode (`0` turns it off) | Manage Channels |

### 🤝 Community
- **`/poll "Question?" A | B | C`**: up to 10 options, or none for a yes/no poll
- **`/suggest idea`**: posts to `#suggestions` with 👍/👎 voting
- **`/report @member reason`**: privately flags a member to staff in `#mod-log`
- **Report a message:** right-click a message → **Apps** → **Report to staff**
- **Welcome messages** in `#welcome-lounge`, and new members get the `⚔️ Crusader` role
- **Reaction roles** in `#roles`: 🚀 Builder, 🚩 CTF / Cyber, 🎮 Gamer, ✅ Crusader

### 🧰 Utility
- **`/help`**: every command, generated automatically (staff also see staff commands)
- **`/ping`**, **`/rules`**, **`/serverinfo`**, **`/userinfo [@member]`**, **`/avatar [@member]`**
- **`/remind 2h submit the assignment`**: sends you a DM when it's time (max 30 days, 10 per person); **`/reminders`** lists yours

### 🚩 CTF
- **`/ctfnow`**: CTFs running right now, split into ones you can join and ones you can't (on-site, invite-only, qualified teams…), ending soonest first. If none you can join are live, it shows the next ones starting.
- **`/ctf [count] [online_only] [ai] [can_join]`**: upcoming CTF competitions (next 30 days) from [CTFtime](https://ctftime.org), with times shown in each viewer's own timezone
- **Who can join:** every listing says ✅ Open to everyone, 🎓 University students only, 🏫 High-school only, 🔒 Qualified teams / Invite only, or 📍 On-site only, based on CTFtime's restrictions. Some CTFs close registration early, so check the event page.
- **AI policy for every CTF:** each listing is labelled 🤖 AI allowed, 🚫 No AI, ⚖️ Separate AI / human leaderboards, ⚠️ Mixed rules, or ❔ Not stated. Filter with `/ctf ai:`.
  - The bot reads the CTF's CTFtime description first, then its website (homepage and `/rules`); website results are marked "(from website)".
  - It looks for actual rules ("AI is strictly prohibited", "we don't ban AI"), not mentions of AI as a challenge category.
  - Most CTFs don't publish an AI policy, and sites that load their text with JavaScript can't be read, so many show "Not stated". Always check the official rules.
  - The rules live in [`ai_policy.py`](ai_policy.py).
- **Automatic CTF digest every 3 days** in `#cyber-and-ctf`, listing the CTFs starting in the next week and any joinable CTFs that are live. The bot checks the channel for its own last digest, so restarts don't reset the schedule. Change the interval with `CTF_POST_EVERY_DAYS` in `config.py`.
- **`/ctfpost`** (staff, Manage Messages): post the digest right now; the next automatic one follows 3 days later

### 🧠 Daily AI news
- **Every day at 9:00 IST** in `#ai-and-ml`: the top 10 AI updates of the last 24 hours, each with its source, a short summary from the source itself, and a link.
- **Trusted sources only**, each checked to publish a working feed:
  - Official AI labs: OpenAI, Google DeepMind, Google AI, Microsoft Research, Hugging Face, NVIDIA
  - Established tech news: MIT Technology Review, IEEE Spectrum, Ars Technica, The Verge, TechCrunch, Wired
- **How it picks:** lab announcements first (up to 6), then news; at most 2 per source and 2 per company, and the same story from different outlets appears once. NVIDIA posts that aren't about AI are skipped.
- **Reliable:** a failing feed is retried, then its last good copy is used; the bot checks the channel for today's post, so restarts never double-post or skip a day.
- **`/ainews`**: the latest AI news on demand. **`/ainewspost`** (staff): post today's update now.
- Change sources or the time in `config.py` (`AI_NEWS_SOURCES`, `AI_NEWS_HOUR_IST`).

---

## Setup

```bash
pip install -r requirements.txt
export DISCORD_BOT_TOKEN="your_bot_token_here"
python bot.py
```

Environment variables:
- `DISCORD_BOT_TOKEN` (required): your bot token from the Discord Developer Portal
- `EXTRA_BLOCKED_PHRASES` (optional): extra phrases for the harassment filter, comma-separated
- `PORT` (optional, default `8080`): port for the `/health` endpoint

Everything else (channel names, roles, filter limits) is in [`config.py`](config.py).

### Discord permissions
- In the Developer Portal, turn on the **Server Members** and **Message Content** intents.
- The bot's role needs **Manage Messages**, **Manage Roles**, **Timeout Members** and **Manage Channels**, and must sit **above** the members it moderates.
- Invite the bot with the `bot` and `applications.commands` scopes so slash commands appear.

### Channels
The bot finds channels by the plain words at the end of the name, so `🎭・roles`, `🎭•roles` and `roles` all work.
Optional channels are simply skipped if they don't exist:

| Channel | Used for |
|---|---|
| `#mod-log` | Record of auto-deletions, reports and staff actions. **Make it staff-only.** Until it exists, reports are sent to the server owner by DM. |
| `#suggestions` | `/suggest` posts (otherwise posted in the current channel) |
| `#cyber-and-ctf` | CTF digest every 3 days |
| `#ai-and-ml` | Daily AI news at 9:00 IST |
| `#roles`, `#rules-and-info`, `#welcome-lounge`, `#introductions`, `#showcase` | Existing channels, linked from messages |

### Saved data
Warnings and reminders are saved in `data/` (not committed to git). On hosts with a temporary disk, such as Render's free tier, this folder is wiped on every redeploy.

## Project layout
```
bot.py          starts the bot, loads the cogs, health check server
config.py       all settings
ai_policy.py    works out a CTF's AI policy from its description or website
utils.py        shared helpers (channel lookup, #mod-log, durations, saving data)
cogs/
  guardrails.py automatic moderation
  moderation.py staff commands
  community.py  welcome, reaction roles, polls, suggestions, reports
  utility.py    help, info commands, reminders
  ctf.py        CTFtime integration
  ai_news.py    daily AI news from trusted feeds
```
