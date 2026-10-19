# Customs entry check (WWL / CBP 7501)

Checks a US customs entry before its duty bill is approved in bill.com.
Started 2026-10-19.

- `check_customs.py` — the check (reads one entry as JSON).
- `us_duty_rates.csv` — our duty sheet's US table: tariff code, base rate,
  China Sec 301 rate, and the sheet's own audit notes. Extracted from the
  "Inbound Customs Data" tab of *Master Inventory Tracker 2026*.
- `test_check_customs.py` — 12 cases on made-up entries.

## How customs is billed today

WWL (Worldwide Logistics) is both our ocean forwarder and our customs broker.
For each container WWL emails three documents: the ACE cargo release, the
**CBP Form 7501 entry summary** (every product's value, tariff code, duty
rate and duty, plus the port fees), and WWL's own brokerage invoice
(numbers like `CLA260800385`). The duty is paid to CBP through bill.com as a
bill from "Bureau of Customs and Border Protection", one per entry number
(`8NW-1592065-…`, `NYS-0051539-1`), approved by Mahjoub. Recent ones run
from about $1,800 to $18,800.

## What it checks

1. **Line math** — each duty line = entered value × the rate printed beside
   it, for the product's own code and every Chapter 99 add-on (Sec 301
   `9903.88.xx`, reciprocal `9903.01.xx`).
2. **Port fees** — MPF 0.3464% of the total value inside the yearly minimum
   and maximum; HMF 0.125% of value, ocean entries only.
3. **Totals** — duty + fees = the 7501 total = the bill.com bill.
4. **Rates against our sheet** — base rate per tariff code, and the Sec 301
   rate for China. A difference is flagged for review, not as an overcharge:
   the official tariff schedule wins over our sheet, and the sheet already
   flags several of its own rows (PS Frame, Metal Frame, Basket, Pillow).

Math and total errors → `discrepancy` (the amount over). Rate differences
from the sheet, a code not on the sheet, a reciprocal tariff charged while
the sheet says "paused", or an MPF cap we don't have for that fiscal year →
`needs_detail`.

## Open items

1. **Real 7501s.** Every case so far is made up. Need a few real WWL entry
   summaries (PDF) to build the reader for their layout — e.g. the ones
   behind bill.com bills NYS-0051539-1 ($4,040.79), NYS-0051722-3
   ($17,602.05, Mahjoub noted "+23usd") and CLA261000320 ($18,835.68).
2. **MPF limits.** Loaded: FY2025 $32.71–$634.62 and FY2026 $33.58–$651.50.
   FY2027 (entries from 2026-10-01) isn't loaded — add CBP's figures to
   `MPF_LIMITS` when confirmed (WWL will know them).
3. **Reciprocal (IEEPA) tariffs.** The sheet lists them as "paused" with
   rates beside them (China 30%, others 10%). If they are actually being
   collected, every entry will show them and should not be flagged — confirm
   which it is and update the check.
4. **Fix the sheet's own flagged rows** (PS Frame Sec 301, Metal Frame Sec
   301, the three products sharing 4420.90.8000, Basket's missing Sec 301
   code) so the comparison is against correct rates.
5. **WWL's brokerage fee** (the CLA invoice) isn't checked — need WWL's
   brokerage rate sheet. Mahjoub has asked WWL to send ocean rates on the 1st
   and 15th of each month for the same purpose.
6. Mahjoub mentioned to WWL (10/16) that he is building a tool to validate
   customs and WWL invoices — line this up with him so there's one tool.
