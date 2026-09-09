# SC (Savannah/Hardeeville) Storage Over-Billing — Credit Quantification

**Prepared:** 2026-09-09 · **Window:** invoices dated 4/13–8/31/2026 (21 weekly
storage invoices, week-ending 4/12 through 8/30) · **Billed total: $203,684.44**

## Method

- **Billed pallets** per week: invoice amount ÷ billed rate. April + 5/03 weeks
  divide exactly by the legacy $5.0925/pallet/week rate (integer pallet counts,
  and invoice 751118's own note states "peak 3188 pallets @ 5.0925"); weeks
  5/10 onward divide exactly by the reduced $3.35 rate (notes confirm
  "rebilled at reduced rate").
- **Justified ("deemed") pallets** per week: peak daily stored cube that week ÷
  0.87 CBM per pallet (the utilization standard in the MSA draft; 30.7 cu ft).
  Stored cube = units on hand per SKU (BigQuery
  `Demand_Planning.Warehouse_Inventory`, warehouse `SC`, deduplicated — the
  feed writes each row in triplicate) × per-unit CBM
  (`Demand_Planning.CBMs`). Peak-day convention matches how Yusen bills
  (their notes bill the weekly peak).
- Benchmarks: 0.87 CBM = the maintenance standard AMF proposed; 1.02 CBM = the
  bottom of Yusen's own 36–38 cu ft inbound build commitment.

## Weekly result

| Week end | Billed pallets | Peak stored CBM | Justified @0.87 | Actual CBM/pallet | Over-billed @0.87 |
|---|---|---|---|---|---|
| 04/12 | 3,388 | 2,423 | 2,786 | 0.72 | $3,065.68 |
| 04/19 | 3,316 | 2,354 | 2,707 | 0.71 | $3,101.33 |
| 04/26 | 3,276 | 2,322 | 2,669 | 0.71 | $3,091.15 |
| 05/03 | 3,188 | 2,260 | 2,599 | 0.71 | $2,999.48 |
| 05/10 | 3,097 | 2,033 | 2,337 | 0.66 | $2,546.00 |
| 05/17 | 2,965 | 1,900 | 2,184 | 0.64 | $2,616.35 |
| 05/24 | 2,942 | 1,792 | 2,060 | 0.61 | $2,954.70 |
| 05/31 | 2,903 | 1,791 | 2,059 | 0.62 | $2,827.40 |
| 06/07 | 2,696 | 1,594 | 1,832 | 0.59 | $2,894.40 |
| 06/14 | 2,510 | 1,524 | 1,752 | 0.61 | $2,539.30 |
| 06/21 | 2,432 | 1,376 | 1,582 | 0.57 | $2,847.50 |
| 06/28 | 2,420 | 1,294 | 1,488 | 0.53 | $3,122.20 |
| 07/05 | 2,346 | 1,247 | 1,433 | 0.53 | $3,058.55 |
| 07/12 | 2,332 | 1,207 | 1,387 | 0.52 | $3,165.75 |
| 07/19 | 2,193 | 1,164 | 1,338 | 0.53 | $2,864.25 |
| 07/26 | 2,091 | 1,112 | 1,279 | 0.53 | $2,720.20 |
| 08/02 | 2,066 | 1,088 | 1,250 | 0.53 | $2,733.60 |
| 08/09 | 2,033 | 1,028 | 1,182 | 0.51 | $2,850.85 |
| 08/16 | 1,967 | 1,017 | 1,169 | 0.52 | $2,673.30 |
| 08/23 | 1,928 |   981 | 1,128 | 0.51 | $2,680.00 |
| 08/30 | 1,863 |   953 | 1,096 | 0.51 | $2,569.45 |

Totals: **53,952 pallet-weeks billed** against **32,458 CBM stored** —
an average of **0.60 CBM (21 cu ft) per billed pallet**, versus Yusen's own
36–38 cu ft inbound build standard. Utilization *declined* all period
(0.72 → 0.51): inventory fell 65% while billed pallets fell only 45% —
the signature of pallets never being consolidated as they emptied.

## The claim, in components

| Component | Basis | Amount |
|---|---|---|
| A. Utilization over-billing | billed minus justified @0.87, at rates actually billed | **$59,921.44** |
| B. April rate differential | 13,168 pallet-weeks (4 invoices, 4/12–5/03) billed at legacy $5.0925 despite the rate schedule's own validity of April 2026–March 2027; × ($5.0925 − $3.35) | **$22,945.24** |
| Overlap (A pallets also in B) | 2,407 over-pallets × $1.7425 | −$4,194.20 |
| **Combined headline** | billed $203,684.44 minus (justified pallets × $3.35 = $125,011.95) | **$78,672.49** |

Alternative benchmarks: at the 1.02 CBM inbound standard the utilization
component alone is **$81,046** (aggressive anchor); allowing a generous +15%
master-carton packaging factor on the cube still leaves ~$38K of utilization
over-billing (conservative floor), ~$61K combined with the rate differential.

## Caveats (state up front — they make the number credible)

1. Cube uses **sell-unit CBM** (product cube), not master-carton cube. Master
   cartons add packaging air, so true stored cube is somewhat higher; the +15%
   floor above bounds this. Yusen's counter-data would be actual carton dims —
   which AMF also holds (master data), so this narrows, not explodes.
2. ~0.2–0.5% of units have no CBM match; they were excluded (this *understates*
   stored cube, i.e., slightly overstates the claim — immaterial at <0.5%).
3. Peak-day basis mirrors Yusen's own billing convention (peak pallets/week).
4. **Jan 8 – Apr 12 is not included**: inventory snapshots exist but those SC
   storage invoices are not in the ledger. January stored cube averaged ~3,658
   CBM/day — if billed pallets then were proportional, the same analysis adds
   roughly three more months at the legacy rate. Forward those invoices and
   this report extends.
5. Supporting admission: Todd Morrison (Yusen VP Ops), 4/6/2026, forwarded by
   Susan Guarino: ~1,600 of ~2,000 active Hardeeville items held **less than a
   full pallet's worth of inventory** (at 38 cf = 1 pallet).

## Suggested negotiation posture

Anchor at **$81K** (inbound-standard utilization), justify at **$78.7K**
(combined, contract-rate math), settle at **~$60K**, floor **~$38–40K**
(utilization-only with the carton allowance conceded). Bundle acceptance as a
credit memo against future invoices, offered alongside AMF accepting billable
post-inbound consolidation with the lesser-of storage cap prospectively.

*Reproduce: query in this report's commit; sources
`finance.yusen_invoices` (TS South storage), `Demand_Planning.Warehouse_Inventory`
(dedup by sku+date), `Demand_Planning.CBMs`.*
