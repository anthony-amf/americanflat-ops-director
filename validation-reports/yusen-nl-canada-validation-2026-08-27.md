# Yusen Netherlands + Canada — invoice validation against supporting docs and agreements

*Run 2026-08-27 from a cloud session. Scope: every `Yusen NL` and `Yusen CA` row in
`americanflat.finance.yusen_invoices` sitting at `needs_detail` — 24 NL rows and 15 Canada rows,
**€135,122.68 + $60,436.05**. Sources: the live Notion rate card (`3898555c…`, fetched this run),
the Brampton rate schedule embedded in each Canada worksheet, the Benelux LSA Schedule 2 rates,
and the invoice PDFs + supporting workbooks in Drive.*

*Cloud BigQuery access is read-only, so **nothing was stamped**. Recommended stamps are listed at
the end for a Mac run. No payment marks are proposed — payment stays a human decision.*

---

## Headline

| | Verdict |
|---|---|
| **Canada — 8 monthly invoices** | **Clean.** Every line, section subtotal, 13% HST, FX conversion and ledger split ties to the cent against the Brampton worksheet. Two housekeeping items, no money at risk. |
| **NL warehousing — 4 `FTI…` invoices** | **Arithmetic clean, rates on-contract.** Every rate recomputes as the LSA 2025 rate × **1.047** Panteia indexation, exactly. €3,851.76 of off-card lines to query. |
| **NL transport — 6 `CA262…` invoices** | **Math exact, rate basis unverifiable.** Fuel/surcharge runs **4.7%–68.4%** of transport with no contractual formula anywhere. This is the real problem. |

---

## 1. Canada (Brampton) — 8 months, $60,436.05

Each monthly invoice is billed in USD off a CAD worksheet. The worksheet *is* the rate schedule —
"Warehousing & Distribution Rates (Brampton, Ont)" — so it doubles as the agreement for line-rate
purposes, and every rate on it matches the Notion card's Canada column ($5.75 pallet, $16.00 pallet
supply, $6.00 wrap, $8.00 BOL, $15.00 manual order, $1,000 + $100 WMS monthly, $50 labour).

Checked per month: line math (qty × rate), rate vs contract, three section subtotals, grand subtotal,
HST at 13%, CAD→USD at the stated FX, the pallet-count basis, and the split into the ledger's
Storage/Receiving rows.

| Invoice | Period | CAD total | FX | USD | Result |
|---|---|---|---|---|---|
| CA2WFS0003089 | Aug 2025 | 15,288.17 | 1.34538 | 11,363.46 | ✅ exact |
| CA2WFS0003115 | Sep 2025 | 15,723.44 | 1.33851 | 11,746.97 | ✅ exact |
| CA2WFS0003152 | Oct 2025 | 14,960.41 | 1.35917 | 11,007.02 | ⚠️ one query (below) |
| CA2WFS0003194 | Nov 2025 | 10,031.29 | 1.43664 | 6,982.47 | ✅ exact |
| CA2WFS0003214 | Dec 2025 | 15,947.29 | 1.32798 | 12,008.69 | ✅ exact |
| CA2WFS0003251 | Jan 2026 | 19,531.99 | 1.33501 | 14,630.60 | ✅ exact |
| CA2WFS0003390 | May 2026 | 19,549.28 | 1.33959 | 14,593.48 | ✅ exact |
| CA2WFS0003477 | Jul 2026 | 11,590.98 | 1.36829 | 8,471.15 | ✅ exact — but see 1.2 |

**The storage basis is confirmed and correct.** Pallet storage bills
`(weekly pallet count − 115) × $5.75`, on top of the fixed $2,850 "Space Reservation 1500 SQFT".
The 115-pallet exclusion is what the $2,850 buys. This holds in all 40 billed weeks across the eight
months, checked against the worksheet's own Weekly Storage Tracking tab. It is not documented
anywhere in our rate card — worth adding, since it is the single largest Canada charge.

**Ledger mapping** (useful for anyone reading `notes`): the invoice's three charge lines map to the
worksheet's three sections — `Storage Charge` = Storage section, `Warehouse Charge` = Value Added
Services section, `WHS In/Out Charge` = Inbound + Order Processing sections. The ledger's `Storage`
row carries the first two; the `Receiving` row carries the third.

### 1.1 Query — October 2025 order processing billed on two mutually exclusive lines

October bills **107 orders at $15.00 "Order processing (Manual Regular)" *and* the same 107 orders
at $2.60 "Order processing (E.D.I.)"** — $278.20 CAD. An order is keyed manually or arrives by EDI,
not both. Every other month bills one or the other, never both.

But October also bills **$0 for "Courier Parcel Shipping Creation"**, where every other month bills
it at the manual-order count ($10 × orders). On 107 orders that is $1,070 CAD *not* charged.

