# Ops Projects — Weekly Meeting Tool

Replacement for the Slack "Ops Projects" list (`F08BA9R8E8L`), which had grown to
340 rows with inconsistent statuses, duplicate entries, and no way to group,
filter, or spot stale work.

## Architecture

- **Source of truth: Airtable base [`Ops Projects`](https://airtable.com/appaFuK87Xk9Nn5vR)**
  (base ID `appaFuK87Xk9Nn5vR`). The team edits projects there — grid, kanban
  (group by Status or Owner), calendar, and filtered views can all be added in
  the Airtable UI. Two tables:
  - `Projects` — one row per project: Status, Priority, Owners, Category, Notes,
    Latest Update, Last Discussed, Target Date, Slack Link, and a computed
    `Days Since Discussed`.
  - `Meeting Log` — one row per weekly meeting: Date, Wins, Decisions, Notes.
- **Meeting dashboard: `dashboard.html`** — a self-contained AF-branded page
  generated from the Airtable data. Blocked / In Progress (stale-first) /
  Up Next / Needs Review / Recent Wins sections, KPI tiles, owner + category +
  text filters. Light and dark theme.

## Scripts

| Script | Purpose |
|---|---|
| `migrate_slack_to_airtable.py` | One-time migration of the Slack list CSV export into Airtable. Cleans statuses/priorities, maps emails to names, merges duplicates, auto-categorizes. Already run on 2026-07-21 (331 projects loaded). |
| `build_dashboard.py` | Regenerates `dashboard.html` from the current Airtable data. Run before each weekly meeting (or ask Claude to "refresh the ops projects dashboard"). |

Both scripts call `api.airtable.com` with no API key — the Claude Code agent
proxy injects credentials. To run them outside that environment, add an
`Authorization: Bearer <PAT>` header.

## Data cleaning rules used in the migration

- Blank project names dropped (7 rows); exact-duplicate names merged (2).
- Status: blank → **Needs Review** (a triage queue for the meeting —
  14 projects had no status in Slack).
- Priority: `Last` and `Low of the Low` → **Low**; `Unassigned` → none.
- People emails → first names (e.g. `jnunez@` → John N.); unresolved Slack
  user IDs dropped.
- Every project keyword-auto-categorized (3PL & Warehouses, Marketplaces & EDI,
  Shipping & Carriers, Finance & Billing, AI & Data, IT & Systems, People & HR,
  Lean & Culture, Other) — recategorize freely in Airtable.

## Weekly meeting flow

1. Open the dashboard (regenerate first so it's current).
2. Start with **Blocked**, then walk **In Progress** stale-first — the red-edged
   cards (>21 days since last discussed) are the ones slipping.
3. Triage **Needs Review** — claim or close.
4. Celebrate **Recent Wins**; log the meeting in the `Meeting Log` table.
5. Any edits (status changes, new projects, updates) happen in Airtable during
   the meeting.
