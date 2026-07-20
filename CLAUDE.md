# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
(v1.0.0, promoted 2026-06-30 — several commits behind local). Updates go through
the `skill-fixer` skill → `americanflat/skill-candidates` branch → Publisher
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

## Dashboard

`~/yusen_invoices_dashboard.html` (outside the repo) is a static snapshot with
an embedded `const DATA = [...]` array. Other processes re-export it from a base
template, wiping the Validated/Paid columns — `refresh_yusen_dashboard.py` is
idempotent and re-applies its columns/chip helpers plus fresh data every run.
When adding dashboard features, extend the patcher's add-if-missing /
upgrade-if-stale pattern; a plain string replace will double-insert.

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

## Conventions

- Commits go directly to `main`; messages are imperative summaries with a body
  explaining the why (see `git log`).
- Payment status (`paid_at`) is written **only** on explicit user confirmation —
  never inferred, never from "OK to pay" verdicts. SP/LTL invoices additionally
  require a Stedi order-level pass before payment marking.
