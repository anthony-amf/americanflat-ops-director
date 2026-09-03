-- Weekly load for americanflat.finance.stamps_shipping_costs
--
-- Written 2026-09-03 for the plan to upload the previous week's shipping costs
-- each week. The table is currently clean — 20,528 rows, 20,528 distinct
-- tracking numbers — and the point of this file is to keep it that way.
--
-- APPEND IS THE WRONG VERB HERE, for two independent reasons.
--
-- 1. The exports overlap. A weekly Stamps.com export re-states shipments the
--    previous one already covered, so appending stacks the same charge two or
--    three times. This exact thing happened in the Drive sheets these files come
--    from: 4,266 of the FedEx sheet's 7,963 rows were repeats, and summing them
--    raw put Target's cost per unit at $35.92 against a real ~$13. In a
--    spreadsheet that is recoverable. In a table other people query, every
--    downstream number is quietly wrong and nothing looks broken.
--
-- 2. Stamps re-rates after the fact. A label already loaded can pick up an
--    adjusted_amount days later — that is what the $23,147 of adjustment in the
--    table is. A load that skips tracking numbers it has already seen freezes
--    the original quote and loses the re-rate, which is the audit signal.
--
-- So: MERGE on the normalized tracking number, insert what is new, and update
-- what has changed.
--
-- Run: load the week's export to the staging table, then this.

-- Step 1 — stage the raw export. Replace the whole staging table each week;
-- it holds one export and nothing depends on its history.
--   bq load --replace --source_format=CSV --autodetect \
--     americanflat:finance._stage_stamps_weekly ~/Downloads/PrintHistory_*.csv

-- Step 2 — merge it in.
MERGE `americanflat.finance.stamps_shipping_costs` AS t
USING (
  SELECT
    -- Normalizing here is not optional. Stamps writes USPS tracking numbers
    -- Excel-escaped (="0004010549…") and UPS numbers bare, in the same column.
    -- Every USPS row in the table today carries those characters, which is why
    -- a raw join to the 945 feed matches 98.3% of UPS shipments and 0.0% of
    -- USPS ones — 4,114 shipments, about $47,000, priced at nothing with
    -- nothing visibly wrong. Strip it once, at load, so no consumer has to know.
    REGEXP_REPLACE(UPPER(CAST(tracking_number AS STRING)), r'[^A-Z0-9]', '') AS tracking_number,
    ship_date, carrier, service, weight_lb,
    -- amount_paid is already final: quoted + adjusted = paid. Do not add the
    -- adjustment on top of it.
    amount_paid, adjusted_amount,
    order_id, reference_1, cost_code, to_name, to_zip,
    source_file, CURRENT_TIMESTAMP() AS ingested_at, SESSION_USER() AS ingested_by
  FROM `americanflat.finance._stage_stamps_weekly`
  WHERE tracking_number IS NOT NULL
    AND CAST(tracking_number AS STRING) != ''
  -- One row per tracking number even within a single export, keeping the row
  -- that states the largest amount — that is the one carrying any re-rate.
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY REGEXP_REPLACE(UPPER(CAST(tracking_number AS STRING)), r'[^A-Z0-9]', '')
    ORDER BY amount_paid DESC
  ) = 1
) AS s
ON t.tracking_number = s.tracking_number

-- A charge that moved is a re-rate, not a duplicate: take the new figures.
WHEN MATCHED AND (
     t.amount_paid      IS DISTINCT FROM s.amount_paid
  OR t.adjusted_amount  IS DISTINCT FROM s.adjusted_amount
) THEN UPDATE SET
  amount_paid     = s.amount_paid,
  adjusted_amount = s.adjusted_amount,
  service         = s.service,
  weight_lb       = s.weight_lb,
  source_file     = s.source_file,
  ingested_at     = s.ingested_at,
  ingested_by     = s.ingested_by

WHEN NOT MATCHED THEN INSERT ROW;

-- Step 3 — confirm the invariant still holds. These must be equal. If they ever
-- diverge, the merge key stopped doing its job and every total built on this
-- table is inflated until it is fixed.
SELECT COUNT(*) AS rows_total,
       COUNT(DISTINCT tracking_number) AS distinct_tracking,
       COUNTIF(REGEXP_CONTAINS(tracking_number, r'[^A-Z0-9]')) AS must_be_zero,
       MIN(ship_date) AS first_ship,
       MAX(ship_date) AS last_ship
FROM `americanflat.finance.stamps_shipping_costs`;

-- One backfill, once, to strip the escaping from the 5,420 USPS rows already
-- loaded. Safe to re-run; it is a no-op after the first time.
--
-- UPDATE `americanflat.finance.stamps_shipping_costs`
-- SET tracking_number = REGEXP_REPLACE(UPPER(tracking_number), r'[^A-Z0-9]', '')
-- WHERE REGEXP_CONTAINS(tracking_number, r'[^A-Z0-9]');
