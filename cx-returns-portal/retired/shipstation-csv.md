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

## The API would be better than the CSV — here's where that stands

Checked 2026-08-27. **Cloud sessions cannot reach ShipStation.** Both hosts are
denied at the egress proxy by organization policy:

```
kind:   connect_rejected
detail: gateway answered 403 to CONNECT (policy denial or upstream failure)
host:   ssapi.shipstation.com:443   /   api.shipstation.com:443
```

That is a policy decision, not a transient failure, so there is nothing to retry
here. An API key does **not** change it — the connection is refused before any
credential is offered, which is why the key should not be pasted into a cloud
session or committed anywhere.

Two ways forward:

1. **Run it from the Mac** — available today. A local session isn't behind this
   proxy. `scripts/shipstation_probe.py` is a read-only probe: export
   `SHIPSTATION_API_KEY` and `SHIPSTATION_API_SECRET` in your shell, run it, and it
   lists stores and warehouses and captures the field names of a real order.
   **This is what closes the open questions in this file** — real header names
   instead of guessed ones, and the `warehouseId` → name mapping that BigQuery
   couldn't provide (`data-sources.md`).

2. **Have the domain allow-listed** for the cloud environment. `ssapi.shipstation.com`
   added to the environment's allowed domains — ideally with proxy credential
   injection, the way `api.airtable.com` and `bigquery.googleapis.com` already work,
   so the key lives in the proxy and never in the repo, a transcript, or an env file.

Once either is in place, replacement orders can be **created directly** rather than
exported and imported by hand, and the CSV becomes the fallback for when the API is
down.

### Credential handling

The probe reads both values from the environment only. Don't pass them as CLI
arguments (shell history keeps them), don't put them in a file inside this repo, and
note that its output file records field *names* and warehouse IDs — never customer
data and never the credentials.

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
