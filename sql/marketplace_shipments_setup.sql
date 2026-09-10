-- Marketplace shipment ledger — one durable row per marketplace order.
--
-- Why this table exists at all, when the source feeds are already in BigQuery:
-- Target Plus redacts consumer PII about 45 days after the order (the name turns
-- into the literal "Customer Name" and the street into "1234 Redacted St"), and
-- the acenda feed re-syncs those rows in place. So the marketplace feeds are a
-- *current* picture, not a historical one — a name we can read today is gone from
-- them next month. This table captures each order once and never lets a later
-- sync blank out a field it already holds.
--
-- Run once, from the Mac (gcloud ADC). The cloud sessions' BigQuery access is
-- read-only, and neither Anthony's account nor the cloud service account has
-- tables.create on `finance` — if CREATE fails here, Ivan Calderon (dataset
-- owner) has to run it or grant the permission.

CREATE TABLE IF NOT EXISTS `americanflat.marketplaces.marketplace_shipments` (
  marketplace   STRING  NOT NULL OPTIONS(description="Target | Macy's | Michaels | Shopify"),
  order_ref     STRING  NOT NULL OPTIONS(description="Stable per-marketplace key: acenda orderId, Mirakl orderId, ShipStation orderId"),
  order_number  STRING  OPTIONS(description="Customer-facing order / PO number"),
  customer      STRING  OPTIONS(description="Ship-to name; blank where the marketplace redacts it"),
  city          STRING,
  state         STRING,
  order_date    DATE,
  ship_date     DATE,
  units         INT64,
  skus          INT64,
  carrier       STRING  OPTIONS(description="FedEx | UPS | USPS | DHL, normalized"),
  tracking      STRING,
  status        STRING  OPTIONS(description="Shipped | Shipping | Open | On hold | Cancelled"),
  order_value   NUMERIC OPTIONS(description="Sum of the order's line totals — what the customer paid"),
  ship_cost     NUMERIC OPTIONS(description="What the carrier billed us for this shipment, matched from parcel_charges by tracking number. NULL = no invoice matched yet, which is not the same as zero"),
  cost_source   STRING  OPTIONS(description="Carrier whose invoice the ship_cost came from"),
  items         ARRAY<STRUCT<
                  sku        STRING,
                  product    STRING,
                  qty        INT64,
                  unit_price NUMERIC,
                  line_total NUMERIC
                >> OPTIONS(description="Order lines. A line with no SKU is an adjustment (a Shopify discount code), counted in order_value but not in units."),
  first_seen_at DATE    OPTIONS(description="First refresh that captured this order"),
  loaded_at     DATE    OPTIONS(description="Most recent refresh that touched the row")
)
PARTITION BY order_date
CLUSTER BY marketplace, order_number
OPTIONS(description="Per-order shipment ledger behind the Marketplace Shipments portal. Loaded by refresh_marketplace_shipments.py in americanflat-ops-director.");


-- ---------------------------------------------------------------------------
-- Per-refresh load. Stage the NDJSON, then MERGE.
--
--   python3 refresh_marketplace_shipments.py --days 30 --ndjson /tmp/mps.ndjson
--   bq load --source_format=NEWLINE_DELIMITED_JSON --autodetect \
--       americanflat:marketplaces._stage_marketplace_shipments /tmp/mps.ndjson
--   bq query --use_legacy_sql=false --max_rows=1 < sql/marketplace_shipments_setup.sql
--
-- (Run only the MERGE below on a refresh — the CREATE above is a one-time step
-- and is a no-op afterwards.)
-- ---------------------------------------------------------------------------

