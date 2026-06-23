-- Load extracted invoice line items into BigQuery
-- This script handles idempotent inserts (dedupes on invoice_number + line_hash)
-- Run after extraction/extract_invoice.py completes

-- Example usage:
-- bq load --source_format=NEWLINE_DELIMITED_JSON invoice_line_items extracted_invoice.json

-- Idempotent merge: skip rows that already exist
MERGE INTO invoice_line_items AS target
USING (
  SELECT
    invoice_number,
    invoice_date,
    invoice_type,
    carrier,
    warehouse_location,
    canonical_charge_code,
    charge_description,
    quantity,
    unit_price,
    billed_amount,
    currency,
    hst_amount,
    supporting_doc_url,
    line_hash,
    CURRENT_TIMESTAMP() AS created_at
  FROM `{{ PROJECT_ID }}.{{ DATASET }}.invoice_line_items_staging`
) AS source
ON target.invoice_number = source.invoice_number
  AND target.line_hash = source.line_hash
WHEN NOT MATCHED THEN
  INSERT (
    invoice_number,
    invoice_date,
    invoice_type,
    carrier,
    warehouse_location,
    canonical_charge_code,
    charge_description,
    quantity,
    unit_price,
    billed_amount,
    currency,
    hst_amount,
    supporting_doc_url,
    line_hash,
    created_at
  )
  VALUES (
    source.invoice_number,
    source.invoice_date,
    source.invoice_type,
    source.carrier,
    source.warehouse_location,
    source.canonical_charge_code,
    source.charge_description,
    source.quantity,
    source.unit_price,
    source.billed_amount,
    source.currency,
    source.hst_amount,
    source.supporting_doc_url,
    source.line_hash,
    source.created_at
  );
