# Decision rules

What the warehouse email should be, given what the customer said.

Cases are referred to **by name** here, not by the numbers in `templates.md` —
those shift whenever a case is inserted, and silently pointed at the wrong
templates once already.

## Check the fulfillment status before anything else

**A customer reporting a shortage is not evidence of a short-ship.** Look at the
Shopify order status first:

- **Fulfilled** and the customer is short → a real discrepancy. open a **Missing units verification**.
- **Partially fulfilled** and the customer is short → the balance was **never
  shipped**. The warehouse picked exactly what was released to them and did nothing
  wrong. send an **Unshipped balance** chase, not an investigation.

Getting this backwards is expensive in both directions. An investigation email on a
partially-fulfilled order has the warehouse count inventory for a discrepancy that
doesn't exist, and burns the day the customer is actually waiting on. It also spends
credibility: warehouses that get asked to chase phantom shortages answer the real
ones more slowly.

The tell is only visible on the Shopify screenshot — the `Unfulfilled (n)` card.
The Zendesk ticket alone will always read like a short-ship.

## Reship, investigate, or both

| Customer says | Send | Also |
|---|---|---|
| "Arrived damaged" | Damaged on arrival | Reship — prioritize, if the RS order is placed |
| "Missing items / came up short", order **Fulfilled** | Missing units verification | Reship — prioritize; run both in parallel |
| "Missing items / came up short", order **Partially fulfilled** | Unshipped balance | No investigation — nothing was mis-picked |
| "Never arrived", tracking shows delivered | Tracking verification | Carrier claim, not a WH issue, if the scan is clean |
| "Never arrived", tracking never scanned | Tracking verification | The package likely never left — WH issue |
| "Wrong item" | **Replacement row**, reason `Wrong Item Sent` | Missing units verification if you also want to know what was picked |
| "I want to return it" | Nothing to the WH yet | Wait for the return to land, then Return disposition |
| Return landed at WH, they're asking | Return disposition | Decide restock vs. discard before replying |
| Customer found the original | Cancel replacement | Immediately, if the RS hasn't shipped |

**The parallel case is the common one.** A short-ship means an unhappy customer *and*
an inventory discrepancy. The replacement ships today so the customer is fixed;
the investigation runs on its own clock so inventory gets corrected and we learn
whether it was a warehouse short-pick. Don't hold the reship waiting on the answer.

## Before sending anything, check

1. **Is the RS order actually placed?** Templates 1 and 6 reference a PO number the
   warehouse will search for. If it isn't in their system, you get "we don't see this"
   and lose a day. Confirm with the operator.
2. **Is this the right warehouse?** See the routing rules in `warehouses.md`.
3. **Has this order already been emailed about?** Search Gmail for the order number
   first. If a thread exists, **reply on it** rather than opening a second one — the
   warehouse tracks by thread, and a duplicate gets one of the two ignored.
4. **Is the customer waiting on an answer from us?** If CX has promised a response
   time, put the deadline in the email.

## What not to do

- **Don't batch customer issues.** One order per email. The daily shorted-orders
  sweep is a separate batched workflow with a different purpose; customer-facing
  issues get their own thread so the reply is attributable.
- **Don't ask the warehouse to decide.** "Please advise" produces silence. Say what
  you want: ship it, cancel it, discard it, count it.
- **Don't send an investigation email without the SKU and quantity.** "Some items
  are missing" cannot be answered.
- **Don't chase inside 24h** on an investigation. Counts and camera pulls take a day.
  Reships are different — those are same-day and worth chasing at EOD.

## Cost context

Worth knowing, because it shapes when a reship is the right call:

- A replacement costs the unit, the outbound freight, and a pick fee, and the original
  unit is usually unrecoverable.
- Fontana bills every e-com pick; NJ and SC bill on their own schedules. An RS order
  is a fully-billed order, not a free correction.
- For low-value single frames, a refund is often cheaper than a reship. That's the
  marketplace owner's call, not this skill's — but flag it when the item is cheap and
  the customer only wants to be made whole.

## Privacy

The paste will contain a real person's name and address. That's fine — it's needed to
ship. But:

- Don't put the customer's **email address or phone number** in the warehouse email.
  The 3PL has no reason to contact them, and it widens exposure of personal data for
  no operational gain.
- Don't paste customer details into anything outside Gmail and the portal.
- The portal parses entirely in the browser and stores nothing.
