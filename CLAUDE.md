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
changelog — not yet pushed. Per the Repo Merge Policy (2026-07-08), published
skill repos are **no longer PR-gated**: commit directly to the skill repo's
`main`, tag `vX.Y.Z` matching `skill.toml`, then ask `@governors` in
#ai-github-skills to update the `ai-skills-registry` entry (Governors-only —
never edit the registry yourself). Use the `skill-pr-helper` skill for this
flow. The push must run from the Mac (or a session sourced on that repo) —
sessions scoped to `anthony-amf` cannot reach `americanflat/*` repos.

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
  **SC bills pallets through VAS work orders, not SP/LTL invoices** — and SC
  VAS PDFs are scanned images (no text layer; OCR them).
- **Rate source of truth is the Yusen MSA** (draft 7.15.2026; Anthony confirmed
  8/5 the rates are final). The Notion rate card (page
  `3898555c2abc81efab1decc73a53973a`) was rebuilt from it 2026-08-05 and is
  current, with pre-June history preserved. The MSA's rate table is an
  **embedded EMF image** in the docx — extract text from
  `word/media/image2.emf` (EMR_EXTTEXTOUTW records); pandoc/text alone misses
  it. Below-card billing is a stale-card flag, not a dispute.
- **`validation_status` vocabulary:** `valid` / `needs_detail` / `discrepancy`
  / **`disputed`** (MSA-conflict charges present — wrap beside a $10 pallet,
  0.92/0.966 pack-out, Fontana every-pick billing; disputed $ goes in
  `validation_variance`, detailed spec appended to `validation_report`, which
  both dashboards render as the chip tooltip/report card). Never re-stamp a
  `disputed` row back to `needs_detail`. Consolidated dispute position:
  `validation-reports/yusen-msa-billing-dispute-2026-08-05.md`; automation
  punch list: `VALIDATION-AUTOMATION.md`.

## Dashboards

**The Claude Artifact is the user-facing invoice search UI** (stable URL
`https://claude.ai/code/artifact/23dd148b-1fb0-4219-80e1-53ca8d9d3d97`) — people
search invoices there, not in raw BigQuery. Built by `~/build_artifact_dashboard.py`
(imports `~/generate_yusen_dashboard.py`; both live in `~`, outside this repo),
auto-refreshed **weekdays at 8:30 AM, 12:00 PM, 3:30 PM and 6:00 PM ET**
(Anthony, 2026-08-06) by two Routines — `refresh-yusen-artifact-830am-330pm`
(`trig_01YG7tbcgDnpBRKkxo1KDHok`) and `refresh-yusen-artifact-noon-6pm`
(`trig_01PrPh79KQSXtmK2fK9MBBVr`). Both are **gated**: the script compares a
fingerprint of the BigQuery rows and prints `NO_CHANGE`, in which case nothing
is republished. (Prior schedule was Mon/Thu 7:09 AM only — the older note
saying "weekdays 7:09 AM" was wrong.) Ingestion itself runs daily 3 PM MT via
launchd. Two traps:
republishing MUST pass `url:` with the stable artifact URL or a duplicate
artifact gets minted; and pre-2026-07-13 rows hold legacy `docs.google.com`
supporting-doc links in BigQuery — deliberately not backfilled, the generators
rewrite them to `drive.google.com/file/d/<id>/view` at render time (any
non-dashboard consumer of `supporting_doc_url` needs the same rewrite).

**The cloud refresher's template is a SNAPSHOT and goes stale.** The gated
refresher on branch `claude/website-auto-refresh-efficiency-9x474j`
(`refresh_artifact_dashboard.py` + `dashboard_template.html`) renders from a
copy of the published page with the `const DATA` / `const KPI` literals swapped
for `/*DATA*/` / `/*KPI*/`. When the artifact's design changes anywhere else
(e.g. the Mac generators adding the validation UI), that snapshot silently
falls behind and republishing it **downgrades the live page**. Caught 2026-08-07:
the snapshot predated the Validated column entirely, and its query projected 13
columns with no validation fields — `normalize()` also whitelists fields, so
both the SELECT *and* the whitelist need the new columns. Fix procedure: WebFetch
the live artifact, extract from `<title>` to the last `</script>`, restore the
two placeholders, and confirm every `r.<field>` the template reads is emitted by
`normalize()`. Do this whenever the page design changes.

