# Nightly Stedi (EDI) order check — runbook

*Executed by the scheduled cloud session `yusen-stedi-nightly`, 2:00 AM ET
daily. Purpose: close the shipping axis on Small Parcel / LTL invoices so they
stop parking at `needs_detail`. Written 2026-08-07; owner
anthony@americanflat.com.*

## What this does, in one line

For every SP/LTL invoice that hasn't had its shipping check yet, confirm each
billed order actually shipped (EDI 945, falling back to 940 = in warehouse),
recompute the e-com pick charge on the contract's **additional-only** basis,
and record both findings on the invoice row. It never marks anything paid.

## Guard 1: is the API key present?

```bash
[ -n "$STEDI_API_KEY" ] && echo KEY_OK || echo KEY_MISSING
```

`KEY_MISSING` → **STOP**. Report one line: "STEDI_API_KEY not set in this
environment — nightly EDI check skipped, no rows touched." Do not attempt
workarounds, do not guess match rates, change nothing.

The key and the network route both landed **2026-08-11**: `STEDI_API_KEY` is in the
environment (id `rmyNws8`) and `core.us.stedi.com` is allowed through the proxy —
verified with an authenticated call returning HTTP 200. So `KEY_MISSING` is no
longer the expected outcome; if it happens, the environment setting was removed or
the session did not pick it up, and that is worth reporting as a fault rather than
a routine skip.

## Guard 2: BigQuery write access

Same probe as the validation sweep:

```
POST https://bigquery.googleapis.com/bigquery/v2/projects/americanflat/queries
{"query": "UPDATE `americanflat.finance.yusen_invoices` SET validated_by = validated_by WHERE FALSE", "useLegacySql": false}
```

Access Denied → STOP with one line, as above.

## 1. Work list — SP/LTL invoices whose shipping check hasn't run

```sql
SELECT invoice_number, warehouse, amount, CAST(date AS STRING) d,
       supporting_doc_url, validation_status, validation_variance,
       validation_report
FROM `americanflat.finance.yusen_invoices`
WHERE type_of_invoice LIKE 'SML%'
  -- US warehouses only. Stedi indexes the US EDI feed; NL and Canada orders are
  -- simply absent from it, so checking them yields false "unmatched" findings.
  AND NOT STARTS_WITH(invoice_number, 'CA262')      -- NL transport
  AND NOT STARTS_WITH(invoice_number, 'CA252')      -- NL
  AND NOT STARTS_WITH(invoice_number, 'CA2WFS')     -- Canada
  AND NOT STARTS_WITH(invoice_number, 'FTI')        -- NL warehousing
  -- Unsettled only. A paid row, or one already stamped valid, is closed: the
  -- shipping question was answered before payment and re-asking it changes
  -- nothing. `disputed` IS included — the shipping evidence supports the claim.
  AND paid_at IS NULL
  AND IFNULL(validation_status,'') IN ('', 'needs_detail', 'error', 'disputed')
  AND supporting_doc_url IS NOT NULL
  AND (
        -- never checked
        validation_report NOT LIKE '%[STEDI %'
        -- or checked, came back with gaps, and is still inside the 5-day retry window
        OR (validation_report LIKE '%[STEDI %'
            AND validation_report LIKE '%UNMATCHED%'
            AND REGEXP_EXTRACT(validation_report, r'\[STEDI (\d{4}-\d{2}-\d{2})[^\]]*\](?!.*\[STEDI )')
                >= FORMAT_DATE('%Y-%m-%d', DATE_SUB(CURRENT_DATE(), INTERVAL 5 DAY)))
      )
ORDER BY date DESC
```

**The `[STEDI <date>]` block is the "already checked" marker — with one
exception: a check that found unmatched orders is retried for 5 days.**

A clean result is final: checked once, then left alone forever. But EDI
shipment data lags — an order billed today may not appear in Stedi for a day or
two, so a same-week check can report a gap that is really just timing. Those
get retried each night for **5 days from the last check**, then stop.

Five days is deliberate (Anthony, 2026-08-07): unmatched orders already trigger
manual lookups on the ops side, so anything real will have surfaced by then. A
gap still open after 5 days is a genuine finding — Yusen billed an order with
no shipping evidence — and should stay flagged rather than be re-queried
forever.

