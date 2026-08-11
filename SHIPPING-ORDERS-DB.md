# Shipped-orders database + Cost Per SKU shipping artifact

The Cost Per SKU report has always been file-in / file-out: five downloads on a
Thursday, an Excel workbook, four CSVs in Drive. Nothing kept the shipments
themselves, so any question that reached past the current week meant re-opening
old folders.

This adds a database that keeps them, and a dashboard that reads it — the same
shape as the Yusen billing artifact.

- **`americanflat.finance.shipping_orders`** — one row per shipped package for the
  four marketplaces where **we** cover the freight: Target, Michaels, Shopify,
  Macy's. Everything else in the 3PL reports (Amazon, Wayfair, Walmart, Kohl's,
  Faire, wholesale) is dropped on the way in — those channels pay their own
  shipping, so they have no place in a cost-per-unit number.
- **The artifact** — searchable dashboard over that table: cost per unit by week
  and marketplace, units shipped, and every individual package with its invoice.

## Pieces

| File | What it does | Where it runs |
|---|---|---|
| `sql/create_shipping_orders_table.sql` | Creates the table. Once, ever. | Mac or the BigQuery console |
| `scripts/load_shipping_orders_to_bq.py` | Reads a week's 3PL + carrier files, matches invoices to packages, writes rows | **Mac only** (needs write access) |
| `scripts/generate_shipping_dashboard.py` | Builds the dashboard HTML from the table | Mac or a cloud session |
| `scripts/bq_read.py` | Shared read-only BigQuery access | both |

The matching itself is **not** reimplemented here. The loader imports
`process_shipments.py` from the `shipping-cost-report` skill, so the weekly Excel
report and this database always agree about which invoice paid for which package.
If that skill's matching changes, this picks it up with no edit.

## First-time setup

**1. Make the table** (once):

```bash
bq query --use_legacy_sql=false --max_rows=100 < sql/create_shipping_orders_table.sql
```

If that comes back saying permission to create tables is denied, paste the same
file into the BigQuery web console query editor and run it there. Everything
after this step only needs the write access the account already has.

**2. Load the history.** Two ways in, depending on where the files are.

Every dated week folder the Thursday job has staged, oldest first:

```bash
python3 scripts/load_shipping_orders_to_bq.py \
    --backfill-root "~/Documents/Claude/Projects/Weekly Shipping Reports"
```

Or the consolidated sheets in Drive (`AMF Fontana 3PL Orders`, `AMF New Jersey
3PL Orders`, `AMF South Carolina 3PL Orders`, `AMF FedEx Invoices`, `AMF
Stamps.com Invoices` — these hold roughly Feb through April 2026). Download each
as CSV/XLSX into a folder, then:

```bash
python3 scripts/load_shipping_orders_to_bq.py --files \
    --week-label drive-archive-2026-04-30 \
    --fontana ~/Downloads/archive/fontana.csv \
    --newjersey ~/Downloads/archive/newjersey.csv \
    --sc ~/Downloads/archive/southcarolina.xlsx \
    --fedex ~/Downloads/archive/fedex.csv \
    --stamps ~/Downloads/archive/stamps.csv
```

A multi-week file is fine — each row's week comes from its own ship date, not
from the label. The label is only provenance, so you can find or replace that
batch later.

**3. Build the page:**

```bash
python3 scripts/generate_shipping_dashboard.py --out shipping_dashboard.html
```

## Every week

After the Thursday `weekly-shipping-reports` job stages its folder:

```bash
python3 scripts/load_shipping_orders_to_bq.py \
    --week-dir "~/Documents/Claude/Projects/Weekly Shipping Reports/<week folder>"
python3 scripts/generate_shipping_dashboard.py --out shipping_dashboard.html \
    --fingerprint-file .shipping_dashboard.fingerprint
```

Then republish the artifact (see below). With `--fingerprint-file` the generator
prints `NO_CHANGE` and writes nothing when the numbers are identical to last
time, so a schedule can skip the republish — same gate the Yusen artifact uses.

