---
name: eod-update
description: >
  Build the user's End of Day (EOD) update — a bullet-style summary of everything they
  did today, swept from Gmail (sent mail), Google Calendar (meetings), Slack (messages
  sent AND reacted to), and Claude (sessions worked in today) — plus a full-detail
  context page as a second deliverable. Produces a draft for the user to REVIEW AND
  POST THEMSELVES — never post it anywhere automatically. Use this skill whenever the
  user says "process my EOD update", "EOD update", "end of day summary", "what did I
  do today", "daily update for the CEO", or similar — even if they don't say "use the
  skill".
---

# EOD Update

Goal: one paste-ready, bullet-style summary of the user's workday, swept from four
sources, plus a context page with the full backstory per bullet. The deliverables are
**drafts shown in chat for the user to review and post themselves**. Never post to
Slack, email, or anywhere else — not even if asked to "just send it"; posting the EOD
is the user's action.

## Step 0 — Personal config (first run only)

Look for `~/.claude/eod-update-config.md`. If it exists, load it and skip to Step 1.
If missing, calibrate — takes ~2 minutes, once:

1. **Identity**: confirm the user's full name and work email. Get their Slack user ID
   (the Slack MCP tool descriptions state the logged-in user's ID; otherwise use
   `slack_search_users` with their name).
2. **Reaction-emoji audit**: Slack has no "any reaction from me" search, so discover
   which reaction emojis this user actually uses. Run
   `hasmy::<emoji>: after:<14 days ago>` for each candidate:
   `:+1:`, `:white_check_mark:`, `:raised_hands:`, `:eyes:`, `:pray:`, `:100:`,
   `:saluting_face:`, `:fire:`, `:clap:`, `:ok_hand:`, `:heart:`, `:muscle:`.
   Keep the ones with hits; ask the user if any favorites are missing.
3. **Style**: default bullet length is "outcome + one clause of context" (~20-25
   words). Ask if they prefer punchier or more detailed.
4. **Work channels**: ask which channels carry most of their work (e.g. mostly email
   with externals, mostly Slack, mostly tickets) so the sweep emphasis is right.
5. **Recurring off-channel tasks**: ask for standing daily/weekly tasks that leave no
   email or Slack trail — portal work, invoicing, system checks, physical tasks
   (e.g. "invoicing in the billing portal, daily"). Save each with its cadence. On
   every run, list the ones due that day and ask the user to quickly confirm which
   happened (and any notable numbers) — then include them as bullets. The user can
   add more anytime by saying "add a recurring task to my EOD".

Save all of it to `~/.claude/eod-update-config.md` and confirm to the user.

## Step 1 — Establish the day

Use today's date (local). If the user names a different day ("do Friday's"), use that.
All source sweeps below filter to that single day.

## Step 2 — Sweep the four sources (run independently; parallelize where possible)

### A. Slack (MCP connector — direct)
- `slack_search_public_and_private` with query: `from:<@USER_ID> on:<YYYY-MM-DD>` —
  paginate through ALL result pages (a busy day can be 4+ pages).
- Group hits by channel. For threads where the user replied, use `slack_read_thread`
  on the parent to recover what the reply was about.
- Ignore pure noise ("thanks", "on it", greetings) — keep messages that represent
  work: reports posted, decisions made, questions answered, escalations handled.
- Also sweep messages the user REACTED to (alignment signal): run
  `hasmy::<emoji>: on:<date>` for each emoji in their config. Interpretation guide:
  👍/✅/💯 = aligned/approved; 🫡 = acknowledged an assignment (often becomes a task);
  👀 = reviewing/monitoring; 🙏 = thanks. Phrase as "aligned with X on …" /
  "reviewed X's …" / "picked up Y from X". Skip reactions on their own messages and
  on trivial messages. Known limitation: `on:` filters by the message's date, so a
  reaction added today to an older message won't surface.

### B. Claude sessions (session-management MCP — if available)
- If a session-management MCP is available (`mcp__ccd_session_mgmt__list_sessions`),
  filter to sessions with activity that day. If the MCP isn't present in this
  environment, skip this source and note it at the bottom.
- Session titles usually suffice. If a title is vague, `search_session_transcripts`
  or `list_events` on that session to recover what was produced.
