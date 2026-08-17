# Amazon payables vs. remittance detail — 2026-08-17

Line-by-line match of the Vendor Central **"Your payables — ready for deduction"**
export against the **Payments / remittance detail** export.

Produced by `amazon-payables-remittance-match.py`. Workbook:
`amazon-payables-remittance-match.xlsx` (6 tabs, every line accounted for).

| | |
|---|---|
| Vendor code | AMWV0 (single vendor across all 1,881 payable lines) |
| Payable lines | 1,881 — invoice total **-$87,223.32**, open balance **-$86,939.89** |
| Remittance payments | 51, dated **8/3/2026 – 8/17/2026**, totalling **$1,017,352.58** |
| Remittance lines | 3,046 across 46 payments |
| Join key | payables *Transaction number* = remittance *Invoice Number* |

## The one thing to act on

**32 payable lines totalling -$892.85 have already been deducted, but the
payables file still shows -$857.14 of them as open.**

All 32 are on-time-shipment chargebacks dated 8/13/2026. Payment **368031671**
(8/14/2026) took -$857.14 of them; two of the 32 had a first slice of -$35.71
taken on 8/13 that the payables file *does* reflect. The payables export was
pulled 8/17 but its "Deducted amount" column had not caught up with the 8/14
payment.

Nothing is owed here and nothing was double-taken — the payables list is simply
stale by about three days. Do not chase these; they will drop off the list on
their own. Full detail on tab **1 Already deducted**.

## What is genuinely still open

1,849 lines, **-$86,082.75** open balance, with no remittance hit inside the
8/3–8/17 window (tab **2 Still open**):

| Type | Lines | Amount |
|---|---:|---:|
| Contra COGS | 31 | -$70,042.03 |
| Chargeback | 1,767 | -$15,150.17 |
| Product Returns | 51 | -$1,138.27 |

Contra COGS is 81% of the open balance from 31 lines, and one line is most of
it: **6268-1493883845, 8/16/2026, -$56,285.83**. The next largest is
-$3,231.25. Everything else in that bucket is under $1,300.

Open chargebacks by transaction month — the June 2026 block dominates:

| Month | Lines | Amount |
|---|---:|---:|
| Dec 2025 | 3 | -$30.23 |
| Mar 2026 | 146 | -$1,477.06 |
| Jun 2026 | 1,529 | -$12,527.36 |
| Aug 2026 | 89 | -$1,115.52 |

Product returns are all small: 51 lines from -$145.44 down to -$10.06.

### Scope limit on "still open"

The remittance export only covers payments from 8/3/2026 forward, but payables
go back to 12/10/2025. A line on tab 2 means *no remittance in this window
touched it* — not that it was never deducted. Anything with a transaction date
before August would need an earlier remittance export to confirm. That mainly
affects the March and June chargebacks and most of the Contra COGS.

One line already shows this: **6268-1365200160** (Contra COGS, 3/17/2026) has
-$247.72 of its -$284.75 deducted, and the offsetting remittance is outside
this file's date range.

## Payment tie-out

**42 of 51 payments tie out to the penny** — the sum of each payment's
remittance lines equals the payment amount exactly.

The 9 that do not are **exactly the 9 Amazon flagged** in the note embedded in
the export: *"One or more remittance items processed as part of this payment
will not be displayed, as the corresponding ordering codes are not setup in your
account."* Their combined gap is **$77,909.43** (5 payments partially detailed,
4 with no line detail at all):

| Payment | Date | Amount | Lines shown | Missing |
|---|---|---:|---:|---:|
| 367531888 | 8/3 | $5,417.17 | $1,482.68 | $3,934.49 |
| 367597718 | 8/5 | $12,642.12 | — | $12,642.12 |
| 367685796 | 8/6 | $6,513.79 | — | $6,513.79 |
| 367734387 | 8/7 | $4,869.25 | — | $4,869.25 |
| 367840854 | 8/10 | $11,424.09 | $770.32 | $10,653.77 |
| 367906916 | 8/12 | $14,218.47 | $3,261.73 | $10,956.74 |
| 367987643 | 8/13 | $9,116.89 | $1,507.47 | $7,609.42 |
| 368031614 | 8/14 | $6,762.72 | — | $6,762.72 |
| 368110393 | 8/17 | $13,967.13 | — | $13,967.13 |

The fix is on Amazon's side: those payments settled orders billed under
ordering codes that are not attached to the AMWV0 account, so the portal will
not render their lines. Worth asking the vendor manager to attach the missing
ordering codes — until then $77,909.43 of received cash cannot be traced to
invoices from this export.

Whole-file check: invoices settled $2,623,198.90, deductions taken
-$1,683,755.75, net $939,443.15, plus the $77,909.43 of hidden lines =
$1,017,352.58, the payments total exactly.

## No duplicate deductions

11 claims were applied in slices across more than one payment (tab
**5 Multi-payment claims**). Every one sums back to its full claim amount — no
claim was taken twice:

| Claim | Slices | Applied | Result |
|---|---:|---:|---|
| 260807_PROVISION_FOR_AGED_RECEIVABLE | 9 | -$561,119.52 | ties |
| 16222737HPA26 (DFP for AR invoice) | 7 | -$317,227.20 | ties |
| 6268-1482323095 (Co-op) | 2 | -$218,181.80 | ties |
| 6268-1490026100 (Damage allowance) | 3 | -$127,492.06 | ties |
| 6268-1490899880 (Co-op) | 2 | -$55,514.66 | ties |
| 6268-1482815445 (Co-op) | 2 | -$4,389.16 | ties |
| 6268-1491314905 (SPA) | 2 | -$3,059.08 | ties |
| VC17413SC (Shortage claim) | 2 | -$877.82 + $17.91 discount | ties |
| 1520586356VCBSINV, 1520809184VCBSINV, 1520815899VCBSINV | 2 each | small | tie |

**The aged-receivable provision nets to zero.** -$561,119.52 was taken across 9
payments between 8/7 and 8/10, then reversed in full (+$561,119.52,
`260807_PROVISION_FOR_AGED_RECEIVABLE-R`) on payment 367872930 on 8/10. No cash
impact.

The largest deduction that was **not** reversed is **16222737HPA26** at
-$317,227.20, applied across 7 payments 8/4–8/6 and described only as "DFP for
AR Invoice". Co-op deductions across the window total -$434,313.93 over 46
lines, and shortage claims -$90,889.03 over 104 lines. These are the amounts
worth auditing if any of the August deductions are being disputed.

## Deductions taken but not on the payables list

2,063 negative remittance lines have no matching payable (tab
**3 Deducted not on list**). This is expected: once Amazon takes a deduction it
falls off the "ready for deduction" list. It includes all the large co-op,
damage-allowance and provision items above.

## Reproducing

```bash
python3 amazon-payables-remittance-match.py \
  "Your payables - ready for deduction.csv" \
  "Payments.xlsx" \
  --out amazon-payables-remittance-match.xlsx
```

Both exports come from Vendor Central: Payments → *Remittance* (the Payments
workbook, which carries the line detail in a second section below the payment
list) and Payments → *Payables ready for deduction*.
