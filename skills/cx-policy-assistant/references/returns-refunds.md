# Returns, refunds, and replacements — process detail

Snapshot of **How To: Returns/Replacements/Refunds** (Notion
`1bcf13a0-15dc-41ae-a155-0b2894d5d3c1`, last edited 2025-10-07, Status: Live),
with the label-creation detail from **How To: Create Shipping Return Labels**
(`2fe8555c-2abc-8091-91f6-fea4436f034a`, last edited 2026-05-25) and
**How To: Get a Cost Estimation for a Return Shipping Label**
(`8d5336c1-d0bc-4433-9663-d4242ab2ff89`, last edited 2026-04-28).

Taken **2026-08-17**. These three pages **conflict on who creates return labels** —
read the conflict note at the bottom before answering a label question.

---

## Who handles the return at all

- **Orders placed on americanflat.com (Shopify)** — we handle every part of the
  return process.
- **Orders from any other marketplace** (Target, Wayfair, Walmart, Etsy, eBay,
  Faire, Macy's, Michaels, Amazon) — the customer contacts **that marketplace's**
  support for returns. Don't start a return we don't own.

## Return process (Shopify)

**Step 1 — Customer contact and confirmation.**
Customer reaches out via live chat, email, or a phone message. The rep confirms the
return details — including **the reason for the return** — through Zendesk.

**Step 2 — Label creation request.**
USPS is named as the preferred return carrier, purchased through Endicia.

- Return label requests are entered into the **Replacement Orders** Google Sheet,
  tab **"Return Label"**.
- Scroll to the bottom of the list and add the customer's information, following the
  format of the entries above it.
- Labels are created, uploaded to Dropbox, and the link goes in the **"Link to Label"** cell.
- Download the label from Dropbox and email it to the customer **in the Zendesk thread**.

*(This is the Oct-2025 process. The May-2026 label SOP has CX creating labels
directly in Stamps or FedEx — see the conflict note.)*

**Step 3 — Return integration.**
Once the package is confirmed received at Taylored Services, the warehouse contact
checks which products are in re-sellable condition, lists the SKUs and quantities,
and has a Taylored employee re-enter them into the system for resale.

## Who pays for the return

**Not Americanflat's fault** (changed their mind, didn't like it, wrong size):

- The customer is responsible for return shipping, **deducted from their refund**.
- **Alternative:** offer a **15%–25% discount to keep the item**, depending on the
  situation. This is often the better outcome — no freight, no restock, customer keeps
  a product they may warm to. Reach for it before processing a return.

**Is Americanflat's fault** (damaged, defective, wrong item sent):

- Ask for a **picture** to verify.
- The item is replaced and **no return shipping is charged**.

## Refund process (Shopify)

1. Log into Shopify — `americanflat.com/admin`.
2. **Orders** → search (magnifying glass) → enter the order number → click the order.
3. Click **Refund** (top right).
4. Choose the items being refunded, type a **concise but specific reason**, and click
   the **Refund $\_\_\_\_** button.
5. **Record the refunded amount** in the **Replacement Orders** sheet, tab **"CX Refunds"**.

Step 5 is not optional — the CX Refunds tab is how refund spend gets tracked.

## Replacement process (Shopify)

1. **Customer contact and confirmation** — confirm the replacement details and the
   reason via Zendesk.
2. **Add the customer and order information** to the Replacement Orders sheet, tab
   **"Replacement Orders"**.

For **marketplace** orders where we're responsible for the product, replacements go
through the **Manual Order sheet** instead — the Ops-Marketplace team monitors it and
sends the replacement. Fill columns A through N.

## Refund policy (the customer-facing terms)

- Merchandise must be returned within **30 days of delivery**.
- Merchandise must be **unopened, unused, and in original packaging**.
- Returns must include the **original packing slip** listing the items, so we know
  who sent it.
- If an item comes back in unsuitable condition, **the return is refused**.
- Returns that are **not Americanflat's fault** incur a **flat $5 return handling
  cost**, deducted from the refund amount.
- **Original shipping charges and expedited delivery fees are non-refundable.**
- Customers are responsible for **return postage at their own expense**.
- Refunds are processed within approximately **7–10 business days** after we receive
  the returned items.
- Americanflat is **not responsible for items returned to us by mistake**. If the
  customer wants it shipped back, confirm the address is correct first — and **the
  customer pays** for that second shipment.
- **Lost packages:** the customer has **10 days** after an item is marked delivered
  to report it missing. We are not responsible for reports beyond 10 days post-delivery.
- Anything marked **"Non-Returnable"** cannot be returned.

