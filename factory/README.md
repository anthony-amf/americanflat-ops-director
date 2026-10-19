# Factory invoice check (against the WIP purchase orders)

Checks a factory's invoice against our purchase orders before it is paid.
Started 2026-10-19.

- `check_factory.py` — the check. Reads the WIP tab (CSV export) and one
  invoice as JSON.
- `test_check_factory.py` — 14 cases on a small made-up WIP (real supplier
  prices are deliberately not stored in the repo).

## Where the prices come from

The **WIP** tab of *Master Inventory Tracker 2026*: one row per PO line with
PO number, SKU, factory, quantity, FOB unit price, shipped quantity and stage.
At export (2026-10-19): 42,787 rows, 1,697 POs, Jan 2022 – Oct 2026.

## What it checks, per invoice line

1. **The PO and SKU exist**, and the PO belongs to the factory that billed it.
2. **Unit price = that PO's FOB.** Always the invoice's own PO — the same SKU
   from the same factory had more than one price on 1,192 factory/SKU pairs
   since 2025.
3. **Quantity** — billed now plus billed before (pass earlier invoices with
   `--prior`) must not exceed what was ordered (overcharge) or what has
   shipped (review).
4. **Math** — qty × price = line amount, and lines = invoice total.

Also flagged for review: price below the PO, more than one price on the same
PO line, a PO line on hold, a non-USD invoice.

`--deposit` runs the price/PO checks only (for deposit invoices raised
before goods ship).

Split shipments repeat a PO line on several WIP rows; quantities are summed
and the WIP's "Total cost" column is ignored, because it repeats the full line
total on every split row (37 such rows at export).

## Tried on the real WIP

Loads all 41,667 PO lines in about a second. A correctly billed line from PO
9812 (Jinlida, 168 × $2.84) comes back valid; the same line at $2.94 comes
back as $16.80 over.

## Open items

1. **A real factory invoice** (and a deposit invoice, if deposits are used) —
   to learn the layout and payment terms (deposit %, balance on shipment?).
   Factory invoices don't reach Anthony's inbox or bill.com; they seem to go
   to sourcing (Jessie / amfsourcing) and be paid by wire.
2. **Who pays them, and where the paid history lives** — needed for the
   double-billing check (`--prior`) to work on real data.
3. **Live WIP** — the check reads a CSV export today; it can read the Google
   Sheet directly once that's set up.
4. **Storage for results** — `finance.freight_invoices` with an invoice-type
   column, once write access is granted.