- Frame these bullets by the business outcome ("processed daily shorts and sent
  warehouse actions"), not "used Claude".

### C. Gmail — sent mail (connector first, Chrome fallback)
- **Preferred: Gmail MCP connector**, if available (tool names like
  `mcp__Gmail__search_threads` / `mcp__Gmail__get_thread` — load via ToolSearch).
  Search `in:sent after:YYYY/MM/DD before:YYYY/MM/DD` (target day / next day),
  then `get_thread` on EVERY hit and read the full thread. Same rule as below:
  never summarize a thread from its list snippet. READ ONLY — never send, reply,
  label, or delete.
- **Fallback: Claude in Chrome** (desktop only), when no Gmail connector is
  connected. Load Chrome tools via one ToolSearch call:
  `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__find,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__browser_batch`
- Navigate to `https://mail.google.com/mail/u/0/#search/in%3Asent+after%3AYYYY%2FMM%2FDD+before%3AYYYY%2FMM%2FDD`
  (target day / next day).
- `get_page_text` to read the sent list first (recipients + subjects), THEN open
  EVERY thread in the day's sent list — click into each one and `get_page_text` the
  full thread. NEVER summarize a thread from its list snippet: snippets truncate
  replies and hide follow-ups, diagnostics, dollar values, and decisions further down
  the thread. Most real work (trucks booked, pickup windows scheduled, BOLs/labels
  sent, escalations, fires put out) lives in mid-thread replies, never in subjects.
  Skipping a thread means missing a task.
- READ ONLY. Never compose, reply, archive, or delete anything.

### D. Google Calendar (via Claude in Chrome; skip if Chrome unavailable)
- Navigate to `https://calendar.google.com/calendar/r/day/YYYY/M/D`.
- `get_page_text` / `read_page` to list the day's events: title, time, attendees.
- Skip declined events and all-day placeholders like "Focus time" unless meaningful.

If a source can't be read (no Gmail connector AND no Chrome; Calendar without
Chrome; no session MCP), don't stall: produce the summary from whatever sources are
available (+ Google Drive `list_recent_files` as a fallback signal for docs touched
that day) and add a one-line note at the bottom listing which sources were not swept.

## Step 3 — Compose the bullet draft

Merge all sources into ONE summary grouped by **workstream/topic, not by source**.
The same piece of work often shows up in multiple sources (a Claude session that
produced a report, the Slack post sharing it, the email sending it) — that is ONE
bullet.

Format (Slack-friendly plain text):

```
*EOD Update — {Weekday}, {Mon D}*
• {Outcome-first bullet: what was done / decided / shipped}
• {…}
• Meetings: {mtg 1}, {mtg 2}  ← only if calendar had real meetings
```

Rules:
- 5–10 bullets max; lead each with the outcome, past tense, no fluff.
- DEFAULT LENGTH: outcome + ONE clause of context per bullet, ~20-25 words — enough
  that a reader gets what happened and why it mattered without asking, but no
  thread-level play-by-play. Compress at compose time, not at sweep time (capture
  full detail during the sweep so any bullet can be expanded on request). "Punchy
  version" = strip to one ~15-word line; "detailed version" = 2-3 lines with who/why.
- Concrete numbers where available (POs processed, orders flagged, $ reconciled).
- Escalations, fires, and carrier/vendor issues keep their identifiers (case #, PO,
  order #, tracking) and a clause on what the user actually did (diagnosed, directed,
  escalated) — never compress a fire down to a vague half-bullet. Fires MAY be
  grouped into one "Fires:" bullet as long as each keeps its identifier.
- Order by significance, not chronology.
- Do NOT include: the EOD-building session itself, private/personal items, or
  anything the user was only cc'd on / attended passively unless it involved their
  action.

## Step 3b — Context page (second deliverable, always)

Below the bullet list, produce a "CONTEXT PAGE" — one numbered section per bullet
with the full backstory: who was involved, what happened and why, all identifiers
(case #, PO, ARN, tracking, $ values, file names), what was resolved vs still open.
This is the user's reference if their manager or a teammate asks what a bullet is
about. Write it from the detail captured during the sweep — this is why sweeps
capture everything even though bullets compress.

## Step 4 — Hand off

Show both deliverables in chat (bullets first, context page second) and stop. Ask
nothing unless a source failed. The user reviews, edits, and posts the bullets
themselves; the context page is for their reference, not for posting. If they ask
for tweaks ("make it shorter", "drop the meetings"), revise and re-show — still
never post.

Remind the user once per run: work with no digital trail (phone calls, huddles,
physical fixes) won't be captured — tack those on manually before posting.
