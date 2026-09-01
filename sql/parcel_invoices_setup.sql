-- Carrier invoices in BigQuery, joined to the 945 order-cost feed.
--
-- The rule Anthony asked for: when the carrier's invoice and the label's own
-- charge disagree, the invoice wins, because it is the actual bill. Otherwise
-- take the label charge already in the warehouse feed.
--
-- Two objects:
--   finance.parcel_invoices   raw invoice lines, keyed by TRACKING NUMBER
--   finance.shipment_cost     one row per order: the resolved cost + provenance
--
-- Why the invoice table is keyed by tracking and not by order: a FedEx or
-- Stamps.com invoice has no idea what an order is. It knows the tracking number.
-- The 945 feed is what carries both (orderNumber and cartonTracking), so it is
-- the bridge — invoice -> tracking -> 945 -> order. Nothing needs to guess.

CREATE TABLE IF NOT EXISTS `americanflat.finance.parcel_invoices` (
  tracking       STRING  NOT NULL OPTIONS(description="Tracking number, letters and digits only, uppercased. Stamps exports USPS numbers Excel-escaped as =\"9434...\" — strip to alphanumerics before loading or USPS silently never matches"),
  amount         NUMERIC OPTIONS(description="Net charge on this line. Negative for a credit"),
  carrier        STRING  OPTIONS(description="FedEx | UPS | USPS | DHL"),
  invoice_number STRING  OPTIONS(description="Carrier invoice number — what a dispute is filed against"),
  invoice_date   DATE,
  charge_class   STRING  OPTIONS(description="'base' = the freight quoted when the label was made. 'adjustment' = anything the carrier added afterwards. This split is what keeps a re-rate out of cost per unit without hiding it"),
  charge_type    STRING  OPTIONS(description="Why the carrier charged it: dimensional re-rate, residential surcharge, address correction, fuel, delivery area. The reason is what makes a charge actionable"),
  quoted_amount  NUMERIC OPTIONS(description="Price at label creation where the export states it. Stamps gives it directly (Quoted + Adjusted = Paid); FedEx does not, so the first charge on a tracking number is the base and later ones are adjustments"),
  service        STRING,
  weight_lb      NUMERIC,
  source_file    STRING  OPTIONS(description="Which export this line came from, so a wrong number is traceable"),
  loaded_at      DATE
)
PARTITION BY invoice_date
CLUSTER BY tracking
OPTIONS(description="Carrier invoice lines from FedEx Billing Online and Stamps.com print history. One row per charge line; a shipment can have several.");


-- ---------------------------------------------------------------------------
-- Loading. Stage, then MERGE — never plain INSERT.
--
-- A shipment is legitimately billed more than once (an original charge plus a
-- dimensional re-rate weeks later), so duplicates cannot be collapsed on
-- tracking alone. But the weekly exports overlap, so the same physical line
-- shows up in two or three files: 4,266 of the 7,963 rows in the consolidated
-- FedEx sheet are repeats. Summing those raw put Target's FedEx cost per unit at
-- $35.92 against a real ~$13. The identity of a line is
-- (tracking, invoice_date, amount, charge_type).
-- ---------------------------------------------------------------------------
MERGE `americanflat.finance.parcel_invoices` T
USING (
  SELECT tracking, invoice_date, amount, charge_type,
         ANY_VALUE(carrier) AS carrier, ANY_VALUE(invoice_number) AS invoice_number,
         ANY_VALUE(charge_class) AS charge_class, ANY_VALUE(quoted_amount) AS quoted_amount,
         ANY_VALUE(service) AS service, ANY_VALUE(weight_lb) AS weight_lb,
         ANY_VALUE(source_file) AS source_file, MIN(loaded_at) AS loaded_at
  FROM `americanflat.finance._stage_parcel_invoices`
  GROUP BY tracking, invoice_date, amount, charge_type
) S
ON  T.tracking = S.tracking
AND T.amount = S.amount
AND COALESCE(T.invoice_date, DATE "1900-01-01") = COALESCE(S.invoice_date, DATE "1900-01-01")
AND COALESCE(T.charge_type, "") = COALESCE(S.charge_type, "")
WHEN NOT MATCHED THEN INSERT
  (tracking, amount, carrier, invoice_number, invoice_date, charge_class, charge_type,
   quoted_amount, service, weight_lb, source_file, loaded_at)
VALUES
  (S.tracking, S.amount, S.carrier, S.invoice_number, S.invoice_date, S.charge_class,
   S.charge_type, S.quoted_amount, S.service, S.weight_lb, S.source_file, S.loaded_at);


