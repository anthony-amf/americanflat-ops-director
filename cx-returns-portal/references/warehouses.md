# Warehouse routing

Contacts verified against live `[nyc_ops]` threads on **2026-08-24**. These rotate —
if a reply comes from a new address or one bounces, fix it here and re-run
`scripts/build_portal.py`.

`NYC_Ops@americanflat.com` is on **every** Cc line. It is the shared Ops mailbox;
dropping it means nobody else can pick the thread up.

---

## Fontana, CA — Taylored Services / Yusen (TS Fontana)

Yusen Logistics (Americas) Inc., 8375 Sultana Ave. Unit 1, Fontana, CA 92335

- **To:** `fontanacsr@us.yusen-logistics.com`, `FontanaShipping@us.yusen-logistics.com`
- **Cc:** `Marisol.Luna@us.yusen-logistics.com`, `William.Keller@us.yusen-logistics.com`, `NYC_Ops@americanflat.com`
- **Add on inventory questions:** `FontanaInventory@us.yusen-logistics.com`, `Norma.Luna@us.yusen-logistics.com` (Inventory Supervisor — she is the one who physically counts and adjusts)
- **Escalation:** Marisol Luna (Ops Manager), William Keller (Contract Logistics)
- **Day-to-day CSR:** Monica Cortez — fast, replies same morning
- Subject prefix: `AMF x TS Fontana`

Serves: Shopify West, Amazon DF, Amazon VC, Walmart 1P.

## New Jersey — Taylored Services / Yusen (TS NJ)

- **To:** `Livel.Beltrez@us.yusen-logistics.com`, `Donald.Kistner@us.yusen-logistics.com`
- **Cc:** `Leandra.Murchison@us.yusen-logistics.com`, `Jorge.Blanco@us.yusen-logistics.com`, `NYC_Ops@americanflat.com`
- **Add on VAS/project work:** `Shirlei.Guzman@us.yusen-logistics.com`, `Fernando.Saenz@us.yusen-logistics.com`, `Ernesto.Juarez@us.yusen-logistics.com`
- **Escalation:** Don Kistner (Manager, Operations), Jorge Blanco
- Subject prefix: `AMF x TS New Jersey` (or `AMF x TS NJ` on the daily short sweep)
- WMS order prefix: `AME*` — e.g. `AME*25162`

> Don Kistner's address changed to `Donald.Kistner@...` in Aug 2026. The old one
> still forwards, but use the new one.

## South Carolina — Hardeeville (TS South Carolina)

Yusen Logistics (Americas) Inc., 186 Exchange Pl. Unit 102, Hardeeville, SC 29927

- **To:** `Gilma.Munoz@us.yusen-logistics.com`, `aanguiano@tpservices.com`, `Bryan.Lopez@us.yusen-logistics.com`
- **Cc:** `Hardeeville_CSRs@us.yusen-logistics.com`, `Hardeeville_Mgmt@us.yusen-logistics.com`, `NYC_Ops@americanflat.com`
- **Add on ops/quality escalation:** `Kwayne.Huggins@us.yusen-logistics.com` (Manager, Operations)
- **Camera checks:** `Douglas.Noll@us.yusen-logistics.com` — SC can pull packing-station footage to settle a "we shipped it / I never got it" dispute. Worth asking for on high-value disputes.
- **EDI / IT issues:** `Douglas.Wachs@us.yusen-logistics.com`, `Mahmood.Subhi@us.yusen-logistics.com`
- Subject prefix: `AMF x TS South Carolina`
- WMS order prefix: `AMS*` — e.g. `AMS*24124`

> SC bills pallet work through VAS work orders, not SP/LTL invoices — irrelevant to
> CX, but it means SC "extra work" requests need a work-order number, not just an email.

## Yusen Canada — Brampton, ON

Yusen Logistics (Canada) Inc., 261 Parkhurst Square, Brampton, ON L6T

- **To:** `Warehousenorth.CSR@ca.yusen-logistics.com`
- **Cc:** `sayaka.ambo@ca.yusen-logistics.com`, `Taranjeet.Kaur@ca.yusen-logistics.com`, `Eric.Houston@ca.yusen-logistics.com`, `Brian.Lapointe@ca.yusen-logistics.com`, `NYC_Ops@americanflat.com`
- Subject prefix: `AMF x Yusen Canada` — **no `TS`**, this is not a Taylored site

## Yusen Netherlands — Moerdijk (NL / Benelux)

Yusen Logistics Europe, Cluster North, Appelweg 12A, 4782 PX Moerdijk

- **To:** `customerservice.MRD@bnl.yusen-logistics.com`
- **Cc:** `mahjoub@americanflat.com`, `NYC_Ops@americanflat.com`
- Subject prefix: `AMF x Yusen NL` — **no `TS`**
- NL handles EU returns including Amazon DHL returns. They will ask for a disposition
  decision (restock vs. discard) and will not act without one.
- NL frequently cannot match a barcode to a SKU — include the **AF style code** and
  the **EAN/UPC** whenever you have both.

---

## Picking the warehouse when the paste doesn't say

In rough order of reliability:

1. **The order prefix.** `AME*` → NJ. `AMS*` → SC. Bare 5-digit Shopify → could be any US site.
2. **The tracking number.** Pull it up; the origin scan city names the warehouse.
   Fontana CA / Edison-area NJ / Hardeeville SC.
3. **Customer ship-to.** West Coast usually Fontana, Northeast usually NJ, Southeast
   usually SC — a tendency, not a rule. Do not route on this alone.
4. **Ask.** John Nunez or the Ops mailbox will know in minutes. Cheaper than a
   misrouted request.

If two warehouses are plausible, ask the operator rather than guessing.
