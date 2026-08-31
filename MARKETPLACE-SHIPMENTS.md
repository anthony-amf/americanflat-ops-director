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

There are two money columns and they are different things:

- **Order value** — what the customer paid. The sum of that order's own line
  totals, so the column and the expanded lines can never disagree.
- **Ship cost** — what the carrier billed us, from the FedEx and Stamps.com
  invoices, matched to the shipment by tracking number. A dash means no invoice
  has been matched yet, which is not the same as free.

## Where the data comes from

Nothing new is scraped — the marketplace order feeds already land in BigQuery
daily. The builder normalizes four of them onto one shipment-shaped row.

| Marketplace | BigQuery source | Ship date + tracking | Customer name | Line items |
|---|---|---|---|---|
| Target | `acenda.ship_advice_raw` + `acenda.fulfillment_raw` | yes (98%) | recent orders only — see redaction below | yes |
| Macy's | `macys.orders_clean` (Mirakl) | yes (94%) | yes | yes |
| Michaels | `shipstation.orders_clean`, store `AMF Michaels` | only via `--3pl` | yes | yes |
| Shopify | `shipstation.orders_clean`, store `Shopify` | only via `--3pl` | yes | yes |

The query runs at line grain and the builder groups it into orders, so the SKU
detail and the order totals come from the same rows.

Last 180 days, as of 2026-08-31: 42,462 orders / 73,785 units / $1.80M order
value / $107,031 of matched shipping cost — Target 32,612, Shopify 7,232, Michaels 1,447, Macy's 1,171. The feeds
move during the day, so a re-run minutes later will not match to the order.

`dsco.orders_clean` is a fifth feed in the same shape, but its only retailer
(`dscoRetailerId 1000007328`, ~500 orders/month since 2021) is not one of these
four, so it is deliberately left out.

## Shipping cost

No order feed carries what shipping actually cost: acenda's fulfillment `cost`
field is 0.00 on all 43,634 rows, and ShipStation's `shipmentCost` died with the
rest of that feed in 2023. The real number is on the carrier invoices, so the
builder joins them the same way the weekly shipping cost report does — by
tracking number.

```bash
python3 refresh_marketplace_shipments.py --costs ~/Downloads/week-of-2026-08-25
python3 refresh_marketplace_shipments.py --costs "AMF FedEx Invoices.csv" "AMF Stamps.com Invoices.csv"
```

Two things about the Stamps.com print history specifically, both learned the
hard way:

- **`Amount Paid` is already the final number.** A re-rated label shows
  `Quoted Amount` + `Adjusted Amount` = `Amount Paid` (9.85 + 7.50 = 17.35), so
  adding the adjustment on top would double-count it.
- **USPS tracking numbers come out Excel-escaped** as `="9434650105798022300341"`
  while UPS numbers come through bare. A tracking normalizer that only strips
  spaces and dashes therefore matches every UPS shipment and no USPS one — which
  is exactly what happened on the first load (UPS 99%, USPS 0%). `norm_tracking`
  keeps letters and digits only.

A refunded label is skipped: Stamps keeps the row with its original `Amount
Paid`, so counting it would bill a shipment that was credited back.

`--costs` takes files or a folder and recognizes four layouts: the two
consolidated Drive sheets (`AMF FedEx Invoices`, `AMF Stamps.com Invoices`) and
the raw FedEx Billing Online and Stamps.com print-history exports the weekly
download already produces. Charges are **summed** per tracking number — FedEx
re-rates a shipment on a later invoice and both lines are real money — but a
charge is counted **once** per (tracking, date, amount).

That second rule is not optional. The consolidated Drive sheets are weekly
exports stacked on each other and the downloads overlap, so the same invoice
line is physically present two or three times: 4,266 of the FedEx sheet's 7,963
rows are repeats. Summing them raw put Target's FedEx cost per unit at $35.92
against a known ~$13.47. With repeats dropped it lands at $12.66, and the
blended figure at $8.51 — in the band the weekly report reports ($7.69 for a
wider mix that includes the cheap Shopify and Michaels USPS volume).

**Coverage as of 2026-08-31: 37,861 of 42,462 shipments priced ($573,412),
$9.47 per unit** — 97–99% of March through July, 86% of August. Two sources got
it there: a current Stamps.com print history (`--costs`) and the weekly cost
report's per-order roll-up (`--order-costs`, below), which carries FedEx through
Aug 24 and reaches the orders with no tracking number at all.

What remains unpriced is almost entirely the last stretch of August, where FedEx
has not billed yet. A shipment shows a dash for one of two reasons:

1. **The invoice hasn't been loaded.** Note the two carriers behave differently:
   FedEx bills weeks in arrears, so a recent FedEx shipment genuinely has no
   invoice yet — but **Stamps.com print history is available the same day**. A
   Stamps shipment with no cost means nobody handed the builder a current
   export, not that the charge is pending. Export the print history and pass it
   to `--costs` and those shipments price immediately, right up to today.