**The Marketplace Shipments portal** is the second artifact — Target, Macy's,
Michaels and Shopify orders, searchable by order number, customer name or
tracking (`https://claude.ai/code/artifact/53c82d03-9788-4ac2-a2a3-ca5322ad458f`).
Built by this repo's `refresh_marketplace_shipments.py` straight off the
marketplace feeds already in BigQuery (`acenda`, `macys`, `shipstation`) — no
schedule, republish with `url:` like the Yusen one. Three facts it is built
around: ShipStation's *shipment* feed stopped loading in Oct 2023, so
Michaels/Shopify rows have no ship date or tracking, and so no shipping cost
until `--3pl` recovers all three from the weekly warehouse shipped-order reports
(keyed by order number; strip the `THP` prefix and `-N` suffix off a Michaels
order to match); Target Plus redacts customer names ~45
days after the order and the sync rewrites the rows in place, which is why
`sql/marketplace_shipments_setup.sql` defines a durable ledger table whose MERGE
never overwrites a captured fact with a blank; and **no order feed carries what
shipping cost** (acenda's `cost` is 0.00 on every row), so `--costs` joins the
FedEx/Stamps invoice exports by tracking number. Those stacked Drive sheets
repeat the same invoice line across overlapping weekly exports — de-dupe on
(tracking, date, amount) or CPU comes out ~3x high. The durable fix is
`marketplaces.parcel_charges`, loaded weekly from the same files the shipping
cost report downloads. Note the two carriers differ on lag: FedEx bills weeks
behind, but **Stamps.com print history is same-day**, so an unpriced Stamps
shipment means nobody loaded a current export. Full detail:
`MARKETPLACE-SHIPMENTS.md`.

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
- `validation-reports/` — per-invoice markdown report cards, written on
  request, plus the consolidated MSA dispute report.
- `sql/` — one-off BigQuery scripts (e.g. the 2026-08-05 disputed-status
  backfill); run from the Mac, once each.
- `VALIDATION-AUTOMATION.md` — the validate-on-ingest design + Mac punch list
  (backfill → dashboard → skill v1.2.0 disputed hook → post-ingestion launchd
  sweep).
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
  **BigQuery via the cloud proxy is READ-ONLY** — `SELECT` against
  `bigquery.googleapis.com` works with proxy-injected auth (curl the REST API
  directly), but DML/ALTER return permission-denied. All writes (stamps,
  backfills, `--init`) run from the Mac's gcloud ADC. Notion/Drive/Gmail/Slack
  MCP connectors work in cloud; Chrome automation does not; there is **no `gh`
  CLI** — use the GitHub MCP tools.
- **PDF tooling:** the container's `pypdf` is broken until
  `pip install cryptography cffi`; `apt-get install tesseract-ocr
  poppler-utils` works (needed for the scanned SC VAS invoices).
- **Repo scope:** cloud sessions are scoped to one repo owner — a session on
  this repo cannot attach or push to `americanflat/*` repos (cross-tier), and
  Gmail MCP cannot download attachments (ask for the file, or via Drive).
- **Dashboard:** `~/yusen_invoices_dashboard.html` and `refresh_yusen_dashboard.py`
  are local-to-the-Mac; skip dashboard refreshes in cloud sessions.

## Conventions

- **Use plain language with Anthony** (standing preference, 2026-08-06). Skip
  jargon like "DML", "ACL", "principal", "idempotent" — say "database write",
  "permission list", "account", "safe to re-run". Explain what a command does
  in normal words before showing it.

- Local (Mac) commits go directly to `main`; cloud sessions push to their
  designated feature branch, with a PR when Anthony wants review (PR #1 set
  the pattern). Messages are imperative summaries with a body explaining the
  why (see `git log`).
- **NO DELETE ANYTHING** (standing rule, Anthony 2026-08-05). Never run *or
  suggest* `rm`, `rsync --delete`, `git clean`, `git reset --hard`, force flags,
  `mv` onto an existing path, or `>` truncation of an existing file. Copies are
  additive only, into freshly created directories. If removal is genuinely
  needed, move the item to a dated quarantine folder
  (`~/quarantine/YYYY-MM-DD/`) as its own separately approved step — never
  bundled into a larger command. All multi-command blocks chain with `&&` so a
  failure stops the chain.
- Commits go directly to `main`; messages are imperative summaries with a body
  explaining the why (see `git log`).
- Payment status (`paid_at`) is written **only** on explicit user confirmation —
  never inferred, never from "OK to pay" verdicts. SP/LTL invoices additionally
  require a Stedi order-level pass before payment marking.
- Invoice-billing convention: e-com **pick charges invoice at exactly half the
  supporting-worksheet pick-column sum** (the worksheet counts pick+pack
  events) — the invoice never matches the raw worksheet total.