-- ---------------------------------------------------------------------------
-- The resolved per-order cost. This is the one object anything downstream reads
-- — the shipments portal, the weekly cost report, any CPU question.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW `americanflat.finance.shipment_cost` AS
WITH invoice_per_tracking AS (
  -- Sum the lines: an original charge plus a later re-rate is what we actually paid.
  SELECT tracking,
         SUM(amount)                                              AS invoice_cost,
         -- Base and adjustment are carried separately all the way through, so a
         -- cost-per-unit figure can be read either all-in or on base freight
         -- alone without recomputing anything.
         SUM(IF(charge_class = 'adjustment', 0, amount))           AS base_cost,
         SUM(IF(charge_class = 'adjustment', amount, 0))           AS adjustment_cost,
         ANY_VALUE(carrier)                                        AS invoice_carrier,
         STRING_AGG(DISTINCT IF(charge_class = 'adjustment', charge_type, NULL)
                    ORDER BY IF(charge_class = 'adjustment', charge_type, NULL))
                                                                   AS adjustment_reasons,
         MAX(invoice_date)                                         AS last_invoice_date,
         COUNT(*)                                                  AS invoice_lines
  FROM `americanflat.finance.parcel_invoices`
  GROUP BY tracking
),
package AS (
  -- The 945 feed is line-grain (one row per SKU per carton), so collapse to the
  -- package first or the freight charge gets counted once per line.
  SELECT
    orderNumber,
    ANY_VALUE(channel)                  AS channel,
    cartonTracking                      AS tracking,
    MIN(shipDate)                       AS ship_date,
    ANY_VALUE(carrierScac)              AS scac,
    ANY_VALUE(warehouse)                AS warehouse,
    MAX(freightChargeShipment)          AS label_cost,
    SUM(quantityShipped)                AS units
  FROM `americanflat.finance.shipment_reconciliation`
  WHERE orderNumber IS NOT NULL AND orderNumber != ''
  GROUP BY orderNumber, cartonTracking
),
resolved AS (
  SELECT
    p.*,
    i.invoice_cost,
    i.base_cost,
    i.adjustment_cost,
    i.adjustment_reasons,
    i.invoice_carrier,
    i.last_invoice_date,
    i.invoice_lines,
    -- The rule. An invoice for this tracking number wins outright; with no
    -- invoice yet, fall back to what the label charged.
    COALESCE(i.invoice_cost, p.label_cost) AS cost,
    CASE WHEN i.invoice_cost IS NOT NULL THEN 'invoice'
         WHEN p.label_cost   IS NOT NULL THEN 'label'
         ELSE 'none' END                   AS cost_source
  FROM package p
  LEFT JOIN invoice_per_tracking i ON i.tracking = p.tracking
)
SELECT
  orderNumber                                          AS order_number,
  ANY_VALUE(channel)                                   AS channel,
  MIN(ship_date)                                       AS ship_date,
  STRING_AGG(DISTINCT scac ORDER BY scac)              AS carriers,
  STRING_AGG(DISTINCT warehouse ORDER BY warehouse)    AS warehouses,
  COUNT(*)                                             AS packages,
  SUM(units)                                           AS units,
  -- An order can ship in several cartons under different tracking numbers, so
  -- the order's cost is the sum across its packages, not one of them.
  SUM(cost)                                            AS cost,
  SUM(label_cost)                                      AS label_cost,
  SUM(invoice_cost)                                    AS invoice_cost,
  -- The cost-per-unit pair. base_cost answers "what does it cost to ship a
  -- unit"; cost answers "what did we pay". Report whichever the question wants,
  -- but never quietly fold the second into the first.
  SUM(COALESCE(base_cost, label_cost))                 AS base_cost,
  SUM(COALESCE(adjustment_cost, 0))                    AS adjustment_cost,
  STRING_AGG(DISTINCT adjustment_reasons)              AS adjustment_reasons,
  -- What the carrier billed above (or below) the label. This is the audit
  -- number: a positive variance is a re-rate or surcharge we absorbed.
  SUM(invoice_cost) - SUM(IF(invoice_cost IS NULL, NULL, label_cost)) AS invoice_variance,
  CASE WHEN COUNTIF(cost_source = 'invoice') = COUNT(*) THEN 'invoice'
       WHEN COUNTIF(cost_source = 'invoice') > 0        THEN 'mixed'
       WHEN COUNTIF(cost_source = 'label')   > 0        THEN 'label'
       ELSE 'none' END                                 AS cost_source,
  MAX(last_invoice_date)                               AS last_invoice_date
FROM resolved
GROUP BY orderNumber;


-- ---------------------------------------------------------------------------
-- The audit view. Every shipment where the carrier billed something other than
-- the label, newest first — what was quoted, what was billed, the gap, and why.
--
-- This is the question the cost column can't answer once it resolves to one
-- number: not "what did shipping cost" but "what is the carrier adding after
-- the fact, and is any of it disputable".
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW `americanflat.finance.shipment_cost_variance` AS
SELECT
  order_number,
  channel,
  ship_date,
  carriers,
  packages,
  units,
  label_cost,
  invoice_cost,
  invoice_variance,
  adjustment_cost,
  adjustment_reasons,
  SAFE_DIVIDE(invoice_variance, NULLIF(label_cost, 0)) AS variance_pct,
  last_invoice_date
FROM `americanflat.finance.shipment_cost`
WHERE invoice_cost IS NOT NULL
  AND label_cost IS NOT NULL
  AND ABS(invoice_variance) > 0.005
ORDER BY ship_date DESC, ABS(invoice_variance) DESC;
