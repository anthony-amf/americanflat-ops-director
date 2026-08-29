# What we can look up, and what we can't

Checked against live BigQuery on **2026-08-26**. Re-check before relying on any
"not available" line below — pipelines get fixed.

`scripts/lookup_order.py <order#>` pulls the authoritative order facts so nobody
retypes a SKU. It covers less than you'd hope, and the gaps are the fields that
decide routing — so the lookup **supplements** the Shopify screen, it doesn't
replace it.

## Available — `americanflat.shopify`

| Table | Rows | What it gives |
|---|---|---|
| `orders` | ~24k | `name` (`#25402`), created_at, financial_status, fulfillment_status, totals, refunded |
| `order_line_items` | ~34k | **sku, title, quantity** per order |
| `order_refunds` | — | refunds against an order |

**Freshness is good.** The most recent order was created 13:50 UTC and ingested
14:07 UTC the same day — roughly a 17-minute lag. A ticket that arrives the same
morning will find its order.

This is the part worth automating: **SKUs and quantities ordered** were the fields
being mistyped, and here they're exact.

## Not available, with the reason

### The warehouse — nowhere at order level

There is no order-level warehouse column in any dataset. The nearest thing is
`shipstation.shipments_raw.warehouseId`, and it doesn't work as a signal:

| warehouseId | shipments | top ship-to states |
|---|---|---|
| 512455 | 18,554 | CA 2398, TX 1222, NY 1136, FL 948 |
| 93230 | 1,822 | TX 228, CA 179, NY 138 |
| 167512 | 339 | CA 48, FL 22, NY 22 |
| 93228 | 1 | NY 1 |

89% of shipments sit on one ID, and every ID's ship-to spread just mirrors US
population rather than a fulfillment region. It's a ship-from profile, not a per-3PL
identifier. **Read the fulfillment Location off the Shopify screen instead.**

### Tracking numbers — the feed is dead

`shipstation.orders_with_tracking` looks right, and isn't. Of 27,578 Shopify rows,
**zero** carry a tracking number, and `shipments_raw` stops at **2023-10-06** — the
shipment half of the ShipStation pipeline has been stale for nearly three years.
The order half is still current (latest Shopify order 2026-08-25), which is what
makes this trap easy to fall into.

Tracking comes off the Shopify order screen.

### Partial fulfilment — collapsed by the pipeline

`fulfillment_status` only ever holds `FULFILLED` (23,902), `UNFULFILLED` (483) or
`ON_HOLD` (7). Shopify's own `PARTIALLY_FULFILLED` never appears.

This matters: distinguishing a genuine short-ship from an unshipped balance
(`playbook.md`) depends on seeing `Partially fulfilled` and an `Unfulfilled (n)`
card. **The lookup cannot make that call** — the Shopify screenshot can.

### What the customer is complaining about

Never in Shopify by definition. That is the Zendesk side, and it's also where the
**affected quantity** comes from. The lookup returns quantities **as ordered**; the
shortfall is ordered minus received, and only the customer knows what they received.

## What would close the gaps

A **Shopify Admin API connection** would return fulfillment location, tracking
numbers and true partial-fulfilment state in one call — every gap above, from the
source of truth. It needs a private app token plus an allow-listed domain, neither
of which exists in this environment today (`admin.shopify.com` is not reachable from
a cloud session, and there is no Shopify connector).

Worth raising if order lookup becomes the main intake. Until then: lookup for the
SKUs and quantities, Shopify screen for warehouse and tracking, Zendesk for the
complaint.
