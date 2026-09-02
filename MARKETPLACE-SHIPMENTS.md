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

**Reships and manual orders are set aside, not deleted**, under one Order type
control: Standard orders (the default, 41,909), Reships only (139), Manual only
(149), All order types. Manual means ShipStation's `Manual ...` stores — anything
raised by hand rather than by a marketplace — and it is where reships live, so
139 of the 149 are both. The 10 that are manual without being reships run $20.54
a unit.

**Reships specifically.** An order number ending `RS` — `24584RS`
against the original `24584` — is a second shipment for a sale already made, so
it is cost with no revenue behind it and it distorts cost per unit. The toolbar
defaults to "Reships: set aside"; "Reships only" shows them. Over 180 days: 139
of them, 292 units, $4,060 of shipping at **$16.85 per unit against $10.57
overall**, and 138 of the 139 are Shopify.

Match on the **suffix**, never on "contains". 681 order numbers in the 945 have
those two letters somewhere and nearly all are random Amazon-style ids like
`P4CXLRsbV` where they mean nothing.

**Cancelled orders are dropped.** 373 of them over 180 days, carrying 2,043
units and their order value against no shipment. `--include-cancelled` keeps
them. Five of those had already shipped when they were cancelled and carried
$209.99 of real carrier cost, which leaves the totals with them — small, but it
means portal spend is what shipped and stayed sold, not everything ever billed.

**Export CSV** sits beside the row count and exports exactly the current filter
and sort — 19 columns, one row per order, with each order's SKUs and quantities
in a single `Items` cell so the file stays a table. The filename follows the
filters (`marketplace-shipments-Target-Fontana-2026-08.csv`).

A published artifact cannot start a download itself — `<a download>` and
script-driven saves are inert in the viewer sandbox — so this uses the
`downloads` runtime capability, declared as `capabilities: {downloads: true}` at
publish time. **Republishing without that declaration silently removes the
button**, since a non-empty capabilities object is a full-set declaration and
omitting the field carries the stored one forward. The page feature-detects: no
capability, no button, rather than a click that fails.

## Where the data comes from

Nothing new is scraped — the marketplace order feeds already land in BigQuery
daily. The builder normalizes four of them onto one shipment-shaped row.

**`americanflat.finance.shipment_reconciliation` is the spine.** It is the EDI
945 warehouse shipping advice from all four warehouses, loaded daily, and it
carries ship date, carrier, tracking, packages and the freight charge keyed by
order number. Everything about how a shipment went out comes from there. The
marketplace feeds supply who ordered and what.

| Marketplace | Order feed | Joins to the 945 on |
|---|---|---|
| Target | `acenda.ship_advice_raw` + `acenda.fulfillment_raw` | `purchaseOrder` |
| Macy's | `macys.orders_clean` (Mirakl) | `commercialId` |
| Michaels | `shipstation.orders_clean`, store `AMF Michaels` | order number, `THP` prefix and `-N` suffix stripped |
| Shopify | `shipstation.orders_clean`, store `Shopify` | order number as-is |

