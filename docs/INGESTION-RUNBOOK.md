# Invoice ingestion — runbook (cloud, unattended)

*Phase 0 of the single nightly run `yusen-nightly-validation-2am-mt`, **2:00 AM MT
daily**, executed before phase 1 (contract validation) and phase 2 (EDI shipping).
Written 2026-08-11; owner anthony@americanflat.com.*

*Anthony chose **fully unattended** ingestion (2026-08-11) over the human-sign-off
alternative. The safety property that replaces the operator's eyes is the money
gate in step 5: an invoice whose stated total does not equal the sum of its parts is
**parked, never loaded**. Nothing reaches the ledger unless its arithmetic is
internally consistent.*

## Prerequisite — the drop folder (BLOCKING, not yet configured)

This job reads invoice PDFs from **one Google Drive folder**. It cannot read email
attachments: the Gmail connector exposes attachment *names* but no way to download
attachment *bytes*, so an invoice that only exists as an email attachment is
unreachable from here. That is a structural limit of the cloud environment, not a
permission that can be granted.

So something has to put each invoice PDF into Drive before 2 AM. Options, best
first:

1. **A Gmail filter plus an Apps Script** that saves attachments from the Yusen
   sender (or anything arriving at a dedicated address) into the drop folder. One
   time to set up, then invisible. This is the recommended route.
2. **Yusen sends to a Drive-connected address** or shares the invoice into the
   folder directly — worth asking, since it removes a moving part.
3. **A person drops the PDFs in.** Still a manual step, but a 10-second one that
   needs no context, unlike running the loader.

Set `DROP_FOLDER_ID` below once the folder exists, and delete the "not configured"
line. **Until then, phase 0 must no-op in one line** — do not guess a folder, do
not fall back to searching all of Drive, and do not try to reconstruct invoices from
email bodies.

```
DROP_FOLDER_ID = <not configured>
```

Note where finished invoice PDFs live today, which is *not* the drop folder: they
are in **administrator@americanflat.com**'s Drive, created by the current Mac
process seconds before it writes the row (756711.pdf: file created 20:00:21 UTC,
row written 20:00:30). Drive is presently the *output* of ingestion, not its input.
That is exactly what this changes.

## Step A — the staleness check (ALWAYS run this, even when phase 0 no-ops)

**Run this before the guards, every single night, whether or not the drop folder is
configured.** It is the one part of phase 0 that works today.

```sql
SELECT DATE_DIFF(CURRENT_DATE(), DATE(MAX(ingested_at)), DAY) AS days_since_ingest,
       DATE_DIFF(CURRENT_DATE(), MAX(date), DAY)              AS days_since_newest_invoice
FROM `americanflat.finance.yusen_invoices`
```

Report against these thresholds, which come from the real cadence (median gap
**1 day**; normal runs land 1–3 days apart):

| `days_since_ingest` | Say |
|---|---|
| 0–3 | nothing — this is normal, don't mention it |
| 4–6 | "no invoices ingested in N days — worth a glance" |
| 7 or more | **"INGESTION STALE: nothing loaded in N days."** Treat as a probable fault |

Same for `days_since_newest_invoice`: past **14 days** say
**"no invoice newer than <date> — we may be missing billing weeks."** That one
catches a different failure: the pipe works but Yusen stopped sending.