**Re-running a week is safe and is the normal fix for anything that looks wrong.**
Before inserting, the loader clears the rows that week wrote last time *and* any
row matching a package it is about to write. So when a FedEx invoice arrives late
and shows up in a later week's file, that package flips from unmatched to matched
in place instead of appearing twice.

## What these scripts can and cannot destroy

Per the standing no-delete rule, neither script removes a file, and neither can
overwrite one it did not write.

Every file they generate carries a marker near the top — the dashboard's
`<title>`, a comment line in the fingerprint file, a `_written_by` key in the
rows JSON. Before writing to a path that already exists, the marker has to be
there. Rebuilding the dashboard over last week's copy works, because that copy is
its own output; a mistyped `--out` that lands on a real file stops with
"Refusing to overwrite" and changes nothing. The guard lives in
`scripts/safe_write.py`.

The one thing that genuinely deletes is **rows inside the BigQuery table**, and
only the loader, and only in the narrow way described above: the week being
reloaded, plus any row matching a package about to be rewritten. That is what
makes re-running a week safe instead of duplicating. It never touches a row for
any other week or any other package, and there is deliberately no "wipe the
table" option — a full rebuild is just loading every week again.

## Reading the numbers

- **Cost per unit is invoiced freight ÷ matched units.** Packages still waiting on
  an invoice are counted in units shipped and in the match rate, never in cost per
  unit. A dip in match rate means an invoice hasn't landed yet, not that shipping
  got cheaper.
- **Never average the `cost_per_unit` column.** It is per-row convenience. Blended
  CPU is always `SUM(shipping_cost) / SUM(units)`.
- **Multi-package orders.** When one order ships in more than one box, the 3PL
  reports the order's units once but each box carries its own freight. Rows past
  the first are flagged `is_additional_package` and carry `units = 0`, so units
  are counted once and cost in full. The weekly Excel report does **not** do this
  — it counts the order's units again for every extra box, which understates its
  cost per unit slightly. Where the two disagree, this table is the more careful
  one.
- **Unmatched shipments are kept on purpose.** Dropping them would silently
  shrink units shipped and make CPU look better than it is.

## The artifact

Stable URL: **https://claude.ai/code/artifact/f4b62a70-d920-4448-a66b-efea639a93e8**

It is live now, showing the setup steps, because the table has not been created
yet. Once the first load lands, republishing the rebuilt HTML to that same URL
fills it in.

Same trap as the Yusen artifact: **republishing must pass the existing artifact
URL**, or a second artifact gets minted and whoever bookmarked the first keeps
reading stale numbers.

Unlike the Yusen cloud refresher, there is **no separate HTML template file
here.** That refresher renders from a snapshot of the published page, and the
snapshot fell behind the live design more than once — silently downgrading the
page on republish. The template in `generate_shipping_dashboard.py` is inside the
script, so it cannot drift from itself.

Two notes on the design:

- The brand face (Glacial Indifference) is not embedded. An artifact may not fetch
  a font CDN, and there is no licensed font file to inline, so the page falls
  through to the closest system geometric sans.
- Chart colors are not the AF accents. Cost per unit needs four series that stay
  apart for a colorblind reader, and AF Red is reserved for the unmatched state,
  so the four series use lifted, more chromatic steps of the AF blue plus a teal,
  ochre and violet — checked with the dataviz palette validator in both light and
  dark. If a fifth marketplace ever joins, add its hue to `SERIES` in the script
  and re-run that validator rather than picking one by eye.

## Cloud sessions

Read works, write does not. A cloud session can rebuild and republish the page
(`generate_shipping_dashboard.py` uses the proxy's BigQuery access), but the
loader has to run on the Mac. To check that a folder of files parses without
writing anything:

```bash
python3 scripts/load_shipping_orders_to_bq.py --week-dir <dir> --dry-run \
    --out-json /tmp/rows.json
python3 scripts/generate_shipping_dashboard.py --from-json /tmp/rows.json \
    --out preview.html
```

## Still to do

- Wire the loader into the Thursday `weekly-shipping-reports` job so the database
  fills itself instead of needing the two commands by hand.
- Decide whether the four Drive dashboard CSVs stay as they are or start being
  generated from this table, so there is one number instead of two.
