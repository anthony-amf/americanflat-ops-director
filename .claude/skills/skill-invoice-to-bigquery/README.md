# skill-invoice-to-bigquery

Reads PDF invoices and loads their contents into BigQuery for Americanflat.

## What it does

Invoices arrive as PDFs with different layouts and a varying number of line
items. This skill:

1. **Checks for `gcloud`** and offers to install it if it's missing.
2. **Extracts** each PDF's text (PyMuPDF).
3. **Maps** the text onto a fixed schema — header fields, a repeated
   `line_items` array (so any number of lines fits one row), and a
   `raw_extraction` catch-all so nothing from an unfamiliar layout is lost.
4. **Shows you the total** it captured vs. the sum of the line items and waits
   for your okay — these are money documents.
5. **Loads** the row into BigQuery by impersonating a service account (no key
   files on anyone's laptop).

## Permissions model (important)

The skill performs **no IAM changes**. One service account is the only
identity that writes to BigQuery; operators *impersonate* it. Adding or
removing an operator is a single grant the admin runs — see
[`references/admin_setup.md`](references/admin_setup.md). On permission-denied,
the skill tells the operator whom to ask; it never escalates access itself.

## Usage

Within Claude Code, ask things like:

- "Upload this invoice to BigQuery"
- "Load the bills in my Downloads folder into BQ"
- "Record this carrier invoice in the finance dataset"

## Operator setup (one-time)

1. Install gcloud (the skill can do this for you).
2. `gcloud auth login` — sign in as yourself.
3. Ask the admin to grant you impersonation on the writer service account.

No service-account key file is ever created or shared.

## Admin setup (one-time)

See [`references/admin_setup.md`](references/admin_setup.md): create the
service account, dataset, and table; grant the SA `WRITER` on the dataset;
grant each operator `roles/iam.serviceAccountTokenCreator`; fill in
`config.json`.

## Configuration

`config.json` (committed — these are identifiers, not secrets):

| key | meaning |
|-----|---------|
| `project_id` | GCP project |
| `dataset` | BigQuery dataset |
| `table` | target table |
| `impersonate_service_account` | the writer SA's email |
| `location` | dataset location (e.g. `US`) |

Override any of them per-run with `INVOICE_BQ_PROJECT`, `INVOICE_BQ_DATASET`,
`INVOICE_BQ_TABLE`, `INVOICE_BQ_SA`, `INVOICE_BQ_LOCATION`.

## Scripts

| script | purpose |
|--------|---------|
| `scripts/extract_text.py` | PDF → text (PyMuPDF) |
| `scripts/load_to_bq.py review <json>` | print totals comparison; no cloud access |
| `scripts/load_to_bq.py load <json>` | load via impersonation (after sign-off) |

## Dependencies

- Google Cloud CLI (`gcloud` + `bq`)
- Python 3.9+ and `pymupdf`
