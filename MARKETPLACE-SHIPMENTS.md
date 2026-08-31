# Marketplace Shipments portal

A searchable portal over the orders Americanflat ships to its four direct
marketplaces — **Target, Macy's, Michaels, Shopify**. Same look and behaviour as
the Yusen invoice portal: KPI cards, two bar panels, a sticky search bar, and a
sortable table.

- **Live page:** https://claude.ai/code/artifact/53c82d03-9788-4ac2-a2a3-ca5322ad458f
- **Builder:** `refresh_marketplace_shipments.py` (this repo)
- **Ledger table (planned):** `americanflat.marketplaces.marketplace_shipments`

Search matches order number, customer name, tracking number, SKU, city and
state. Filters: marketplace, month, carrier, status, has-tracking. Every column
sorts. Clicking an order number expands it to its line items — SKU, item, qty,
unit price, line total.

**"Order value" is what the customer paid, not what shipping cost us.** It is the
sum of that order's own line totals, so the column and the expanded lines can
never disagree. Actual carrier cost per shipment is not in any of these feeds —
it lives in the FedEx and Stamps.com invoices, matched to orders by tracking
number, which is what `shipping-cost-report` and `cost-per-sku-dashboard` do.
Adding a true shipping-cost column means feeding those invoices in as a fifth
source; the acenda feed has a `cost` field but every row of it is 0.00.

## Where the data comes from

Nothing new is scraped — the marketplace order feeds already land in BigQuery
daily. The builder normalizes four of them onto one shipment-shaped row.

| Marketplace | BigQuery source | Ship date + tracking | Customer name | Line items |
|---|---|---|---|---|
| Target | `acenda.ship_advice_raw` + `acenda.fulfillment_raw` | yes (98%) | recent orders only — see redaction below | yes |
| Macy's | `macys.orders_clean` (Mirakl) | yes (94%) | yes | yes |
| Michaels | `shipstation.orders_clean`, store `AMF Michaels` | **no** | yes | yes |
| Shopify | `shipstation.orders_clean`, store `Shopify` | **no** | yes | yes |

The query runs at line grain and the builder groups it into orders, so the SKU
detail and the order totals come from the same rows.

Last 180 days, as of 2026-08-31: 42,462 orders / 75,151 units / $1.80M order
value — Target 32,612, Shopify 7,232, Michaels 1,447, Macy's 1,171. The feeds
move during the day, so a re-run minutes later will not match to the order.

`dsco.orders_clean` is a fifth feed in the same shape, but its only retailer
(`dscoRetailerId 1000007328`, ~500 orders/month since 2021) is not one of these
four, so it is deliberately left out.

## Two data problems worth knowing about

**1. ShipStation's shipment feed died in October 2023.** `shipstation.orders_raw`
is current to today, but `shipstation.shipments_raw` — the table holding ship
date, tracking number and label cost — has no row after 2023-10-06. That is why
Michaels and Shopify rows in the portal show the order, the customer and the
destination but a dash for ship date and tracking. Restarting that half of the
ShipStation ingest fills both marketplaces in with no change to the portal.

Until then, the ship-side truth for those two lives in the weekly 3PL shipped
order reports (NJ / Fontana / SC) that `shipping-cost-report` and
`cost-per-sku-dashboard` read. Those Drive sheets were last refreshed
2026-04-30, so they are not a stand-in as things are.

**2. Target Plus redacts customer PII after about 45 days.** The name becomes the
literal `Customer Name` and the street `1234 Redacted St`, and the acenda sync
rewrites the existing rows — so a name readable today is gone next month. Of
42,714 Target rows, 35,930 are already redacted; only July–August 2026 still has
names. The portal shows a dash rather than pretending "Customer Name" is one.

This is the reason to keep a ledger table rather than reading the feeds forever.

## The ledger table

`sql/marketplace_shipments_setup.sql` holds the `CREATE TABLE` for
`americanflat.marketplaces.marketplace_shipments` plus the `MERGE` that loads it.
The MERGE is `COALESCE(new, stored)` on every field, so a later sync that arrives
redacted or blank never erases a fact already captured. Once it is populated the
portal can read from it instead of the feeds:

```bash
python3 refresh_marketplace_shipments.py --source ledger --days 365
```

**Setup has to run from the Mac, and may need Ivan.** Cloud sessions have
read-only BigQuery, and `bigquery.tables.create` is not on the `finance` or
`marketplaces` datasets for either the cloud service account or Anthony's own
account (checked 2026-08-24). If `CREATE TABLE` comes back permission-denied,
Ivan Calderon owns the dataset — same route as the yusen_invoices write grant.

Load, from the Mac:

```bash
python3 refresh_marketplace_shipments.py --days 30 --ndjson /tmp/mps.ndjson
bq load --source_format=NEWLINE_DELIMITED_JSON --autodetect \
    americanflat:marketplaces._stage_marketplace_shipments /tmp/mps.ndjson
bq query --use_legacy_sql=false --max_rows=1 < sql/marketplace_shipments_setup.sql
```

For a one-time backfill of everything the feeds still hold, run the first line
with `--days 2000` instead — that captures the Nov-2025-onward Target history
(already redacted), all of Macy's, and ShipStation back to 2021.

## Refreshing the portal

```bash
python3 refresh_marketplace_shipments.py                 # 180 days -> marketplace_shipments.html
python3 refresh_marketplace_shipments.py --days 365      # wider window
```

Then republish to the **same** artifact URL — passing `url:` is required, or a
duplicate artifact gets minted:

```
Artifact(file_path="marketplace_shipments.html",
         url="https://claude.ai/code/artifact/53c82d03-9788-4ac2-a2a3-ca5322ad458f")
```

The builder runs anywhere: in a cloud session BigQuery auth is injected by the
agent proxy, and on the Mac it borrows the gcloud ADC token (`--auth` forces
either). The page is one self-contained HTML file, ~5.3 MB at 180 days: 42k
orders and 50k line items, dictionary-encoded (the ~4,200 distinct products are
stored once and referenced by index) and painted 250 rows at a time.

No schedule yet. If it earns one, the Yusen artifact's gated pattern is the model
— fingerprint the rows, skip the republish when nothing changed.

## A note on what is on the page

Customer names, cities, states, and what each person ordered are on it; email
addresses and street addresses are not. Artifacts are private until shared, and this one should stay
inside Americanflat.
