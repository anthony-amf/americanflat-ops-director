# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## NO-DELETE RULE (standing order from Anthony, 2026-08-05)

Never run — and never hand Anthony terminal commands containing — anything
that deletes or destructively overwrites: no `rm`, no `rsync --delete`, no
`git clean`/`git reset --hard`, no force flags, no `mv` onto an existing path,
no `>` truncation of existing files. Copies are additive only, into freshly
created directories (never `~`, never a populated folder). If removal is truly
needed, `mv` the item into a dated quarantine folder as its own explicitly
approved step. Any multi-command block MUST chain with `&&` so a failure stops
the chain. (Origin: a pasted command block where a failed `git clone` + `cd`
let `rsync --delete` run against the Mac home directory.)

## What this repo is

Americanflat's invoice-audit workspace for Yusen/Taylored 3PL freight invoices.
The system validates invoices on three axes (invoice math, rate-card alignment,
Stedi EDI shipment evidence) and tracks approval/payment in BigQuery. Full
domain documentation — invoice families, hard rules, verified rate history,
data model — lives in `YUSEN-INVOICE-VALIDATOR.md`; read it before touching
validation logic.

## Critical: where the real code lives

The **canonical skill source is NOT in this repo**. It lives at
`~/.claude/skills/yusen-invoice-validator/` (SKILL.md, scripts/, references/).
This repo carries:

- `yusen-invoice-validator.skill` — the packaged zip of that source (committed artifact)
- Root-level `*.py` validators (`rate-card-validator.py`, `invoice-stedi-validator.py`,
  `invoice-validator-demo.py`, `scripts/parse_invoice_excel.py`) — **stale dev
  predecessors** of the skill scripts. Do not edit these expecting behavior to
  change; edit the skill source instead.
- `refresh_yusen_dashboard.py` — live companion tool (see Dashboard below)

**Change workflow for validator logic:**
1. Edit files under `~/.claude/skills/yusen-invoice-validator/`
2. Repackage: `cd "<skill-creator dir>" && python3 -m scripts.package_skill ~/.claude/skills/yusen-invoice-validator`
   (skill-creator dir: `~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/*/*/skills/skill-creator`)
3. Copy the produced `.skill` to `~/Downloads/` and this repo, then commit

The skill is also published org-wide as `americanflat/skill-yusen-invoice-validator`
(v1.0.0, promoted 2026-06-30). Local source is at **v1.1.0** with a complete
changelog — submission-ready but not yet published. Updates go through the
`skill-fixer` skill → `americanflat/skill-candidates` branch → Publisher
review; never push directly to the published repo.

## Common commands

All validator commands run from the skill directory
(`cd ~/.claude/skills/yusen-invoice-validator`) and need
`export STEDI_API_KEY=<key>` for Stedi steps plus gcloud ADC for BigQuery:

```bash
# Validate one invoice / sweep everything (with BigQuery stamp write-back)
python3 scripts/validate_rate_card.py <invoice> --write
python3 scripts/validate_rate_card.py --list-all --limit 400 --write

# One-time provisioning of tracking columns on a fresh table
python3 scripts/validate_rate_card.py --init

# Payment marking (only on explicit user confirmation; stores report card)
python3 scripts/validate_rate_card.py <invoice> --mark-paid [--report-file rpt.txt]
python3 scripts/validate_rate_card.py <invoice> --unmark-paid

# SP/LTL deep pass: parse supporting doc → Stedi 945/940 sweep
python3 scripts/parse_invoice_excel.py <file.xlsx> <invoice> --output /tmp/orders.json
python3 scripts/validate_stedi.py <invoice> --json-file /tmp/orders.json

# NL (Benelux) invoices — EUR + VAT, separate path
python3 scripts/validate_nl_invoice.py <extraction.json>

# Refresh the HTML dashboard from BigQuery (run from this repo)
python3 refresh_yusen_dashboard.py
```

There is no test suite; validation changes are verified by re-running known
invoices (752857 = valid Admin, 752738 = partial-week Admin, an NL transport
extraction JSON for `validate_nl_invoice.py`) and confirming statuses don't
regress. For Stedi sweeps over ~1,000 orders, use a concurrent checker
(ThreadPoolExecutor ~10 workers against `core.us.stedi.com/2023-08-01/transactions`)
instead of the sequential script.

## Data & environment facts that bite

- **BigQuery** `americanflat.finance.yusen_invoices` is the ledger. The
  account has DML + `tables.update` (ALTER works) but **not** `tables.create`.
  Rows in the streaming buffer (~90 min after insert) reject UPDATE — stamp
  writes auto-defer; re-run `--list-all --write` later to catch them.
