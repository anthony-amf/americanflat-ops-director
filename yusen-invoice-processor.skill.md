# skill-yusen-invoice-processor — complete skill bundle

Single-file markdown export of the entire skill directory (`~/skill-yusen-invoice-processor`), generated 2026-07-14. Each section below is the verbatim content of one file, in a fenced block. Includes the three post-review patches: NL/intl handling, scanned-PDF Slack alert, and Drive /file/d/ link fix.

## Contents

- [`skill.toml`](#skilltoml)
- [`SKILL.md`](#skillmd)
- [`README.md`](#readmemd)
- [`CHANGELOG.md`](#changelogmd)
- [`.env.example`](#envexample)
- [`requirements.txt`](#requirementstxt)
- [`references/classification.md`](#referencesclassificationmd)
- [`references/international.md`](#referencesinternationalmd)
- [`scripts/invoice_processor.py`](#scriptsinvoice-processorpy)
- [`scripts/intl_invoices.py`](#scriptsintl-invoicespy)
- [`scripts/generate_yusen_dashboard.py`](#scriptsgenerate-yusen-dashboardpy)

## `skill.toml`

````toml
[skill]
name = "skill-yusen-invoice-processor"
version = "0.1.1"
description = "Pulls Yusen/Taylored 3PL invoices (US, Canada, Netherlands) from Gmail, parses them by warehouse and charge type, and appends to the americanflat.finance.yusen_invoices BigQuery table (append-only, native currency). The daily run auto-inserts high-confidence rows and Slacks the rest; also rebuilds the dashboard."
owner = "Anthony Armstrong <anthony@americanflat.com>"
tier = 2
department = "ops"
language = "python"

[environment]
requires_network = true
requires_secrets = true
stdlib_only = false
python = "3.13"

[compatibility]
platforms = ["macos", "linux"]
providers = ["anthropic"]
````

## `SKILL.md`

````markdown
---
name: skill-yusen-invoice-processor
description: >-
  Operate the Yusen / Taylored Service 3PL invoice pipeline for Americanflat — pull invoices
  from Gmail, parse the US (Taylored: NJ / Fontana / Savannah), Canada (Yusen CA), and
  Netherlands (Yusen NL / Benelux) formats, classify each charge into Admin / Receiving /
  SMLPRCL·LTL / Storage / VAS, and append rows to the americanflat.finance.yusen_invoices
  BigQuery table (append-only, native currency), then rebuild the invoice dashboard. Use this
  whenever the user mentions Yusen or Taylored invoices, the yusen_invoices table, the daily
  invoice processor / invoice_processor.py, ingesting or (re)classifying a 3PL invoice, the
  invoice dashboard, a new warehouse or invoice format, or Canada / Netherlands / EUR invoice
  handling — even if they don't name the script. Do NOT use it to audit one invoice against a
  rate card (that's yusen-invoice-validator) or for generic PDF→BigQuery ingestion of non-Yusen
  bills (that's skill-invoice-to-bigquery).
---

# Yusen invoice processor

Pulls Yusen/Taylored 3PL invoices from Gmail, parses them, archives the PDF to Drive, and
**appends** rows to `americanflat.finance.yusen_invoices`. A daily run auto-inserts
high-confidence rows and Slacks the rest for review. A companion script rebuilds a
self-contained dashboard from the table.

**Read `README.md` first** for setup (env vars, OAuth, `bq` access) and the exact run commands.

## The one rule that overrides everything

**The table is append-only. Never delete, truncate, overwrite, or `CREATE OR REPLACE` it,
and never drop rows.** Corrections are done with a targeted, guarded `UPDATE` (or a single
guarded `DELETE` of a clearly-identified junk/test row) — and only with the user's explicit
go-ahead. The processor itself only ever `INSERT`s.

## Scripts (in `scripts/`)

- `invoice_processor.py` — the entry point. Gmail discovery → download → parse → Drive upload
  → BigQuery append. Modes: interactive preview (default), `--auto` (daily), `--dry-run`.
  Flags: `--intl` (also process Canada/NL; or env `YUSEN_INTL=1`), `--since` / `--until`
  (bound a historical load), `--max`.
- `intl_invoices.py` — Canada & Netherlands parsers (uses **pdfplumber**; imported by the
  processor). See `references/international.md`.
- `generate_yusen_dashboard.py` — rebuilds `~/yusen_invoices_dashboard.html` (multi-currency,
  per-currency totals, clickable PDF/doc links, filters). Read-only on the table.

## Common tasks

**Run / backfill.** Use the commands in `README.md`. Prefer `--dry-run` first to see what
would be ingested. For a historical backfill, bound it with `--since`/`--until`. After a US
backfill, regenerate the dashboard.

**Reclassify a stored row.** The user will say e.g. "752504 is a receiving invoice." Confirm
against the PDF/notes (see `references/classification.md`), then run a guarded in-place
`UPDATE` (e.g. `SET type_of_invoice = 'Receiving' WHERE invoice_number = '752504' AND
type_of_invoice = 'Admin'`). Verify the affected row count. This is the one sanctioned
mutation besides INSERT — keep the `WHERE` tight so only the intended row(s) match.

**Audit / "make sure they're classified right."** Pull the rows, classify each **blind** (hide
the stored type to avoid confirmation bias), reconcile predicted vs stored, and read the PDFs
for any disagreement. Apply corrections only after the user confirms. See
`references/classification.md`.

**Add a warehouse or a new invoice format.** US logic lives in `parse_invoice_data`
(`invoice_processor.py`); CA/NL logic in `intl_invoices.py`. New international charge
descriptions that don't map to a known type fall to **VAS, flagged** for review — extend the
mapping there. New senders/subjects go in the discovery query (`build_query` /
`INTL_QUERY_CLAUSES`). A corrected reissue that supersedes an earlier invoice goes in
`SUPERSEDED_INVOICES` so it doesn't double-count.

**Regenerate the dashboard.** `python3 scripts/generate_yusen_dashboard.py`. It pulls the live
table; amounts render in native currency and totals are kept per-currency (USD and EUR are
never summed together).

## Classification & formats

Don't guess from memory — the rules and traps are documented:

- **`references/classification.md`** — the five `type_of_invoice` values and their PDF-body
  signals; the **CONTAINER ADMIN FEE trap** (a receiving line item that must not read as
  Admin); boilerplate-notes rows (read the PDF — almost always Receiving); the warehouse list.
- **`references/international.md`** — Canada (USD, GST-inclusive) and Netherlands (EUR,
  VAT-inclusive, native currency) formats; one row per service type; parse NL transport
  **page 1 only**; NL transport emails bundle **multiple PDFs**; superseded-invoice handling;
  currency is stored, not converted.

## Tier 2 — notify behavior

In `--auto`, high-confidence rows (no flags) insert automatically; flagged rows (low-confidence
field, ambiguous type, unparsed international line items) are **not** inserted — they DM the
configured Slack user (`SLACK_USER_ID`) once each and wait for a human. If Slack isn't
configured, flagged rows are simply held (logged), never silently inserted. Re-running after a
blocker clears picks them up; the BigQuery `invoice_number` set is the authoritative dedupe, so
re-runs never double-insert.
````

## `README.md`

````markdown
# skill-yusen-invoice-processor

Ingests Yusen / Taylored Service 3PL invoices for Americanflat and loads them into the
`americanflat.finance.yusen_invoices` BigQuery table, then rebuilds a self-contained invoice
dashboard. Handles US (Taylored: NJ / Fontana / Savannah), Canada (Yusen CA), and Netherlands
(Yusen NL / Benelux) invoice formats.

- **Tier 2** (writes with notify): it appends to BigQuery and DMs Slack on anything it
  doesn't auto-insert. It is **append-only** — it never deletes, truncates, or overwrites the
  table.
- **Owner:** Anthony Armstrong (anthony@americanflat.com), Ops.

## What's in here

| File | Role |
|---|---|
| `scripts/invoice_processor.py` | Gmail → parse → Drive archive → BigQuery append. The entry point. |
| `scripts/intl_invoices.py` | Canada / Netherlands parsers (imported by the processor). |
| `scripts/generate_yusen_dashboard.py` | Rebuilds the standalone HTML dashboard from the table. |
| `references/classification.md` | The five `type_of_invoice` values, their signals, the CONTAINER ADMIN FEE trap. |
| `references/international.md` | Canada / NL formats, currency, superseded-invoice handling. |

## Prerequisites

- **Python 3.10+** (developed on 3.13). Third-party deps (`google-api-python-client`,
  `slack_sdk`, `PyPDF2`, `pdfplumber`, `certifi`) are pip-installed automatically on first run.
- **`bq` / gcloud SDK** authenticated against the `americanflat` GCP project with read+insert
  on `finance.yusen_invoices`. (`bq` must be on `PATH`, or set `CLOUDSDK_BIN_PATH`.)
- **Google OAuth client** (Gmail + Drive scopes) — a `client_secret*.json` from the Google
  Cloud console. The mailbox it authorizes must receive the Yusen/Taylored invoice emails.
- **Slack bot token** (optional) for review notifications.

## Setup

1. `cp .env.example .env` and fill it in (see comments in `.env.example`):
   - `YUSEN_GMAIL_CREDENTIALS` → path to your OAuth `client_secret*.json`
   - `SLACK_BOT_TOKEN`, `SLACK_USER_ID` → for review DMs (leave blank to disable Slack)
   - `YUSEN_INTL=1` → enable Canada/Netherlands processing (default: US only)
2. First run opens a browser to authorize Gmail+Drive; the token caches to
   `~/.invoice_token_v2.pickle`.
3. Confirm `bq query 'SELECT COUNT(*) FROM \`americanflat.finance.yusen_invoices\`'` works.

`.env`, the cached token, and generated output are gitignored — never commit them.

## Running

```bash
# Interactive preview (review/edit, then approve insert):
python3 scripts/invoice_processor.py

# Daily automated mode — auto-insert high-confidence rows, Slack the rest:
python3 scripts/invoice_processor.py --auto

# Parse + print only, never insert:
python3 scripts/invoice_processor.py --dry-run

# Also process Canada/Netherlands (or set YUSEN_INTL=1):
python3 scripts/invoice_processor.py --auto --intl

# Bound a historical backfill:
python3 scripts/invoice_processor.py --dry-run --intl --since 2026/03/01 --until 2026/06/01

# Rebuild the dashboard from the live table:
python3 scripts/generate_yusen_dashboard.py   # writes ~/yusen_invoices_dashboard.html
```

## Daily schedule (macOS launchd)

Run `--auto` on a schedule. Set `YUSEN_INTL=1` in the job's environment to include CA/NL, and
ensure `bq`/gcloud are on the job's `PATH` (launchd's default `PATH` is minimal). A cron/systemd
timer works equally on Linux.

## The BigQuery table

`americanflat.finance.yusen_invoices` columns: `date`, `bill_period`, `invoice_number`,
`type_of_invoice`, `warehouse`, `amount` (NUMERIC), `currency`, `notes`, `ingested_at`,
`pdf_url`, `supporting_doc_url`. International invoices yield one row per service type, with the
invoice number suffixed by type (e.g. `FTI0006387-Storage`). See `references/` for the
classification rules and per-country formats.

**Safety:** the processor only ever `INSERT`s, and verifies the table exists before running —
it never creates, deletes, truncates, or alters it.
````

## `CHANGELOG.md`

````markdown
# Changelog

All notable changes to skill-yusen-invoice-processor are documented here.

## 0.1.1 — 2026-07-01

Idempotent loads. Fixes the 2026-06-30 incident where the daily `--auto` run re-inserted 10 Yusen NL/Canada rows that a manual session had loaded five hours earlier, double-counting ~€47K.

- **Duplicate guard no longer truncates**: the existing-invoice query now passes `--max_rows` explicitly — `bq query` returns only 100 rows by default, so the guard went blind once the table passed 100 distinct invoice numbers.
- **Fail closed**: if the existing-invoice query fails or can't be parsed, the run aborts instead of proceeding with an empty dedupe set.
- **Pre-insert re-check**: `insert_rows` re-queries the table for the batch's invoice numbers immediately before writing and skips any already present, guarding against concurrent/manual loads between startup and insert.
- **Durable processed-emails log**: moved from `/tmp` (purged by macOS, not shared with sandboxed manual runs) to `~/.yusen/processed_emails.json`, with automatic migration from the legacy path.

## 0.1.0 — 2026-06-30

Initial release. Packages the Yusen/Taylored 3PL invoice pipeline as an Americanflat skill.

- **Gmail → BigQuery ingestion** (`scripts/invoice_processor.py`): discovers Yusen/Taylored invoice emails, downloads PDFs, parses them, archives the PDF to Drive, and appends rows to `americanflat.finance.yusen_invoices` (append-only — never deletes/overwrites). Modes: `--auto` (daily, auto-insert high-confidence + Slack the rest), preview (interactive), `--dry-run`.
- **International parsers** (`scripts/intl_invoices.py`): Canada (Yusen CA, USD, GST-inclusive) and Netherlands (Yusen NL/Benelux, native EUR, VAT-inclusive) formats, each exploded into one row per service type. Gated behind `--intl` / `YUSEN_INTL=1`.
- **Dashboard** (`scripts/generate_yusen_dashboard.py`): regenerates a self-contained, multi-currency HTML dashboard (per-currency totals, clickable PDF/doc links, filters).
- **Secrets externalized** to environment variables (`SLACK_BOT_TOKEN`, `SLACK_USER_ID`, `YUSEN_GMAIL_CREDENTIALS`); see `.env.example`. Nothing sensitive is committed.
````

## `.env.example`

````bash
# Copy to .env and fill in. .env is gitignored; never commit it.

# --- Slack notifications (Tier 2 "notify") ---
# Bot token (xoxb-...). Leave blank to run without Slack alerts — the pipeline
# still ingests and processes; it just won't DM on flagged/low-confidence rows.
SLACK_BOT_TOKEN=
# Slack user ID to DM with review alerts (e.g. U0XXXXXXX). Blank disables Slack.
SLACK_USER_ID=

# --- Google (Gmail + Drive) OAuth ---
# Path to the OAuth client_secret JSON downloaded from the Google Cloud console
# (Gmail + Drive scopes). First run opens a browser to authorize; the token is
# cached at ~/.invoice_token_v2.pickle thereafter.
YUSEN_GMAIL_CREDENTIALS=

# --- Optional behavior ---
# Absolute path to a secrets env file the loader reads FIRST (e.g. ~/.yusen/yusen.env).
# Usually set in the launchd plist / your shell, not inside .env itself.
YUSEN_ENV_FILE=
# "1" enables Canada/Netherlands invoice processing (default off; US only).
YUSEN_INTL=
# EUR->USD fallback rate used only if a live/pinned rate is unavailable (default 1.08).
# NOTE: by current design NL invoices are stored in native EUR, so this is rarely used.
YUSEN_EUR_USD_FALLBACK=

# --- Optional: gcloud SDK location (dashboard generator) ---
# Only needed if `bq` is not already on PATH.
CLOUDSDK_BIN_PATH=
CLOUDSDK_PYTHON=
````

## `requirements.txt`

````text
# Third-party dependencies for skill-yusen-invoice-processor.
# The scripts also install these at first run, but they are declared here so the
# dependency set is explicit (required because skill.toml sets stdlib_only = false).
google-auth-oauthlib
google-auth-httplib2
google-api-python-client
slack-sdk
openpyxl
PyPDF2
pdfplumber
certifi
````

## `references/classification.md`

````markdown
# Invoice classification (type_of_invoice)

`americanflat.finance.yusen_invoices.type_of_invoice` has **five canonical values**.
For US (Taylored) invoices the type is signalled by the PDF **body** — specifically the
text *above* the payment block ("MAKE CHECKS PAY…"); the legal boilerplate below it
contains words like "STORAGE" (warehouseman's-lien clause) that cause false matches, so
it is deliberately ignored.

| Type | Body signals |
|---|---|
| **Receiving** | `INBOUND PROCESSING` / `RECEIVED CARTONS` / `RECEIVING SORTATION` |
| **SMLPRCL/LTL** | `OUTBOUND PROCESSING` / `SMALL PARCEL SHIPMENTS` / `TRUCK SHIPMENTS` |
| **Storage** | `STORAGE` / `WEEKLY STORAGE` / `STORAGE BILLING FOR THE WEEK` / per-pallet rates |
| **Admin** | `ADMINISTRATIVE SUPPORT` / `BACK OFFICE` (and `ADMIN FEE`, but NOT `CONTAINER ADMIN FEE`) |
| **VAS** | `VAS #`, RELABEL/RE-LABEL, REPACK, REMARK CARTONS, PALLET LABEL(S), P65 / Cancer Warning Labels, strap/tape, consolidation, Returns, BREAK DOWN PALLETS |

Write the value **exactly** as shown (including `SMLPRCL/LTL`).

## The CONTAINER ADMIN FEE trap

Receiving invoices carry a `CONTAINER ADMIN FEE` line item. A naive "ADMIN FEE" match
tags them **Admin** — that's how invoice 752504 was mis-stored before correction. Two
guards in `parse_invoice_data` (see `scripts/invoice_processor.py`) prevent it:

1. Receiving keywords are checked **before** Admin (order matters).
2. The Admin rule explicitly excludes `CONTAINER ADMIN FEE`.

So a receiving invoice missing its INBOUND header still can't fall through to Admin.

## Boilerplate-notes rows

Some Receiving invoices have **no descriptive line item** — their only "notes" text is the
Yusen legal boilerplate beginning *"No action may be maintained by Client or the holder of a
valid warehouse receipt…"*. When you see that as the only signal, **read the PDF**: it is
almost always Receiving (look for `INBOUND PROCESSING` / `RECEIVED CARTONS`). The notes
extractor now captures the `INBOUND PROCESSING…` line so new receiving rows get a real
description instead of boilerplate.

## Warehouses

`TS East (NJ)`, `TS West (CA)` (Fontana — California, **not** Canada), `TS South (SC)`
(Savannah), `Yusen CA` (Canada — Brampton), `Yusen NL` (Netherlands — Moerdijk/Benelux).
Warehouse is read from the PDF body (`LOC #31 NEW JERSEY`, `FONTANA`, `SAVANNAH`,
`MOERDIJK`/`BENELUX`) and falls back to the email subject when absent.

## Verifying classification

A blind two-pass + PDF ground-truth audit (2026-06-29) confirmed all then-current US/Canada
rows were correctly classified. When auditing: hide the stored type from the classifier
(avoid confirmation bias), classify from evidence, then reconcile against what's stored, and
read the PDFs for any disagreement.
````

## `references/international.md`

````markdown
# International invoices (Canada & Netherlands)

Canada and Netherlands invoices are parsed by `scripts/intl_invoices.py`, separate from the
US Taylored flow. They use **pdfplumber** (PyPDF2 scrambles their table layouts). Each is a
single PDF bundling several service types, **exploded into one BigQuery row per mapped
`type_of_invoice`**, with the invoice number suffixed (e.g. `FTI0006387-Storage`). Amounts
are **tax-inclusive** and stored in the invoice's **native currency** — no FX conversion
(see "Currency" below). Processing is gated: off unless `--intl` or `YUSEN_INTL=1`.

## The three streams

| Stream | Detect / sender | Invoice # | Date | Currency | Charges → type |
|---|---|---|---|---|---|
| **Canada warehouse** | `INVOICE CA2WFS…`, `sayaka.ambo@ca.yusen-logistics.com`, subj "AMERICANFLAT - Invoice <Month> <Year>" | `CA2WFS0003352` | `30-Apr-26` (DD-Mon-YY) | **USD** | Storage/Warehouse → Storage; "WHS In/Out" → Receiving (ambiguous, flagged) |
| **NL handling & storage** | `Invoice FTI…`, `billing.mrd@bnl.yusen-logistics.com`, subj "Americanflat Invoice FTI… MM/YYYY" | `FTI0006387` | `31/05/2026` (DD/MM/YYYY) | **EUR** (European numerals `13.526,31`) | INBOUND→Receiving, OUTBOUND→SMLPRCL/LTL, STORAGE→Storage, ADMINISTRATION→Admin, CONSUMABLES+VAL→VAS; **any other line → VAS, flagged** |
| **NL land transport** | `INVOICE CA26…`, `transport.rtm@`/`piotr…@bnl.yusen-logistics.com`, subj "INVOICE YUSEN NL: CA…" | `CA26200110` | `29/05/2026` (DD/MM/YYYY) | **EUR** (US numerals `1,608.99`) | all `Transport - …` → SMLPRCL/LTL |

Notes:
- **NL transport: parse page 1 only** — later pages repeat the charges per shipment (double-count risk).
- **NL transport emails bundle 2+ invoice PDFs** — `download_attachments` returns every PDF (`pdf_paths`), not just the first.
- **Tax**: Canada GST is per-line 13% (stored GST-inclusive → row total ties to the invoice grand total). NL transport adds 21% VAT (stored VAT-inclusive). NL handling is 0% export VAT (subtotal = total).

## Currency

Amounts are stored in native currency, tagged by the `currency` column (`USD`/`EUR`). **No
FX conversion** — Anthony's call: don't guess historical rates. The dashboard keeps
per-currency totals (never sums €+$) and the charts are USD-only. (`intl_invoices.eur_to_usd`
and the optional per-month rate file remain in code but are unused under this design.)

## Superseded invoices

A corrected reissue (same billing period, new invoice number) must not double-count. Skip it
via `SUPERSEDED_INVOICES` in `scripts/invoice_processor.py`. Example:
`FTI0006156` (02/2026, reissued 2026-03-04) supersedes `FTI0006124`.

## Mailbox

The processor reads `administrator@americanflat.com` (a catch-all that sees all three
streams). It may lag the very latest invoice (e.g. a just-sent Canada month); the daily run
picks it up once it lands. NL invoices also flow through bill.com for AP approval.

## Odd / unparseable layouts

The NL handling parser captures **any** line item; unknown descriptions (e.g.
`Implementation cost`, `TPM licentie`) map to **VAS, flagged** for review. If a detected
international PDF parses to **zero** line items, the pipeline Slack-alerts it rather than
silently dropping it.
````

## `scripts/invoice_processor.py`

````python
#!/usr/bin/env python3
"""
Gmail Invoice Processor
Pulls 3PL invoices (Taylored / Yusen Logistics) from Gmail and loads them into
the BigQuery table americanflat.finance.yusen_invoices.

SAFETY GUARANTEES
- READ-ONLY for the BigQuery table: only INSERT (append) is ever performed.
- It never deletes, truncates, recreates, or alters the table.
- Before each run it verifies the table exists; if not, it exits.

RUN MODES
  (default)    preview  -> parse, show a review table, let you approve/edit, then insert
  --auto                -> parse, auto-insert high-confidence rows, Slack-notify the rest
                           (this is the mode the daily Cloud Scheduler job uses)
  --dry-run             -> parse and print the table only; never inserts, never prompts

WHY A CONFIDENCE FLAG
The invoices vary in layout. Some state the warehouse explicitly in the body
("LOC #31 NEW JERSEY"), others only hint at it via the email subject ("Fontana CA"),
and a few line-item descriptions don't map cleanly to a single invoice type. Rather
than guess silently, the parser marks any uncertain field low-confidence so a human
reviews it (preview mode) or it routes to Slack instead of being inserted (auto mode).
"""

import os
import sys
import json
import base64
import argparse
import subprocess
import tempfile
import re
from datetime import datetime, timezone
import pickle

# Install dependencies quietly (no-op if already present)
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "google-auth-oauthlib", "google-auth-httplib2", "google-api-python-client",
                "slack-sdk", "openpyxl", "PyPDF2", "pdfplumber", "certifi"], check=False)

# Parsers for the international (Canada / Netherlands) Yusen invoices live in a
# sibling module. They use pdfplumber (PyPDF2 scrambles those table layouts).
# Ensure this script's own directory is importable regardless of the caller's CWD
# (launchd runs us by absolute path; a different CWD must not break the import).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import intl_invoices

# --- macOS Python SSL fix -------------------------------------------------
# The python.org build ships without a CA bundle, so HTTPS calls (Slack, Google)
# fail with CERTIFICATE_VERIFY_FAILED. Point the standard env vars at certifi's
# bundle BEFORE any networking library builds its SSL context.
import certifi
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from slack_sdk import WebClient
import PyPDF2


def _load_env_file():
    """Load KEY=VALUE pairs from a .env file into the environment (without
    overriding vars already set, so the launchd plist / shell win). Keeps secrets
    in a gitignored file instead of in code. Checks $YUSEN_ENV_FILE, then a .env
    beside or one level above this script, then ~/.yusen/yusen.env."""
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.environ.get("YUSEN_ENV_FILE"),
                 os.path.join(here, ".env"),
                 os.path.join(here, os.pardir, ".env"),
                 os.path.expanduser("~/.yusen/yusen.env")):
        if path and os.path.isfile(path):
            with open(path) as fh:
                for line in fh:
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            break


_load_env_file()


# --- Configuration --------------------------------------------------------
# Secrets and per-deployment config are read from the environment (.env) — never
# hardcode them. See .env.example for the full list. SLACK_* may be left unset to
# disable Slack notifications; the pipeline still inserts/processes without them.
GMAIL_CREDENTIALS = os.environ.get(
    "YUSEN_GMAIL_CREDENTIALS", os.path.expanduser("~/.yusen/gmail_client_secret.json"))
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_USER_ID = os.environ.get("SLACK_USER_ID", "")
GCP_PROJECT = "americanflat"
BIGQUERY_TABLE = "finance.yusen_invoices"
# Not /tmp: macOS purges it, and sandboxed manual runs (e.g. a Claude session)
# get their own /tmp, so a log written there is invisible to the launchd job —
# which is how the same email got processed twice on 2026-06-30.
PROCESSED_EMAILS_LOG = os.path.expanduser("~/.yusen/processed_emails.json")
LEGACY_PROCESSED_EMAILS_LOG = "/tmp/processed_emails.json"

# Google Drive archive. With the non-sensitive drive.file scope the app can only
# write into folders IT creates, so it owns a dedicated archive folder rather than
# a pre-existing human-made one. The folder ID is cached locally after first run.
DRIVE_FOLDER_NAME = "Yusen Invoices (auto-archive)"
DRIVE_FOLDER_CACHE = os.path.expanduser("~/.yusen_invoice_drive_folder.json")

# OAuth scopes. drive.file is NON-sensitive (app only touches files it creates),
# so it avoids the "restricted scope" verification wall that full drive scope hits.
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive.file",
]

# Invoice types that are expected to arrive with a supporting Excel workbook.
REQUIRES_SUPPORTING_DOC = {"SMLPRCL/LTL", "Storage", "Receiving"}

# International invoices superseded by a corrected reissue (same billing period,
# new number). Their exploded rows are skipped so the period isn't double-counted.
# FTI0006156 (NL handling, 02/2026, reissued 2026-03-04) supersedes FTI0006124.
SUPERSEDED_INVOICES = {"FTI0006124"}

# US Taylored / FMI invoices (subject "Invoice #..."), plus invoices manually
# forwarded by staff ("Fwd: Invoice # NNN" from an americanflat.com address) —
# the standard way to hand the pipeline an invoice that bypassed email (e.g.
# bill.com-only or rebilled invoices). The BigQuery dedupe makes re-forwards safe.
US_QUERY = ('subject:"Invoice #" (from:Taylored from:FMI OR from:no-reply@tpservices.com)'
            ' OR (subject:"Fwd: Invoice #" from:americanflat.com)')

# The three international Yusen streams use different senders/subjects and carry
# no "Invoice #" in the subject. They are OFF by default and only included when
# international processing is enabled (--intl flag or env YUSEN_INTL=1), so the
# daily --auto job's behaviour is unchanged until you opt in:
#   Canada warehouse      ca.yusen-logistics.com               "AMERICANFLAT - Invoice <Month> 2026"
#   NL handling & storage  billing.mrd@bnl.yusen-logistics.com  "Americanflat Invoice FTI... MM/YYYY"
#   NL land transport      transport.rtm@/...@bnl...            "INVOICE YUSEN NL: CA... "
INTL_QUERY_CLAUSES = (
    ' OR (from:ca.yusen-logistics.com subject:invoice)'
    ' OR (from:billing.mrd@bnl.yusen-logistics.com subject:invoice)'
    ' OR subject:"INVOICE YUSEN NL"'
)


def build_query(intl_enabled):
    inner = US_QUERY + (INTL_QUERY_CLAUSES if intl_enabled else "")
    return f'has:attachment -label:processed ({inner})'


# --- Processed-email tracking (dedupe) ------------------------------------
def load_processed_emails():
    # Fall back to the legacy /tmp location so an existing log migrates on the
    # first save instead of being forgotten.
    for path in (PROCESSED_EMAILS_LOG, LEGACY_PROCESSED_EMAILS_LOG):
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return []


def save_processed_email(email_id):
    processed = load_processed_emails()
    if email_id not in processed:
        processed.append(email_id)
    os.makedirs(os.path.dirname(PROCESSED_EMAILS_LOG), exist_ok=True)
    with open(PROCESSED_EMAILS_LOG, "w") as f:
        json.dump(processed, f)


# --- Auth -----------------------------------------------------------------
def authenticate():
    """Authenticate for both Gmail and Drive. Returns (gmail_service, drive_service).

    Uses a scope-versioned token file so that adding the Drive scope forces a
    fresh consent rather than silently reusing a Gmail-only token.
    """
    creds = None
    # Stable location (not /tmp, which macOS purges) so the daily job keeps its login.
    token_file = os.path.expanduser('~/.invoice_token_v2.pickle')
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS, OAUTH_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)
    gmail_service = build('gmail', 'v1', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)
    return gmail_service, drive_service


def ensure_drive_folder(drive_service):
    """Return the ID of the app-owned archive folder, creating it once if needed.

    drive.file confines the app to files it created, so the archive folder must be
    one the app makes itself. The ID is cached locally to avoid creating duplicates;
    if the cache is stale we search the app's own files by name before creating.
    """
    if os.path.exists(DRIVE_FOLDER_CACHE):
        try:
            fid = json.load(open(DRIVE_FOLDER_CACHE))["folder_id"]
            drive_service.files().get(fileId=fid, fields="id").execute()
            return fid
        except Exception:
            pass  # cache stale/unreadable — fall through to search/create
    try:
        res = drive_service.files().list(
            q=(f"mimeType='application/vnd.google-apps.folder' "
               f"and name='{DRIVE_FOLDER_NAME}' and trashed=false"),
            spaces="drive", fields="files(id,name)").execute()
        found = res.get("files", [])
        if found:
            fid = found[0]["id"]
        else:
            fid = drive_service.files().create(
                body={"name": DRIVE_FOLDER_NAME,
                      "mimeType": "application/vnd.google-apps.folder"},
                fields="id").execute()["id"]
            try:
                drive_service.permissions().create(
                    fileId=fid, body={"role": "reader", "type": "anyone"}).execute()
            except Exception:
                pass
            print(f"   ✓ Created Drive archive folder: "
                  f"https://drive.google.com/drive/folders/{fid}")
        json.dump({"folder_id": fid}, open(DRIVE_FOLDER_CACHE, "w"))
        return fid
    except Exception as e:
        print(f"   ✗ Could not create/find Drive archive folder: {str(e)[:160]}")
        return None


def upload_to_drive(drive_service, file_path, invoice_number, kind, folder_id):
    """Upload a file into the archive folder and return a shareable view link.

    `kind` is 'pdf' or 'xlsx', used only to name the stored file. Returns the
    webViewLink, or None on failure (failure must never block the BigQuery insert).
    """
    if not file_path or not os.path.exists(file_path) or not folder_id:
        return None
    try:
        ext = "pdf" if kind == "pdf" else "xlsx"
        meta = {"name": f"{invoice_number}.{ext}", "parents": [folder_id]}
        media = MediaFileUpload(file_path, resumable=False)
        f = drive_service.files().create(
            body=meta, media_body=media, fields="id, webViewLink").execute()
        try:
            drive_service.permissions().create(
                fileId=f["id"], body={"role": "reader", "type": "anyone"}).execute()
        except Exception:
            pass  # folder is already link-shared; file inherits it
        # Don't return webViewLink: for office files (xlsx) it's a docs.google.com
        # editor URL that fails without a signed-in Google session ("File could
        # not open"). The Drive previewer link works for anyone with the link.
        return f"https://drive.google.com/file/d/{f['id']}/view"
    except Exception as e:
        print(f"   ✗ Drive upload failed for {invoice_number}.{kind}: {str(e)[:160]}")
        return None


def send_slack_notification(invoice_number, email_link, message_body, ok=False):
    """DM the configured Slack user (SLACK_USER_ID). ok=True formats as info, else error.
    No-op when SLACK_BOT_TOKEN / SLACK_USER_ID are unset — the pipeline still runs."""
    if not (SLACK_BOT_TOKEN and SLACK_USER_ID):
        print(f"   ⊘ Slack not configured — skipping alert for invoice {invoice_number}")
        return
    try:
        client = WebClient(token=SLACK_BOT_TOKEN)
        icon = "🟡" if ok else "❌"
        header = "Invoice needs review" if ok else "Invoice processing error"
        text = (f"{icon} {header}\n\n"
                f"Invoice #: {invoice_number}\n"
                f"Email: {email_link}\n"
                f"{message_body}")
        client.chat_postMessage(channel=SLACK_USER_ID, text=text)
        print(f"   → Slack sent for invoice {invoice_number}")
    except Exception as e:
        print(f"   ✗ Slack send failed: {e}")


def get_email_link(email_id):
    return f"https://mail.google.com/mail/u/0/#inbox/{email_id}"


# --- PDF parsing ----------------------------------------------------------
def extract_text(pdf_path):
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            return "\n".join(p.extract_text() or "" for p in reader.pages[:3])
    except Exception as e:
        print(f"   ✗ PDF text extraction failed: {e}")
        return ""


def parse_invoice_data(pdf_text, invoice_number, subject=""):
    """
    Parse a Taylored / Yusen Logistics invoice.

    Returns a dict of fields plus `_flags`: a list of field names whose values
    are uncertain and should be reviewed. Empty `_flags` == high confidence.

    Layout facts this relies on (observed across all invoice types):
    - The invoice date is the first MM/DD/YYYY on the page.
    - The grand total is the LAST "$ n,nnn.nn" that appears before the payment
      block ("Make Checks Payable"); line-item amounts all sit above it.
    - Type is signalled by section headers / work-order text, not a labelled field.
    - Warehouse is stated as "LOC #31 NEW JERSEY" etc. when present; otherwise the
      only hint is the email subject, which is less reliable -> flagged.
    """
    flags = []
    upper = pdf_text.upper()
    # Only the invoice BODY (above the payment block) is reliable for keyword
    # detection. The legal boilerplate below it contains words like "STORAGE"
    # (warehouseman's-lien clause) and vendor addresses that cause false matches.
    body = re.split(r'MAKE CHECKS PAY', upper)[0]

    # --- date: first MM/DD/YYYY on the page ---
    date_str = datetime.now().strftime("%Y-%m-%d")
    m = re.search(r'(\d{2})/(\d{2})/(\d{4})', pdf_text)
    if m:
        mm, dd, yyyy = m.groups()
        date_str = f"{yyyy}-{mm}-{dd}"
    else:
        flags.append("date")

    # --- amount: last $ amount before the payment block ---
    dollars = re.findall(r'\$\s*([\d,]+\.\d{2})', body)
    amount = 0.0
    if dollars:
        amount = float(dollars[-1].replace(",", ""))
    else:
        flags.append("amount")

    # --- type (body only) ---
    # Order matters. Receiving must be checked before Admin: inbound invoices
    # carry a "CONTAINER ADMIN FEE" line that would otherwise match Admin.
    if "VAS #" in body:
        invoice_type = "VAS"
    elif ("INBOUND PROCESSING" in body or "RECEIVED CARTONS" in body
          or "RECEIVING SORTATION" in body):
        invoice_type = "Receiving"
    elif ("OUTBOUND PROCESSING" in body or "SMALL PARCEL SHIPMENTS" in body
          or "TRUCK SHIPMENTS" in body):
        invoice_type = "SMLPRCL/LTL"
    elif "STORAGE" in body:
        invoice_type = "Storage"
    elif ("ADMINISTRATIVE SUPPORT" in body or "BACK OFFICE" in body
          or ("ADMIN FEE" in body and "CONTAINER ADMIN FEE" not in body)):
        # Note: "CONTAINER ADMIN FEE" is a receiving line item, not an admin
        # invoice. Receiving is matched above, but guard here too (defense in
        # depth) so a receiving invoice missing its INBOUND header can't fall
        # through to Admin.
        invoice_type = "Admin"
    else:
        invoice_type = "Unknown"
        flags.append("type_of_invoice")

    # --- warehouse ---
    # Prefer the explicit location line in the PDF body. When it's absent, fall
    # back to the email subject, which reliably encodes the site for these
    # Taylored invoices (", Fontana CA" / "/AME" = NJ / "Savannah"), so treat it
    # as authoritative rather than flagging. Only a total absence of signal flags.
    subj = subject.upper()
    if "LOC #31" in body or "LOC #331" in body or "NEW JERSEY" in body:
        warehouse = "TS East (NJ)"
    elif "FONTANA" in body:
        warehouse = "TS West (CA)"
    elif "SAVANNAH" in body:
        warehouse = "TS South (SC)"
    elif "MOERDIJK" in body or "BENELUX" in body or "NETHERLANDS" in body:
        warehouse = "Yusen NL"
    elif "FONTANA" in subj:
        warehouse = "TS West (CA)"
    elif "SAVANNAH" in subj:
        warehouse = "TS South (SC)"
    elif "/AME" in subj:
        warehouse = "TS East (NJ)"
    else:
        warehouse = "Unknown"
        flags.append("warehouse")

    # --- bill period ---
    bp = re.search(r'BETWEEN\s+(\d{2}/\d{2}/\d{4})\s+AND\s+(\d{2}/\d{2}/\d{4})', upper)
    wk = re.search(r'WEEK OF\s+([A-Z]+ \d{1,2})', upper)
    if bp:
        a, b = bp.groups()
        bill_period = f"{a[:5].replace('/', '/')}-{b[:5]}"
    elif wk:
        bill_period = "Week of " + wk.group(1).title()
    else:
        bill_period = date_str

    # --- notes: first meaningful description line ---
    notes = ""
    for line in pdf_text.splitlines():
        s = line.strip()
        if (re.search(r'(VAS #|WO #|OUTBOUND PROCESSING|INBOUND PROCESSING|'
                      r'RECEIVED CARTONS|RECEIVING SORTATION|'
                      r'ADMINISTRATIVE SUPPORT|BACK OFFICE|STORAGE)', s, re.I)
                and len(s) > 8):
            notes = s
            break

    return {
        "date": date_str,
        "bill_period": bill_period,
        "invoice_number": invoice_number,
        "type_of_invoice": invoice_type,
        "warehouse": warehouse,
        "amount": amount,
        "currency": "USD",          # US Taylored/FMI invoices are always USD
        "notes": notes,
        "_flags": flags,
    }


# --- BigQuery -------------------------------------------------------------
def verify_table_exists():
    r = subprocess.run(["bq", f"--project_id={GCP_PROJECT}", "show", BIGQUERY_TABLE],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("❌ FATAL: BigQuery table not found. This script never creates it.")
        print(f"   Table: {BIGQUERY_TABLE}")
        sys.exit(1)


def fetch_existing_invoice_numbers():
    """Return the set of invoice_numbers already in BigQuery.

    This is the authoritative duplicate guard: the local processed-emails log can
    be cleared or lost, but the table itself is the source of truth, so we never
    re-insert an invoice that's already there regardless of local state.

    Two rules learned from the 2026-06-30 duplicate incident:
    - `--max_rows` must be explicit. bq returns only 100 rows by default, so once
      the table passed 100 distinct invoices this set was silently truncated and
      already-loaded invoices were re-inserted.
    - A failed read ABORTS the run instead of returning an empty set. Appending
      without the guard is exactly how duplicates happen; a skipped day is far
      cheaper than double-counted spend.
    """
    res = subprocess.run(
        ["bq", f"--project_id={GCP_PROJECT}", "query", "--nouse_legacy_sql",
         "--format=json", "--max_rows=1000000",
         f"SELECT DISTINCT invoice_number FROM {BIGQUERY_TABLE}"],
        capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit("❌ FATAL: could not read existing invoice numbers — aborting so "
                 "nothing is inserted without the duplicate guard.\n   "
                 + (res.stderr or "").strip()[:300])
    try:
        return {row["invoice_number"] for row in json.loads(res.stdout or "[]")}
    except (json.JSONDecodeError, KeyError):
        sys.exit("❌ FATAL: could not parse the existing-invoice query result — "
                 "aborting so nothing is inserted without the duplicate guard.")


def _already_in_bigquery(invoice_numbers):
    """Return the subset of invoice_numbers already present in the table, or
    None if the check itself failed (callers must then refuse to insert)."""
    quoted = ", ".join(
        "'" + n.replace("\\", "\\\\").replace("'", "\\'") + "'"
        for n in invoice_numbers)
    res = subprocess.run(
        ["bq", f"--project_id={GCP_PROJECT}", "query", "--nouse_legacy_sql",
         "--format=json", "--max_rows=1000000",
         f"SELECT DISTINCT invoice_number FROM {BIGQUERY_TABLE} "
         f"WHERE invoice_number IN ({quoted})"],
        capture_output=True, text=True)
    if res.returncode != 0:
        return None
    try:
        return {row["invoice_number"] for row in json.loads(res.stdout or "[]")}
    except (json.JSONDecodeError, KeyError):
        return None


def insert_rows(rows):
    """Insert a list of record dicts. Returns (ok: bool, error: str).

    Re-checks the table for every invoice_number immediately before writing.
    The set fetched at startup can be stale — another session may have loaded
    the same invoices in the meantime — and the insert is append-only with no
    key constraint, so this is the last line of defense against duplicates.
    An invoice found already present is skipped and counts as success; a failed
    check fails the whole insert (never append blind).
    """
    existing = _already_in_bigquery([r["invoice_number"] for r in rows])
    if existing is None:
        return False, ("pre-insert duplicate check failed — nothing inserted "
                       "(refusing to append without the guard)")
    dup = [r["invoice_number"] for r in rows if r["invoice_number"] in existing]
    if dup:
        print(f"   ⊘ Already in BigQuery — not re-inserting: {', '.join(dup)}")
    rows = [r for r in rows if r["invoice_number"] not in existing]
    if not rows:
        return True, ""
    ts = datetime.now(timezone.utc).isoformat()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for r in rows:
            rec = {k: v for k, v in r.items() if not k.startswith("_")}
            rec["amount"] = str(rec["amount"])
            rec.setdefault("ingested_at", ts)
            f.write(json.dumps(rec) + "\n")
        path = f.name
    res = subprocess.run(["bq", f"--project_id={GCP_PROJECT}", "insert", BIGQUERY_TABLE, path],
                         capture_output=True, text=True)
    os.remove(path)
    return res.returncode == 0, (res.stderr or res.stdout).strip()


# --- Attachment handling --------------------------------------------------
def _walk_parts(parts):
    """Yield every MIME part, recursing into nested multipart containers."""
    for p in parts or []:
        yield p
        if p.get('parts'):
            yield from _walk_parts(p['parts'])


def download_attachments(service, email_id, message):
    """Return (pdf_path, excel_path, subject, invoice_number, pdf_paths).

    pdf_path / excel_path are the first PDF / Excel (US single-invoice emails);
    pdf_paths is EVERY PDF attachment — NL land-transport emails bundle several
    invoices in one message (e.g. "CA26200110 + CA26200096").
    """
    headers = message['payload'].get('headers', [])
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "Unknown")
    invoice_number = "Unknown"
    m = re.search(r'Invoice #\s*(\d+)', subject)
    if m:
        invoice_number = m.group(1)

    pdf_paths, excel_path = [], None
    for part in _walk_parts(message['payload'].get('parts', [])):
        fn = part.get('filename')
        if not fn:
            continue
        att_id = part['body'].get('attachmentId')
        if not att_id:
            continue
        data = service.users().messages().attachments().get(
            userId='me', messageId=email_id, id=att_id).execute()
        blob = base64.urlsafe_b64decode(data['data'])
        safe = fn.replace('/', '_')
        if fn.lower().endswith('.pdf'):
            p = f"/tmp/{safe}"
            with open(p, 'wb') as f:
                f.write(blob)
            pdf_paths.append(p)
        elif fn.lower().endswith(('.xlsx', '.xls')):
            excel_path = f"/tmp/{safe}"
            with open(excel_path, 'wb') as f:
                f.write(blob)
    pdf_path = pdf_paths[0] if pdf_paths else None
    return pdf_path, excel_path, subject, invoice_number, pdf_paths


# --- Candidate display / editing ------------------------------------------
FIELDS = ["date", "bill_period", "invoice_number", "type_of_invoice",
          "warehouse", "amount", "notes"]


def print_table(candidates):
    print()
    print(f"{'#':<3}{'Invoice':<13}{'Date':<12}{'Type':<13}{'Warehouse':<15}{'Amount':>12}  Flags")
    print("-" * 90)
    for i, c in enumerate(candidates, 1):
        flag = ",".join(c["_flags"]) if c["_flags"] else ""
        mark = "⚠️ " if c["_flags"] else "  "
        print(f"{i:<3}{c['invoice_number']:<13}{c['date']:<12}{c['type_of_invoice']:<13}"
              f"{c['warehouse']:<15}{c['amount']:>12,.2f}  {mark}{flag}")
    print()


def edit_candidate(c):
    print(f"\nEditing invoice {c['invoice_number']} (press Enter to keep current value):")
    for field in FIELDS:
        cur = c[field]
        new = input(f"  {field} [{cur}]: ").strip()
        if new:
            c[field] = float(new.replace(",", "").replace("$", "")) if field == "amount" else new
    # re-evaluate flags the human has now resolved
    c["_flags"] = [f for f in c["_flags"] if f in FIELDS and not str(c.get(f))]
    if c["warehouse"] != "Unknown" and "warehouse" in c["_flags"]:
        c["_flags"].remove("warehouse")
    if c["type_of_invoice"] != "Unknown" and "type_of_invoice" in c["_flags"]:
        c["_flags"].remove("type_of_invoice")
    return c


# --- Modes ----------------------------------------------------------------
def attach_drive_links(drive_service, cands):
    """Upload each candidate's PDF + Excel to Drive and record the links."""
    folder_id = ensure_drive_folder(drive_service)
    if not folder_id:
        print("   ⚠ Skipping Drive archiving (no folder); invoices still insert.")
        return
    # International invoices explode into several rows that share ONE source PDF;
    # cache by path so each file uploads to Drive once, not once per row.
    pdf_cache, xls_cache = {}, {}
    for c in cands:
        pp, xp = c.get("_pdf_path"), c.get("_excel_path")
        if pp:
            if pp not in pdf_cache:
                pdf_cache[pp] = upload_to_drive(drive_service, pp, c["invoice_number"], "pdf", folder_id)
            if pdf_cache[pp]:
                c["pdf_url"] = pdf_cache[pp]
        if xp:
            if xp not in xls_cache:
                xls_cache[xp] = upload_to_drive(drive_service, xp, c["invoice_number"], "xlsx", folder_id)
            if xls_cache[xp]:
                c["supporting_doc_url"] = xls_cache[xp]


def gather_candidates(service, messages, processed, existing_invoices, intl_enabled=False):
    """Download + parse every new email. Returns list of (candidate, email_id, link).

    Skips emails already in the local processed log AND invoices whose number is
    already present in BigQuery (the authoritative duplicate guard).
    """
    by_inv = {}   # invoice_number -> (cand, email_id, link, subject)
    order = []    # preserve first-seen order of distinct invoice numbers
    for message in messages:
        email_id = message['id']
        if email_id in processed:
            print(f"⊘ Skipping already-processed email: {email_id}")
            continue
        msg = service.users().messages().get(userId='me', id=email_id).execute()
        link = get_email_link(email_id)
        pdf, _excel, subject, inv, pdf_paths = download_attachments(service, email_id, msg)
        print(f"\n📧 {subject}  (invoice {inv})")
        # Only Yusen/Taylored invoices belong in this pipeline. The forward-sweep
        # ("Fwd: Invoice #" from americanflat.com) also matches unrelated vendor
        # invoices people forward internally — those must be dropped SILENTLY
        # (marked processed, no Slack), not alerted. An email is trusted when its
        # sender is a Yusen/Taylored address; otherwise the PDF text must contain
        # a Yusen/Taylored marker before we parse or alert on it.
        headers = msg['payload'].get('headers', [])
        sender = next((h['value'] for h in headers if h['name'] == 'From'), "").lower()
        yusen_sender = any(k in sender for k in ("taylored", "tpservices", "yusen-logistics"))
        if inv in existing_invoices:
            print(f"   ⊘ Already in BigQuery — skipping to avoid a duplicate.")
            save_processed_email(email_id)
            continue
        if not pdf:
            if yusen_sender:
                send_slack_notification(inv, link, "No PDF attachment found.")
            else:
                print("   ⊘ Non-Yusen email without invoice PDF — ignoring silently.")
                save_processed_email(email_id)
            continue

        # --- International (Canada / Netherlands) invoices ---
        # Different layout; one PDF explodes into several rows (one per service
        # type), and NL transport emails bundle MULTIPLE invoice PDFs. The real
        # invoice number is inside each PDF, so handle these before the US path
        # (which keys off the subject's "Invoice #").
        intl_added, intl_seen = [], False
        for one_pdf in (pdf_paths if intl_enabled else []):
            try:
                fmt = intl_invoices.detect_format(one_pdf)
            except Exception as e:
                print(f"   ⚠ International detect error on {os.path.basename(one_pdf)}: {e}")
                continue
            if not fmt:
                continue
            intl_seen = True
            try:
                rows = intl_invoices.parse_international(one_pdf)
            except Exception as e:
                send_slack_notification(inv, link,
                    f"International ({fmt}) parse failed for {os.path.basename(one_pdf)}: {e}")
                continue
            if not rows:
                send_slack_notification(inv, link,
                    f"International ({fmt}) PDF parsed 0 line items: "
                    f"{os.path.basename(one_pdf)} — needs manual handling.")
                continue
            for row in rows:
                rinv = row["invoice_number"]
                if rinv.rsplit("-", 1)[0] in SUPERSEDED_INVOICES:
                    print(f"   ⊘ {rinv} superseded — skipping.")
                    continue
                if rinv in existing_invoices or rinv in by_inv:
                    print(f"   ⊘ {rinv} already seen — skipping.")
                    continue
                row["_pdf_path"] = one_pdf
                row["_excel_path"] = None          # the combined PDF is self-contained
                by_inv[rinv] = (row, email_id, link, subject)
                order.append(rinv)
                intl_added.append(rinv)
        if intl_seen:
            print(f"   🌐 international: {len(intl_added)} new row(s)"
                  + (f" — {', '.join(intl_added)}" if intl_added else " (all already in BigQuery)"))
            if not intl_added:
                # Every parsed row already exists — nothing this email can ever add,
                # so retire it instead of re-downloading its PDFs on every run.
                save_processed_email(email_id)
            continue

        text = extract_text(pdf)
        if not text.strip():
            # Scanned/image PDFs extract no text, so the Yusen-marker check below
            # can never clear them — and real invoices arrive this way (10 scanned
            # SC invoices were silently dropped here on 2026-07-09). Alert instead
            # of dropping quietly; retire forwarded copies so the alert fires once.
            print("   ⚠ PDF has no extractable text (likely scanned) — Slack alert sent.")
            send_slack_notification(inv, link,
                "PDF has no extractable text (likely a scanned invoice) — needs "
                "manual review/ingestion before it can reach BigQuery.")
            if not yusen_sender:
                save_processed_email(email_id)
            continue
        if not yusen_sender and "YUSEN" not in text.upper() and "TAYLORED" not in text.upper():
            print("   ⊘ PDF has no Yusen/Taylored marker — not ours; ignoring silently.")
            save_processed_email(email_id)
            continue
        cand = parse_invoice_data(text, inv, subject)
        cand["_pdf_path"] = pdf
        cand["_excel_path"] = _excel
        if cand["type_of_invoice"] in REQUIRES_SUPPORTING_DOC and not _excel:
            cand["_flags"].append("supporting_doc")

        # Within-batch dedupe: the same invoice can arrive in two emails (resend,
        # or an explicit "REVISED INVOICE"). Keep one row per number, preferring
        # the revised copy; the BigQuery guard above only catches already-inserted
        # numbers, not repeats inside a single run.
        is_revised = "REVISED" in subject.upper()
        if inv in by_inv:
            prev_revised = "REVISED" in by_inv[inv][3].upper()
            if is_revised and not prev_revised:
                print(f"   ↻ Duplicate {inv}: replacing with REVISED version.")
                by_inv[inv] = (cand, email_id, link, subject)
            else:
                print(f"   ⊘ Duplicate {inv} in this batch — keeping first copy.")
            continue
        by_inv[inv] = (cand, email_id, link, subject)
        order.append(inv)
    return [(by_inv[i][0], by_inv[i][1], by_inv[i][2]) for i in order]


def run_preview(drive_service, candidates):
    cands = [c for c, _, _ in candidates]
    print_table(cands)
    flagged = [c for c in cands if c["_flags"]]
    if flagged:
        print(f"⚠️  {len(flagged)} invoice(s) have low-confidence fields (see Flags column).")
    while True:
        choice = input("Insert [a]ll, [e]dit one, [s]kip flagged, or [c]ancel? ").strip().lower()
        if choice == "c":
            print("Cancelled. Nothing inserted.")
            return
        if choice == "e":
            num = input("  Row # to edit: ").strip()
            if num.isdigit() and 1 <= int(num) <= len(cands):
                edit_candidate(cands[int(num) - 1])
                print_table(cands)
            continue
        if choice in ("a", "s"):
            to_insert = cands if choice == "a" else [c for c in cands if not c["_flags"]]
            if not to_insert:
                print("Nothing to insert.")
                return
            print(f"Archiving {len(to_insert)} invoice(s) to Google Drive...")
            attach_drive_links(drive_service, to_insert)
            ok, err = insert_rows(to_insert)
            if ok:
                inserted_invoices = {c["invoice_number"] for c in to_insert}
                for c, email_id, link in candidates:
                    if c["invoice_number"] in inserted_invoices:
                        save_processed_email(email_id)
                print(f"✓ Inserted {len(to_insert)} invoice(s) into {BIGQUERY_TABLE}.")
                if choice == "s" and len(to_insert) < len(cands):
                    held = len(cands) - len(to_insert)
                    print(f"  Held back {held} flagged invoice(s) — re-run to review them.")
            else:
                print(f"✗ Insert failed: {err}")
            return


NOTIFIED_LOG = os.path.expanduser("~/.yusen_notified.json")


def _load_notified():
    if os.path.exists(NOTIFIED_LOG):
        try:
            return set(json.load(open(NOTIFIED_LOG)))
        except Exception:
            return set()
    return set()


def _save_notified(s):
    json.dump(sorted(s), open(NOTIFIED_LOG, "w"))


def run_auto(drive_service, candidates):
    """Cloud mode: insert high-confidence rows, Slack the rest. No prompts.

    Flagged invoices are NOT marked processed (so they get picked up once their
    blocker clears, e.g. OCR), but they're tracked in NOTIFIED_LOG so the daily
    run alerts on each only once instead of re-pinging Slack every day.
    """
    high = [(c, e, l) for c, e, l in candidates if not c["_flags"]]
    low = [(c, e, l) for c, e, l in candidates if c["_flags"]]

    if high:
        attach_drive_links(drive_service, [c for c, _, _ in high])
        ok, err = insert_rows([c for c, _, _ in high])
        if ok:
            for c, email_id, link in high:
                save_processed_email(email_id)
            print(f"✓ Auto-inserted {len(high)} high-confidence invoice(s).")
        else:
            for c, email_id, link in high:
                send_slack_notification(c["invoice_number"], link, f"BigQuery insert failed: {err}")

    notified = _load_notified()
    new_alerts = 0
    for c, email_id, link in low:
        inv = c["invoice_number"]
        if inv in notified:
            continue  # already flagged on a prior run — don't spam
        send_slack_notification(
            inv, link,
            f"Low confidence on: {', '.join(c['_flags'])}. Parsed as "
            f"{c['type_of_invoice']} / {c['warehouse']} / ${c['amount']:,.2f}. "
            f"Run the processor in preview mode to confirm.", ok=True)
        notified.add(inv)
        new_alerts += 1
    _save_notified(notified)
    print(f"Auto run done: {len(high)} inserted, {new_alerts} new Slack alert(s) "
          f"({len(low) - new_alerts} flagged but already alerted).")


def run_dry(drive_service, candidates):
    print_table([c for c, _, _ in candidates])
    print("DRY RUN — nothing inserted, nothing uploaded to Drive.")


# --- Main -----------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Gmail -> BigQuery invoice processor")
    ap.add_argument("--auto", action="store_true",
                    help="Insert high-confidence rows automatically, Slack the rest (cloud mode)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse and show the table only; never insert")
    ap.add_argument("--since", metavar="YYYY/MM/DD",
                    help="Only emails on/after this date (Gmail 'after:' filter)")
    ap.add_argument("--until", metavar="YYYY/MM/DD",
                    help="Only emails before this date (Gmail 'before:' filter)")
    ap.add_argument("--max", type=int, default=100,
                    help="Max emails to pull per run (default 100)")
    ap.add_argument("--intl", action="store_true",
                    help="Also process Canada/Netherlands invoices (off by default; "
                         "env YUSEN_INTL=1 also enables)")
    args = ap.parse_args()
    mode = "auto" if args.auto else "dry-run" if args.dry_run else "preview"
    intl_enabled = args.intl or os.environ.get("YUSEN_INTL") == "1"

    # Build the Gmail search query, optionally bounded by a date range for
    # historical loads (e.g. --since 2026/03/31 --until 2026/05/01 for April).
    query = build_query(intl_enabled)
    if args.since:
        query += f" after:{args.since}"
    if args.until:
        query += f" before:{args.until}"

    print("=" * 80)
    print(f"GMAIL INVOICE PROCESSOR  —  mode: {mode}")
    print("=" * 80)
    print(f"Started: {datetime.now():%Y-%m-%d %H:%M:%S}")

    print("🔒 Verifying BigQuery table (read-only; never deletes/modifies)...")
    verify_table_exists()
    print("✓ Table verified")

    service, drive_service = authenticate()
    print("✓ Gmail + Drive authenticated")

    print(f"Searching: {query}")
    results = service.users().messages().list(userId='me', q=query, maxResults=args.max).execute()
    messages = results.get('messages', [])
    if not messages:
        print("✓ No matching emails found.")
        return
    print(f"Found {len(messages)} email(s)")

    processed = load_processed_emails()
    existing_invoices = fetch_existing_invoice_numbers()
    print(f"✓ {len(existing_invoices)} invoice number(s) already in BigQuery (will be skipped)")
    candidates = gather_candidates(service, messages, processed, existing_invoices, intl_enabled)
    if not candidates:
        print("\n✓ No new invoices to process.")
        return

    if mode == "auto":
        run_auto(drive_service, candidates)
    elif mode == "dry-run":
        run_dry(drive_service, candidates)
    else:
        run_preview(drive_service, candidates)

    print(f"\nEnded: {datetime.now():%Y-%m-%d %H:%M:%S}")


if __name__ == "__main__":
    main()
````

## `scripts/intl_invoices.py`

````python
#!/usr/bin/env python3
"""Parsers for Yusen *international* invoices: Canada, NL handling/storage, NL
land transport. These differ from the US Taylored/Yusen format in every field:

  - alphanumeric invoice numbers (CA2WFS0003352, FTI0006387, CA26200110)
  - non-US dates (30-Apr-26 ; 31/05/2026)
  - EUR currency with European numerals (13.526,31) on the NL handling invoice
  - one document bundles several service types (Storage, Inbound, Outbound, ...)

Each invoice is exploded into ONE ROW PER MAPPED type_of_invoice (per Anthony's
decision). Amounts are kept in the invoice's NATIVE CURRENCY (EUR for the
Netherlands, USD for Canada) and tagged with a `currency` field — no FX
conversion (Anthony's call: don't guess historical rates). Amounts are
tax-INCLUSIVE (Canada GST, NL transport VAT; NL handling is 0% export VAT).
Text is extracted with **pdfplumber** because PyPDF2 scrambles these layouts.

Public API:
  detect_format(pdf_path) -> 'canada' | 'nl_handling' | 'nl_transport' | None
  parse_international(pdf_path) -> list[row dict] | None
Row dict keys match invoice_processor candidates: date, bill_period,
invoice_number, type_of_invoice, warehouse, amount, notes, _flags.
"""
import os
import re
import json
import urllib.request
from datetime import datetime

import pdfplumber

# EUR->USD conversion. The live ECB API (frankfurter.app) has no data for very
# recent / future-dated invoices, so we fall back to a per-month override file
# that finance maintains, then to a constant. Override the constant with env
# YUSEN_EUR_USD_FALLBACK=1.0850.
EUR_USD_FALLBACK = float(os.environ.get("YUSEN_EUR_USD_FALLBACK", "1.08"))
# {"YYYY-MM": rate} — pinned month rates used when the live ECB lookup is empty.
RATE_FILE = os.path.expanduser("~/.yusen_eur_usd_rates.json")


def _month_rates():
    try:
        with open(RATE_FILE) as fh:
            return json.load(fh)
    except Exception:
        return {}


# --------------------------------------------------------------------------
# extraction / number / date helpers
# --------------------------------------------------------------------------
def _text(pdf_path, max_pages=None):
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]
        return "\n".join((p.extract_text() or "") for p in pages)


def parse_amount(s):
    """Parse money in either US (1,608.99) or EU (13.526,31 / 568,05) format."""
    s = s.strip().replace(" ", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):           # comma is decimal -> EU
            s = s.replace(".", "").replace(",", ".")
        else:                                      # period decimal -> US
            s = s.replace(",", "")
    elif "," in s:                                 # comma only
        s = s.replace(",", ".") if len(s.rsplit(",", 1)[-1]) == 2 else s.replace(",", "")
    return float(s)


def _date_ddmonyy(s):     # 30-Apr-26
    return datetime.strptime(s.strip(), "%d-%b-%y").strftime("%Y-%m-%d")


def _date_ddmmyyyy(s):    # 31/05/2026
    return datetime.strptime(s.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")


def eur_to_usd(amount_eur, date_iso):
    """(usd, rate, source). Order: live ECB rate at the invoice date -> pinned
    per-month rate (RATE_FILE) -> constant fallback. Source is recorded in notes.
    Only the constant fallback flags the row for review; pinned rates are trusted."""
    # 1) live ECB rate at the invoice date (when the API has that date)
    try:
        url = f"https://api.frankfurter.app/{date_iso}?from=EUR&to=USD"
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.load(r)
        rate = float(d["rates"]["USD"])
        return round(amount_eur * rate, 2), rate, f"ECB {d.get('date', date_iso)}"
    except Exception:
        pass
    # 2) finance-maintained per-month override
    rate = _month_rates().get(date_iso[:7])
    if rate is not None:
        return round(amount_eur * float(rate), 2), float(rate), f"pinned {date_iso[:7]}"
    # 3) constant fallback (flagged for review)
    return round(amount_eur * EUR_USD_FALLBACK, 2), EUR_USD_FALLBACK, f"FALLBACK {EUR_USD_FALLBACK}"


# --------------------------------------------------------------------------
# charge description -> canonical type_of_invoice
# --------------------------------------------------------------------------
def _canada_type(desc):
    """(type, needs_review) for a Canada charge description."""
    key = re.sub(r"\s+", " ", re.sub(r"\s*[-–].*$", "", desc)).strip().upper()
    if key.startswith("STORAGE") or key.startswith("WAREHOUSE"):
        return "Storage", False
    if key.startswith("WHS") or "IN/OUT" in key:
        return "Receiving", True   # combined warehouse in/out handling — ambiguous
    return "Storage", True         # unknown -> default Storage, flag for review

# NL handling line item -> type. CONSUMABLES & VAL both fold into VAS.
_NL_HANDLING_MAP = {
    "INBOUND": "Receiving", "OUTBOUND": "SMLPRCL/LTL", "STORAGE": "Storage",
    "ADMINISTRATION": "Admin", "CONSUMABLES": "VAS", "VAL": "VAS",
}


# --------------------------------------------------------------------------
# format detection
# --------------------------------------------------------------------------
def detect_format(pdf_path):
    head = _text(pdf_path, max_pages=1)
    u = head.upper()
    if "YUSEN LOGISTICS (CANADA)" in u or re.search(r"INVOICE\s+CA2WFS", u):
        return "canada"
    if re.search(r"INVOICE\s+FTI\d", u):
        return "nl_handling"
    if re.search(r"INVOICE\s+CA\d{6,}", u) and ("BENELUX" in u or "MOERDIJK" in u
                                                or "TRANSPORT -" in u):
        return "nl_transport"
    return None


# --------------------------------------------------------------------------
# per-format parsers -> {invoice, date, bill_period, warehouse, currency, lines}
# lines: list of (type, native_amount, needs_review, description)
# --------------------------------------------------------------------------
def _parse_canada(pdf_path):
    text = _text(pdf_path)
    inv = re.search(r"INVOICE\s+(CA2WFS\d+)", text, re.I).group(1)
    date = _date_ddmonyy(re.search(r"INVOICE DATE\s*(\d{1,2}-[A-Za-z]{3}-\d{2})", text).group(1))
    lines, bill = [], None
    # Each line: "<desc> <pct>%=<gst> <charge>". Store the GST-INCLUSIVE amount
    # (charge + GST) so the row total matches the invoice's grand total.
    for m in re.finditer(r"^(.*?)\s+(\d+)%=([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$", text, re.M):
        desc = re.sub(r"\s+", " ", m.group(1).strip())
        pct, gst, charge = m.group(2), parse_amount(m.group(3)), parse_amount(m.group(4))
        typ, flag = _canada_type(desc)
        lines.append((typ, round(charge + gst, 2), flag, f"{desc} (+{pct}% GST {gst:,.2f})"))
        mb = re.search(r"-\s*([A-Z][a-z]+ \d{4})", desc)   # "Storage Charge - April 2026"
        if mb:
            bill = mb.group(1)
    return {"invoice": inv, "date": date, "bill_period": bill or _month_label(date),
            "warehouse": "Yusen CA", "currency": "USD", "lines": lines}


def _parse_nl_handling(pdf_path):
    text = _text(pdf_path)
    inv = re.search(r"Invoice\s+(FTI\d+)", text).group(1)
    date = _date_ddmmyyyy(re.search(r"Invoice Date\s+(\d{2}/\d{2}/\d{4})", text).group(1))
    bm = re.search(r"Americanflat\s+(\d{2}/\d{4})", text)
    lines = []
    # General line item: "<description> <qty> <unit price> <VAT code> <amount> EUR".
    # Standard charges (INBOUND/OUTBOUND/STORAGE/...) map to known types; any other
    # charge (e.g. "Implementation cost", "TPM licentie") -> VAS, flagged for review.
    for m in re.finditer(r"^(.+?)\s+\d+\s+[\d.,]+\s+\w+\s+([\d.,]+)\s+EUR\s*$", text, re.M):
        desc = re.sub(r"\s+", " ", m.group(1).strip())
        typ = _NL_HANDLING_MAP.get(desc.upper())
        lines.append((typ or "VAS", parse_amount(m.group(2)), typ is None, desc))
    return {"invoice": inv, "date": date, "bill_period": bm.group(1) if bm else _month_label(date),
            "warehouse": "Yusen NL", "currency": "EUR", "lines": lines}


def _parse_nl_transport(pdf_path):
    text = _text(pdf_path, max_pages=1)   # page 1 = summary; later pages repeat per-shipment
    inv = re.search(r"INVOICE\s+(CA\d{6,})", text).group(1)
    date = _date_ddmmyyyy(re.search(r"INVOICE DATE\s+(\d{2}/\d{2}/\d{4})", text).group(1))
    lines = []
    # "Transport - <desc> <amount> EUR <pct>%". Store the VAT-INCLUSIVE amount.
    for m in re.finditer(r"Transport\s*-\s*(.+?)\s+([\d.,]+)\s+EUR\s+(\d+)%", text):
        net, pct = parse_amount(m.group(2)), int(m.group(3))
        incl = round(net * (1 + pct / 100), 2)
        lines.append(("SMLPRCL/LTL", incl, False, f"Transport - {m.group(1).strip()} (+{pct}% VAT)"))
    return {"invoice": inv, "date": date, "bill_period": _month_label(date),
            "warehouse": "Yusen NL", "currency": "EUR", "lines": lines}


_PARSERS = {"canada": _parse_canada, "nl_handling": _parse_nl_handling,
            "nl_transport": _parse_nl_transport}


def _month_label(date_iso):
    return datetime.strptime(date_iso, "%Y-%m-%d").strftime("%B %Y")


# --------------------------------------------------------------------------
# explode parsed invoice into one row per (invoice, mapped type)
# --------------------------------------------------------------------------
def _build_rows(p):
    by_type = {}
    for typ, native, flag, desc in p["lines"]:
        d = by_type.setdefault(typ, {"native": 0.0, "flag": False, "descs": []})
        d["native"] += native
        d["flag"] = d["flag"] or flag
        d["descs"].append(f"{desc}={native:,.2f}")

    cur = p["currency"]                       # 'EUR' for NL, 'USD' for Canada
    rows = []
    for typ, d in by_type.items():
        amt = round(d["native"], 2)           # kept in native currency, no FX
        rows.append({
            "date": p["date"],
            "bill_period": p["bill_period"],
            "invoice_number": f"{p['invoice']}-{typ.replace('/', '')}",
            "type_of_invoice": typ,
            "warehouse": p["warehouse"],
            "amount": amt,
            "currency": cur,
            "notes": f"{typ}: {cur} {amt:,.2f} | {', '.join(d['descs'])}",
            "_flags": ["type_of_invoice"] if d["flag"] else [],
        })
    return rows


def parse_international(pdf_path):
    """Return a list of row dicts for a CA/NL invoice, or None if not international."""
    fmt = detect_format(pdf_path)
    if not fmt:
        return None
    return _build_rows(_PARSERS[fmt](pdf_path))


# --------------------------------------------------------------------------
# self-test:  python3 intl_invoices.py <pdf> [<pdf> ...]
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        fmt = detect_format(path)
        print(f"\n=== {os.path.basename(path)}  [{fmt}] ===")
        rows = parse_international(path)
        if not rows:
            print("   (not international)")
            continue
        tot = 0.0
        for r in rows:
            tot += r["amount"]
            fl = f"  flags={r['_flags']}" if r["_flags"] else ""
            print(f"   {r['invoice_number']:<24} {r['type_of_invoice']:<12} ${r['amount']:>11,.2f}{fl}")
            print(f"        period={r['bill_period']!r}  {r['notes']}")
        print(f"   --> {len(rows)} row(s), total USD ${tot:,.2f}")
````

## `scripts/generate_yusen_dashboard.py`

````python
#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard for americanflat.finance.yusen_invoices.

Pulls the live table via `bq`, then writes a single standalone HTML file with:
  - KPI cards (per-currency totals, link coverage, date range)
  - Spend-by-type and spend-by-warehouse charts (USD invoices only — see note)
  - A sortable / filterable / searchable invoice table whose pdf_url and
    supporting_doc_url columns render as clickable links.

Invoices are billed in multiple currencies (USD for US + Canada, EUR for the
Netherlands), so amounts are shown in their native currency and totals are kept
separate per currency — never summed across currencies.

Re-run any time to refresh:  python3 generate_yusen_dashboard.py
Output: ~/yusen_invoices_dashboard.html  (open in any browser, no server needed).

Read-only — runs a single SELECT, never writes to the table.
"""
import json
import os
import subprocess
import sys

OUT_PATH = os.path.expanduser("~/yusen_invoices_dashboard.html")

QUERY = """
SELECT
  FORMAT_DATE('%Y-%m-%d', date) AS date,
  bill_period,
  invoice_number,
  type_of_invoice,
  warehouse,
  CAST(amount AS FLOAT64) AS amount,
  IFNULL(currency, 'USD') AS currency,
  paid_at IS NOT NULL AS paid,
  FORMAT_TIMESTAMP('%Y-%m-%d', paid_at) AS paid_at,
  paid_marked_by,
  notes,
  pdf_url,
  supporting_doc_url,
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M', ingested_at) AS ingested_at
FROM `americanflat.finance.yusen_invoices`
ORDER BY date DESC, invoice_number DESC
"""


def fetch_rows():
    """Return the table as a list of dicts. Falls back to a JSON file arg for offline runs."""
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        with open(sys.argv[1]) as fh:
            return json.load(fh)

    env = dict(os.environ)
    # `bq` is expected on PATH. If your gcloud SDK lives elsewhere, point these
    # optional env vars at it (see .env.example); otherwise the system `bq` is used.
    sdk_bin = os.environ.get("CLOUDSDK_BIN_PATH", "")
    if sdk_bin:
        env["PATH"] = sdk_bin + ":" + env.get("PATH", "")
    cloudsdk_py = os.environ.get("CLOUDSDK_PYTHON", "")
    if cloudsdk_py:
        env.setdefault("CLOUDSDK_PYTHON", cloudsdk_py)

    out = subprocess.run(
        ["bq", "query", "--use_legacy_sql=false", "--format=prettyjson", "--max_rows=100000", QUERY],
        capture_output=True, text=True, env=env, check=True,
    )
    return json.loads(out.stdout)


def build_html(rows):
    # Normalize: amounts to float, strip the boilerplate legal footer that some
    # Receiving invoices carry as their "notes" so the table stays readable.
    BOILERPLATE = "No action may be maintained by Client"
    # Display-only exclusions (test/junk rows). The row stays in the table per the
    # standing "never delete" rule; it just doesn't pollute the dashboard totals.
    EXCLUDE_INVOICES = {"TEST_DELETE_ME"}
    clean = []
    for r in rows:
        if (r.get("invoice_number") or "") in EXCLUDE_INVOICES:
            continue
        notes = r.get("notes") or ""
        if notes.startswith(BOILERPLATE):
            notes = "(no line-item description — see PDF)"
        clean.append({
            "date": r.get("date") or "",
            "bill_period": r.get("bill_period") or "",
            "invoice_number": r.get("invoice_number") or "",
            "type_of_invoice": r.get("type_of_invoice") or "",
            "warehouse": r.get("warehouse") or "",
            "amount": float(r["amount"]) if r.get("amount") not in (None, "") else 0.0,
            "currency": r.get("currency") or "USD",
            "paid": str(r.get("paid")).lower() == "true",
            "paid_at": r.get("paid_at") or "",
            "paid_marked_by": r.get("paid_marked_by") or "",
            "notes": notes,
            "pdf_url": r.get("pdf_url") or "",
            "supporting_doc_url": r.get("supporting_doc_url") or "",
            "ingested_at": r.get("ingested_at") or "",
        })

    data_json = json.dumps(clean)
    totals = {}
    for r in clean:
        totals[r["currency"]] = round(totals.get(r["currency"], 0.0) + r["amount"], 2)
    dates = sorted([r["date"] for r in clean if r["date"]])

    kpi = {
        "totals": totals,                       # {"USD": x, "EUR": y}
        "n": len(clean),
        "n_pdf": sum(1 for r in clean if r["pdf_url"]),
        "n_doc": sum(1 for r in clean if r["supporting_doc_url"]),
        "date_lo": dates[0] if dates else "—",
        "date_hi": dates[-1] if dates else "—",
    }
    return TEMPLATE.replace("/*DATA*/", data_json).replace("/*KPI*/", json.dumps(kpi))


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Yusen Invoices</title>
<style>
  :root {
    --bg: #f6f7f9;
    --panel: #ffffff;
    --ink: #1a1f29;
    --muted: #6b7280;
    --line: #e6e8ec;
    --accent: #2563eb;
    --accent-soft: #eff4ff;
    --shadow: 0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.1);
    --radius: 12px;
    --t-Admin: #6366f1;
    --t-Receiving: #d97706;
    --t-SMLPRCLLTL: #0891b2;
    --t-Storage: #7c3aed;
    --t-VAS: #16a34a;
    --ok: #15803d;
    --warn: #b45309;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1280px; margin: 0 auto; padding: 28px 24px 64px; }
  header.page { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 4px; }
  h1 { font-size: 26px; font-weight: 700; letter-spacing: -.02em; margin: 0; }
  .sub { color: var(--muted); font-size: 13px; }
  .sub code { background: var(--accent-soft); color: var(--accent); padding: 1px 6px; border-radius: 5px; font-size: 12px; }

  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin: 22px 0 26px; }
  .kpi { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 16px 18px; box-shadow: var(--shadow); }
  .kpi .label { color: var(--muted); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
  .kpi .value { font-size: 24px; font-weight: 700; letter-spacing: -.02em; margin-top: 6px; }
  .kpi .value small { font-size: 13px; font-weight: 500; color: var(--muted); letter-spacing: 0; }

  .panels { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 26px; }
  @media (max-width: 860px) { .panels { grid-template-columns: 1fr; } }
  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 18px 20px; box-shadow: var(--shadow); }
  .panel h2 { font-size: 14px; font-weight: 600; margin: 0 0 2px; }
  .panel .hint { color: var(--muted); font-size: 11.5px; margin: 0 0 12px; }
  .bar-row { display: grid; grid-template-columns: 130px 1fr auto; align-items: center; gap: 10px; margin: 8px 0; }
  .bar-row .name { font-size: 12.5px; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .bar-track { background: #f0f1f4; border-radius: 6px; height: 18px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 6px; }
  .bar-row .amt { font-variant-numeric: tabular-nums; font-size: 12.5px; color: var(--muted); white-space: nowrap; }

  .toolbar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }
  .toolbar input[type=search], .toolbar select {
    font: inherit; padding: 8px 11px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); color: var(--ink);
  }
  .toolbar input[type=search] { flex: 1; min-width: 220px; }
  .toolbar input[type=search]:focus, .toolbar select:focus { outline: 2px solid var(--accent-soft); border-color: var(--accent); }
  .count { color: var(--muted); font-size: 13px; margin-left: auto; }

  .table-wrap { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; min-width: 1120px; }
  thead th {
    position: sticky; top: 0; background: #fafbfc; z-index: 1;
    text-align: left; font-size: 12px; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: .03em; padding: 11px 14px; border-bottom: 1px solid var(--line);
    cursor: pointer; user-select: none; white-space: nowrap;
  }
  thead th.num { text-align: right; }
  thead th .arrow { opacity: .4; font-size: 10px; margin-left: 3px; }
  thead th.sorted .arrow { opacity: 1; color: var(--accent); }
  tbody td { padding: 10px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }
  tbody tr:hover { background: #fafbfc; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  td.inv { font-variant-numeric: tabular-nums; font-weight: 600; }
  td.notes { color: var(--muted); max-width: 300px; }
  .chip { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 600; white-space: nowrap; }
  .cur { font-size: 11px; color: var(--muted); font-weight: 600; }
  a.link { color: var(--accent); text-decoration: none; font-weight: 600; white-space: nowrap; }
  a.link:hover { text-decoration: underline; }
  .dash { color: #c2c7cf; }
  footer.page { color: var(--muted); font-size: 12px; margin-top: 18px; text-align: center; }
  @media (prefers-reduced-motion: no-preference) { .bar-fill { transition: width 0.25s ease; } }
</style>
</head>
<body>
<div class="wrap">
  <header class="page">
    <div>
      <h1>Yusen Invoices</h1>
      <div class="sub">Live from <code>americanflat.finance.yusen_invoices</code></div>
    </div>
    <div class="sub" id="meta"></div>
  </header>

  <section class="kpis" id="kpis"></section>

  <section class="panels">
    <div class="panel"><h2>Spend by invoice type</h2><p class="hint" id="hint-type"></p><div id="chart-type"></div></div>
    <div class="panel"><h2>Spend by warehouse</h2><p class="hint" id="hint-wh"></p><div id="chart-wh"></div></div>
  </section>

  <div class="toolbar">
    <input type="search" id="q" placeholder="Search invoice #, notes, period…" autocomplete="off">
    <select id="f-month"><option value="">All months</option></select>
    <select id="f-type"><option value="">All types</option></select>
    <select id="f-wh"><option value="">All warehouses</option></select>
    <select id="f-cur"><option value="">All currencies</option></select>
    <select id="f-paid" aria-label="Filter by payment"><option value="">Paid + unpaid</option><option value="paid">Paid</option><option value="unpaid">Unpaid</option></select>
    <span class="count" id="count"></span>
  </div>

  <div class="table-wrap">
    <table>
      <thead><tr>
        <th data-k="date">Date<span class="arrow">▼</span></th>
        <th data-k="invoice_number">Invoice #<span class="arrow">▼</span></th>
        <th data-k="type_of_invoice">Type<span class="arrow">▼</span></th>
        <th data-k="warehouse">Warehouse<span class="arrow">▼</span></th>
        <th data-k="bill_period">Bill period<span class="arrow">▼</span></th>
        <th data-k="amount" class="num">Amount<span class="arrow">▼</span></th>
        <th data-k="paid" tabindex="0">Paid<span class="arrow">▼</span></th>
        <th data-k="notes">Notes<span class="arrow">▼</span></th>
        <th>PDF</th>
        <th>Doc</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>

  <footer class="page" id="foot"></footer>
</div>

<script>
const DATA = /*DATA*/;
const KPI = /*KPI*/;

const SYM = {USD: "$", EUR: "€", GBP: "£"};
const money = (n, cur) => (SYM[cur] || (cur + " ")) + n.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
const money0 = (n, cur) => (SYM[cur] || (cur + " ")) + Math.round(n).toLocaleString("en-US");
const typeVar = t => "--t-" + t.replace(/[^A-Za-z]/g, "");
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const fmtDate = iso => { if (!iso) return ""; const [y, m, d] = iso.split("-"); return `${MON[+m - 1]} ${d}, ${y.slice(2)}`; };
const fmtMonth = ym => { const [y, m] = ym.split("-"); return `${MON[+m - 1]} ${y}`; };

// ---- KPI cards ----
document.getElementById("meta").innerHTML =
  KPI.n + " invoices · " + fmtDate(KPI.date_lo) + " → " + fmtDate(KPI.date_hi);
// ---- reactive KPI cards + charts (recomputed for the current filter) ----
function kpiCards(rows) {
  const totals = {};
  for (const r of rows) totals[r.currency] = (totals[r.currency] || 0) + r.amount;
  const curTotals = Object.entries(totals).sort((a, b) => b[1] - a[1])
    .map(([cur, amt]) => ({label: `Total billed (${cur})`, value: money0(amt, cur)}));
  const unpaid = {};
  for (const r of rows) if (!r.paid) unpaid[r.currency] = (unpaid[r.currency] || 0) + r.amount;
  const unpaidCards = Object.entries(unpaid).sort((a, b) => b[1] - a[1])
    .map(([cur, amt]) => ({label: `Unpaid (${cur})`, value: money0(amt, cur),
      sub: rows.filter(r => !r.paid && r.currency === cur).length + " inv"}));
  const cards = [
    ...(curTotals.length ? curTotals : [{label: "Total billed", value: "—"}]),
    ...unpaidCards,
    {label: "Invoices", value: rows.length, sub: rows.length === DATA.length ? "" : "of " + DATA.length},
    {label: "With PDF link", value: rows.filter(r => r.pdf_url).length, sub: "of " + rows.length},
    {label: "With supporting doc", value: rows.filter(r => r.supporting_doc_url).length, sub: "of " + rows.length},
  ];
  document.getElementById("kpis").innerHTML = cards.map(k =>
    `<div class="kpi"><div class="label">${k.label}</div>
     <div class="value">${k.value}${k.sub ? ` <small>${k.sub}</small>` : ""}</div></div>`
  ).join("");
}

function chart(elId, hintId, key, rows) {
  // One currency per axis: honor the currency filter; otherwise chart USD and
  // point at the cards for the rest. If the filter leaves no USD rows (e.g.
  // warehouse = Yusen NL), chart the single currency that remains.
  const cur = fCur.value || (rows.some(r => r.currency === "USD") ? "USD"
              : (rows.length ? rows[0].currency : "USD"));
  const agg = {};
  for (const r of rows) { if (r.currency !== cur) continue; agg[r[key]] = (agg[r[key]] || 0) + r.amount; }
  const items = Object.entries(agg).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...items.map(i => i[1]), 1);
  document.getElementById(elId).innerHTML = items.length ? items.map(([name, amt]) => {
    const color = key === "type_of_invoice" ? `var(${typeVar(name)})` : "var(--accent)";
    const pct = (amt / max * 100).toFixed(1);
    return `<div class="bar-row"><div class="name" title="${esc(name)}">${esc(name)}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${color}"></div></div>
      <div class="amt">${money0(amt, cur)}</div></div>`;
  }).join("") : `<div class="bar-row"><div class="name" style="grid-column:1/-1;color:var(--muted)">No invoices match the current filter</div></div>`;
  const others = [...new Set(rows.filter(r => r.currency !== cur).map(r => r.currency))];
  document.getElementById(hintId).textContent =
    `${cur} invoices in the current filter` + (others.length ? ` — ${others.join("/")} totals in the cards above` : "");
}

// ---- filters ----
const uniq = key => [...new Set(DATA.map(r => r[key]).filter(Boolean))].sort();
const fType = document.getElementById("f-type"), fWh = document.getElementById("f-wh"),
      fMonth = document.getElementById("f-month"), fCur = document.getElementById("f-cur"),
      fPaid = document.getElementById("f-paid");
uniq("type_of_invoice").forEach(t => fType.add(new Option(t, t)));
uniq("warehouse").forEach(w => fWh.add(new Option(w, w)));
uniq("currency").forEach(c => fCur.add(new Option(c, c)));
[...new Set(DATA.map(r => (r.date || "").slice(0, 7)).filter(Boolean))].sort().reverse()
  .forEach(ym => fMonth.add(new Option(fmtMonth(ym), ym)));

let sortKey = "date", sortDir = -1;
const q = document.getElementById("q");

function filtered() {
  const term = q.value.trim().toLowerCase();
  const ft = fType.value, fw = fWh.value, fm = fMonth.value, fc = fCur.value, fp = fPaid.value;
  let rows = DATA.filter(r => {
    if (ft && r.type_of_invoice !== ft) return false;
    if (fw && r.warehouse !== fw) return false;
    if (fm && (r.date || "").slice(0, 7) !== fm) return false;
    if (fc && r.currency !== fc) return false;
    if (fp === "paid" && !r.paid) return false;
    if (fp === "unpaid" && r.paid) return false;
    if (term) {
      const hay = (r.invoice_number + " " + r.notes + " " + r.bill_period + " " + r.date + " " + fmtDate(r.date)).toLowerCase();
      if (!hay.includes(term)) return false;
    }
    return true;
  });
  rows.sort((a, b) => {
    let x = a[sortKey], y = b[sortKey];
    if (sortKey === "paid") return ((a.paid ? 1 : 0) - (b.paid ? 1 : 0)) * sortDir;
    if (sortKey === "amount") return (x - y) * sortDir;
    return String(x).localeCompare(String(y)) * sortDir;
  });
  return rows;
}

function render() {
  const rows = filtered();
  kpiCards(rows);
  chart("chart-type", "hint-type", "type_of_invoice", rows);
  chart("chart-wh", "hint-wh", "warehouse", rows);
  const tbody = document.getElementById("rows");
  tbody.innerHTML = rows.map(r => {
    const chip = `<span class="chip" style="background:color-mix(in srgb, var(${typeVar(r.type_of_invoice)}) 14%, white);color:var(${typeVar(r.type_of_invoice)})">${esc(r.type_of_invoice)}</span>`;
    const pdf = r.pdf_url ? `<a class="link" href="${esc(r.pdf_url)}" target="_blank" rel="noopener">View PDF ↗</a>` : `<span class="dash">—</span>`;
    const doc = r.supporting_doc_url ? `<a class="link" href="${esc(r.supporting_doc_url)}" target="_blank" rel="noopener">View doc ↗</a>` : `<span class="dash">—</span>`;
    return `<tr>
      <td title="${esc(r.date)}">${esc(fmtDate(r.date))}</td>
      <td class="inv">${esc(r.invoice_number)}</td>
      <td>${chip}</td>
      <td>${esc(r.warehouse)}</td>
      <td>${esc(r.bill_period)}</td>
      <td class="num">${money(r.amount, r.currency)} <span class="cur">${esc(r.currency)}</span></td>
      <td>${r.paid
        ? `<span class="chip" title="Paid ${esc(r.paid_at)}${r.paid_marked_by ? " by " + esc(r.paid_marked_by) : ""}" style="background:color-mix(in srgb, var(--ok) 15%, transparent);color:var(--ok)">✓ Paid</span>`
        : `<span class="chip" style="background:color-mix(in srgb, var(--warn) 15%, transparent);color:var(--warn)">Unpaid</span>`}</td>
      <td class="notes" title="${esc(r.notes)}">${esc(r.notes)}</td>
      <td>${pdf}</td>
      <td>${doc}</td>
    </tr>`;
  }).join("");
  const byCur = {};
  for (const r of rows) byCur[r.currency] = (byCur[r.currency] || 0) + r.amount;
  const totalStr = Object.entries(byCur).sort((a, b) => b[1] - a[1]).map(([c, a]) => money(a, c)).join(" · ");
  document.getElementById("count").textContent =
    rows.length + " of " + DATA.length + (totalStr ? " · " + totalStr : "");
  document.querySelectorAll("thead th[data-k]").forEach(th => {
    const on = th.dataset.k === sortKey;
    th.classList.toggle("sorted", on);
    const ar = th.querySelector(".arrow");
    if (ar) ar.textContent = on ? (sortDir === 1 ? "▲" : "▼") : "▼";
  });
}

document.querySelectorAll("thead th[data-k]").forEach(th => {
  th.addEventListener("click", () => {
    const k = th.dataset.k;
    if (k === sortKey) sortDir = -sortDir;
    else { sortKey = k; sortDir = (k === "amount" || k === "date") ? -1 : 1; }
    render();
  });
});
q.addEventListener("input", render);
[fType, fWh, fMonth, fCur, fPaid].forEach(el => el.addEventListener("change", render));

document.getElementById("foot").textContent =
  "Generated from americanflat.finance.yusen_invoices · regenerate with generate_yusen_dashboard.py";

render();
</script>
</body>
</html>
"""


def main():
    rows = fetch_rows()
    html = build_html(rows)
    with open(OUT_PATH, "w") as fh:
        fh.write(html)
    print(f"Wrote {OUT_PATH} ({len(rows)} invoices)")


if __name__ == "__main__":
    main()
````
