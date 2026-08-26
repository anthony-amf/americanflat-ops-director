# Reading the screenshots

The fastest intake is two screenshots dragged straight into Claude: the **Shopify
order** (what we actually shipped) and the **Zendesk ticket** (what the customer says
went wrong). Neither one is sufficient alone, and they answer different questions.

| Question | Comes from |
|---|---|
| What was ordered, and what shipped? | Shopify |
| Which warehouse shipped it? | Shopify (fulfillment location) |
| What is the customer missing / complaining about? | **Zendesk** |
| How many units are wrong? | **Zendesk**, not Shopify |
| Order number, SKUs, tracking | Shopify |

## Shopify order page

Read, top to bottom:

- **Order name** — `#22397` at the top left, with status pills beside it (`Paid`,
  `Fulfilled`, `Partially fulfilled`, `Unfulfilled`). Partially fulfilled matters:
  it means part of the order is still owed and the customer may be reporting a
  shortage that isn't a warehouse error at all.
- **Line items** — product title, variant, SKU, and quantity shown as `× 2`.
  The SKU is the AF style code (`MW0808WH44`). If the screenshot is cropped and the
  SKU column isn't visible, **ask for it** — don't infer it from the product title.
- **Fulfilled / Unfulfilled cards** — each fulfilled card carries a **Location** and
  a **tracking number**. The Location name is the warehouse signal.
- **Customer / Contact / Shipping address** — take the shipping name. Do **not**
  carry the email address or phone into the warehouse email.

### Location → warehouse

Shopify shows the fulfillment location's own name, which is not the name the
warehouse team uses. Map it, and if the mapping isn't obvious, ask:

| Shopify location contains | Warehouse |
|---|---|
| Fontana, CA, West | Fontana |
| NJ, New Jersey, Edison | New Jersey |
| SC, South Carolina, Hardeeville, Savannah, TS South | South Carolina |
| Brampton, Canada, ON | Yusen Canada |
| Moerdijk, Schiphol, NL, Netherlands | Yusen NL |

### Two traps

1. **`× 2` is the quantity ordered, not the quantity missing.** The shortage figure
   comes from the customer in Zendesk. An order for 8 where the customer received 2
   is `MW1114WH57 x 6` missing — Shopify alone would have you write `x 8`.
2. **Multiple fulfillments mean multiple tracking numbers.** If the order shows two
   fulfilled cards, the customer may have received one parcel and not the other, and
   nothing was ever short-picked. Check both tracking numbers before opening a
   short-ship investigation. This has been a real cause twice: once as two parcels
   under one label at SC, once as a split shipment at Fontana.

## Zendesk ticket

- **Ticket number** — for our records only. **Never put it in the warehouse email.**
  The warehouse cannot search a Zendesk ID; they need the Shopify order number.
- **Requester name** — often differs from the Shopify shipping name (a gift, or a
  spouse ordered it). When they differ, trust the **Shopify shipping name** for
  anything the warehouse sees, and don't treat the mismatch as a red flag on its own.
- **The customer's own words** — this is the whole point of the second screenshot.
  What is broken, what is missing, how many. Quote quantities from here.
- **Status and tags** — tells you whether CX has already promised something. If the
  ticket says a replacement was offered, the RS order should already exist; confirm
  before writing an email that references it.
- **Requester email and phone** — visible in the left panel. Leave them out.

## What to do with what you read

Restate the extracted fields back to the operator before drafting, as a short list
they can correct in one line:

```
Order 22397 · Shopify · Fontana · Sarah Whitfield
Missing: MW0808WH44 x 1, MW1114WH57 x 2
Tracking 525499496652 (one fulfillment)
Zendesk #48213 — customer reports a short shipment, replacement not yet placed
→ Missing units verification, plus a reship once the RS order exists
```

Then ask about anything the screenshots didn't answer. The three that block a draft:

- **Which warehouse**, when the location is cropped or ambiguous.
- **Whether the RS order is placed**, for any reship or damaged case.
- **Full carton or loose units**, for a reship.

## When a screenshot is unreadable

Low-resolution or heavily cropped screenshots are common. Say which field you can't
read and ask for that one thing — don't guess a SKU or a quantity. A wrong SKU sends
the wrong product to an already-unhappy customer, and the second mistake costs far
more than the question would have.
