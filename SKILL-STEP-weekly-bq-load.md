# Draft: BigQuery load step for `download-weekly-shipping-reports`

Paste-ready text for the skill's canonical source on the Mac
(`~/.claude/skills/download-weekly-shipping-reports/SKILL.md`), then repackage
per the change workflow in CLAUDE.md. Written 2026-09-10 from the synced copy of
that skill, so it matches its current numbering: **it inserts as Step 5 and the
existing "Notify on Slack" becomes Step 6.**

Three small edits elsewhere are listed at the bottom.

---

## The new step

````markdown
## Step 5 — Load the costs into BigQuery

The staged Stamps and FedEx exports are the only copy of what the carriers
actually billed. Load them now, while they are on disk and the week window is
known — nothing downstream can reach these files later.

```bash
python3 <ops-director repo>/scripts/load_shipping_costs_to_bq.py \
  --dir "<staging folder>" --write
```

The script finds `Stamps_PrintHistory_*.csv` and `FedEx_Invoice_*_most-recent.csv`
itself and ignores everything else in the folder, including the three 3PL
reports. Without `--write` it reports what it would do and changes nothing —
useful if a run looks wrong.

It writes to two tables, and they are deliberately shaped differently:

- `finance.stamps_shipping_costs` — one row per shipment. Stamps states a final
  figure per label (quoted + adjusted = paid).
- `finance.fedex_shipping_costs` — one row per invoice **line**. FedEx bills a
  shipment again on a later invoice when it re-rates, and both lines are money
  we paid, so a shipment's cost is the sum of its lines.

Both merge rather than append: the weekly exports re-state shipments the last
one covered, so appending would stack the same charge two or three times. In the
FedEx sheet 7,965 rows carry only 3,697 distinct charges.

**Read the checks it prints before moving on.** Each merge is followed by a
verification query:

- Stamps: `rows_total` must equal `distinct_tracking`, and `still_escaped` must
  be 0.
- FedEx: `must_be_zero_duplicate_lines` and `must_be_zero_escaped` must both be
  0. `lines_total` being greater than `shipments` is **correct** there — that gap
  is the re-rates.

If any of those is wrong, the table is double-counting and every number built on
it is inflated. Say so in the Slack post and DM Anthony; do not quietly continue.

**If the load fails, do not abandon the run.** The Excel report is the week's
deliverable and it is already written. Note the failure, carry on to Step 6, and
include it in the Slack message. Two failures worth recognising:

- *Table not found: fedex_shipping_costs* — the table has not been created yet.
  Run `sql/fedex_shipping_costs_setup.sql` from the ops-director repo once, then
  re-run this step.
- *Permission denied* — the load needs gcloud's write credentials, so it only
  works on the Mac. A cloud session has read-only BigQuery and will always fail
  here.

Append a line to `run_summary.txt` with the row counts loaded per table.
````

---

## Three edits elsewhere in the same file

**1. `## What it does`** — add a fourth numbered item before the Slack one:

> 4. Loads the Stamps and FedEx exports into BigQuery
>    (`finance.stamps_shipping_costs`, `finance.fedex_shipping_costs`) so the
>    marketplace shipment portals price from a table instead of a stale file.

**2. `## Output`** — nothing new lands in the folder, so only the note under the
tree needs a sentence:

> The two carrier exports are also merged into BigQuery by Step 5, which is what
> keeps the Marketplace Shipments portals current between manual runs.

**3. `## How to run`** — the scheduled chain gains a link:

> The scheduled run does the full chain: download → stage → cost report →
> **BigQuery load** → Slack notify.

Optionally, one line in the Step 6 Slack message so a silent load failure cannot
hide:

> `BigQuery: NNN Stamps · NNN FedEx rows loaded` — or
> `BigQuery: :warning: load failed, see run_summary.txt`

---

## Why this is a step and not a hook

Anthony asked for a hook. Claude Code's hook events fire around tool calls, so a
hook on the Skill tool would run when this skill *loads*, not when its work
finishes — the wrong moment, since the files do not exist yet. And the load needs
three things that only coexist inside this skill's own run on the Mac: the raw
exports on disk, gcloud's write credentials, and a known week window. A step is
the mechanism; the Thursday 7:00 AM schedule already provides the trigger.
