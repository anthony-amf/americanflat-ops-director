# Yusen MSA — "Final" Draft Analysis (received ~8/19–8/20 markup round)

**Analyzed:** 2026-08-20 from `Americanflat_Yusen_MSA_Final.docx`. Despite the
filename, this is NOT signable — it still carries the AF red markup plus a new
round of comments from Yusen legal (Rachel Hollander, 7/30) and Yusen ops/
pricing (Leyvi Ramirez, 8/19).

## Resolved in this draft (wins banked)

- **Rate table regenerated (AF-7 done):** "Per Pack Out" line REMOVED,
  "Packling Slip" typo fixed, separate "Pallet Stretch Wrap" lines DELETED —
  the table now reads "Per Pallet (Grade B) and Stretch Wrap — $10.0000" at
  all three sites. AF-9 all-in pallet rate achieved in both text and table.
- **Chargeback senior point of contact:** Rachel commented "OK" — accepted.
- **Cycle Counting Program:** in, now with AMF selecting count dates on 30
  days' notice (improvement over 7.15).
- **Storage scope language** (sellable inventory only, no charges on pallets/
  supplies) retained.
- **CPI/escalation paragraph** retained: 120-day initial review moratorium,
  no Year-1 escalation, lesser of PPI or 3.5% cap.

## The consolidation fight — Yusen's comments decoded (anchors verified)

| Clause | Yusen comment (Leyvi Ramirez, 8/19) | Meaning |
|---|---|---|
| (a) Inbound build | "Relative to only inbound shipment, not pulling out of inventory to combine or across multiple containers" | Narrows 36–38 build to per-container; no cross-inventory build at receipt |
| (b) Ongoing consolidation | "Billable activity." | Rejects free post-pick consolidation |
| (c) Measurement/reporting | "Not covered under current admin work" | Resists the weekly utilization report |
| (d) Consolidation trigger | "Billable activity" | Rejects free cure consolidation |
| (e) Storage relief | "Rely on B and D to keep us in compliance. Should not happen." | Does NOT reject the billing cap — says it should never trigger |
| Inbound no-fee line | "3-4 SKUs per pallet only what comes off the container - no charge; if we need to consolidate with existing inventory, that will be billed." | The crux: container-scope free, everything after billable |
| National Pallet Rate | "Add language to protect increase in pallet cost" | Wants pallet-cost escalation protection on the $10 |

**Counter-strategy — the money is in (e), not (b)/(d):** AMF does not need
free consolidation labor; it needs to not pay storage on air. Concede that
physical consolidation beyond the inbound container is billable *only when AMF
requests it* — and in exchange make (e) unconditional:

> Storage invoices for each facility are billed at the lesser of (i) actual
> occupied pallet positions or (ii) the number of positions the stored
> inventory would occupy at 0.87 CBM per position, calculated weekly from
> Yusen's inventory report and Americanflat's master carton dimensions.

Under this structure consolidation becomes Yusen's business decision: they
can consolidate (billable only if AMF orders it — otherwise at their option
and expense) or leave pallets loose and absorb the storage difference. No
compliance machinery, no trigger weeks, no labor disputes. Leyvi's own (e)
comment ("should not happen") signals they can live with the cap.

On (c): counter "not covered under current admin work" by offering that AMF
computes utilization from Yusen's existing weekly inventory report + AMF
master carton dims — zero added Yusen admin; the report is invoice backup,
not a new service. (The draft already says the AMF-provided CBM-per-carton
data is the measurement of record.)

On pallet-cost protection: no new language needed — point to the escalation
clause (PPI/3.5% cap) which already governs all rates including the $10.

## Still open from prior rounds

- **Rates-clause fallback:** Rachel: "We're not going to agree to this change"
  on AMF's "then-current rates continue" insert. The paragraph still contains
  BOTH fallbacks (garbled). Compromise: accept the CPI fallback but cap it at
  3.5%, consistent with the escalation clause.
- **KPI forecast excusal:** Rachel: "Susan to discuss with customer" — still
  in the document. Hold position: delete, or limit the excusal to
  volume-driven KPIs in months exceeding 1.5× peak-to-average (Schedule C's
  own assumption).
- **Rate validity:** April day still blank ("_April , 2026").
- **DOCUMENTS fee scope:** still "shipping documents (e.g. commercial
  invoice, bill of lading etc.)" — the per-BOL narrowing (AF-8) not applied.
- **Jan–Mar retro credit:** still unaddressed anywhere.

## SC over-billing credit (Angela/Kent ask)

**The admission already exists in writing.** Todd Morrison (Yusen VP Ops),
internal email forwarded by Susan Guarino 4/6/2026: in Hardeeville ~1,600 of
~2,000 active items had **less than a full pallet's worth of inventory**
(at 38 cf = 1 pallet). Yusen's own operations leadership documented that the
overwhelming majority of SC pallet positions were sub-pallet quantities —
positions AMF paid for by the week.

**Quantification method:** for each billed week at SC: total stored cube
(units on hand × master carton CBM) ÷ 0.87 CBM = deemed pallets; compare to
billed pallet positions on the storage invoice; differential × $3.35/week
(SC storage rate; legacy rate for pre-April weeks). Inputs: weekly SC stock
reports + storage invoices (in BigQuery `finance.yusen_invoices` with
supporting docs).

**Negotiation frame:** bundle retro relief into one settlement — the SC
utilization credit and the Jan–Mar rate differential — offered against AMF
accepting billable post-inbound consolidation with the (e) cap prospective
only. Yusen gets a clean forward deal; AMF gets made whole for the documented
past over-billing.
