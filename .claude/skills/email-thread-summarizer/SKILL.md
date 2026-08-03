---
name: email-thread-summarizer
description: >
  Summarizes a Gmail email thread from a pasted identifier — normally a subject line.
  Use this skill when the user says "summarize this thread", "summarize this email",
  "give me the key points of a thread", "what's the latest on a subject", "TL;DR this thread",
  or pastes a subject line, Gmail link, or thread ID and asks for a summary or action items.
  Searches Gmail by the pasted identifier, finds the matching thread, reads it efficiently,
  and produces a skimmable key-points and action-items summary. Offers to set up a daily
  recurring update for the thread.
---

# Email Thread Summarizer

Turn a pasted identifier (usually an email **subject line**) into a clean, skimmable summary of the whole Gmail thread — key points, how it played out, per-item status, and action items with owners.

## Step 1 — Resolve the identifier to a thread

The user will paste something to identify the thread. Handle whatever they give you, in this priority order:

1. **Subject line** (the normal case, e.g. `FBA flow`): search Gmail with
   `search_threads`, query `subject:"<their text>"`. Quote multi-word subjects.
2. **Thread ID** (16-hex-char string, e.g. `19e3a7fa4ca32eaa`): pass straight to `get_thread`.
3. **A Gmail web URL** (e.g. `.../#inbox/FMfcgz...`): the trailing ID in a browser URL is a *web permalink*, **not** an API thread ID and cannot be looked up directly. Don't try `get_thread` on it. Instead ask the user for the subject line (or a sender/keyword) and search by that.
4. **Sender or keyword**: search with `from:<addr>` or the bare keyword.

If the search returns **multiple** threads, don't guess — list the top candidates (subject · most recent sender · date) and ask the user to pick one. If it returns exactly one, proceed.

## Step 2 — Read the thread efficiently

Call `get_thread` with the chosen `threadId` and **`messageFormat: "MINIMAL"`**.

> ⚠️ Do **not** use `FULL_CONTENT` first. These threads often have embedded images/attachments and the full payload can exceed the token limit (one real thread was ~7M characters). MINIMAL returns each message's sender, recipients, date, subject, and snippet — enough to reconstruct the narrative. Only fall back to `FULL_CONTENT` (or read it from the saved tool-result file in chunks) if the snippets are genuinely insufficient for a specific message, and then only fetch what you need.

Walk the messages in date order. Track: who said what, dates, quantities, IDs/SKUs, decisions, escalations, and anything still open.

## Step 3 — Write the summary (house format)

Produce a skimmable summary in this structure. Keep it tight — short bullets, no walls of text. Use bold for entity/ID labels.

```
Here's the rundown of the **"<subject>"** thread — <N> messages, <first date> → <last date>.

## What it's about
1–3 sentences of context: who's involved (both orgs) and the core subject.

## How it played out
Chronological bullets of the key beats — group by phase or date range. Name who
did what and call out errors, escalations, and resolutions.

## Current status
One line per item/shipment/topic being tracked (ready? booked? blocked? next date?).

## Open action items
Bullets, each tagged with the owner (e.g. **John Nunez**, **Carolina**, **Yusen/Piotr**)
and any due date or deadline. Lead with whatever needs action soonest.
Flag any risks (charges, deadlines, rejections).
```

End with a **Sources:** line linking the thread:
`[<subject> — Gmail thread](https://mail.google.com/mail/u/0/#inbox/<threadId>)`

## Step 4 — Offer a recurring update

After delivering the summary, offer once:

> Want me to check this thread automatically each morning and post an updated summary when there are new replies?

If yes, create a scheduled task (daily, e.g. 8:30 AM local) whose prompt is self-contained: it must include the thread ID, the participant list, the "use MINIMAL format" warning, and instructions to report only what's new since the last run (or "No new activity" if nothing changed). Confirm to the user that scheduled tasks run only while the app is open.

## Notes
- This is read-only on Gmail — it never sends, archives, or labels anything.
- If the Gmail connector isn't available, tell the user and stop; don't try to fetch mail another way.
