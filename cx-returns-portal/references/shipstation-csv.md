# The ShipStation reship CSV

Instead of emailing the warehouse to place a replacement, build the order in
ShipStation directly. The warehouse picks from ShipStation, so an imported order
becomes work without anyone reading an email, and the order carries its own audit
trail.

## Read this before the first production import

**The header names in `shipstation-csv.json` have not been validated against a real
ShipStation import.** They follow ShipStation's standard order-import template, but
nothing in this environment can reach ShipStation to confirm them — the shipment
half of the BigQuery feed died in Oct 2023 and `shipstation.com` isn't reachable
from a cloud session.

Two things make this low-risk rather than reckless:

1. **ShipStation's CSV import asks you to map columns to its fields** before it
   commits anything, and lets you save that mapping as a preset. A header we named
   differently gets fixed in that screen once, not in every file. *(Confirm this on
   your first run — if the import turns out to be strict-header, the fix is the
   next point.)*
2. **The headers are config, not code.** Edit `header` values in
   `references/shipstation-csv.json`, re-run `scripts/build_portal.py`, and both
   the portal and the CLI emit the corrected file.

**Do one test import with a single-line CSV before using this for real**, and set
`verified_against_real_import: true` once it lands correctly. Until someone does
that, treat every generated file as a draft.

## What the CSV contains

One row per item. Order-level fields repeat on every row of the same order — that's
how ShipStation associates multiple items with one order.

| Column | Where it comes from |
|---|---|
| Order Number | The **RS** number — original order + `RS` |
| Order Date | Today |
| Order Status | `awaiting_shipment` (a real value from the live data) |
| Requested Shipping Service | Blank unless the reship is being expedited |
| Recipient · Address · City · State · Postal · Country · Phone | **The Shopify order screen** — not in BigQuery |
| Item SKU · Item Name · Item Quantity | The replacement units |
| Item Unit Price | `0.00` — a replacement is not a sale |
| Internal Notes | Original order, the reason, the pick instruction |

### Why `0.00`

A replacement bills nothing to the customer. Leaving the real price in makes the
reship look like revenue in any downstream report that reads ShipStation order
totals. The Internal Notes line says what it is so nobody reads the zero as an error.

### The address is the one field nothing can fill for you

BigQuery holds `shipToCity`, `shipToState` and `shipToPostalCode` but **no street
address** — not in `shipstation.orders_raw`, not in `shopify.orders`. Copy address
line 1 and 2 off the Shopify order screen. A reship to a city and ZIP with no street
line will not ship.

### The pick instruction has no ShipStation field

Full master carton vs. loose units doesn't map to any import column, so it goes in
**Internal Notes**, where the picker sees it. If a reship must go as a sealed case,
check that the note survived the import.

## What still needs an email

The CSV creates a shipment. It cannot ask a question, so these stay as warehouse
emails (`templates.md`):

- Missing units verification — asking what physically shipped
- Unshipped balance — asking when the rest is allocated
- Tracking verification
- Return disposition — restock or discard
- The packing-quality half of a damaged-on-arrival case
- Cancelling an order that's already in ShipStation

A **damaged on arrival** case usually needs both: the CSV to get the replacement
moving, and the email to ask why it broke.
