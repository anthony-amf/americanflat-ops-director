# EOD Update Skill

Builds your daily End of Day update automatically: at the end of the day, tell Claude
**"process my EOD update"** and it sweeps your Slack, sent Gmail, Google Calendar, and
Claude sessions for the day, then hands you two things to review:

1. **A bullet list** (5–10 outcome-first bullets) ready to paste into the EOD channel.
2. **A context page** — the full backstory per bullet (case numbers, POs, $ values,
   who/what/why) so you have receipts when someone asks about a bullet.

It never posts anything itself — you always review and post.

## Install

1. Copy the `eod-update` folder into your skills directory:
   `C:\Users\<you>\.claude\skills\eod-update\`  (Mac: `~/.claude/skills/eod-update/`)
2. Restart Claude Code / Cowork (or start a new session).
3. Say "process my EOD update". The first run calibrates to you (~2 min): your name,
   Slack ID, which reaction emojis you actually use, and your preferred bullet style.
   That's saved to `~/.claude/eod-update-config.md` and reused every day after.

## Requirements

- **Slack connector** connected in Claude (used to find messages you sent + reacted to).
- **Gmail**: the Gmail MCP connector if connected (works in cloud sessions too), else
  the **Claude in Chrome** extension with Chrome signed into your work Google account.
  Read-only either way: it never sends, replies, or deletes.
- **Google Calendar**: read via Claude in Chrome (no Calendar connector exists);
  skipped with a note if Chrome isn't available.
- Claude Code / Cowork desktop (for the Claude-sessions sweep; skipped elsewhere).

First run will ask you to approve mail.google.com and calendar.google.com in the
browser — one time.

## Known blind spots

Phone calls, huddles, and physical work leave no digital trail — add those bullets
manually before posting. Slack reactions only surface if the reacted-to message was
posted the same day.

## Tips

- "process my EOD update" → today. "process my EOD for Friday" → that day.
- "punchy version" → one-line bullets. "detailed version" → 2-3 lines each.
- The more your work lives in Slack/email, the better the draft. Review before
  posting — it's your update, the skill just does the sweeping.

---
Built by John Nunez (jnunez@americanflat.com) with Claude — July 2026.
Questions/improvements: ping John.
