-- BigQuery DDL for Invoice Audit System
-- Dataset: invoice_audit (create if it doesn't exist)
-- This schema supports 5 invoice types: SMALL_PARCEL_LTL, VAS, STORAGE, ADMIN, CANADA

CREATE TABLE IF NOT EXISTS invoice_line_items (
  invoice_number STRING NOT NULL,
  invoice_date DATE NOT NULL,
  invoice_type STRING NOT NULL, -- SMALL_PARCEL_LTL, VAS, STORAGE, ADMIN, CANADA
  carrier STRING, -- Yusen, Taylored, etc.
  warehouse_location STRING NOT NULL, -- Fontana, New Jersey, South Carolina, Brampton
  canonical_charge_code STRING NOT NULL, -- normalized code (e.g., SMALL_PARCEL_ECOM_ORDER)
  charge_description STRING, -- carrier's original language
  quantity DECIMAL64,
  unit_price DECIMAL64,
  billed_amount DECIMAL64,
  currency STRING, -- USD, CAD
  hst_amount DECIMAL64, -- Canada invoices only
  supporting_doc_url STRING, -- link to Excel/supporting documentation
  line_hash STRING NOT NULL, -- FARM_FINGERPRINT for idempotency
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),

  PRIMARY KEY (invoice_number, line_hash) NOT ENFORCED
)
PARTITION BY invoice_date
CLUSTER BY warehouse_location, canonical_charge_code;

CREATE TABLE IF NOT EXISTS rate_card (
  warehouse_location STRING NOT NULL,
  canonical_charge_code STRING NOT NULL,
  effective_date DATE NOT NULL,
  end_date DATE, -- NULL = current rate
  unit_price DECIMAL64 NOT NULL,
  currency STRING NOT NULL, -- USD, CAD
  notes STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),

  PRIMARY KEY (warehouse_location, canonical_charge_code, effective_date) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS charge_code_map (
  carrier STRING NOT NULL,
  invoice_type STRING NOT NULL,
  carrier_charge_description STRING NOT NULL,
  warehouse_location STRING NOT NULL,
  canonical_charge_code STRING NOT NULL,
  notes STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),

  PRIMARY KEY (carrier, invoice_type, carrier_charge_description, warehouse_location) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS discrepancies (
  invoice_number STRING NOT NULL,
  invoice_date DATE NOT NULL,
  invoice_type STRING NOT NULL,
  warehouse_location STRING NOT NULL,
  carrier STRING,
  canonical_charge_code STRING NOT NULL,
  billed_quantity DECIMAL64,
  billed_unit_price DECIMAL64,
  billed_amount DECIMAL64,
  expected_unit_price DECIMAL64,
  expected_amount DECIMAL64,
  delta DECIMAL64, -- billed - expected
  delta_percent FLOAT64,
  flagged BOOL,
  tolerance_threshold DECIMAL64,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),

  PRIMARY KEY (invoice_number, canonical_charge_code) NOT ENFORCED
)
PARTITION BY invoice_date
CLUSTER BY warehouse_location;

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_invoice_lines_invoice_number ON invoice_line_items (invoice_number);
CREATE INDEX IF NOT EXISTS idx_rate_card_lookup ON rate_card (warehouse_location, canonical_charge_code, effective_date);
CREATE INDEX IF NOT EXISTS idx_charge_map_lookup ON charge_code_map (carrier, invoice_type, carrier_charge_description);
