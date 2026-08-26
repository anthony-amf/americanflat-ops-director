# Americanflat CX bot

Answers customer-experience questions about Americanflat products from the live
catalogue instead of from memory. Two ways in, one shared set of rules:

| Surface | Who it's for | What it does |
|---|---|---|
| **Skill** — `.claude/skills/americanflat-cx-bot/` | anyone in Claude Code on this repo | ask a question in plain English, get a grounded answer or a drafted customer reply |
| **Console** — `cx_console.html` | the CX team, in a browser | type a size, colour, UPC, SKU or product name and read the facts |

Both refuse to answer past what the catalogue supports, and both flag the
listings that are unsafe to quote.

## Build and refresh

```bash
python3 cx-bot/build_kb.py --report --defects   # pull BigQuery -> product_kb.json
python3 cx-bot/build_console.py                 # render cx_console.html
```

`build_kb.py` reads BigQuery through the Mac's gcloud credentials if the
`google-cloud-bigquery` package is importable, and otherwise through the cloud
session's proxy — no configuration either way. It only reads, so it is safe to
re-run.

Stock and price drift, so rebuild before answering anything price- or
stock-sensitive. Every surface prints the build time.

## Ask a question

```bash
python3 cx-bot/cx_lookup.py "black 11x14 frame with a mat"
python3 cx-bot/cx_lookup.py --upc 810131993696
python3 cx-bot/cx_lookup.py --sku LX2424BLKNOMAT
python3 cx-bot/cx_lookup.py --size 11x14 --color black --in-stock --limit 10
python3 cx-bot/cx_lookup.py --category "Shadow Box" --limit 20
python3 cx-bot/cx_lookup.py "shower curtain" --json
```

`[!]` is blocking — do not quote that price, stock level or size until it is
checked in Shopify admin. `[i]` is context. A **WEAK MATCH** header means
nothing in the catalogue clearly matches, so confirm the product with the
customer instead of naming one of the guesses.

## Where the facts come from

`americanflat.merchant_center.Products_136085689` — the Google Merchant Center
feed, which is the only customer-facing product catalogue we hold in BigQuery.
The most recent snapshot is used; 6,022 feed rows dedupe to 4,249 products.

Product policy (returns, refunds, replacements, damage, delivery) is **not** in
the catalogue. It lives in `POLICY.md` next to the skill, condensed from the two
live Notion SOPs, which stay the source of truth.

## Rules the catalogue forced on us

Each was measured, not assumed, and `build_kb.py --report` re-checks all of them
on every rebuild:

- **Titles are the spec; descriptions are not.** 547 products carry a
  description quoting a different size than their own title, and 2,386 share
  recycled boilerplate with hundreds of others. Descriptions are deliberately
  left out of the console entirely.
- **`sale_price` is the real price.** It matched actual Shopify selling prices
  86% of the time against 1.4% for `price`, which is the compare-at figure.
- **A UPC is not a unique product.** 1,036 UPCs are reused across 2,665
  products; one sits on 7.
- **The variant wins over the parent name.** 997 titles open with the parent
  listing's size, so *"8.5x11 | Walnut | Picture Frame | Streamline 24x24 /
  Black / 1 Pack"* is a 24x24 black frame. Everything after the `/` is what the
  customer actually bought.
- **Two US feeds disagree.** `US` and `US2` share 1,773 offer_ids and differ on
  145 prices and 165 stock states. `US` wins (it matched real Shopify sales 11-0
  where they conflict), and every remaining disagreement is flagged rather than
  silently resolved.
- **Missing from the feed ≠ discontinued.** The feed holds only what is
  currently published to Google.

## Fixing the listings

`build_kb.py --defects` writes `listing-defects.csv` — 1,854 blocking defects
across 1,643 products, sorted by type, with the product URL for each. Fixing
these at the source is the only thing that makes the catalogue safe to quote
from directly; until then the flags are doing that work at answer time.
