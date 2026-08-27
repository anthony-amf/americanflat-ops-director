# Cloud validation sweep — runbook

*Executed by the scheduled cloud sessions — 10:00 AM, 1:00 PM and 5:30 PM ET
(the last is 30 min after the 3 PM MT ingestion). A fresh session follows this
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
       notes, pdf_url, validation_status, validation_report,
       validated_by, paid_at, currency, supporting_doc_url
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

`validated_by` and `paid_at` are not decoration: step 5's stickiness rules key
off both (a stamp whose `validated_by` isn't `AUTO_WRITER` is a *human* verdict
that an automated pass must not overwrite). Selecting them here avoids a second
round-trip once you reach the write step.

## 2. Get the validator — MUST be v1.4.0 or newer, verify it

v1.4.0 (on the default branch since 2026-08-06) is the first release with both
halves: the stickiness rules (a disputed stamp, a paid-valid stamp, and any
human-set stamp survive an automated re-sweep) **and** the PDF line-level pass.
Unzip the committed package and check before doing anything:

```bash
cd ~/americanflat-ops-director && git fetch origin && git pull --ff-only 2>/dev/null; \
  unzip -qo yusen-invoice-validator.skill -d /tmp/skill && \
  grep -qE 'version = "1\.([4-9]|[1-9][0-9])' /tmp/skill/yusen-invoice-validator/skill.toml && \
  grep -q 'apply_line_pass' /tmp/skill/yusen-invoice-validator/scripts/validate_rate_card.py && \
  grep -q 'AUTO_WRITER' /tmp/skill/yusen-invoice-validator/scripts/validate_rate_card.py && \
  echo VALIDATOR_OK
```

If `VALIDATOR_OK` does not print, **STOP**: report "validator v1.4.0+ not
available — sweep skipped" and change nothing. Never fall back to an older
script; the older ones lack either the line pass or the stamp protections.

```bash
pip install pypdf cryptography cffi 2>/dev/null   # container pypdf is broken without these
pip install --ignore-installed packaging google-cloud-bigquery   # validate_rate_card imports it at module level
apt-get update && apt-get install -y tesseract-ocr poppler-utils   # scanned SC VAS
```

Both installs are load-bearing, not optional:

- **`google-cloud-bigquery`** — the script imports `google.cloud.bigquery` at the
  top, so *importing* it fails without the library even though this sweep writes
  over REST and never builds a client. Plain `pip install` aborts on the system
  `packaging` ("Cannot uninstall packaging 24.0, RECORD file not found");
  `--ignore-installed packaging` clears it.
- **OCR** — `apt-get install` alone 404s on the pinned `poppler-utils` build, so
  `apt-get update` first. Skipping OCR is not cosmetic: on 2026-08-27 the three
  scanned SC VAS invoices (756671, 756631, 755390) came back "PDF has no
  extractable text → needs_detail" without it and cleared to `valid` on the
  re-run with it. Install OCR *before* the validation pass, not after.

**Never run `validate_rate_card.py --list-all --write`.** That path writes
with the script's own label and sweeps by invoice number descending, which
puts the excluded NL (`FTI…`) rows first and burns the run on them. Import
the functions and write via step 5 instead.

## 3. Download the PDFs (Drive MCP — drive.google.com is not proxy-reachable)

For each work-list row, extract the Drive file id from `pdf_url`
(`/file/d/<id>/` or `?id=<id>`), download via the Google Drive connector's
`download_file_content`, base64-decode, and save to `/tmp/pdf-cache/<invoice_number>.pdf`
(the name the validator's cache lookup expects).
Batch sensibly; a missing/failed PDF is not fatal — that row just degrades to
the header-level result.

Expect **every** download to come back as "result exceeds maximum allowed tokens"
— an invoice PDF is ~0.5-4 MB, so its base64 always blows the tool-result cap.
That is the normal path, not a failure: the payload is written to a file under
`tool-results/` whose JSON is `{content, id, mimeType, title}`. Decode from those
files with a script, matching each one's `id` back to the invoice by the Drive id
from `pdf_url`; never read the base64 into the conversation. Fire the downloads in
parallel batches of ~8 and decode them all in one pass at the end.

## 4. Validate

Import the skill script and run the same pass the Mac sweep runs:

```python
import sys; sys.path.insert(0, '/tmp/skill/yusen-invoice-validator/scripts')
import validate_rate_card as V
from pathlib import Path
import json
rates = json.load(open('/tmp/skill/yusen-invoice-validator/references/rate-card-snapshot.json'))
r = V.validate(row_dict, rates)                          # header pass
V.apply_msa_conflicts(row_dict, r)                       # notes-based dispute check
V._line_pass_keeping_disputes(row_dict, r, Path('/tmp/pdf-cache'))   # PDF line pass
```

Run all three in that order. `_line_pass_keeping_disputes` is the wrapper that
stops the PDF pass from demoting a dispute the notes-based check already found.
When `r["_settled"]` is set, the row was already settled — skip it, do not write.

`row_dict` is the BigQuery row as a dict (keys as in the SELECT above).

## 5. Write the stamps (REST, one multi-statement script)

Generate one UPDATE per changed row, mirroring `write_result` semantics
exactly — build the report with `V.merge_report(prior_report, V.compose_report(r))`,
which replaces only its own previous `[AUTO <date>]` block and leaves payment
cards, `[MSA DISPUTE …]` specs and human notes alone.

- SET `validated_at = CURRENT_TIMESTAMP()`, `validation_status`,
  `validation_variance` (disputed $ for disputed rows, else the result's
  variance), `validated_by = V.AUTO_WRITER`, and `validation_report` = the
  merged report.
- **`validated_by` MUST be `V.AUTO_WRITER` (`yusen-invoice-validator`), never a
  cloud-specific label.** v1.4.0 treats any other value as a *human* stamp and
  makes it sticky — labelling cloud writes separately would freeze every row
  the sweep touches against all future automated updates. Provenance belongs in
  the report text (the `[AUTO <date>]` block), not in `validated_by`.
- WHERE `invoice_number = '<inv>' AND IFNULL(validation_status,'') NOT IN
  ('disputed', 'valid')` — never downgrade disputed or valid. (A `discrepancy`
  result may overwrite `valid`: drop `'valid'` from the guard for those rows
  only.)
- **Never stamp SP/LTL `valid`** (the engine already enforces this) and
  **never touch `paid_at`** (payment is human-confirmed only).
- Prefer **named query parameters** (`parameterMode: "NAMED"` + `queryParameters`
  in the REST body, one UPDATE per row) over string-building the SQL. That is
  what `write_result` does, and it removes the quote-escaping hazard entirely —
  report cards routinely contain apostrophes. If you do build SQL by hand,
  escape single quotes out of the report text. Either way: no free text after
  intl `notes` components.
- Rows ingested <~90 min ago may reject UPDATE (streaming buffer) — skip on
  that error; tomorrow's sweep catches them.

Every write carries a fresh `[AUTO <date>]` block in `validation_report`. That
is the signature to check: if a run finishes and no row shows today's `[AUTO]`
block, the run did not actually do its job — say so in the summary rather than
reporting success.

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
