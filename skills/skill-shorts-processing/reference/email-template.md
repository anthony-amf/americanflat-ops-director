# Warehouse Action Email Template

One email per origin warehouse that has any action items today (cancels and/or partial ships).

## How many emails to produce

Group all shorted orders by their **origin warehouse** (from `Order#` prefix):

- `AMF*` → Fontana
- `AME*` → NJ
- `AMS*` → SC

Produce one email per warehouse that has actions. If all are `AMF*`, that's one email to Fontana. If spread across two prefixes, that's two emails.

**Only the origin warehouse gets the email.** The redirect destination warehouse does not — that's coordinated through the Slack post.

If there are no shorts at all today, skip this output entirely.

## Subject

```
AMF x TS [Warehouse] Shorted Orders [MM/DD/YY] - [N] order[s]
```

- `[Warehouse]` = Fontana / NJ / SC
- `[N]` = total action items (cancels + partial ships) for that warehouse only
- Pluralize: "order" → "orders" when N > 1

Examples:
- `AMF x TS Fontana Shorted Orders 05/20/26 - 1 order`
- `AMF x TS Fontana Shorted Orders 05/20/26 - 6 orders`
- `AMF x TS NJ Shorted Orders 05/21/26 - 2 orders`

## Body

```
Hi [Warehouse] Team,

Please action the following orders from today's short report:

CANCEL — do not ship:
• [Order#] — [Consignee]

PARTIAL SHIP — ship only the allocated portion, do not ship the shorted units:
• [Order#] — [Consignee]

Full short report attached for SKU and quantity detail.

Thanks,
[Sender]
```

## Rules

- Greeting uses the warehouse name: "Hi Fontana Team," / "Hi NJ Team," / "Hi SC Team,".
- Two sections in this order: **CANCEL**, then **PARTIAL SHIP**.
- **`CANCEL` means cancel the ENTIRE packslip — the origin ships zero units of the order.** ⚠️ Only put an order here when its `TS POA = Cancel` (every shorted line Alloc 0 AND `Total Order Units == sum of shorted Ord Qty`). **Never put a redirected order in CANCEL if the origin still has other lines to ship** — that cancels the in-stock lines too. If `Total Order Units > sum of shorted Ord Qty`, the order is `Partial Ship`, full stop, even when the shorted line(s) are being redirected away. (This caused real lost shipments on 2026-07-06 — see the Step 1 worked example in SKILL.md.)
- **`PARTIAL SHIP` means: ship everything you have allocated, do NOT ship only the shorted/redirected units.** Use for any order with `TS POA = Partial Ship`, including orders whose shorted lines are all being redirected but which have other lines shipping from origin. When helpful, add a short parenthetical so the warehouse knows what's leaving vs. held, e.g. `(ship the rest of the order; the shorted line(s) are being redirected — do not ship those)`.
- **Skip a section's heading and bullets entirely** if there are none of that type for this warehouse today. (E.g., if Fontana only has partial ships, skip the CANCEL section.)
- One bullet per order, not per line. If an order has multiple shorted lines, it still gets one bullet.
- Format: `[Order#] — [Consignee]`.
- Don't list SKUs or redirect destinations — those go in the attached short report and the Slack post respectively.
- Sign off with `[Sender]` as a placeholder — the user will fill in their name before sending.
- Render each warehouse's email in its own labeled block, e.g.:
  ```
  **Email to Fontana:**
  Subject: ...
  [body]
  ```

## Ad-hoc warehouse emails (mid-day cancel requests, OOS notices)

Warehouses sometimes email mid-day asking permission to cancel an order they can't fulfill (Bryan from SC, Monica from Fontana, etc.). The reply rule depends on what we're doing with the order:

- **If we're redirecting to another warehouse → YES, cancel at origin.** The origin warehouse has nothing to ship; the cancel keeps their books clean while the redirect warehouse fulfills. Reply confirming the cancel AND name the warehouse that's taking the redirect. Never tell origin "don't cancel" while a redirect is in flight — that risks two warehouses trying to ship the same order, or worse, origin holding the line open expecting eventual stock.
- **If we're partial shipping → DO NOT cancel.** Origin keeps the allocated portion and ships it; we redirect only the shorted units. Reply: "please proceed with the partial ship — origin ships [allocated qty], the shorted [N] units are being redirected to [warehouse]."
- **If we're truly cancelling (no redirect path, full OOS) → YES, cancel.** Reply confirms the cancel and CS will handle customer notification.

The decision tree is independent of how many other warehouses the order has already bounced through — only the current routing matters. Origin TS POA (Cancel vs Partial Ship) is the test, not the order's lifecycle history.

## Formatting — never hard-wrap

Write **one continuous line per paragraph and per bullet**, however long it runs. Only break for a genuinely new paragraph, bullet or heading. Hard-wrapped text pastes into Gmail as literal line breaks that do not reflow to the window width and looks broken. Avoid space-padded ASCII columns for the same reason — use inline form (`SKU — 120 units (15 cases of 8)`).

## Group the CANCEL orders by reason

Do not put every cancel in one undifferentiated list — the warehouse cannot tell what is happening. Use a separate heading per reason, in this order:

1. `CANCEL — SUBSTITUTION. Please cancel these packslips so we can re-send a new order with the corrected SKU line.` Name the substitute SKU per order. The warehouse must genuinely cancel so ops can raise the replacement order; a "down confirm" does not create it and leaves the substitution in limbo.
2. `CANCEL — do not ship. Being fulfilled in full from another warehouse.` Name the warehouse.
3. `CANCEL — do not ship. No stock at any warehouse.` CS notifies the customer.

## Amazon VC / Walmart 1P lines

These use `DOWN CONFIRM`, not CANCEL — they confirm down to the nearest whole carton in the vendor portal rather than cancelling a packslip. Give them their own heading, state the carton size and the confirmed quantity per line, and note that a confirmed quantity above 0 also partial ships.

## One email per warehouse, complete on its own

When a day carries both routine shorts and an urgent event (a pricing-error recall, a mass short), keep it to a single email per warehouse with the urgent part first under its own heading. Do not split one warehouse across two emails — the second one gets missed.
