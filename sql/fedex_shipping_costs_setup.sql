-- americanflat.finance.fedex_shipping_costs
--
-- The FedEx counterpart to finance.stamps_shipping_costs, written 2026-09-10.
-- Same idea, one structural difference that is easy to get wrong.
--
-- ONE ROW PER INVOICE LINE, NOT PER SHIPMENT.
--
-- Stamps.com states a final figure per label: quoted + adjusted = paid, so one
-- row per tracking number is right and merging on tracking is right.
--
-- FedEx does not. It bills a shipment, then bills it again on a later invoice
-- when it re-rates — a dimensional-weight correction, an address surcharge —
-- and both lines are real money we paid. In the current export, tracking
-- 476147675207 carries $26.67 on invoice 2026-02-02 and $13.09 on invoice
-- 2026-02-16. What that shipment cost is $39.76, the sum.
--
-- So the shipment's cost is SUM(net_charge) over its lines, and the merge key
-- has to identify the charge, not the shipment: (tracking, invoice_date,
-- net_charge). Key it on tracking alone and every re-rate is discarded.
--
-- Measured on the current export, that loss is small: 9 of 3,688 shipments are
-- re-rated, $151.33 of $100,883.90, 0.2%. The reason to key it properly anyway
-- is not the 0.2% — it is that the correct key costs nothing, the wrong one
-- fails silently, and dimensional-weight re-rates are the thing most likely to
-- grow if large-format frames keep moving on FedEx. A 0.2% error you can see is
-- fine; a 0.2% error that becomes 5% without changing shape is not.
--
-- What still has to be de-duplicated is the export overlap. Weekly exports
-- re-state what the last one covered: of 7,965 rows in the current sheet only
-- 3,689 tracking numbers are distinct, and of 400 multi-line tracking numbers
-- sampled, 398 were the same charge exported twice and 2 were genuine re-rates.
-- The three-part key separates them without judgement — an identical line
-- collapses, a different amount or invoice date is kept.
--
-- Unlike Stamps, FedEx tracking numbers arrive clean: no Excel escaping in any
-- of the 7,965 rows. The normalization below is belt-and-braces, and keeps both
-- tables' tracking columns in the same shape so they can be unioned.

-- Step 1 — create the table. Once.
CREATE TABLE IF NOT EXISTS `americanflat.finance.fedex_shipping_costs` (
  tracking_number  STRING    NOT NULL OPTIONS(description="Letters and digits only, to match shipment_reconciliation.cartonTracking normalized the same way"),
  invoice_date     DATE               OPTIONS(description="Date of the invoice this line appeared on. Part of the charge's identity: a re-rate is the same tracking on a later invoice"),
  ship_date        DATE               OPTIONS(description="When the shipment moved, not when it was billed. FedEx bills weeks behind"),
  net_charge       NUMERIC            OPTIONS(description="What this line charged. A shipment's cost is the SUM of its lines, never one of them"),
  service_type     STRING,
  package_weight   NUMERIC,
  zone             STRING,
  source_file      STRING             OPTIONS(description="Which export this line came from, for tracing a bad load back"),
  ingested_at      TIMESTAMP,
  ingested_by      STRING
)
PARTITION BY invoice_date
CLUSTER BY tracking_number
OPTIONS(description="FedEx invoice lines, one row per line. A shipment's cost is SUM(net_charge) grouped by tracking_number — FedEx re-rates on later invoices and both lines are real. Loaded weekly by sql/fedex_shipping_costs_setup.sql. Sibling of finance.stamps_shipping_costs, which is one row per shipment because Stamps states a final figure.");

-- Step 2 — stage the week's export. Replace the staging table each time;
-- nothing depends on its history.
--   bq load --replace --source_format=CSV --autodetect \
--     americanflat:finance._stage_fedex_weekly ~/Downloads/fedex_invoices_*.csv
--
-- The export's headers are: Invoice Date, Shipment Date, Tracking Number,
-- Service Type, Package Weight, Zone, Net Charge, Source File. Dates arrive as
-- 20260202, so PARSE_DATE rather than a cast.

