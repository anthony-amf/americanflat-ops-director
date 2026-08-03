---
name: skill-invoice-to-bigquery
description: >
  Reads PDF invoices and loads their contents into BigQuery for Americanflat.
  Use this skill whenever the user wants to ingest, upload, record, or log one
  or more invoice PDFs into BigQuery — including freight/drayage carrier bills
  (Line Haul, FSC, Chassis Rental, BOB Tail, container numbers) and other
  vendor invoices with varying layouts and a variable number of line items.
  Trigger when the user says things like "upload this invoice to BigQuery",
  "load these bills into BQ", "record this PDF invoice", "ingest the invoices
  in my Downloads folder", "add this carrier invoice to the finance dataset",
  or points at one or more `Bill_*`/`INV_*` PDFs and wants them in BigQuery.
  The skill checks for gcloud first, parses each PDF onto a fixed schema,
  shows the operator the total for sign-off, then writes via service-account
  impersonation. It performs no IAM changes itself.
---

# Invoice → BigQuery

## What this skill does (and deliberately doesn't)

It turns invoice PDFs — whose layouts and line-item counts vary from vendor to
vendor — into rows in a BigQuery table, with a human checkpoint on the money
before anything is written.

It **does not** manage permissions. It never creates service accounts,
datasets, tables, or IAM bindings. It only *uses* access the admin has already
granted, by impersonating a service account. If the operator hasn't been
granted that access, the skill stops and tells them whom to ask. This keeps
the admin as the single gatekeeper — see `references/admin_setup.md`.

There are two roles in play. Keep them straight:
- **Operator** — the person running this skill to load invoices. Needs gcloud
  + a one-time `gcloud auth login` + the admin's impersonation grant.
- **Admin** — owns the dataset, runs the one-time setup, grants/revokes
  operators. That's not this skill's job.

## Step 0 — Warm-up (always do this first)

Greet the operator and orient them before doing anything. Say, in your own
words, something like:

> Hi! I'll load your invoice PDF(s) into BigQuery. First I'll check that the
> Google Cloud CLI (`gcloud`) is installed — if it isn't, I can install it for
> you. Heads up on one thing before we start: once I've read each invoice,
> I'll show you the total I extracted next to the sum of the line items and
> ask you to confirm the number looks right **before** I write anything.
> These are money documents, so you get the final say.

Then check for gcloud:

```bash
gcloud --version
```

- **If it's installed**, continue.
- **If it's missing** (command not found), tell the operator and *offer to
  install it for them* — don't just dump instructions. Installing a CLI is a
  local tool install and grants no cloud access, so it's safe to do on their
  behalf with their go-ahead. Read `references/install_gcloud.md` and run the
  command for their platform (this machine is Windows — prefer
  `winget install --id Google.CloudSDK`). After install, remind them to open a
  new terminal and run `gcloud auth login` once as themselves.

Don't verify dataset permissions up front — a real load attempt gives a
clearer, more actionable error than a pre-flight probe, and the load script
already handles permission-denied gracefully.

## Step 1 — Extract the text from each PDF

These invoices are digitally generated, so a plain text extraction is faithful
and cheap:

```bash
python scripts/extract_text.py "<path-to-invoice.pdf>" ["<more.pdf>" ...]
```

Read the printed text. If a file reports **NO TEXT LAYER FOUND**, it's a
scanned image — use the `pdf` skill to OCR it, then carry on with that text.

## Step 2 — Map the text onto the canonical schema

This is the step that absorbs layout variability: *you* read the extracted
text and produce one JSON object per invoice that matches the canonical shape.
A new vendor with a different layout needs no code change — only careful
mapping. Use `references/example_invoice.json` as the template.

Rules that make the data trustworthy and queryable:

- **Normalize as you map.** Dates → `YYYY-MM-DD`. Money → plain numbers (strip
  `$`, `USD`, and thousands separators; `1,234.50` → `1234.50`). `invoice_id`
  is the invoice number as a string.
- **Capture every line item**, in order, with `line_number` starting at 1.
  Each has `description`, `quantity`, `rate`, `amount`. If a value isn't
  printed, use `null` — don't invent one.
- **Never drop information.** Anything that doesn't map to a canonical column
  (extra fees, tax lines, remit-to address, notes, a second container number,
  unfamiliar fields from a new vendor) goes into `raw_extraction`. This is the
  safety net — it means an unexpected layout still lands losslessly and stays
  queryable later.
- **Infer `vendor_name`** from who *issued* the invoice (the letterhead /
  remit-to party), not the bill-to (which is American Flat).
- If a field genuinely isn't present, set it to `null`. Don't guess.

Save each invoice object to its own file, e.g.
`<scratchpad>/invoice_<invoice_id>.json`.

## Step 3 — Human checkpoint on the totals (required)

Before any write, run the review (this touches nothing in the cloud):

```bash
python scripts/load_to_bq.py review "<scratchpad>/invoice_<id>.json"
```

Show the operator the output — especially **stated total vs. summed line
items** — and the line-item table. Then explicitly ask them to confirm, e.g.
"Does $905.00 look right for invoice 13540? Want me to load it?"

- Wait for a clear yes. Loading is gated on their okay — never load on
  assumption.
- If review prints **MISMATCH**, treat it as a real signal: re-read the PDF
  text and fix your mapping (a missed, doubled, or misread line is the usual
  cause). Only proceed past a genuine mismatch if the operator confirms the
  invoice itself is internally inconsistent — and then the load needs
  `--force`.

For a batch, review them all and let the operator approve the set (or
cherry-pick) rather than making them okay each one blindly.

## Step 4 — Load into BigQuery

After the operator's okay:

```bash
python scripts/load_to_bq.py load "<scratchpad>/invoice_<id>.json"
```

The script impersonates the configured service account, refuses silent
duplicates (same `invoice_id` already present) and totals mismatches, stamps
provenance (who loaded it, when, which model parsed it), and writes the row.

Handle the common outcomes plainly:
- **Success** → report which invoice landed in which table.
- **PERMISSION DENIED** → the operator hasn't been granted impersonation. Pass
  along the script's message: ask the admin to grant
  `roles/iam.serviceAccountTokenCreator` on the writer service account, then
  `gcloud auth login` and retry. Do **not** try to fix permissions yourself.
- **Duplicate** → the invoice is already loaded. Confirm with the operator
  before re-running with `--allow-duplicate`.
- **Placeholder config** → `config.json` hasn't been filled in by the admin
  yet; point them to `references/admin_setup.md`.

## Configuration

Target is resolved from `config.json` (committed — these are identifiers, not
secrets), overridable per-run by environment variables
`INVOICE_BQ_PROJECT` / `INVOICE_BQ_DATASET` / `INVOICE_BQ_TABLE` /
`INVOICE_BQ_SA` / `INVOICE_BQ_LOCATION` (handy for pointing at a test dataset
without editing the file).

## Dependencies

- Google Cloud CLI (`gcloud` + `bq`) — see Step 0.
- Python 3.9+ with PyMuPDF: `python -m pip install pymupdf`
