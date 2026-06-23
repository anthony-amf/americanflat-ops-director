-- Views for Invoice Audit System

-- View: rate_card_snapshot
-- Returns the effective rate for a given invoice date
CREATE OR REPLACE VIEW rate_card_snapshot AS
SELECT
  warehouse_location,
  canonical_charge_code,
  effective_date,
  end_date,
  unit_price,
  currency,
  notes
FROM rate_card
WHERE end_date IS NULL OR end_date >= CURRENT_DATE()
ORDER BY warehouse_location, canonical_charge_code, effective_date DESC;

-- View: discrepancies (main audit output)
-- Compares billed amounts to expected rates
-- Requires parameters: tolerance_threshold (e.g., 5.00 for ±$5)
CREATE OR REPLACE VIEW discrepancies AS
WITH rate_lookup AS (
  SELECT
    il.invoice_number,
    il.invoice_date,
    il.invoice_type,
    il.warehouse_location,
    il.carrier,
    il.canonical_charge_code,
    il.quantity AS billed_quantity,
    il.unit_price AS billed_unit_price,
    il.billed_amount,
    COALESCE(rc.unit_price, 0) AS expected_unit_price,
    COALESCE(rc.unit_price * il.quantity, 0) AS expected_amount,
    rc.currency,
    il.currency AS invoice_currency
  FROM invoice_line_items il
  LEFT JOIN (
    SELECT
      warehouse_location,
      canonical_charge_code,
      effective_date,
      unit_price,
      currency
    FROM rate_card
    WHERE end_date IS NULL OR end_date >= CURRENT_DATE()
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY warehouse_location, canonical_charge_code
      ORDER BY effective_date DESC
    ) = 1
  ) rc
  ON il.warehouse_location = rc.warehouse_location
    AND il.canonical_charge_code = rc.canonical_charge_code
)
SELECT
  invoice_number,
  invoice_date,
  invoice_type,
  warehouse_location,
  carrier,
  canonical_charge_code,
  billed_quantity,
  billed_unit_price,
  billed_amount,
  expected_unit_price,
  expected_amount,
  ROUND(billed_amount - expected_amount, 2) AS delta,
  CASE
    WHEN expected_amount != 0 THEN ROUND((billed_amount - expected_amount) / expected_amount * 100, 2)
    ELSE NULL
  END AS delta_percent,
  CASE
    WHEN ABS(billed_amount - expected_amount) > 5.00 THEN TRUE
    ELSE FALSE
  END AS flagged,
  5.00 AS tolerance_threshold,
  CURRENT_TIMESTAMP() AS created_at
FROM rate_lookup
ORDER BY invoice_number, canonical_charge_code;

-- View: invoice_summary
-- Summary by invoice for quick review
CREATE OR REPLACE VIEW invoice_summary AS
SELECT
  invoice_number,
  invoice_date,
  invoice_type,
  warehouse_location,
  carrier,
  COUNT(DISTINCT canonical_charge_code) AS unique_charges,
  COUNT(*) AS line_item_count,
  SUM(billed_amount) AS total_billed,
  SUM(expected_amount) AS total_expected,
  ROUND(SUM(billed_amount) - SUM(expected_amount), 2) AS total_delta,
  COUNTIF(flagged = TRUE) AS flagged_count,
  MAX(created_at) AS last_updated
FROM discrepancies
GROUP BY invoice_number, invoice_date, invoice_type, warehouse_location, carrier
ORDER BY invoice_date DESC, invoice_number;

-- View: flagged_discrepancies
-- Only rows where delta exceeds tolerance
CREATE OR REPLACE VIEW flagged_discrepancies AS
SELECT
  invoice_number,
  invoice_date,
  invoice_type,
  warehouse_location,
  carrier,
  canonical_charge_code,
  billed_quantity,
  billed_unit_price,
  billed_amount,
  expected_unit_price,
  expected_amount,
  delta,
  delta_percent,
  tolerance_threshold
FROM discrepancies
WHERE flagged = TRUE
ORDER BY invoice_date DESC, ABS(delta) DESC;
