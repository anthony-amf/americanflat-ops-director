-- Create yusen_invoice_line_items table
-- Stores order numbers and line-item details extracted from supporting Excel docs

CREATE TABLE IF NOT EXISTS finance.yusen_invoice_line_items (
  invoice_number STRING NOT NULL,
  line_item_id INT64 NOT NULL,
  order_number STRING,                -- From Excel: order/tracking number
  quantity INT64,                     -- Units shipped
  service_type STRING,                -- Small Parcel, LTL, Storage, Admin, VAS
  amount NUMERIC,                     -- Line item charge
  warehouse_location STRING,          -- Fontana, New Jersey, South Carolina
  notes STRING,                       -- Any special notes from Excel
  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),

  PRIMARY KEY (invoice_number, line_item_id) NOT ENFORCED
)
PARTITION BY DATE(ingested_at)
CLUSTER BY invoice_number, service_type;

-- Index for fast lookups by order number (for Stedi validation)
CREATE INDEX IF NOT EXISTS idx_order_number ON finance.yusen_invoice_line_items (order_number);