Write the retry so it is visible: each retry appends a fresh `[STEDI <date>]`
block, so the row's history shows the gap was re-checked and when. If a retry
clears the gap, apply the normal status rules (100% matched, no pick overcharge
-> `valid`). If day 5 passes with the gap open, say so in the summary once so a
human picks it up — do not keep raising it nightly after that.

Rows whose status is already `disputed` still get checked (the shipping
evidence is useful either way) but their status is never changed by this job.

**Scope matters — check the count before you start.** The first version of this
query had no status filter and no non-US exclusions, so it selected **61 invoices
worth $552K** including invoices paid and closed as far back as October 2025, plus
12 NL/Canada rows whose orders are not in the US Stedi feed at all. Caught
2026-08-11 on the first manual run, before it wrote anything. Two consequences,
both bad: the NL rows would have collected false `UNMATCHED` findings — which then
re-query for five nights and read like "Yusen billed an order that never shipped" —
and 754807 alone carries 8,966 orders, so re-checking dozens of settled invoices
means tens of thousands of needless API calls and a real chance of hitting a rate
limit partway through a run.

With the filters above the list should be roughly **10 US invoices** (as of
2026-08-11: 756521, 756156, 756028, 755721, 755725, 755486, 755131, 754807,
754702, 754698 — about $174K, mostly `disputed` rows awaiting the shipping axis).
If the count comes back far outside that range, stop and say so rather than
working through it — the query or the data has changed and it is worth a human
look first.

## 2. Get the supporting worksheet

`supporting_doc_url` is a Drive link. Pre-2026-07-13 rows hold legacy
`docs.google.com` links — rewrite to
`https://drive.google.com/file/d/<id>/view` before use. Download via the Google
Drive connector (`download_file_content`), base64-decode to
`/tmp/stedi/<invoice>.xlsx`.

No supporting doc, or download fails → record nothing for that invoice, list it
in the summary as "worksheet unavailable", move on.

**Guard 3: is the Google Drive connector attached to this session?** Without it
there is no way to fetch a worksheet, so every invoice degrades to "worksheet
unavailable" and the whole run does nothing. If Drive is unavailable, STOP after
the work list and report one line naming the count of invoices that were skipped
for this reason — do not walk the list writing "unavailable" onto each row.
The connector cannot be set through the trigger API for this org; it is attached
per-Routine in the claude.ai Routines UI. As of 2026-08-11 it is attached to
`yusen-cloud-validation-sweep` only — **not** to `yusen-stedi-nightly` and not to
`yusen-cloud-validation-sweep-midday`.

## 3. Parse the order numbers

```bash
python3 /tmp/skill/yusen-invoice-validator/scripts/parse_invoice_excel.py \
  /tmp/stedi/<invoice>.xlsx <invoice> --output /tmp/stedi/<invoice>.json
```

Handles all three layouts (modern Yusen, Taylored, per-carton SHIPPED report),
dedupes order IDs and strips the `AME*`/`AMF*`/`AMS*` prefixes Stedi doesn't
index. **BOL numbers are not Stedi identifiers** — they are excluded from the
denominator and verified by worksheet count instead.

## 4. Run the check

For invoices under ~300 orders the bundled script is fine:

```bash
python3 /tmp/skill/yusen-invoice-validator/scripts/validate_stedi.py <invoice> \
  --json-file /tmp/stedi/<invoice>.json
```

Above that it is too slow — use a concurrent checker (ThreadPoolExecutor, ~10
workers) against `https://core.us.stedi.com/2023-08-01/transactions`, 945
first then 940 for anything not found. Fontana invoices run 1,000–9,000 orders.

Record: orders checked, matched via 945, matched via 940, and the specific
unmatched IDs (cap the stored list at ~20 with a count). **When any order is
unmatched, the stored block must contain the literal word `UNMATCHED`** — the
5-day retry query in step 1 keys off it. A fully matched check must NOT contain
that word, or it will be re-queried needlessly.

## 5. Recompute the e-com pick charge (the money question)

The MSA line is "Per **Additional** Ecom Pick" — the first pick on an order is
not billable. From the worksheet:

- billed picks and billed pick $ (from the invoice line),
- contract-compliant picks = Σ max(units − 1, 0) over orders,
- overcharge = (billed picks − compliant picks) × the site pick rate
  (0.506 NJ/CA, 0.5796 SC).