- **`bq` CLI silently truncates at 100 rows** without `--max_rows` — this has
  caused real bugs; always set it on row-returning queries used in scripts.
- International invoices land **one row per charge type**
  (`CA2WFS…-Storage`, `FTI…-Admin`) with a machine-parseable breakdown in
  `notes` — the format is load-bearing (`"Type: USD 1,234.56 | Name=…, Name=…"`);
  appending free text after the components breaks the sum-check parser.
- Warehouse text is free-form; `WAREHOUSE_MAP` in `validate_rate_card.py`
  normalizes it. Savannah = TS South = South Carolina; Schiphol/Moerdijk = NL.
  Short aliases ("SC", "NJ") must match whole tokens, never substrings.
- The Notion rate card (page `3898555c2abc81efab1decc73a53973a`) is the rate
  source of truth but **lags the contract** — see the rate history table in
  `YUSEN-INVOICE-VALIDATOR.md` before flagging discrepancies. Below-card
  billing is a stale-card flag, not a dispute.

## Dashboards

**The Claude Artifact is the user-facing invoice search UI** (stable URL
`https://claude.ai/code/artifact/23dd148b-1fb0-4219-80e1-53ca8d9d3d97`) — people
search invoices there, not in raw BigQuery. Built by `~/build_artifact_dashboard.py`
(imports `~/generate_yusen_dashboard.py`; both live in `~`, outside this repo),
auto-refreshed weekdays ~7:09 AM ET by the `refresh-yusen-dashboard-artifact`
scheduled task; ingestion itself runs daily 3 PM MT via launchd. Two traps:
republishing MUST pass `url:` with the stable artifact URL or a duplicate
artifact gets minted; and pre-2026-07-13 rows hold legacy `docs.google.com`
supporting-doc links in BigQuery — deliberately not backfilled, the generators
rewrite them to `drive.google.com/file/d/<id>/view` at render time (any
non-dashboard consumer of `supporting_doc_url` needs the same rewrite).

`~/yusen_invoices_dashboard.html` is the local twin — a static snapshot with an
embedded `const DATA = [...]` array, refreshed by this repo's
`refresh_yusen_dashboard.py`. Other processes re-export it from a base template,
wiping the Validated/Paid columns — the refresher is idempotent and re-applies
its columns/chip helpers plus fresh data every run. When adding dashboard
features, extend the patcher's add-if-missing / upgrade-if-stale pattern; a
plain string replace will double-insert.

## Other directories

- `extraction/`, `schema/`, `samples/`, the root guides
  (`README.md`, `IMPLEMENTATION_GUIDE.md`, `STEDI_*.md`) — the original design
  docs and scaffolding for the extraction→BigQuery pipeline. Extraction itself
  is owned by the separate `skill-invoice-to-bigquery` skill, not this repo.
- `validation-reports/` — per-invoice markdown report cards, written on request.
- `selling-partner-api-models-main/` — vendored Amazon SP-API models (reference
  only; unrelated to invoice validation).
- Committed `*.skill` files are packaged artifacts of other personal skills;
  treat them as binaries.

## Cloud sessions (no access to this Mac)

- **Skill scripts:** the canonical source dir (`~/.claude/skills/...`) is
  machine-local. In a cloud session, unzip the committed package instead:
  `unzip -o yusen-invoice-validator.skill -d /tmp/skill && cd /tmp/skill/yusen-invoice-validator`
  — it contains SKILL.md, scripts/, and references/ at the committed version.
- **Decision queue:** local memory doesn't sync — read `OPEN-ITEMS.md` (kept as
  a mirror; update it when decisions land).
- **Credentials:** `STEDI_API_KEY` must be provided as an environment secret.
  BigQuery needs non-interactive auth (service-account credentials) — the local
  gcloud ADC does not travel. Notion/Drive/Gmail/Slack connectors are
  account-level and work in cloud; Chrome automation (used for Gmail
  attachment → Drive hops) does not.
- **Dashboard:** `~/yusen_invoices_dashboard.html` and `refresh_yusen_dashboard.py`
  are local-to-the-Mac; skip dashboard refreshes in cloud sessions.

## Conventions

- Commits go directly to `main`; messages are imperative summaries with a body
  explaining the why (see `git log`).
- Payment status (`paid_at`) is written **only** on explicit user confirmation —
  never inferred, never from "OK to pay" verdicts. SP/LTL invoices additionally
  require a Stedi order-level pass before payment marking.
