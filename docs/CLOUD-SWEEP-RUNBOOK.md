# Cloud validation sweep — runbook

*Phase 1 of the single nightly run `yusen-nightly-validation-2am-mt`, **2:00 AM MT
daily** (Anthony, 2026-08-11), about 11 hours after the 3 PM MT ingestion so nothing
is still in BigQuery's streaming buffer. Phase 2 is `STEDI-NIGHTLY-RUNBOOK.md`, run
straight after this one in the same session. A fresh session follows this file top
to bottom. Written 2026-08-06; owner anthony@americanflat.com.*

*Replaces the former three-a-day schedule (10 AM / 1 PM / 5:30 PM ET). There is no
second pass: whatever this run leaves unfinished waits a full day, so prefer
finishing an invoice properly over finishing the list quickly.*

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
apt-get install -y tesseract-ocr poppler-utils 2>/dev/null || true   # scanned SC VAS
```

**Never run `validate_rate_card.py --list-all --write`.** That path writes
with the script's own label and sweeps by invoice number descending, which
puts the excluded NL (`FTI…`) rows first and burns the run on them. Import
the functions and write via step 5 instead.

## 3. Download the PDFs (Drive MCP — drive.google.com is not proxy-reachable)

For each work-list row, extract the Drive file id from `pdf_url`
(`/file/d/<id>/` or `?id=<id>`), download via the Google Drive connector's
`download_file_content`, base64-decode, and save to `/tmp/pdf-cache/<invoice_number>.pdf`.

**This step is why the sweep has been ineffective, so read the next paragraph before
running it.** Without PDFs every row stays `needs_detail` for ever — the header pass
alone cannot resolve a single invoice — and the run then looks like a clean no-op when
it has actually done nothing. The 2026-08-12 02:00 MT run wrote nothing at all while
27 invoices sat waiting, and 756711 went from `needs_detail` to `valid` the moment its
PDF was read (3,811 pallets x $4.34 = $16,539.74, exact). **Fetching the PDFs *is* the
job. A pass that skips them is not a cheaper sweep, it is a pointless one.**

**The download will not come back inline.** These invoice PDFs run 0.5-3 MB, so
`download_file_content` returns base64 far larger than a tool result can hold. The
harness spills it to a file and hands you the path instead, in a message that reads
like an error but is not one. Handle it exactly this way:

1. Call `download_file_content` with the file id.
2. If the result is a normal inline JSON payload, decode `content` from it.
3. If instead you get "result (N characters) exceeds maximum allowed tokens … Output
   has been saved to `<path>`", use that path. **Do not read the file into context** —
   it is megabytes of base64 and reading it wastes the run. Decode it with a script:

```python
import base64, json
d = json.load(open("<path from the message>"))          # {content, id, mimeType, title}
open(f"/tmp/pdf-cache/{invoice_number}.pdf", "wb").write(base64.b64decode(d["content"]))
```

4. Sanity-check the first bytes are `%PDF-` before handing it to the line pass.

Then `pip install pypdf cryptography cffi` (the container's pypdf is broken without
them) and confirm `import pypdf` works before starting the batch.

Work through the list one invoice at a time — download, decode, validate, write, then
the next. Do not try to download everything first: each spill file is megabytes, and
holding 27 of them buys nothing. A missing or failed PDF is not fatal for the run;
that row degrades to the header-level result and gets named in the summary as
"PDF unavailable" so it is visible rather than silently unresolved.

## 4. Validate

Import the skill script and run the same pass the Mac sweep runs:

```python
import sys; sys.path.insert(0, '/tmp/skill/yusen-invoice-validator/scripts')
import validate_rate_card as V
from pathlib import Path
import json
rates = json.load(open('/tmp/skill/yusen-invoice-validator/references/rate-card-snapshot.json'))
r = V.validate(row_dict, rates)                          # header pass
V.apply_vas_pallet_check(row_dict, r)                    # Savannah VAS pallet work orders
V.apply_msa_conflicts(row_dict, r)                       # notes-based dispute check
V._line_pass_keeping_disputes(row_dict, r, Path('/tmp/pdf-cache'))   # PDF line pass
```

Run all four in that order. `apply_vas_pallet_check` (v1.6.0+) judges Savannah's
VAS pallet work orders — Savannah bills pallets as VAS jobs, and the generic VAS
logic cannot resolve them, so they parked at `needs_detail` even when billed
correctly. It reads quantity and rate from `notes`, so it needs no PDF and no OCR;
when it fires, the next two calls deliberately step aside rather than re-judging
the same charge. `_line_pass_keeping_disputes` is the wrapper that
stops the PDF pass from demoting a dispute the notes-based check already found.
When `r["_settled"]` is set, the row was already settled — skip it, do not write.

`row_dict` is the BigQuery row as a dict (keys as in the SELECT above).

## 5. Write the stamps (REST, one multi-statement script)

Generate one UPDATE per changed row, mirroring `write_result` semantics
exactly — build the report with `V.merge_report(prior_report, V.compose_report(r))`,
which replaces only its own previous `[AUTO <date>]` block and leaves payment
cards, `[MSA DISPUTE …]` specs and human notes alone.

**Never assign `validation_report` directly.** Always go through `merge_report`.
Each pass owns exactly one tagged block and must leave every other block byte-for-byte
intact — the row's history (`[MSA REVAL …]`, `[DEEP PASS …]`, `[STEDI …]`,
`[PAID …]`) is the audit trail, and on a settled row nothing will ever rebuild it.
Writing the field wholesale is what wiped the itemized math and Stedi results off
754891 and 755265 on 2026-08-11.

**Do not let a header-level result talk over a deeper one.** Before composing,
check the prior report for a `[DEEP PASS …]`, `[STEDI …]`, `[MSA DISPUTE …]` or
`[MSA REVAL …]` block. If one is present and this pass came back `needs_detail`,
write a single line instead of the full card:

```
Invoice <inv> — header-level re-check only, no new findings. Itemized detail is
already on file above (<tags>); this pass does not supersede it. Header total
$<amount>, unchanged.
```

The `[AUTO]` block is written last, so it reads as the current verdict on the
dashboards. Appending "provide itemized counts / no order-level Stedi result" under
a completed deep pass makes a finished invoice look unfinished — exactly what
happened on 755265. Validator v1.5.0+ does this automatically
(`V._deferral_block(r, prior_report)`); on v1.4.0 the sweep must do it by hand.

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
- Escape single quotes out of report text (or avoid them); no free text after
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
