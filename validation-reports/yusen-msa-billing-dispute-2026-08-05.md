# Yusen/Taylored MSA billing dispute — consolidated position

*Prepared 2026-08-05 from a full sweep of all US SP/LTL invoices (15 NJ, 15 SC,
12 Fontana) plus all 27 SC VAS invoices, validated against the 7.15.2026 MSA
markup (rate schedule extracted from the embedded rate table), the supporting
Excel worksheets, and Yusen's own billing history. Anthony confirmed the draft
MSA rates are final — only KPI and insurance language remains open.*

## Contract basis

1. **AF-9 — National Pallet Rate.** "$10.00 per pallet across all warehouses,
   inclusive of pallet and stretch wrap. No separate or additional charge shall
   apply for stretch wrap, pallet materials, or standard pallet preparation."
   The embedded rate table still carries separate "Pallet Stretch Wrap
   (Grade B)" lines ($4.347 NJ / $4.317 CA/GA) — AF-7 flags the table as stale
   and requiring regeneration. Corroboration: Yusen's own week-of-7/23 invoices
   (755721 NJ, 755725 Fontana) bill pallets at $10.00 flat with no wrap line.

2. **Rate schedule line "Per Additional Ecom Pick"** ($0.506 NJ/CA, $0.5796 GA).
   The line item is *additional* picks. Yusen's May worksheets billed exactly
   that way (single-unit orders: zero pick charge). The June Fontana worksheet
   (754807) switches to charging **every** pick — 7,030 of 7,107 single-unit
   orders carry a pick charge, none of which is an "additional" pick.
   (Convention note: invoices bill exactly half the worksheet pick-column sum
   in both eras — the halving is not era-specific and does not affect the
   basis-change claim.)

3. **AF-7 — "Per Pack Out" removed.** Yusen agreed 4/28 that the "Per Pack Out
   rate can be removed" ($0.9200 NJ / $0.9660 CA). NJ invoices from the June
   weeks onward still bill it as "PACK CARTON @ 0.92".

## Disputed amounts by invoice

| Invoice | Site | Paid? | Wrap (AF-9) | Pack-out (AF-7) | Picks (basis) | Disputed |
|---|---|---|---:|---:|---:|---:|
| 754698 | NJ | HOLD | 582.50 | 94.76 | — | **677.26** |
| 754699 | NJ | **PAID 8/1** | 525.99 | 43.24 | — | **569.23** |
| 754702 | NJ | no | 252.13 | 31.28 | — | **283.41** |
| 754704 | NJ | **PAID 8/1** | 778.11 | — | — | **778.11** |
| 755486 | NJ | no | 495.56 | 576.84 | — | **1,072.40** |
| 755721 | NJ | no | — | 18.40 | — | **18.40** |
| 754807 | FON | no | 1,925.38 | — | 2,208.94 | **4,134.32** |
| 755131 | FON | no | 522.36 | — | ~80 (worksheet TBC) | **~602** |
| 754386 | SC VAS | no | 323.78 | — | — | **323.78** |
| 754388 | SC VAS | no | 207.22 | — | — | **207.22** |
| 754391 | SC VAS | no | 246.07 | — | — | **246.07** |
| 754532 | SC VAS | no | 56.12 | — | — | **56.12** |
| 754854 | SC VAS | no | 43.17 | — | — | **43.17** |
| 755266 | SC VAS | no | 172.68 | — | — | **172.68** *(added 8/6)* |
| 756156 | NJ | no | — | 22.08 | — | **22.08** *(added 8/6)* |
| **Total** | | | **6,131.07** | **786.60** | **~2,289** | **≈9,207** |

- NJ wrap figures are billed line items ("STRETCHWRAP STD @ 4.347"). Fontana
  and SC figures are the wrap component embedded in the billed 14.317 pallet
  rate (= 10.00 + 4.317 × pallet count).
- **755266** (SC VAS work order, invoiced 7/14) bills 40 pallets at the
  combined **$14.317** rate = $572.68, of which the wrap component
  40 × $4.317 = **$172.68** is disputed under AF-9; the $400.00 pallet portion
  (40 × $10.00) is payable. Found by the validator's PDF line pass on 8/6 — it
  was never checked in the 8/5 sweep because SC VAS work orders were reviewed
  by document type, and this one carries the combined rate rather than a
  separate wrap line.
- **756156** (NJ SP/LTL, invoiced 7/31 — arrived after the 8/5 sweep) still
  bills PACK CARTON 24 × 0.92 = $22.08 despite the 4/28 AF-7 removal; found in
  the 8/6 post-May MSA revalidation. Note its pallets bill $10.00 flat, no wrap
  — Yusen has adopted AF-9 but keeps billing the removed pack-out.
- **Already paid: $1,347.34** (754699: 569.23; 754704: 778.11) → credit-memo
  claims. Everything else can be short-paid or held.
- 754807 pick overcharge: billed 11,024 picks ($5,578.14); contract-compliant
  additional-only ≈ 6,659 picks ($3,369.20); overcharge $2,208.94. Conservative
  floor (single-unit orders only, indisputably non-additional): $1,778.59.
- 755131 pick line is 411 picks/$207.97; recompute from its worksheet when
  disputing (same method).

## Validation status (everything else)

All 42 US SP/LTL invoices: line math recomputes exactly; all other rates match
the MSA schedule (ship cartons 1.7871/1.8887, order fee 2.1735/2.1585, ecom
order 2.2264, small parcels 0.6532/0.6879/0.84, BOL 6.50, UCC 0.30, SC VAS
pallets 11.74 pre-June). 754807 Stedi: 8,965/8,966. Cosmetic printed-rate typos
(amounts correct): 750791 pallet rate printed 10.3724 (charged 10.3274), 752870
wrap printed 4.72 (charged 4.725). One under-billing in AF's favor: 750091
wrap at 4.00 vs 4.725 (−$137.03).

## Notes

- The "pick & pack" definitions doc (Google Doc "Yusen Definitions", 7/23)
  matches the MSA: "Pick & Pack — Additional pick for Marketplace orders; New
  Jersey doesn't charge this."
- Pre-June NJ "PACK CARTONS @ 1.0000" (Apr–May, ~$3,043 total) predate the new
  rate era; whether the 4/28 pack-out removal reaches back to them is a
  judgment call — not included in the totals above.
- SC pre-June pallet rate via VAS was $11.74 (six invoices, Apr–May) — not in
  the rate history table; worth adding to YUSEN-INVOICE-VALIDATOR.md.