The `shopify` dataset holds the same Shopify orders (7,279 against ShipStation's
7,259 for one window; its `name` is `#25901` to ShipStation's `25901`) but has no
customer name on them, so it stays the financial record and ShipStation stays the
customer record.

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

**Coverage as of 2026-09-01: 40,642 of 42,431 shipments priced (96%), $718,332,
$10.54 per unit.** Ship dates and tracking now come from the warehouse feed, so
Michaels sits at 98% and Shopify at 94% where both were near zero on the
marketplace feeds alone.

**A zero freight charge in the 945 means "not reported", not "free".** The median
USPS row is 0.00. Reading it as a real amount priced thousands of shipments at $0
and made every USPS invoice look like pure overbilling against a zero label —
`NULLIF(freightChargeShipment, 0)` is load-bearing.

A shipment shows a dash for one of two reasons:

1. **Neither the warehouse nor an invoice reported a charge.** Note the two carriers behave differently:
   FedEx bills weeks in arrears, so a recent FedEx shipment genuinely has no
   invoice yet — but **Stamps.com print history is available the same day**. A
   Stamps shipment with no cost means nobody handed the builder a current
   export, not that the charge is pending. Export the print history and pass it
   to `--costs` and those shipments price immediately, right up to today.
2. **There was no tracking number to match on** — see the 3PL join below.

### The audit signal: label against invoice

Both figures are kept, never resolved away. `label_cost` is what the warehouse
recorded; the invoice is what the carrier actually billed; the difference is the
audit number.

On the 21,091 orders where both exist: label $239,323, invoice $267,202 —
**+11.6%**. 57% match to the cent, and 6,774 orders were billed over by $34,053
in total. The portal reports it as "Billed over label", with an Overbilling
filter and a panel ranking the SKUs it lands on.

Before trusting a variance figure, check the zero rule above: an early version
showed +49.5% purely because unreported USPS freight was being read as $0.00.

### The order-level cost report — a cross-check, no longer required

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

### Orders with no tracking number — the 3PL join (superseded)

The 945 feed now supplies tracking for Michaels and Shopify directly, so `--3pl`
is only useful for a window the feed does not cover.

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

Until that table exists, `data/parcel_charges.ndjson.gz` stands in for it. It is
the same parsed, de-duplicated charge lines `--costs-ndjson` writes, committed to
the repo so a run that cannot reach the raw exports still prices the page:

```bash
python3 refresh_marketplace_shipments.py --charges data/parcel_charges.ndjson.gz
```

`--charges` and `--costs` produce identical output — verified on 2026-09-02, both
folding 39,742 charges onto 40,379 of 42,007 shipments at $10.58 a unit. That
matters because the **scheduled refresh has no other cost source**: the FedEx and
Stamps.com exports are files on a laptop, and without them the page falls back to
the warehouse label charge alone, losing the invoice-over-label rule and the
overbilling panel with it.

The snapshot ages at whatever rate invoices are loaded. Refresh it alongside the
weekly cost files and commit it:

```bash
python3 refresh_marketplace_shipments.py --days 30 \
    --costs ~/Downloads/week-of-YYYY-MM-DD \
    --costs-ndjson /tmp/charges.ndjson && gzip -c /tmp/charges.ndjson \
    > data/parcel_charges.ndjson.gz
```

Between refreshes the newest shipments simply show no cost yet, which is the
honest answer — a dash means no invoice has been matched, not free.

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

### The daily refresh

**Disabled as of 2026-09-02.** Two manual test firings built the page correctly
and then ended without republishing — the artifact's version id did not move
either time, and no duplicate artifact was minted, so the publish call never
landed. The build half is proven: the same command run by hand from a clean
checkout produces the right page. What is unexplained is why a Routine-fired
session does not publish; the suspicion is that such a session does not get the
Artifact tool, but that was never confirmed. Re-enable once it is.

A Routine rebuilds and republishes the portal every morning at **7:30 AM ET**
(`30 11 * * *` UTC; the cron is evaluated in UTC, so it shifts an hour against
the clock when daylight saving ends). Each firing starts a fresh cloud session
that clones this repo, runs

```bash
python3 refresh_marketplace_shipments.py \
    --out /tmp/marketplace_shipments.html \
    --charges data/parcel_charges.ndjson.gz
```

and republishes to the artifact URL above with `url:` — never without it.

Two things the schedule depends on, and both are worth checking if a morning run
looks wrong. It needs the builder on the branch it clones, so once this work is
on `main` the fallback checkout in the Routine's prompt stops mattering. And it
needs `data/parcel_charges.ndjson.gz` to be current, per **Keeping it current**
above — a stale snapshot does not produce wrong costs, it produces missing ones
on recent shipments.

Unlike the Yusen artifact this one is not gated on a row fingerprint: the 945
feed lands new shipments every day, so a no-change morning is the exception
rather than the rule and the check would rarely pay for itself.

## A note on what is on the page

Customer names, cities, states, and what each person ordered are on it; email
addresses and street addresses are not. Artifacts are private until shared, and this one should stay
inside Americanflat.
