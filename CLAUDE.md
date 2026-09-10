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

- `yusen-invoice-validator.skill` — the packaged zip, **now v1.6.0** and NOT a dead
  artifact: the nightly cloud validator unzips this very file and imports it (see
  Who actually validates, below). Changing validator behaviour in the cloud means
  repackaging and committing this. The superseded 1.5.0 zip is kept beside the
  release scripts in `skill-updates/v1.6.0/superseded/`.
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

## Who actually validates (checked 2026-09-10, not inferred)

The ledger has more than one writer, and they disagree. Before concluding anything
about why a row reads the way it does, establish which one wrote it.

**The live validator is a cloud Routine, not the Mac skill.** Every one of these is
a Claude session that reads a runbook **from branch `main-07xt41` of this repo** and
executes it. The sweep runbook unzips the committed `yusen-invoice-validator.skill`
into `/tmp/skill` and imports `validate_rate_card` from it, so **the deploy path for
cloud validator behaviour is: edit the skill, repackage, commit the `.skill`, push
to `main-07xt41`** — no Mac and no published skill repo involved.

Real trigger IDs, read from `list_triggers` on 2026-09-10 (an earlier note here
guessed one of these wrong — check, don't copy):

| Routine | id | cron (UTC) | on? | does |
|---|---|---|---|---|
| `yusen-nightly-validation-2am-mt` | `trig_016vL18kChzAxpv7tfZjqzyS` | `0 8 * * *` | yes | phase 1 contract, then phase 2 Stedi |
| `yusen-cloud-validation-sweep-midday` | `trig_01GQSfBrEkUVPJj6MqbkSn5D` | `0 17 * * *` | yes | contract only, no Stedi |
| `yusen-stedi-nightly` | `trig_019Drs2eEgyRt9G3DPu8rwJS` | `0 6 * * *` | **no** — disabled 2026-09-10 | superseded by the nightly's phase 2 |
| `refresh-yusen-artifact-830am-330pm` | `trig_01YG7tbcgDnpBRKkxo1KDHok` | `30 12,19 * * 1-5` | yes | dashboard |
| `refresh-yusen-artifact-noon-6pm` | `trig_01PrPh79KQSXtmK2fK9MBBVr` | `0 16,22 * * 1-5` | yes | dashboard |

The **midday pass was re-enabled 2026-09-10** (Anthony) as a second chance the same
day, now that phase 1 actually runs. Its schedule was `0 14,17 * * *` (two firings);
cut to the single `0 17 * * *` = 11:00 MT, since one pass serves the purpose. It is
**contract-only and must never call Stedi** — those lookups are metered and the
nightly owns them. Its prompt was rewritten at the same time: the old one described
itself as one of a three-a-day scheme that no longer exists, and enabling it on that
text would have been worse than leaving it off.

**`yusen-stedi-nightly` is disabled** (Anthony, 2026-09-10). It ran the same
`STEDI-NIGHTLY-RUNBOOK.md` that the nightly validation runs as its phase 2, but at
06:00 UTC — two hours *before* phase 1, i.e. the shipping axis ahead of the contract
axis, the reverse of the order that exists so a row clearing both gets stamped the
same night. The Stedi runbook had claimed since 2026-08-11 that this Routine was
"retained but disabled"; it was not, it was enabled and firing every morning
(`last_fired_at` 2026-09-10T06:08). **The listing's `last_run` field was empty,
which is not the same as never firing — check `last_fired_at`.**

It wrote nothing on any of those runs, and the likely reason is now guarded: steps
3 and 4 of that runbook execute scripts from `/tmp/skill/`, which **only phase 1's
step 2 ever created**. Run standalone there was no phase 1, so the scripts were
never there. A new "Guard 0b" in the Stedi runbook checks for them and unzips the
package itself if missing — which also makes the nightly prompt's "if phase 1 fails,
still attempt phase 2" actually possible, instead of a no-op. Tested from both a
warm and an empty `/tmp`.

**The cloud run owns the ledger** (Anthony, 2026-09-10). The Mac sweep
`com.americanflat.yusen-validator-sweep` is to be `launchctl unload`ed — steps and
rollback in `mac-handoff/hand-the-ledger-to-the-cloud.md`. It had been the only
thing actually writing, on v1.4.0 with the pre-MSA Notion card, which is why every
one of the 66 storage rows quoting a rate quoted the legacy figure ($5.90 Fontana /
$5.98 NJ / $5.09 SC) while the committed package's card holds the MSA rates and its
code reads `rates["storage"][site]`. The packaged validator cannot produce those
notes; that is how you tell the two writers apart in the data.

**Why the cloud run wrote nothing for a month, and the lesson.** Step 2 of the
sweep runbook began `cd ~/americanflat-ops-director`. In the container `$HOME` is
`/root` and the repo is under `/home/user/`, so the `cd` failed, `unzip` found no
archive, `VALIDATOR_OK` never printed, and the runbook's own guard then stopped the
sweep — correctly, on a false premise. Every night: SUCCEEDED, 82 seconds, zero
rows, 56 invoices waiting. Fixed 2026-09-10; the runbook now derives the repo root
from `git rev-parse --show-toplevel` and **forbids `~` outright**. Never use `~` in
a runbook a cloud Routine executes.

A second latent break of the same shape: step 4 calls `apply_vas_pallet_check` and
`apply_vas_labor_check` (v1.6.0+) while the preflight admitted anything 1.4+, so a
1.5.x package passed the gate and died mid-step-4. The preflight now greps for the
functions it is about to call.

**"The Routine succeeded" does not mean it wrote anything.** Both runbooks exit
quietly when there is nothing to do, so a clean finish is not evidence of work.
Check `MAX(validated_at)` before believing a run did something — it is the only
number that distinguishes a real sweep from a skipped one.

**The cloud path is proven end to end** (2026-09-10, from a cloud session): the
write probe succeeds, the whole ledger reads over REST, Drive returns invoice PDFs
(they spill to a tool-results file — decode with a script, never read the base64
into context), and 758665 went `needs_detail` -> `valid` on 3,528 pallets x $4.34 =
$15,311.52, exact. No Mac involved.

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
- **`validation_report` is an append-only stack of dated blocks**, and each pass
  owns exactly one tag: `[AUTO …]` (header sweep), `[MSA REVAL …]`,
  `[DEEP PASS …]` (in-conversation itemized review), `[STEDI …]`, `[MSA DISPUTE …]`,
  `[PAID …]`. **Never assign the field directly — always splice via
  `merge_report(prior, block, tag=…)`.** Through v1.4.0 `--mark-paid` wrote
  `validation_report = COALESCE(@report, validation_report)`, a full replace, so
  every payment mark silently discarded the row's history; on 2026-08-11 it wiped
  the itemized math and the 106/106 and 289/289 Stedi results off 754891 and
  755265 (1,741/1,644 chars → 386), recoverable only from BigQuery's 7-day table
  history. A settled row is never re-swept, so nothing rebuilds it. Fixed in
  v1.5.0; restore SQL in `sql/restore_clobbered_reports_2026-08-11.sql`.
  Related rule: a **header-level pass must not talk over a deeper one** — when a
  `[DEEP PASS]`/`[STEDI]`/`[MSA DISPUTE]`/`[MSA REVAL]` block is already on the row,
  a `needs_detail` result writes a one-line "no new findings, see above" instead of
  its usual "provide itemized counts / no Stedi result" card, which otherwise reads
  as the current verdict (the AUTO block is written last) and makes a finished
  invoice look unfinished.
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

**What the Routines actually run is NOT in this repo.** Both firings clone
`americanflat/Ops` and run `tools/yusen_dashboard_refresh.py run --published
<the file the Artifact read saved>`; that tool carries its own page template and
uses the published file only to recover the fingerprint (nothing in the cloud
environment can store it — the BigQuery state write is denied and the Ops repo is
read-only to the firing session). A session scoped to `anthony-amf` cannot reach
`americanflat/Ops`, so **the template that actually publishes the page can only be
edited from the Mac or an Ops-scoped session.** This repo's
`refresh_artifact_dashboard.py` + `dashboard_template.html` are the earlier
version of that same tool, kept here because they are editable from a cloud
session and are the reference copy of the page's design.

**Any such template is a SNAPSHOT and goes stale.** It is the published page with
the `const DATA` / `const KPI` literals swapped for `/*DATA*/` / `/*KPI*/`, so when
the page's design changes anywhere else, the snapshot silently falls behind and
republishing it **downgrades the live page**. This has now happened twice. 2026-08-07:
the snapshot predated the Validated column entirely, and its query projected 13
columns with no validation fields — `normalize()` also whitelists fields, so both
the SELECT *and* the whitelist need the new columns. 2026-09-03: a publish dropped
the sticky column headers and the whole mark-paid basket, and the loss went
unnoticed for six days because the gate reported NO_CHANGE and nobody diffed the
page. Restored 2026-09-09 (the CSS recovered byte-for-byte from a saved diff; the
basket's JS had to be rewritten).

So the check is now mechanical, not a procedure to remember: pass
`--published <live page>` to `refresh_artifact_dashboard.py` and it compares the
template against the live page with both literals blanked. Any difference at all
and it refuses, prints the diff and queries nothing. `--accept-template-drift`
overrides it — that is how a deliberate design change ships. **The Ops copy has no
such guard yet; adding one there is what actually protects the page.** Also still
worth confirming by hand when the design changes: every `r.<field>` the template
reads must be emitted by `normalize()`.

`~/yusen_invoices_dashboard.html` is the local twin — a static snapshot with an
embedded `const DATA = [...]` array, refreshed by this repo's
`refresh_yusen_dashboard.py`. Other processes re-export it from a base template,
wiping the Validated/Paid columns — the refresher is idempotent and re-applies
its columns/chip helpers plus fresh data every run. When adding dashboard
features, extend the patcher's add-if-missing / upgrade-if-stale pattern; a
plain string replace will double-insert.

## Other directories

- **Two launchd jobs are live on the Mac** (verified `launchctl list`, 2026-08-12) —
  `com.americanflat.yusen-validator-sweep` (last exit 0; sweeps all ~335 rows
  several times a day on **v1.4.0**, so it keeps rewriting `[AUTO]` blocks in the
  superseded format) and `com.americanflat.yusen-invoice-processor` (last exit
  **1 — failing**; this is the Yusen ingestion job, own org repo
  `skill-yusen-invoice-processor`, *not* `skill-invoice-to-bigquery`, which targets
  `finance.freight_invoices`). Earlier notes claiming the sweep was unloaded on
  2026-08-06 were wrong. Check `launchctl list | grep -i yusen` before concluding
  anything about what writes to the ledger.
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
  **BigQuery reads AND WRITES work from a cloud session** — `SELECT` and `UPDATE`
  both go through `bigquery.googleapis.com` with proxy-injected auth (curl the REST
  API directly). Verified 2026-09-09: thirteen `[STEDI]` stamps written from a cloud
  session, and again 2026-09-10 reading the whole ledger. The older note here said
  writes were denied and that all stamps had to run from the Mac's gcloud ADC; that
  is wrong and it nearly stopped a cloud sweep being attempted at all. Table
  creation (`tables.create`) is still not granted, so `--init` remains a Mac job. Notion/Drive/Gmail/Slack
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