### Non-returnable items

- Washed or used items
- Final Sale items

### Standing instruction

> Use your judgement and try to keep Americanflat profitable when making a decision.
> When in doubt, ask help from senior management.

**Customer ordered the wrong item:** request a return on the returns sheet, reship
the current item, then process the new one.

Public FAQ: <https://support.americanflat.com/hc/en-us/categories/360006091791-FAQ>

---

## Return label cost estimation

From the Apr-2026 SOP. Use this when a customer wants to know what a return will
cost them before committing — especially on multi-item orders.

1. Open the order. **Do not click "Create Return Label."**
2. Click **"Return Items"** instead.
3. Select only the item(s) being returned; set every other item's quantity to **0**.
4. Click **"Create Return"** to see the estimated cost.
   - Example: returning 1 item might show **$7.75** rather than the cost for all items.
5. **If they add items:** cancel the current return request, go back to "Return Items,"
   select the full set, and "Create Return" again to re-estimate.
6. **Never click "Create Return Label"** — it generates a real label immediately.
7. When the estimate is done and the return isn't proceeding right away, click
   **"Cancel Return"** to reset the order status. Movements are logged; cancelling is safe.
8. **After a label already exists** and the customer adds items: a **new label** must
   be created, and **its cost deducted from the refund** too.

This SOP states labels **should only be requested from Raul Sim**.

## Creating the label (May-2026 SOP)

Purpose: create the return label in **Stamps** (formerly Indicia) or **FedEx**,
choosing the **cheapest valid service**, and document it properly.

**You need:** customer name and full return address, item weight (dimensions if
required), order number for the Reference #, and the marketplace/department.
**Print format: 4" × 6"**. Logins are in 1Password.

**Method A — new label in Stamps (Orders → Add):** set the correct **Ship From**
warehouse (Fontana, South Carolina, or Jersey — wrong origin causes billing and
address errors), enter the delivery address, weight and dimensions, pick the
**cheapest** serviceable option, and put the **order number in the Reference #**
field (this is how labels get traced later). Print as a 4×6 label.

**Method B — from shipment history:** Stamps → **History** → search by order number
or customer name (name search often works better) → confirm it's the right shipment
before doing anything → **Return Label** → cheapest service → **Print at home label**
→ enter your work email → enable **Send a copy** for the audit trail → Send. Retrieve
from email and print.

**Method C — FedEx return:** Shipping → Create Shipment → switch from **Outbound** to
**Return Shipment** → confirm the billing account is **110** → set **Deliver To** to
**Fontana** → enter the customer's details as the ship-from → enter weight (dimensions
usually unnecessary) → cheapest FedEx service → Reference format **`OrderNumber / Return`**
(e.g. `123456 / Return`) → fill **Department** with the marketplace → confirm billing
shows our account → Finalize → review, then Print.

---

## ⚠ Conflict: three different return-label paths

The SOPs genuinely disagree. Do not present one of these as *the* process without
saying so.

| Source | Last edited | What it says |
|---|---|---|
| How To: Returns/Replacements/Refunds | 2025-10-07 | CX enters the request in the Replacement Orders sheet ("Return Label" tab); labels are created by someone else, uploaded to Dropbox, and CX emails the link. **USPS via Endicia preferred.** |
| How To: Get a Cost Estimation… | 2026-04-28 | CX must **never** create a label. "Labels should only be requested from **Raul Sim**." |
| How To: Create Shipping Return Labels | 2026-05-25 | **CX creates the label directly** in Stamps or FedEx, choosing the cheapest valid service. No mention of the sheet, Dropbox, or Raul Sim. |

**How to answer:** lead with the **May-2026** version as the current working process
(it's newest and most specific), show the rep that the older pages say otherwise, and
flag that this needs a manager's decision so the SOPs can be reconciled. There is also
a **carrier** conflict inside this — Endicia/USPS (Oct 2025) vs. cheapest-of-Stamps-or-FedEx
(May 2026).

## ⚠ Conflict: who pays return shipping on a Shopify return

- **Customer Service Policies** (2025-10-07): for order values **over $100**,
  *Americanflat provides* the return label, cost deducted from the refund.
- **Refund Policy**, same page-set (2025-10-07): "Customers are responsible to pay for
  return postage at their expense," plus a **flat $5 return handling cost** on returns
  that aren't our fault.

These can be read as compatible — we buy the label and net the cost out of the refund,
so the customer bears it either way — but the **$5 flat handling cost** and the
**actual deducted postage** are two different mechanics and the pages don't say which
applies. **Confirm with a manager before quoting a specific deduction to a customer.**