**Why this earns its place.** Ingestion has gone quiet for 9 days (Jul 13→22),
8 days (Jul 28→Aug 5) and 5 days (Jul 22→27) — every one because it depended on a
person being available to trigger it (Anthony, 2026-08-11: "I was OOO and couldn't
trigger it — hence the move to automation"). Nobody was told; the invoices simply
weren't there.

Automating the load does not by itself fix that. It relocates it. If the email →
Drive step breaks, or the folder id goes stale, or Yusen changes the sending
address, this job reports "nothing to ingest" every night — **which reads exactly
like "no invoices arrived."** A silent gap is the failure mode that already cost
two weeks this summer, and an automated job is better at producing silence than a
person is.

So the rule is: **quiet is only ever reported as quiet for up to three days.**
Beyond that, say something. A false alarm during a genuinely slow week costs one
line in a summary that nobody minds reading. A missed month costs a month.

## Guard 1: BigQuery write access

```
POST https://bigquery.googleapis.com/bigquery/v2/projects/americanflat/queries
{"query": "UPDATE `americanflat.finance.yusen_invoices` SET validated_by = validated_by WHERE FALSE", "useLegacySql": false}
```

Access Denied → STOP phase 0, one-line report, change nothing.

## Guard 2: Drive connector

No Drive connector in the session → STOP phase 0 in one line. Without it there is
nothing to read.

## 1. List candidates

Files in `DROP_FOLDER_ID` (`parentId = '<DROP_FOLDER_ID>'`), `mimeType =
'application/pdf'`. For each, note the file id, title and `createdTime`.

If the folder is empty, phase 0 is done — say so in one line. That is the expected
outcome most nights, the same way the other two phases usually find nothing.

## 2. Skip anything already loaded (dedupe before spending any work)

Pull the invoice numbers already present:

```sql
SELECT invoice_number FROM `americanflat.finance.yusen_invoices`
```

An invoice already in the table is **never re-ingested and never overwritten**, even
if the PDF in Drive looks newer. Duplicate loading is the one failure mode that
corrupts the ledger silently — two rows for one invoice double the amount owed in
every rollup.

Match on the invoice number you extract in step 4, not on the filename — filenames
are a convenience (`756711.pdf`), not a contract. For international invoices the key
is `<invoice_number>-<ChargeType>` (see step 4), so check each charge-type row.

## 3. Get the text

Download via the Drive connector's `download_file_content`, base64-decode to
`/tmp/ingest/<file_id>.pdf`, then extract text. `pypdf` needs
`pip install pypdf cryptography cffi` in this container.

If a PDF has **no text layer** it is a scan — SC VAS work orders are the known case.
OCR it (`apt-get install -y tesseract-ocr poppler-utils`, then `pdftoppm` +
`tesseract`). If OCR yields nothing usable, park the invoice as
`unreadable` and move on. Never guess at numbers from a filename.

## 4. Map onto the table

One row per invoice, columns exactly as the ledger has them:

| Column | Notes |
|---|---|
| `invoice_number` | as printed, string |
| `date` | invoice date, `YYYY-MM-DD` |
| `bill_period` | the billing window as printed |
| `type_of_invoice` | `SMLPRCL/LTL`, `VAS`, `Storage`, `Admin`, `Receiving` |
| `warehouse` | as printed; `WAREHOUSE_MAP` in the validator normalises it later |
| `amount` | invoice total, plain number |
| `currency` | `USD`, or `EUR` for NL |
| `notes` | see the format rule below — **load-bearing** |
| `pdf_url` | `https://drive.google.com/file/d/<file_id>/view` |
| `supporting_doc_url` | same form, if a supporting worksheet accompanies it |
| `ingested_at` | `CURRENT_TIMESTAMP()` |

Leave `validation_status`, `validation_variance`, `validated_at`, `validated_by`,
`validation_report`, `paid_at` and `paid_marked_by` **NULL**. Phase 1 sets the
validation fields minutes later; payment is Anthony's alone. Ingestion never
pre-judges an invoice.

**International invoices land one row per charge type** —
`CA2WFS0003428-Storage`, `FTI0006502-Admin` — each carrying its own share of the
total, with the breakdown in `notes` in exactly this shape:

```
Storage: USD 1,234.56 | Handling=100.00, Storage=1,134.56
```

The parser that sum-checks these reads that format literally. **Never append free
text after the components** — it breaks the sum check on a row that is otherwise
fine.

## 5. The money gate (this is what replaces the operator)

For every invoice, compare the **stated total** against the **sum of the line items
you extracted**.

- **They agree (to the cent)** → eligible to load.
- **They disagree** → **park it. Do not load.** Record it in the summary as
  `MISMATCH <invoice> stated $X vs summed $Y (difference $Z)` and leave the PDF in
  the drop folder so the next run sees it again.

A mismatch means the extraction is probably wrong — a missed line, a doubled line, a
misread digit. Occasionally the invoice really is internally inconsistent, and that
is worth a human knowing about. Either way the answer is the same: it does not go
in. There is no `--force` in an unattended job.

Also park, rather than load, when: no invoice number can be read; the total cannot
be found; `type_of_invoice` cannot be determined; or the currency is ambiguous.
**Parking is cheap and reversible. A bad row in the ledger is neither** — it flows
into the dashboards, the dispute totals, and what Yusen gets paid.

## 6. Insert with DML, not the streaming API

```sql
INSERT INTO `americanflat.finance.yusen_invoices`
  (invoice_number, date, bill_period, type_of_invoice, warehouse, amount,
   currency, notes, pdf_url, supporting_doc_url, ingested_at)
VALUES (@invoice_number, DATE(@date), @bill_period, ...)
```

**Use `INSERT` through the query API. Do not use the streaming insert endpoint
(`tabledata.insertAll`).** Rows written by the streaming API sit in a buffer for
roughly 90 minutes during which `UPDATE` is rejected — which is why freshly
ingested invoices have always had their validation stamps deferred to the next day.
Rows written by DML are updatable immediately, so phase 1 can validate tonight's
invoices tonight. This is the whole reason ingestion runs first in the same session.

One statement per invoice, parameterised. After inserting, re-read each invoice
number back and confirm exactly one row exists.

## 7. Report

Per invoice: loaded (with number, type, amount) or parked (with the reason and the
figures). Then a count of each. Call out explicitly:

- every **MISMATCH**, with both numbers — these need a human to look at the PDF,
- anything **unreadable** after OCR,
- any invoice number that looked like a **duplicate** of an existing row.

If nothing was in the folder, one line saying so.

Then continue to phase 1. Do not stop the run because phase 0 found nothing or
parked everything — the other two phases have their own work.

## Hard rules

1. Never overwrite or update an existing invoice row. Ingestion only inserts.
2. Never load an invoice whose arithmetic does not check out.
3. Never set any `validation_*` field, `paid_at`, or `paid_marked_by`.
4. No DDL, no DELETE, no schema changes — if a column is missing, stop and report.
5. Never invent a value to fill a column. NULL is honest; a guess is not.
6. If anything about an invoice is ambiguous, park it. The next run will see it
   again, and a person can look in the meantime.