**Do not assume the halving convention — verify it per invoice.** The
"invoice bills half the worksheet pick-column sum" rule holds on some
worksheets (754807) but NOT on others: on 756521 the pick column sums to
exactly the billed count (1,883 = 1,883), so halving would have understated
the compliant basis and produced a nonsense result. Procedure: sum the pick
column, compare to the billed pick count, and only halve if the sum is ~2x
billed. Also restrict the comparison to rows that actually carry a pick charge
— 756521 had 75 of 1,214 rows with no pick charge (LTL lines), and including
them distorts the basis.

Any overcharge over $1 is an AF-9/pick-basis dispute item — see
`validation-reports/yusen-msa-billing-dispute-2026-08-05.md` for how 754807
(~$2,209) and 755131 were computed. Report it; do not create the dispute stamp
unless the rules below allow it.

## 6. Write the result

One UPDATE per invoice. Append a `[STEDI <date>]` block to
`validation_report` (leave every other block intact — `[AUTO …]`, `[MSA DISPUTE
…]`, payment cards), containing the match counts, the unmatched IDs, and the
pick recompute.

**Never assign `validation_report` wholesale** — read the current value, splice
your block in, write the whole merged text back (`V.merge_report(prior, block,
tag="STEDI")` in validator v1.5.0+). This job owns the `[STEDI]` tag and nothing
else. Overwriting the field is what destroyed the itemized math and prior Stedi
results on 754891 and 755265 on 2026-08-11; on a settled row nothing rebuilds it.

Status rules — narrow on purpose:

| Finding | Status | Variance |
|---|---|---|
| 100% matched, no pick overcharge, **and the contract check has run** | `valid` | unchanged |
| 100% matched, no pick overcharge, contract check has NOT run | leave as-is (`needs_detail`) | unchanged |
| 100% matched, pick overcharge > $1 | `disputed` | overcharge $ (add to any existing disputed $) |
| Any order unmatched | leave as-is (`needs_detail`) | unchanged |
| Row already `disputed` | leave status; add the `[STEDI]` block | add overcharge to existing variance only if it is a NEW finding |

**A clean shipping check alone must never promote a row to `valid`.** This job
verifies one axis — that the billed orders shipped — plus the one contract
question it can answer from the worksheet (the pick basis). It does not check the
rate card, the $10 all-in pallet rule (AF-9), the removed pack-out (AF-7), or the
invoice math. Those belong to the daytime sweeps.

Stamping `valid` drops the row out of the daytime work list **permanently**, so
promoting on shipping evidence alone can close the file on an invoice whose rates
were never checked. That is a live risk, not a hypothetical: the daytime sweep is
explicitly allowed to fall back to a header-level result when it cannot fetch the
PDF, and the Google Drive connector is still not attached to the `-midday` Routine.
An invoice could take a header-only pass at 10 AM and be sealed `valid` at 2 AM
with its wrap or pack-out lines never examined — the two findings that make up most
of the ~$9,207 dispute position.

So before writing `valid`, confirm the contract side is actually done. It is done
when the row's `validation_report` carries any of:

- a `[DEEP PASS …]` block (in-conversation itemized review), or
- an `[MSA REVAL …]` block, or
- an `[AUTO …]` block reporting a line-level result — it names the parsed lines
  ("at MSA-schedule rates") or carries a `Line detail:` line.

If none of those is present, write the `[STEDI]` block with the clean shipping
result, **leave the status at `needs_detail`**, and list the invoice in the summary
as "shipping clear, waiting on the line-level check" so the next daytime sweep
finishes it. Nothing is lost — the shipping result is recorded and the invoice
gets its `valid` stamp on the next pass that can read the PDF.

- `validated_by` MUST be `yusen-invoice-validator` (the standard automated
  writer). Any other value is treated as a human stamp downstream and freezes
  the row.
- **Never touch `paid_at`.** A clean shipping check makes an invoice payable;
  it does not make it paid. That stays Anthony's call.
- Never downgrade a `valid` or `disputed` stamp.

## 7. Summarize

Report per invoice: orders checked, match rate, pick overcharge if any, and the
status change if any. Call out explicitly:

- any invoice with unmatched orders (billed but no shipping evidence — the
  reason this check exists),
- any NEW pick overcharge, with the dollar figure, since that adds to the
  dispute position and needs a human to fold into the report.

If the work list was empty, say so in one line — that is the expected outcome
most nights.