2. **There was no tracking number to match on** — see the 3PL join below.

### The order-level cost report — the second cost source

The weekly shipping cost pipeline emits a reconciled per-order roll-up
(`all_orders_shipping_costs_<date>.md`): order number, marketplace, ship date,
carrier, and the summed cost of every package on the order. Pass it with
`--order-costs` and it is joined by order number:

```bash
python3 refresh_marketplace_shipments.py \
    --costs ~/Downloads/week-of-2026-08-25 \
    --order-costs ~/Downloads/all_orders_shipping_costs_20260831.md
```

This is what makes Michaels and Shopify work. They have no tracking number in
BigQuery, so no invoice can reach them by tracking — but they do have order
numbers. Loading the 2026-08-31 report took Michaels from 6% to 84% priced and
Shopify from 1% to 67%, and supplied their ship dates too.

**Precedence: a tracking-level match wins where there is one.** The two sources
agree to the cent on 84.9% of the 23,893 orders they both price. Where they
differ it is usually a Stamps adjustment that posted after the report was built
— the report has the quoted amount, a later export has quoted + the adjustment
as Amount Paid (8.23 + 7.50 = 15.73) — so the fresher per-shipment figure is the
one to keep. The page's tooltip says which join produced each number; an
order-level figure is labelled "(order match)", which on a split order is the
whole order's cost rather than one package's.

### Orders with no tracking number — the 3PL join

Michaels and Shopify orders arrive from ShipStation with no tracking number, so
there is nothing for a carrier invoice to match and they showed no cost at all.
The warehouses do report it: the weekly NJ / Fontana / South Carolina
shipped-order reports are keyed by order number and carry tracking, ship date
and carrier.

```bash
python3 refresh_marketplace_shipments.py \
    --3pl ~/Downloads/week-of-2026-08-25 --costs ~/Downloads/week-of-2026-08-25
```

`--3pl` reads the consolidated Drive sheets and both raw export layouts (NJ and
Fontana use `Order` / `Bill of Lading`, South Carolina uses `Order No.` /
`Tracking Number`). It only fills fields the marketplace feed left blank, never
overwrites Target's or Macy's own tracking, and runs before the cost join so the
recovered tracking numbers get priced in the same pass.

Order numbers need one normalization: a Michaels order is `THP6600107706404869-2`
in ShipStation and plain `6600107706404869` at the warehouse. Shopify's (`19528`)
match as-is.

**The consolidated Drive sheets are weak for this**: they kept the order-number
column for only about 7,300 of 85,800 rows (the later weekly exports), which is
why today's build recovers just 294 shipments. Anthony's raw weekly reports have
an order number on every row, so running with those fills Michaels and Shopify
in properly.

### Keeping it current

`sql/marketplace_shipments_setup.sql` defines
`americanflat.marketplaces.parcel_charges` — one row per invoice line, keyed by
tracking number. This is the piece that has never existed in BigQuery. Load it
weekly from the same five files the shipping cost report already downloads:

```bash
python3 refresh_marketplace_shipments.py --days 30 \
    --costs ~/Downloads/week-of-2026-08-25 --costs-ndjson /tmp/charges.ndjson
bq load --source_format=NEWLINE_DELIMITED_JSON --autodetect \
    americanflat:marketplaces._stage_parcel_charges /tmp/charges.ndjson
# then the parcel_charges MERGE at the bottom of the SQL file
```

After that, `--cost-table americanflat.marketplaces.parcel_charges` prices the
portal straight from BigQuery with no files to hand it.

**Cost per unit on this page is not the weekly report's CPU.** It is matched cost
over the units on matched shipments only, and it excludes none of what that
report deliberately excludes (TikTok sample sends, wholesale, LTL). Use it to
see what one shipment cost, not to restate the number in the Friday meeting.

## Two data problems worth knowing about

**1. ShipStation's shipment feed died in October 2023.** `shipstation.orders_raw`
is current to today, but `shipstation.shipments_raw` — the table holding ship
date, tracking number and label cost — has no row after 2023-10-06. That is why
Michaels and Shopify rows in the portal show the order, the customer and the
destination but a dash for ship date and tracking. Restarting that half of the
ShipStation ingest fills both marketplaces in with no change to the portal.

Until then, the ship-side truth for those two lives in the weekly 3PL shipped
order reports (NJ / Fontana / SC), which `--3pl` reads — see the 3PL join above.

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
either). The page is one self-contained HTML file, ~5.6 MB at 180 days: 42k
orders and 50k line items, dictionary-encoded (the ~4,200 distinct products are
stored once and referenced by index) and painted 250 rows at a time.

No schedule yet. If it earns one, the Yusen artifact's gated pattern is the model
— fingerprint the rows, skip the republish when nothing changed.

## A note on what is on the page

Customer names, cities, states, and what each person ordered are on it; email
addresses and street addresses are not. Artifacts are private until shared, and this one should stay
inside Americanflat.
