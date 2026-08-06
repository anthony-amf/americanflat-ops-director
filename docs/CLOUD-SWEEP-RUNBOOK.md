# Cloud validation sweep — runbook

*Executed by the daily scheduled cloud session (`yusen-cloud-validation-sweep`,
21:30 UTC = 3:30 PM MDT, 30 min after ingestion). A fresh session follows this
file top to bottom. Written 2026-08-06; owner anthony@americanflat.com.*

## Guard first: probe write access

The cloud BigQuery credential (`cluade-service-account@americanflat.iam.gserviceaccount.com`,
proxy-injected) starts read-only. Before doing anything else, probe:

```
POST https://bigquery.googleapis.com/bigquery/v2/projects/americanflat/queries
{"query": "UPDATE `americanflat.finance.yusen_invoices` SET validated_by = validated_by WHERE FALSE", "useLegacySql": false}
```

- **Access Denied (`bigquery.tables.updateData`)** → the write grant hasn't
  landed yet. STOP: do no work, produce a one-line summary ("write grant not
  yet in place — sweep skipped"), and end. Do not retry, do not attempt
  workarounds, do not modify anything.
- **Succeeds (0 rows affected)** → proceed.

## 1. Pull the work list (read via BigQuery REST; curl with the proxy CA)

```sql
SELECT invoice_number, type_of_invoice, warehouse, amount, date, bill_period,
       notes, pdf_url, validation_status, validation_report
FROM `americanflat.finance.yusen_invoices`
WHERE IFNULL(validation_status,'') IN ('', 'needs_detail', 'error')
  AND NOT STARTS_WITH(invoice_number, 'CA2WFS')   -- Canada: separate contract
  AND NOT STARTS_WITH(invoice_number, 'CA262')    -- NL transport
  AND NOT STARTS_WITH(invoice_number, 'FTI')      -- NL warehousing
ORDER BY date DESC
```

Set maxResults ≥ 500 (the bq 100-row truncation trap applies to the CLI, but
be explicit anyway). Rows already `valid`/`disputed`/`paid` are settled — the
WHERE clause excludes them; never re-judge them.

## 2. Get the validator (line-level engine, skill v1.2.0+)

```bash
cd /tmp && unzip -o ~/americanflat-ops-director/yusen-invoice-validator.skill -d /tmp/skill
# If the repo clone is on a branch without the v1.2.0 package (check
# CHANGELOG.md inside for "1.2.0"), fetch it from main-07xt41:
#   git -C ~/americanflat-ops-director fetch origin main-07xt41 &&
#   git -C ~/americanflat-ops-director show origin/main-07xt41:yusen-invoice-validator.skill > /tmp/skill.zip &&
#   unzip -o /tmp/skill.zip -d /tmp/skill
pip install pypdf cryptography cffi 2>/dev/null   # container pypdf is broken without these
apt-get install -y tesseract-ocr poppler-utils 2>/dev/null || true   # scanned SC VAS
```

## 3. Download the PDFs (Drive MCP — drive.google.com is not proxy-reachable)

For each work-list row, extract the Drive file id from `pdf_url`
(`/file/d/<id>/` or `?id=<id>`), download via the Google Drive connector's
`download_file_content`, base64-decode, and save to `/tmp/pdf-cache/<invoice_number>.pdf`.
Batch sensibly; a missing/failed PDF is not fatal — that row just degrades to
the header-level result.

## 4. Validate

Import the skill script and run the same pass the Mac sweep runs:

```python
import sys; sys.path.insert(0, '/tmp/skill/yusen-invoice-validator/scripts')
import validate_rate_card as V
from pathlib import Path
import json
rates = json.load(open('/tmp/skill/yusen-invoice-validator/references/rate-card-snapshot.json'))
r = V.validate(row_dict, rates)                      # header pass
V.apply_line_pass(row_dict, r, Path('/tmp/pdf-cache'))  # PDF line pass (cache hit)
```

`row_dict` is the BigQuery row as a dict (keys as in the SELECT above).

## 5. Write the stamps (REST, one multi-statement script)

Generate one UPDATE per changed row, mirroring `write_result` semantics
exactly — see `V._merge_report` for the report merge:

- SET `validated_at = CURRENT_TIMESTAMP()`, `validation_status`,
  `validation_variance` (disputed $ for disputed rows, else the result's
  variance), `validated_by = 'yusen-cloud-sweep'`, and `validation_report` =
  the merged report (prior text with any old `[AUTO-SWEEP ...]` block
  replaced by the fresh dated one).
- WHERE `invoice_number = '<inv>' AND IFNULL(validation_status,'') NOT IN
  ('disputed', 'valid')` — never downgrade disputed or valid. (A `discrepancy`
  result may overwrite `valid`: drop `'valid'` from the guard for those rows
  only.)
- **Never stamp SP/LTL `valid`** (the engine already enforces this) and
  **never touch `paid_at`** (payment is human-confirmed only).
- Escape single quotes out of report text (or avoid them); no free text after
  intl `notes` components.
- Rows ingested <~90 min ago may reject UPDATE (streaming buffer) — skip on
  that error; tomorrow's sweep catches them.

## 6. Summarize

End with a compact rollup (counts per status, disputed $ found, rows deferred
to buffer, PDFs unavailable). If a NEW disputed line is found (an invoice not
already in `validation-reports/yusen-msa-billing-dispute-2026-08-05.md`),
say so explicitly in the summary — that's a human follow-up item.

## Hard rules (from CLAUDE.md / SKILL.md — binding)

1. Never mark anything paid. 2. Never downgrade `disputed`. 3. SP/LTL valid
requires the Stedi gate — the sweep never grants it. 4. All changes to
BigQuery are the UPDATEs described above; no DDL, no DELETE, no schema work.
5. If anything is ambiguous, prefer leaving the row untouched over guessing.
