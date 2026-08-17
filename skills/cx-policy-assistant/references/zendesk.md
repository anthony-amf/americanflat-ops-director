# Zendesk — ticket workflow

Snapshot of **How To: Operate in Zendesk** (Notion
`60797b21-c016-4d70-8d22-0502e58a1b07`, last edited 2025-10-07, Status: Live).
Taken **2026-08-17**.

Purpose of the source SOP: an entry-level look at Zendesk for someone unfamiliar
with basic customer contact.

---

## What lands in Zendesk

Live chat, email, and phone messages all arrive in the Zendesk portal. Zendesk carries
**Shopify, some Amazon, Target, Bed Bath & Beyond, Facebook, Instagram**, phone calls,
and website live chat.

**Not in Zendesk** — these are answered inside each platform's own account:
Wayfair US & UK, Walmart, Amazon, Etsy, eBay, Faire.

## Getting to the tickets

1. Log in: <https://americanflat.zendesk.com/agent>
2. The first view is the dashboard.
3. Go to **Views** — the icon below the home/house icon on the left. All tickets land here.
4. Click **Open Tickets** (the newer ones). Open tickets stay pinned at the top of the
   window until closed with the "x".

## Working a ticket

On the left-hand side of the ticket there are input fields:

- **Non-Shopify marketplace order:** enter the **Order ID** in its box and pick the
  **marketplace** from the dropdown just below it.
- **Shopify order (americanflat.com):** no order ID or marketplace needed.
- **Select the category** that best represents the issue you're solving.

Getting the marketplace field right matters beyond tidiness — it determines whose
return policy applies and whether we own the resolution at all.

## Replying

Either write your own response, or use a **Macro** — pre-written templates that
auto-fill some of the customer's data.

**Read the macro before sending.** Several macros contain multiple branches for
different circumstances, and sending the wrong branch reads as careless.

## Closing: which status to use

| Status | Use when |
|---|---|
| **Solved** | Resolved, no follow-up needed from the customer or any Americanflat team. |
| **Pending** | Waiting on **the customer**. |
| **On-hold** | Waiting on **another Americanflat department** — or on **yourself**, the CX agent. |

Both "waiting on another department" and "waiting on me" map to **On-hold**. Pending is
reserved for the customer's court.

## Common issues and their resolutions

All CX policies live in the Customer Service Policies page — see `policies.md`.

### Amazon order issue

Most Amazon inquiries can be answered with the **Amazon Macro**. If the order was sold
*and shipped by* Amazon, we have no order details.

### Damaged order on a marketplace where we're responsible for the product

1. Ask for a **picture** of the damaged item — proof and validation.
2. **Forward the damage details to the product development team** for quality assurance.
3. Process the replacement through the **Manual Order sheet**: enter the order
   information in the next available row, **columns A through N**.
4. The **Ops-Marketplace team** monitors that sheet and sends the replacement.

Step 2 is easy to skip and shouldn't be — it's the only route damage data takes into
quality work.

### Received the wrong item

Give the customer two options:

1. Keep the item they received, as an acceptable substitution.
2. Take a refund for the incorrect item — a **prepaid label** is emailed to them, and the
   refund is issued once the warehouse confirms receipt.

Cross-check against the value threshold in `policies.md`: under **$50** the customer keeps
the item regardless.

### Product detail inquiry

For questions like "what size are the black 12x21 frames?":

1. In the **Shopify backend**, search by size to narrow down the exact SKU.
2. Copy the SKU, open the **Master Inventory Tracker (MIT)** sheet, and Ctrl-F the SKU to
   find its dimensions.

The source SOP notes this takes practice, and that becoming familiar with the product
catalog makes customer interactions much faster.

## Order-status escalation in Slack

If a customer asks why an order is late and it hasn't shipped yet, post in the **CS Slack
channel** for an update, using the channel's standard format.
