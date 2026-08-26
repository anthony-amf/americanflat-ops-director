# Warehouse email templates

Seven templates. Six are lifted from threads the warehouse actually replied to; the
unshipped-balance one was added after a screenshot walkthrough showed the
missing-units template being sent for orders that were never fully released. Keep the
shape. The warehouses have learned to read these — a reformatted email gets a slower,
vaguer answer.

Placeholders are `{{like_this}}`. `{{wh_greeting}}` is the team name from
`warehouses.md` (`Fontana Team`, `NJ Team`, `SC Team`, `Yusen Canada Team`, `Yusen NL Team`).

---

## 1 — Reship / replacement: prioritize

**Subject:** `AMF x TS {{warehouse}} Request to Prioritize Replacement order # {{rs_order}}`

```
Hi {{wh_greeting}},

Please prioritize replacement order #{{rs_order}} for shipment by {{deadline}}.

{{pick_instruction}}

We are currently dealing with an unhappy customer on the original order, so it's
important that this replacement is processed correctly and leaves the warehouse today.

Once shipped, please send me the tracking number or ensure tracking is properly
placed on the order so my team can retrieve it.

Thanks in advance!

Best,
{{sender_name}}
```

### The pick instruction is a choice, not a constant

`{{pick_instruction}}` has two forms, and picking the wrong one costs a day. The
warehouses follow this line literally.

**Full master carton** — the original shipped as a set, or the replacement is a
whole sealed case:

> This replacement must ship as one full master carton. Please do not piece-pick
> individual units or split the shipment.

**Individual units** — the replacement is one frame, one print, or a few loose
pieces out of a larger order:

> This replacement is a loose-unit pick — please pick only the individual units
> listed below. It does not need to ship as a full master carton.
>
>   - {{sku}} x {{qty}}

Rules of thumb:

- A replacement for a **short-shipped set** goes as a full carton. Splitting it is
  how the same complaint comes back a second time.
- A replacement for **one damaged piece** out of a multi-item order is a loose pick.
  Asking for a sealed case ships the customer far more product than they need, at
  full freight, and Fontana bills the pick either way.
- On a loose pick the **SKU and quantity are mandatory**. "Send a replacement" with
  no unit list cannot be actioned, and you'll get a question back instead of a
  shipment.

## 2 — Missing units / short-ship investigation

**Subject:** `AMF x TS {{warehouse}} {{marketplace}} Order #{{order}} – Missing Units Verification`

```
Hi {{wh_greeting}},

Could you please review {{marketplace}} Order #{{order}}? The customer is reporting
that the order was not received in full.

They specifically state they are missing:

  - {{sku}} x {{qty}}

Could you please confirm:

  - What quantities physically shipped for each SKU?
  - Whether any additional cartons/packages were shipped separately
  - Any additional tracking numbers associated with this order

{{replacement_note}}

Thank you,
{{sender_name}}
```

`{{replacement_note}}` — when a replacement is already placed:

> A replacement has already been placed for the customer, but we need to understand
> what happened with the original shipment and confirm whether this was a warehouse
> short-ship.

Otherwise omit the line entirely. Don't write "no replacement has been placed" — it
reads as an instruction not to act.

## 3 — Unshipped balance

**Subject:** `AMF x TS {{warehouse}} {{marketplace}} Order #{{order}} – Unshipped Balance`

```
Hi {{wh_greeting}},

{{marketplace}} Order #{{order}} shows part of the order still unfulfilled,
and the customer has only received what shipped so far.

Still owed:

  - {{sku}} x {{qty}}

Could you please confirm the balance is allocated and when it will ship?
The customer needs it by {{deadline}}, so if there is a stock issue on this style
please tell me today and we will source it from another site.

Thank you,
{{sender_name}}
```

Use this instead of the missing-units investigation whenever Shopify shows
`Partially fulfilled`. Nothing was mis-picked — the units were never released — so
an investigation request only wastes a day. The offer to source from another site is
what makes this email useful: it turns a status question into a decision.

## 4 — Tracking verification

**Subject:** `AMF x TS {{warehouse}} {{marketplace}} Order #{{order}} – Tracking Verification`

```
Hi {{wh_greeting}},

Could you please review {{marketplace}} Order #{{order}} and verify the tracking
number entered for the shipment?

Tracking: {{tracking}} is coming back as invalid in {{carrier}}, and the customer
cannot track their package.

Could you please confirm the correct tracking number and that the shipment
physically left the building?

Thank you,
{{sender_name}}
```

## 5 — Cancel a replacement order

**Subject:** `AMF x TS {{warehouse}} Request to Cancel {{rs_order}}`

```
Hi team,

Please cancel PO # {{rs_order}} -- this is a replacement order that is no longer
needed, thank you!

Best,
{{sender_name}}
```

Send this the moment the customer says the original turned up. An RS order that
ships after the customer is satisfied is pure loss — product, freight and a pick fee.

## 6 — Return received at the warehouse: disposition

**Subject:** `AMF x TS {{warehouse}} Return {{tracking_or_ref}} – Disposition`

```
Hi {{wh_greeting}},

Thank you for flagging the return received {{received_date}}{{tracking_clause}}.

Item: {{sku}} / {{ean}} — {{qty}} pcs

Please {{disposition}}.

{{condition_note}}

Thank you,
{{sender_name}}
```

`{{disposition}}` is one of:

- `restock this into sellable inventory` — undamaged, resalable
- `discard for damage -- I have logged it from my side` — damaged; the second half
  matters, it tells the WH we've taken the inventory hit so they don't wait
- `hold this aside and send photos before we decide` — unclear condition or high value

`{{condition_note}}` — for anything the WH couldn't identify:

> If the item number doesn't resolve in your system, the AF style code is
> `{{sku}}` and the EAN is `{{ean}}`.

NL specifically hits this: they receive DHL/Amazon returns with a barcode that isn't
in their WMS and will sit on it until someone maps it.

## 7 — Damaged on arrival

**Subject:** `AMF x TS {{warehouse}} {{marketplace}} Order #{{order}} – Damaged on Arrival`

```
Hi {{wh_greeting}},

The customer on {{marketplace}} Order #{{order}} received their order damaged.

Item: {{sku}} x {{qty}}
Shipped under tracking: {{tracking}}

A replacement has been placed under #{{rs_order}} — please prioritize it for
shipment by {{deadline}} and send tracking back on this thread.

Separately, could you please check:

  - How this order was packed (carton size, void fill, corner protection)
  - Whether other units of {{sku}} in the same location show damage

We're seeing enough breakage on this style that we want to know whether it's a
packing issue or an inbound one.

Thank you,
{{sender_name}}
```

The second half is what turns a one-off reship into a fix. Include it whenever the
same SKU has broken more than once.

---

## Signature

Emails send under the CX teammate's own name and signature. The portal appends:

```
{{sender_name}}
{{sender_title}}
americanflat.com
```

Don't sign as John Nunez unless John is sending. The warehouse replies to whoever
signed, and a reply to the wrong person stalls.
