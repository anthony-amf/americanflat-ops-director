# Draft: BigQuery load step for `download-weekly-shipping-reports`

Paste-ready text for the skill's canonical source on the Mac
(`~/.claude/skills/download-weekly-shipping-reports/SKILL.md`), then repackage
per the change workflow in CLAUDE.md. Written 2026-09-10 from the synced copy of
that skill, so it matches its current numbering: **it inserts as Step 5 and the
existing "Notify on Slack" becomes Step 6.**

Three small edits elsewhere are listed at the bottom.

Commands here use shell variables rather than `<angle brackets>`: a
bracketed placeholder inside a fenced block reads as runnable and gets
pasted verbatim, which is exactly what happened to the first draft.

---

## The new step

````markdown
## Step 5 — Load the costs into BigQuery

The staged Stamps and FedEx exports are the only copy of what the carriers
actually billed. Load them now, while they are on disk and the week window is
known — nothing downstream can reach these files later.

```bash
cd "$OPS_REPO" && python3 tools/stamps_shipping_costs_load.py load \
  "$STAGING_FOLDER"/Stamps_PrintHistory_*.csv
```

`$OPS_REPO` is the local clone of `americanflat/Ops`, which owns loading these
tables. `$STAGING_FOLDER` is the folder Step 3 created. Use `prepare` instead of
`load` to parse and report without writing anything — worth doing first on any
week that looks unusual.

Three things about that command:

- **Load one export, not a glob.** The last occurrence of a tracking number
  wins, and a shell glob orders files by the date range in the filename rather
  than by when they were exported — so a wide backfill, usually the newest and
  most adjusted, sorts early and gets overwritten by stale weekly ones. On the
  September files that was worth $3,464.17 understated. The staging folder holds
  one Stamps export per week, so the glob above is safe; it is
  `~/Downloads/PrintHistory_*.csv` that is not.
- **If impersonating the invoice writer fails, add `--no-impersonate`.**
  `anthony@americanflat.com` cannot impersonate
  `invoice-writer@americanflat.iam.gserviceaccount.com` — it lacks the token
  creator role and cannot grant it to itself. Writing directly as `anthony@`
  works and is the normal path.
- **Read what it prints.** It reports the table's row count, distinct label
  count and total after merging, and says whether they agree. `rows == distinct
  labels` is the check: if they diverge, something is double-counting and every
  number built on that table is inflated. Say so in the Slack post and DM
  Anthony rather than quietly continuing.

**FedEx has no loader yet.** `finance.fedex_shipping_costs` does not exist and
nothing loads it, so the week's FedEx export is not going anywhere. When a
loader lands in that repo, call it here too — the FedEx table is one row per
invoice line rather than per shipment, because FedEx re-bills a shipment on a
later invoice and both lines are real money.

**If the load fails, do not abandon the run.** The Excel report is the week's
deliverable and it is already written by this point. Note the failure, carry on
to Step 6, and include it in the Slack message.

Append a line to `run_summary.txt` with what was loaded.
````

## Three edits elsewhere in the same file

**1. `## What it does`** — add a fourth numbered item before the Slack one:

> 4. Loads the Stamps export into BigQuery (`finance.stamps_shipping_costs`, via
>    `americanflat/Ops`) so the marketplace shipment portals price from a
>    maintained table instead of a stale file. FedEx has no loader yet.

**2. `## Output`** — nothing new lands in the folder, so only the note under the
tree needs a sentence:

> The two carrier exports are also merged into BigQuery by Step 5, which is what
> keeps the Marketplace Shipments portals current between manual runs.

**3. `## How to run`** — the scheduled chain gains a link:

> The scheduled run does the full chain: download → stage → cost report →
> **BigQuery load** → Slack notify.

Optionally, one line in the Step 6 Slack message so a silent load failure cannot
hide:

> `BigQuery: NNN Stamps labels loaded` — or
> `BigQuery: :warning: load failed, see run_summary.txt`

---

## Why this is a step and not a hook

Anthony asked for a hook. Claude Code's hook events fire around tool calls, so a
hook on the Skill tool would run when this skill *loads*, not when its work
finishes — the wrong moment, since the files do not exist yet. And the load needs
three things that only coexist inside this skill's own run on the Mac: the raw
exports on disk, gcloud's write credentials, and a known week window. A step is
the mechanism; the Thursday 7:00 AM schedule already provides the trigger.