-- Step 3 — merge.
-- >>> EXECUTABLE: the statements between these markers are the load.
-- Substitute @@STAGE@@ for the staging table holding that run's export.
-- (The markers were read by scripts/load_shipping_costs_to_bq.py, retired
-- 2026-09-10; they are kept because they still delimit what is runnable
-- from the reasoning around it.) >>>
MERGE `americanflat.finance.fedex_shipping_costs` AS t
USING (
  SELECT
    REGEXP_REPLACE(UPPER(CAST(Tracking_Number AS STRING)), r'[^A-Z0-9]', '') AS tracking_number,
    PARSE_DATE('%Y%m%d', CAST(Invoice_Date AS STRING))    AS invoice_date,
    SAFE.PARSE_DATE('%Y%m%d', CAST(Shipment_Date AS STRING)) AS ship_date,
    CAST(Net_Charge AS NUMERIC)                           AS net_charge,
    Service_Type                                          AS service_type,
    SAFE_CAST(Package_Weight AS NUMERIC)                  AS package_weight,
    CAST(Zone AS STRING)                                  AS zone,
    Source_File                                           AS source_file,
    CURRENT_TIMESTAMP()                                   AS ingested_at,
    SESSION_USER()                                        AS ingested_by
  FROM `@@STAGE@@`
  WHERE Tracking_Number IS NOT NULL
    AND CAST(Tracking_Number AS STRING) != ''
    AND Net_Charge IS NOT NULL
  -- Collapse identical lines inside one export, keep genuinely different ones.
  GROUP BY tracking_number, invoice_date, ship_date, net_charge, service_type,
           package_weight, zone, source_file, ingested_at, ingested_by
) AS s
ON  t.tracking_number = s.tracking_number
AND t.invoice_date    = s.invoice_date
AND t.net_charge      = s.net_charge

-- Nothing to update: the three keyed columns *are* the charge. A line whose
-- amount changed is a different charge and inserts as its own row, which is
-- what a re-rate is.
WHEN NOT MATCHED THEN INSERT ROW;

-- Step 4 — checks. Unlike the Stamps table, rows > distinct tracking is
-- CORRECT here; that gap is the re-rates. What must hold:
SELECT
  COUNT(*)                                                        AS lines_total,
  COUNT(DISTINCT tracking_number)                                 AS shipments,
  COUNT(*) - COUNT(DISTINCT FORMAT('%s|%t|%t', tracking_number, invoice_date, net_charge))
                                                                  AS must_be_zero_duplicate_lines,
  COUNTIF(REGEXP_CONTAINS(tracking_number, r'[^A-Z0-9]'))         AS must_be_zero_escaped,
  ROUND(SUM(net_charge), 2)                                       AS total_charged,
  CAST(MIN(ship_date) AS STRING)                                  AS first_ship,
  CAST(MAX(ship_date) AS STRING)                                  AS last_ship,
  CAST(MAX(invoice_date) AS STRING)                               AS last_invoice
FROM `americanflat.finance.fedex_shipping_costs`;
-- <<< END EXECUTABLE <<<


-- What a consumer should join to. Per-shipment, with the re-rate split out —
-- the same shape the portal builds in memory today.
--
-- CREATE OR REPLACE VIEW `americanflat.finance.fedex_shipment_cost` AS
-- SELECT
--   tracking_number,
--   SUM(net_charge)                                       AS cost,
--   MIN(ship_date)                                        AS ship_date,
--   ANY_VALUE(service_type HAVING MIN invoice_date)       AS service_type,
--   -- The first invoice is the base charge; anything billed later is a re-rate.
--   SUM(IF(invoice_date = first_inv, net_charge, 0))      AS base_cost,
--   SUM(IF(invoice_date > first_inv, net_charge, 0))      AS adjustment_cost,
--   COUNT(*)                                              AS invoice_lines
-- FROM (
--   SELECT *, MIN(invoice_date) OVER (PARTITION BY tracking_number) AS first_inv
--   FROM `americanflat.finance.fedex_shipping_costs`
-- )
-- GROUP BY tracking_number;
