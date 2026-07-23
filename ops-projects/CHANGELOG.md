# Changelog — Ops Projects tool

All notable changes to the Ops Projects tracker (Airtable base + dashboard).
Dashboard URL: https://claude.ai/code/artifact/02c51fe9-37a1-4920-a941-7e0cb3390b61

## v7 — 2026-07-23 · Rank the 90 Day Focus

- ▲▼ controls on starred cards reorder the 90 Day Focus section; the order
  persists in a new "Focus Rank" number field in Airtable and syncs through
  the Changes tray. Starred cards keep full editing (click to quick-edit,
  ✎ for the full editor) like any other card.

## v6 — 2026-07-23 · Category assignment in quick edit

- The click-to-edit card (and meeting mode) gained a **Category** chip row,
  so projects can be recategorized inline alongside status and priority.

## v5 — 2026-07-23 · Click-to-edit cards and 90 Day Focus stars

- Click any card to open it full-screen in the meeting-style quick editor —
  status chips, priority chips, and an update note — with **Save & close**
  (or Esc) returning to the board and a **Full editor** shortcut for renames,
  owners, target dates, and delete.
- Star (☆/★) on every card assigns a project to the **90 Day Focus**: starred
  projects pin to a dedicated section at the top of the board. Backed by a new
  "90 Day Focus" checkbox field in the Airtable Projects table; star changes
  sync through the Changes tray like all other edits.

## v4 — 2026-07-23 · Delete projects

- **Delete…** button in the project editor for projects that are no longer
  relevant. Deleted projects disappear from the board and meeting deck
  immediately and queue in the Changes tray under "Projects to delete";
  the Airtable records are removed when the changes are applied.
- Deleting a not-yet-created project (added this session) simply discards it.

## v3 — 2026-07-21 · Filters, sorting, and edit mode

- Status filter (In Progress / Blocked / Not Started / Needs Review / Completed)
  and priority filter (Top / Mid / Low / Ad Hoc) in the filter bar.
- Sort selector: stalest first (default), priority, recently discussed, A–Z.
- Every card gained a ✎ edit button: change status, priority, owners,
  category, name, target date, or attach an update note.
- **+ New project** button creates projects from the page.
- Pending-changes tray (bottom-right), persisted in the browser via
  localStorage; "Copy for Claude" exports the change list, Claude applies it
  to Airtable, and the queue auto-clears after the next data refresh.
- Meeting mode gained priority chips and now feeds the same change queue.

## v2 — 2026-07-21 · Meeting mode

- One-card-at-a-time deck for the weekly meeting: Blocked first, then
  In Progress stale-first, then Needs Review, then Not Started.
- "Discussed — next" (Space/→) sends a card to the back of the deck;
  "Skip" (S) cycles it without marking; Completed cards drop out.
- Per-card status chips and update notes, exported as a meeting recap for
  Claude to apply to Airtable and log in the Meeting Log table.
- Progress bar and discussed counter; filters set before starting scope
  the deck.

## v1 — 2026-07-21 · Initial release

- Created the **Ops Projects** Airtable base (`appaFuK87Xk9Nn5vR`):
  `Projects` table (Status, Priority, Owners, Category, Notes, Latest Update,
  Last Discussed, Target Date, Slack Link, computed Days Since Discussed)
  and `Meeting Log` table.
- Migrated all 340 rows from the Slack "Ops Projects" list (`F08BA9R8E8L`)
  → 331 clean projects: blanks dropped, duplicates merged, statuses and
  priorities normalized, owner emails mapped to names, keyword
  auto-categorization; blank statuses flagged **Needs Review** for triage.
- AF-branded dashboard: KPI tiles, Blocked / In Progress (stale-first,
  red edge >21 days) / Up Next / Needs Review / Recent Wins sections,
  owner + category + text filters, light and dark themes.
- Scripts: `migrate_slack_to_airtable.py` (one-time migration),
  `build_dashboard.py` (regenerates the dashboard from live Airtable data).