MERGE `americanflat.marketplaces.marketplace_shipments` T
USING (
  -- The feeds are line-grain upstream but the generator already collapses to one
  -- row per order; de-dupe defensively so a re-run of the same file can't fan out.
  SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY marketplace, order_ref
                                 ORDER BY loaded_at DESC) AS rn
    FROM `americanflat.marketplaces._stage_marketplace_shipments`
  ) WHERE rn = 1
) S
ON T.marketplace = S.marketplace AND T.order_ref = S.order_ref
WHEN MATCHED THEN UPDATE SET
  -- COALESCE(S, T) everywhere: a later sync may arrive with the customer name
  -- redacted or the tracking dropped, and losing a fact we already recorded is
  -- the one thing this table exists to prevent. Real changes still land, because
  -- a populated new value always wins over the stored one.
  order_number = COALESCE(S.order_number, T.order_number),
  customer     = COALESCE(S.customer,     T.customer),
  city         = COALESCE(S.city,         T.city),
  state        = COALESCE(S.state,        T.state),
  order_date   = COALESCE(S.order_date,   T.order_date),
  ship_date    = COALESCE(S.ship_date,    T.ship_date),
  units        = COALESCE(S.units,        T.units),
  skus         = COALESCE(S.skus,         T.skus),
  carrier      = COALESCE(S.carrier,      T.carrier),
  tracking     = COALESCE(S.tracking,     T.tracking),
  status       = COALESCE(S.status,       T.status),
  order_value  = COALESCE(S.order_value,  T.order_value),
  ship_cost    = COALESCE(S.ship_cost,    T.ship_cost),
  cost_source  = COALESCE(S.cost_source,  T.cost_source),
  -- Same rule for the line array: an empty one is missing data, not a cleared order.
  items        = IF(ARRAY_LENGTH(S.items) > 0, S.items, T.items),
  loaded_at    = S.loaded_at
WHEN NOT MATCHED THEN INSERT
  (marketplace, order_ref, order_number, customer, city, state, order_date,
   ship_date, units, skus, carrier, tracking, status, order_value, ship_cost,
   cost_source, items, first_seen_at, loaded_at)
VALUES
  (S.marketplace, S.order_ref, S.order_number, S.customer, S.city, S.state,
   S.order_date, S.ship_date, S.units, S.skus, S.carrier, S.tracking, S.status,
   S.order_value, S.ship_cost, S.cost_source, S.items, S.loaded_at, S.loaded_at);


-- ---------------------------------------------------------------------------
-- Parcel charges — what FedEx and Stamps.com actually billed, by tracking number.
--
-- This is the piece Americanflat has never had in BigQuery. Today it lives only
-- in the two consolidated Drive sheets and in the weekly downloads that feed the
-- shipping cost report, which is why the portal's Ship cost column stops where
-- those sheets stop. Load this table weekly from the same files and the column
-- keeps up on its own.
--
-- Grain: one row per charge line. A shipment can be billed more than once (a
-- re-rate, a residential surcharge), so the portal SUMs by tracking number.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `americanflat.marketplaces.parcel_charges` (
  tracking    STRING  NOT NULL OPTIONS(description="Tracking number, spaces and dashes stripped, uppercased"),
  amount      NUMERIC OPTIONS(description="Net charge on this line"),
  carrier     STRING  OPTIONS(description="FedEx | UPS | USPS | DHL"),
  charge_date DATE    OPTIONS(description="Invoice date (FedEx) or ship date (Stamps.com)"),
  loaded_at   DATE
)
CLUSTER BY tracking
OPTIONS(description="Parcel invoice lines from FedEx Billing Online and Stamps.com print history. Loaded by refresh_marketplace_shipments.py --costs-ndjson.");

-- Weekly load, from the Mac, using the same five files the shipping cost report
-- already downloads:
--
--   python3 refresh_marketplace_shipments.py --days 30 \
--       --costs ~/Downloads/week-of-2026-08-25 \
--       --costs-ndjson /tmp/charges.ndjson
--   bq load --source_format=NEWLINE_DELIMITED_JSON --autodetect \
--       americanflat:marketplaces._stage_parcel_charges /tmp/charges.ndjson
--
-- Then de-duplicate into the real table. The builder already drops repeated
-- lines within one run; this guards against the same week being loaded twice.
MERGE `americanflat.marketplaces.parcel_charges` T
USING (
  SELECT tracking, amount, charge_date, ANY_VALUE(carrier) AS carrier,
         MIN(loaded_at) AS loaded_at
  FROM `americanflat.marketplaces._stage_parcel_charges`
  GROUP BY tracking, amount, charge_date
) S
ON T.tracking = S.tracking AND T.amount = S.amount
   AND COALESCE(T.charge_date, DATE "1900-01-01") = COALESCE(S.charge_date, DATE "1900-01-01")
WHEN NOT MATCHED THEN INSERT (tracking, amount, carrier, charge_date, loaded_at)
VALUES (S.tracking, S.amount, S.carrier, S.charge_date, S.loaded_at);
