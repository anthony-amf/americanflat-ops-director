# Containers — ocean freight check and container register

Started 2026-10-19.

- `check_ocean_freight.py` — checks a WWL ocean freight (FCL) invoice against
  the rate sheet in effect when the container gated in at origin.
- `register.py` — builds a register of inbound containers (container, HBL,
  MBL, factory, sailing and arrival dates) from WWL's shipment emails.
- `test_check_ocean_freight.py` (13 cases), `test_register.py` (4 cases).

## Ocean freight

No fixed rate card — rates follow the market. WWL sends rate sheets on the 1st
and 15th of each month, East Coast and West Coast
(`Americanflat Ocean Freight Rates 10 15 26 EC.pdf`). Mahjoub asked WWL on
10/16 to keep that schedule and to copy Kent, Angela and Anthony.

**WWL's billing rule** (Ariana Ramos, 2026-10-14, on HBL TAO26070091): the rate
is the **sheet in effect on the day the container gated in at the origin
port**, for that carrier and service. TAO26070091 (1×40HC Xingang → New York,
Yang Ming, gated 8/05) was billed $12,020 off the 8/01 sheet; TAO26080010 on
the same lane gated 8/20 was billed $10,460 on a Yang Ming special rate from
the 8/15 sheet. Mahjoub accepted the explanation.

The check: billed freight vs (sheet rate × containers) for the matching
origin / destination / carrier / service / size. Above the sheet →
`discrepancy`; below → fine, noted; special rates, missing lanes, missing
gate-in dates, per diem and any other charge → `needs_detail`.

Rate sheets are read from CSV rows:

    effective_date,coast,origin,destination,carrier,service,size,rate_usd
    2026-08-01,EC,Xingang,New York,YML,regular,40HC,12020

## Container register — the thread through the cost chain

WWL's arrival notices and sailing advices carry HBL, MBL and container
numbers in the subject line and the factory in the body. Run over the last
five months of arrival notices (2026-05-20 → 10-12) that gives **77
containers** — Dezhou Nissens, Intco, Y&J, Tianjin Tong Shi and others.

The container number is the key that ties one container's bills together:

| Bill | How it carries the container |
|---|---|
| WWL ocean freight | HBL on the invoice → register → containers |
| Customs (CBP 7501) | HBL / container on the entry |
| O'Neill drayage | container on the invoice |
| Yusen receiving | worksheet: `PO: AME*MSMU6558953-… Container: MSMU6558953` |

Checked: Fontana receiving bill 758385 (2026-09-02) is container TGBU4720405,
which the register shows arriving 8/14 under HBL TAO26070092 from Intco; the
June receiving bill 754676 lists 28 containers, 11 of them in the register
(the rest arrived before the five-month window or through Amazon's Century
program).

## Not covered yet

- **Century (Amazon's freight program, cds-net.com)** — "Local Charge
  Invoices" at Ningbo/Tianjin in CNY, mostly confirmed and paid by the
  factories. Need to know which of these Americanflat pays.
- **Per diem / demurrage** follow-up invoices — held for review with the
  carrier's bill.

## Open items

1. **Rate sheets as data.** The PDFs arrive as email attachments, which this
   setup can't open. Either save each sheet's rows to CSV (or a Google Sheet)
   when it arrives, or ask WWL to send them as Excel.
2. **WWL invoices.** Ocean freight invoices come from jlansang@wwllmail.com
   ("INVOICE - AMERICAN FLAT CORPORATION", HBL in the body, invoice numbers
   like LAX261000727). Need a few PDFs to build the reader, plus the
   gate-in date (from WWL's sailing advice or the carrier).
3. **Automate the register** — run the email search on a schedule and write
   the rows to BigQuery (`freight_invoices` or a new containers table) once
   write access is granted.
