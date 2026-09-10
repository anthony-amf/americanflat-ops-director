# Netherlands (Yusen Benelux) invoices

NL is the international warehouse (Yusen Logistics Benelux B.V., Moerdijk). Its
invoices differ from US/Canada in three ways that matter for validation:

1. **Currency is EUR with 21% VAT.** Validate in EUR. Converting to USD would
   inject FX error and break the VAT arithmetic. (US/Canada are USD, no VAT.)
2. **Two charge families**, with different checkable rules (see below).
3. **Different basis** — outbound work is priced per *carton* (not per order),
   and admin is a tiered weekly fee, not a flat one.

Rates live in the `netherlands` block of `rate-card-snapshot.json` (source: the
Notion rate card, which pulls from the Benelux Logistics Service Agreement). All
EUR figures are 2025 cost levels, subject to annual Panteia/NEA indexation.

## Family 1 — Transport (outbound EU delivery)

The invoices actually flowing today. One invoice consolidates several orders;
each order carries three charges:

| Charge | Canonical code | Checkable? |
|---|---|---|
| Transport Outbound | `SMALL_PARCEL_TRANSPORT_OUTBOUND` | No — variable lane/weight rate; surfaced only |
| Fuel Surcharge | `SMALL_PARCEL_FUEL_SURCHARGE` | **Yes** — `fuel = fuel_pct × transport_outbound` (the % is in the line's `quantity`) |
| Amazon Delivery | `SMALL_PARCEL_AMAZON_DELIVERY` | **Yes** — flat €100/order |

Invoice-level checks: per-order charges sum to `netto_eur`; `subtotal = Σ netto`;
`VAT = 21% × subtotal`; `total = subtotal + VAT`.

Run: `python3 scripts/validate_nl_invoice.py <extraction.json>`. It auto-detects
this family from the charge codes (the extractor classifies these as
`SMALL_PARCEL_LTL`).

## Family 2 — Warehousing (Benelux LSA)

Arrives as `FTI…`-numbered invoices (e.g. FTI0006387), one summary line per
activity (INBOUND / OUTBOUND / STORAGE / ADMINISTRATION / CONSUMABLES / VAL).

**VAT: zero-rated.** Warehousing invoices billed to Americanflat's US entity
carry €0.00 VAT — "export service, art. 44 VAT Directive 2006/112/EU" (reverse
charge). Only the *transport* family carries 21% NL VAT. Confirmed on
FTI0006387 (May 2026). Contracted rates (EUR):

- **DTC** €2.89/carton (incl. shipping-label application — no separate label fee),
  additional picks €0.52.
- **B2B / LTL outbound** €1.89/carton ("Outbound Order Fulfillment B2B" — incl.
  pallet config, wrapping, pack-list; covers stretchwrap). NL does not separate VC
  small-parcel vs LTL the way US warehouses do.
- **Storage** €2.75/pallet/week; bin location €0.40/location/week.
- **Admin** tiered weekly by hours: ≤16h €692.85 · ≤24h €1,039.27 ·
  ≤32h €1,385.70 · ≤40h €1,732.12.
- **VAS** hourly: warehouse €45.04 · administration €56.30 · management €78.82.
- **Monthly minimum** €6,222 for warehouse activities.

NL-only charges (no US/Canada equivalent): inbound container unloading
€0.86/carton (€60 min/delivery), inbound additional admin €0.14/carton (first
125k cartons), inbound sortation €24.18/SKU·container, bin-location storage
€0.40/location/week, drayage €467.50/container, project-mgmt & IT €17,500 one-time.

The per-unit charges need counts the invoice header doesn't carry (pallet-weeks,
admin hours/tier, carton counts), so header-level validation surfaces the rates,
applies the €6,222/month minimum, and checks VAT — the rest is `needs_detail`.

## How NL flows through the skill

- NL invoices aren't loaded into the `yusen_invoices` BigQuery table yet. The NL
  validator therefore reads the **extraction JSON** the invoice-to-bigquery
  extractor produces (it carries the per-order line items the header lacks).
- If an NL row *does* land in the header table, `validate_rate_card.py` detects
  the `netherlands` warehouse and routes you to `validate_nl_invoice.py` rather
  than running a meaningless USD check.
- ⚠️ Watch the naming trap: the NL invoice series uses a `CA` prefix
  (e.g. `CA26200110`) that does **not** mean Canada. Genuine Canada (Brampton)
  invoices use `Yusen CA` warehouse with `CA2WFS…` numbers, USD, no VAT.
