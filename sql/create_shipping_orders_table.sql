-- Create the shipped-orders ledger behind the Cost Per SKU shipping dashboard.
--
-- One row per shipped package ("shipment"), for the four marketplaces where
-- Americanflat pays the freight: Target, Michaels, Shopify, Macy's.
--
-- Run ONCE, from the Mac (gcloud ADC) or the BigQuery web console:
--   bq query --use_legacy_sql=false --max_rows=100 < sql/create_shipping_orders_table.sql
--
-- CONFIRMED 2026-08-11: Anthony's account is refused here —
--   "Access Denied: Dataset americanflat:finance: Permission
--    bigquery.tables.create denied on dataset americanflat:finance"
-- The BigQuery web console does NOT get around this; it signs in as the same
-- account and fails the same way. Creating the table needs someone with
-- BigQuery Data Editor (or Owner) on the `finance` dataset — Iván Calderón owns
-- it and made the comparable grant on 2026-08-06 for the cloud service account.
-- Either ask for that role, or send him this file to run once.
--
-- Everything after table creation works on the write permission the account
-- already has: the weekly loader only inserts and deletes rows.
--
-- Safe to re-run: CREATE TABLE IF NOT EXISTS never touches existing rows.

CREATE TABLE IF NOT EXISTS `americanflat.finance.shipping_orders`
(
  -- Identity ---------------------------------------------------------------
  shipment_key STRING NOT NULL
    OPTIONS(description="SHA1 of warehouse|order_number|po_number|tracking. Stable across reloads, so re-running a week replaces rows instead of duplicating them."),

  -- When -------------------------------------------------------------------
  ship_date DATE
    OPTIONS(description="Date the 3PL shipped the package. NULL only when the source report had an unparseable date."),
  week_start DATE
    OPTIONS(description="Monday of the ship week. The grouping key for every weekly number on the dashboard."),
  week_label STRING
    OPTIONS(description="ISO week label of ship_date, e.g. 2026-W24."),

  -- Who --------------------------------------------------------------------
  marketplace STRING
    OPTIONS(description="Normalized marketplace: Target, Michaels, Shopify or Macy's. Only these four are loaded — they are the channels where we cover the shipping."),
  marketplace_raw STRING
    OPTIONS(description="The raw code from the source report (NJ/Fontana Batch#, SC Division), kept so a mapping miss is diagnosable."),
  warehouse STRING
    OPTIONS(description="Fontana, New Jersey or South Carolina."),

  -- What -------------------------------------------------------------------
  order_number STRING,
  po_number STRING,
  tracking STRING
    OPTIONS(description="Carrier tracking number where the 3PL reports one (SC), otherwise the Bill of Lading (NJ/Fontana)."),
  consignee STRING,
  carrier STRING
    OPTIONS(description="Carrier as reported by the 3PL, e.g. FEDEX GROUND, USPS."),
  units INT64
    OPTIONS(description="Units in this package. Zero on additional packages of a multi-package order (see is_additional_package) so unit totals never double-count."),
  is_additional_package BOOL
    OPTIONS(description="TRUE when this row is the 2nd+ package of an order, matched to the invoice by PO reference rather than by its own tracking. Carries cost but no units."),

  -- Cost -------------------------------------------------------------------
  cost_status STRING
    OPTIONS(description="'matched' when an invoice line was found for this shipment, 'unmatched' when the shipment shipped but no FedEx/Stamps charge could be tied to it yet."),
  carrier_source STRING
    OPTIONS(description="Which invoice paid for it: FedEx or Stamps.com. NULL when unmatched."),
  shipping_cost NUMERIC
    OPTIONS(description="Net invoiced charge for this package, in USD. NULL when unmatched."),
  cost_per_unit NUMERIC
    OPTIONS(description="shipping_cost / units for this row. Convenience only — always recompute blended CPU as SUM(cost)/SUM(units), never as an average of this column."),
  billed_weight NUMERIC
    OPTIONS(description="Rated (dim) weight from FedEx, or the Stamps.com weight."),
  match_method STRING
    OPTIONS(description="How the invoice line was tied to the order, e.g. tracking->FedEx, PO->FedEx ref, FedEx ref3->PO (multi-pkg)."),

  -- Provenance -------------------------------------------------------------
  source_week STRING
    OPTIONS(description="Name of the weekly staging folder this row was loaded from, e.g. 2026-06-08_to_2026-06-15. Re-loading a folder deletes and replaces exactly its rows."),
  loaded_at TIMESTAMP
    OPTIONS(description="When the loader wrote this row.")
)
PARTITION BY ship_date
CLUSTER BY marketplace, warehouse, cost_status
OPTIONS(
  description="Shipped packages for the four marketplaces where Americanflat covers the freight (Target, Michaels, Shopify, Macy's), with the FedEx/Stamps.com charge matched onto each one. Loaded weekly by scripts/load_shipping_orders_to_bq.py from the same 3PL and carrier files the Cost Per SKU report reads. Powers the Cost Per SKU shipping artifact. Grain: one package. Unmatched shipments are kept with a NULL cost so unit counts stay complete."
);