**Net, October is $791.80 CAD in Americanflat's favour.** Per the standing rule that below-card
billing is a stale-card flag rather than a dispute, this is a "raise it, don't withhold" item —
but it should be raised, because if Yusen notices the courier-creation gap first, the correction
will come with the EDI line intact.

### 1.2 Action — the July 2026 receiving charge is missing from the ledger

Invoice CA2WFS0003477 bills **three** lines:

```
Storage Charge - July 2026   3,898.30 + 13% (506.78)
WHS In/Out Charge            2,585.71 + 13% (336.14)   <-- not in BigQuery
Warehouse Charge             1,012.58 + 13% (131.64)
SUBTOTAL 7,496.59  GST/HST 974.56  TOTAL USD 8,471.15
```

BigQuery holds only `CA2WFS0003477-Storage` at $5,549.30 (the Storage + Warehouse lines). The
**`CA2WFS0003477-Receiving` row for $2,921.85 was never ingested**. The worksheet independently
confirms it: Order Processing section $3,538.00 CAD × 1.13 ÷ 1.36829 = $2,921.85.

This is an ingestion gap, not a billing error — the invoice is correct and payable in full at
$8,471.15. The ledger currently understates the July Canada liability by $2,921.85.

---

## 2. NL warehousing — `FTI…`, 4 invoices, €90,225.57

All four reconcile exactly, both to the invoice total and to the ledger's per-charge-type split
(the D365 code totals `CLHAI/CLHAO/CLADM/CLSTO/CLVAS/CLCON` map one-to-one onto the
Receiving/SMLPRCLLTL/Admin/Storage/VAS rows).

| Invoice | Period | Total | Reconciles |
|---|---|---|---|
| FTI0006305 | Apr 2026 | €21,502.91 | ✅ every line and code total |
| FTI0006387 | May 2026 | €28,573.26 | ✅ every line and code total |
| FTI0006458 | Jun 2026 | €20,317.20 | ✅ every line and code total |
| FTI0006502 | Jul 2026 | €19,832.20 | ✅ every line and code total |

### 2.1 The 2026 rates are on-contract — indexation confirmed at exactly +4.70%

Every billed rate is the LSA 2025 rate × 1.047, to the cent. This closes a question the rate card
had left open ("~+4.7% Panteia indexation"):

| Charge | LSA 2025 | × 1.047 | Billed | |
|---|---|---|---|---|
| Back-office admin ≤16h / week | €692.85 | 725.41 | €725.410 | ✅ |
| Back-office admin ≤24h / week | €1,039.27 | 1,088.12 | €1,088.120 | ✅ |
| Back-office admin ≤32h / week | €1,385.70 | 1,450.83 | €1,450.830 | ✅ |
| Outbound B2B, per carton | €1.89 | 1.9788 | €1.980 | ✅ |
| VAS warehouse assistance / hr | €45.04 | 47.157 | €47.160 | ✅ |
| DTC e-comm parcel / carton | €2.89 | 3.0258 | €3.030 | ✅ |
| E-comm additional pick | €0.52 | 0.5444 | €0.540 | ✅ |
| Inbound container unloading / carton | €0.86 | 0.9004 | €0.900 | ✅ |
| Inbound additional admin / carton | €0.14 | 0.1466 | €0.150 | ✅ |
| Inbound sortation / SKU / container | €24.18 | 25.316 | €25.320 | ✅ |
| Storage, EURO pallet / week | €2.75 | 2.8793 | €0.411/day ×7 = 2.877 | ✅ |

The €60 container-unloading minimum was **not** indexed (still €60) — in our favour.

**Storage day-rate rounding.** April billed €0.411/pallet/day (the mathematically correct indexed
rate); May–July bill €0.410. The 0.1¢ difference runs in Americanflat's favour — about €25 on a
25,000 pallet-day month. Not worth raising; noted so nobody "fixes" it upward.

### 2.2 Query — €3,851.76 of lines with no contracted rate

These charges are not on the Notion card and not in LSA Schedule 2, so under the standing rule they
cannot be passed silently:

| Line | Apr | May | Jun | Jul | Total |
|---|---|---|---|---|---|
| Consumable pallet — UPS | €111.52 (17 @ 6.56) | €111.52 (17 @ 6.56) | €88.00 (11 @ 8.00) | €216.00 (27 @ 8.00) | €527.04 |
| Consumable pallet — EUR | — | €100.72 (8 @ 12.59) | €407.00 (37 @ 11.00) | €2,442.00 (222 @ 11.00) | €2,949.72 |
| "No show container EGHU8000695" | €300.00 | — | — | — | €300.00 |
| "Relabeling", fixed | — | €75.00 | — | — | €75.00 |
| | | | | | **€3,851.76** |

Two things make the pallet lines the priority:

1. **The rate changed mid-year with no notice we hold** — UPS €6.56 → €8.00 (+22%), EUR €12.59 →
   €11.00 (−13%), between the May and June invoices. Neither move is the 4.7% indexation.
2. **The basis changed too.** April and May bill "UPS Pallet per month" at a flat qty 17 both months
   — a monthly rental. June and July bill "Consumable pallet UPS/EUR" at volumes that track
   shipments (11, 27 / 37, 222). July alone is €2,658.

Worth testing against the LSA clause that "Outbound Order Fulfillment B2B €1.89/carton **includes
pallet configuration, wrapping and pack-list**". That covers configuration and wrap; whether it
covers the pallet itself is exactly the question the US MSA settled the other way in AF-9 ("no
separate or additional charge shall apply for stretch wrap, **pallet materials**, or standard pallet
preparation"). If the NL contract is meant to read the same way, the €2,949.72 of EUR-pallet
consumables is recoverable.

### 2.3 Query — July outbound cartons don't tie to the outbound detail

The B2B carton count billed should equal the "Total Cartons" on the invoice's own Outbound Detail
tab. It does, exactly, in May and June — and doesn't in July:

| Invoice | Billed B2B cartons | Outbound detail total cartons | |
|---|---|---|---|
| FTI0006387 (May) | 313 | 313 | ✅ |
| FTI0006458 (Jun) | 902 | 902 | ✅ |
| FTI0006502 (Jul) | 433 | 3,076 | ❌ 2,643 short |

At €1.98 that is roughly **€5,233 not billed**. July also shows 196 full pallets against 249 billed
consumable pallets, so some of the volume may be intentionally billed per-pallet instead of
per-carton. Either way: no money at risk today, but a correction invoice is a live possibility and
July should not be treated as closed until Yusen explains the basis.

### 2.4 Confirmed, no action

- **VAT is zero-rated on the `FTI…` family** and 21% on the `CA262…` family. Correct — warehousing
  billed to the US entity is an export service (art. 44), transport is not. Not an error.
- **April inbound**: 5,375 cartons charged per-carton and 5 deliveries charged the €60 minimum, out
  of 5,393 cartons total. No double-count — the 18 minimum-charge cartons are excluded from the
  per-carton line. The €0.15 admin fee does run on all 5,393 (€2.70 overlap); immaterial.
- **May inbound sortation** was not billed at all despite 5 SKUs on the container (€126.60 at rate).
  In our favour.
- **The €6,222/month warehouse minimum** is comfortably exceeded every month.

---

## 3. NL transport — `CA262…`, 6 invoices, €44,897.11 — **this is where the money is**

**Every invoice is arithmetically perfect.** Per-order charges sum to netto, netto sums to subtotal,
VAT is exactly 21%, total = subtotal + VAT. The Amazon Delivery line is a flat €100/order on every
invoice (€400 = 4 orders, €500 = 5 orders). Where a UPS manifest is the supporting doc, the
`TRANSPORT OUTBOUND` line equals the manifest total **to the cent**:

- CA26200039 — manifest €2,583.59 = transport €2,583.59 ✅
- CA26200166 — manifest €4,831.72 = transport €4,831.72 ✅

So the transport base is verifiable and correct. The problem is what sits on top of it.

### 3.1 The fuel / surcharge line has no contractual basis and swings by 14×

| Invoice | Date | Status | Transport (netto) | Fuel/surcharge | **%** |
|---|---|---|---|---|---|
| CA25202908 | 2025-11-28 | PAID | 4,985.23 | 1,225.36 | 24.6% |
| CA25203835 | 2026-01-30 | PAID | 6,789.52 | 4,643.36 | **68.4%** |
| CA25203846 | 2026-01-30 | PAID | 2,165.21 | 550.82 | 25.4% |
| CA25204456 | 2026-02-27 | PAID | 7,464.06 | 4,536.45 | **60.8%** |
| CA25204461 | 2026-02-27 | PAID | 3,737.07 | 1,006.02 | 26.9% |
| CA25204851 | 2026-03-31 | PAID | 2,449.93 | 809.43 | 33.0% |
| CA25204854 | 2026-03-31 | PAID | 4,019.41 | 981.17 | 24.4% |
| **CA26200039** | 2026-04-30 | **OPEN** | 2,583.59 | 134.51 | 5.2% |
| **CA26200043** | 2026-04-30 | **OPEN** | 2,180.70 | 1,042.99 | **47.8%** |
| **CA26200096** | 2026-05-29 | **OPEN** | 2,693.56 | 130.62 | 4.8% |
| **CA26200110** | 2026-05-29 | **OPEN** | 1,608.99 | 668.61 | **41.6%** |
| CA26200152 | 2026-06-30 | PAID | 1,210.00 | 100.10 | 8.3% |
| CA26200158 | 2026-07-01 | PAID | 2,255.88 | 478.02 | 21.2% |
| **CA26200166** | 2026-07-31 | **OPEN** | 4,831.72 | 3,072.33 | **63.6%** |
| **CA26200172** | 2026-07-31 | **OPEN** | 13,188.99 | 620.96 | 4.7% |

**€20,000.75 netto of fuel and surcharge on €62,163.86 of transport since November 2025 — a blended
32.2%.** €5,670.02 of it sits on the six open invoices.

Neither the Notion rate card nor LSA Schedule 2 states a fuel-surcharge formula or names an index.
The card explicitly parks Transport Outbound as "a variable lane rate — not rate-card checkable",
and the fuel line inherits that gap. So this cannot be validated either way today.

Two observations that shape the ask:

**The percentages are printed on the invoice, and they move within a single invoice.** CA26200110
bills five orders at 42.43%, 42.43%, 42.43%, 40.29%, 39.46% — descending with loading date
(08/05 → 18/05 → 29/05). CA26200043 bills 44.83%, 48.6%, 48.6%, 48.6%. That is index-like behaviour,
and each line's arithmetic is exact, so this is a *rate* question, not a billing error. A surcharge
in the 40s is defensible **only** if it is quoted against a frozen historic base tariff — a real
Dutch practice, but one we have nothing on file to confirm.

**CA26200166 is the weakest of the set and the one to hold.** Its €3,072.33 surcharge is printed as
a bare lump sum with `UNIT 0.00, TARIFF 0.00` — no percentage, no basis, nothing in the manifest.
The same UPS-manifest product was billed at 5.2% and 4.8% in April and May. On a €9,563.90 open
invoice that is the single largest unexplained charge in this run.

### 3.2 Recommended position

- **Hold CA26200166 (€9,563.90)** pending an itemised basis for the €3,072.33 surcharge.
- **Pay CA26200039, CA26200096 and CA26200172** — 5.2%, 4.8% and 4.7% surcharges, all consistent
  with a normal diesel index, all fully supported.
- **Query CA26200043 and CA26200110** (€7,745.57 combined) before paying — 47.8% and 41.6%.
- **Ask Yusen Benelux for the fuel-surcharge clause: the index, the base tariff and the reset
  frequency.** Once we hold that, the seven paid invoices carrying 21%–68% become a look-back worth
  running; at stake there is €12,635.53 netto of already-paid surcharge if the basis turns out not
  to support it.

### 3.3 Ledger correction

`CA26200043-SMLPRCLLTL` is recorded at **€4,384.67**; the invoice total is **€4,384.66**. The 1¢
comes from storing each component VAT-inclusive and rounding three times. Trivial, but it should be
the invoice figure if this row is ever paid from the ledger.

---

## Recommended stamps (Mac run — cloud BigQuery is read-only)

Nothing below marks anything paid.

| Rows | Stamp | Variance |
|---|---|---|
| 14 Canada rows: 3089, 3115, 3194, 3214, 3251, 3390 (Receiving + Storage each), 3477-Storage, 3152-Receiving | `valid` | — |
| CA2WFS0003152-Storage | `valid` | — |
| 4 × FTI0006305, 5 × FTI0006387, 4 × FTI0006458, 4 × FTI0006502 | `valid` | — |
| CA26200039, CA26200096, CA26200172 | `valid` | — |
| CA26200043, CA26200110 | `needs_detail` | fuel basis unverified |
| CA26200166 | `needs_detail` | €3,072.33 surcharge unsupported |

Ingestion fix, separately: insert `CA2WFS0003477-Receiving`, $2,921.85, Yusen CA, July 2026,
`WHS In/Out Charge (+13% GST 336.14)=2,921.85`.

## Open questions for Yusen

1. **Benelux** — the fuel/surcharge clause: index, base tariff, reset frequency. And an itemised
   basis for CA26200166's €3,072.33.
2. **Benelux** — contractual basis and rate history for the consumable pallet lines (€3,476.76
   Apr–Jul); does the €1.98 B2B carton fee already cover pallet materials?
3. **Benelux** — why FTI0006502 billed 433 outbound cartons against 3,076 on its own detail tab.
4. **Brampton** — October 2025: 107 orders billed on both the Manual Regular and E.D.I. lines, with
   the courier-creation line at zero.

## Housekeeping for our side

- Add the Canada storage basis — `(weekly pallets − 115) × $5.75` plus the $2,850 space reservation
  — to the Notion rate card. It is the largest Canada charge and is currently undocumented.
- Add the confirmed NL indexation factor (**×1.047**, 2026) to the card, and the Brampton line rates
  the Notion Canada column is missing ($12.50 pallet handling in/out, $2.80 Amazon parcel with
  carton pick, $10.00 courier parcel shipping creation, $1.05 container unloading, $0.50 labelling,
  $0.75 bin/week).
