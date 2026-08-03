# BigQuery — `americanflat.finance.yusen_invoices`

The invoice header table. One row per invoice. Populated by the
`skill-invoice-to-bigquery` extraction skill (PDF + supporting Excel → BigQuery).

## Columns

| Column            | Type      | Notes                                                        |
|-------------------|-----------|--------------------------------------------------------------|
| `date`            | DATE      | Invoice date. Table is partitioned by this.                  |
| `bill_period`     | STRING    | Free text, e.g. `May 25-29`, `Week of May 25`, `5/18-5/22`.  |
| `invoice_number`  | STRING    | Clustered. The key you validate by.                          |
| `type_of_invoice` | STRING    | `Admin`, `Storage`, `VAS`, `SMLPRCL/LTL`.                    |
| `warehouse`       | STRING    | Free text, e.g. `TS West (CA)`, `New Jersey (NJ)`, `Yusen CA`.|
| `amount`          | FLOAT     | Total billed amount.                                         |
| `notes`           | STRING    | e.g. `WO #12966: Fontana Back Office Support`.               |
| `ingested_at`     | TIMESTAMP | Load timestamp.                                              |

## Querying

Always parameterize the invoice number (avoid SQL injection / quoting bugs):
```python
from google.cloud import bigquery
client = bigquery.Client(project="americanflat")
q = """
SELECT invoice_number, type_of_invoice, warehouse, amount, date, bill_period
FROM `americanflat.finance.yusen_invoices`
WHERE invoice_number = @inv LIMIT 1
"""
cfg = bigquery.QueryJobConfig(
    query_parameters=[bigquery.ScalarQueryParameter("inv", "STRING", invoice_number)])
row = list(client.query(q, job_config=cfg).result())
```

`validate_rate_card.py` already does this — call the script rather than hand-rolling.

## Warehouse normalization

The `warehouse` field is free text; the rate card is keyed by canonical name.
`validate_rate_card.py:WAREHOUSE_MAP` maps them:

| Rate-card key    | Matches (substring, case-insensitive)     |
|------------------|-------------------------------------------|
| `fontana`        | fontana, ts west, ca west                 |
| `new_jersey`     | new jersey, nj, ts east                   |
| `south_carolina` | south carolina, savannah, ts south, sc    |
| `canada`         | canada, yusen ca, ts canada               |

Netherlands (Yusen NL) is intentionally unmapped — rates are TBD in the SOP, so
those invoices return an `error` rather than a false pass. If a real `warehouse`
value doesn't match, add its alias to `WAREHOUSE_MAP`.

## Order IDs for Stedi validation

The header table has no order numbers. Those come from the supporting Excel file
attached to Small Parcel / LTL invoices — parse it with
`scripts/parse_invoice_excel.py`, which auto-detects both the modern Yusen layout
("Small Parcel" / "LTL" sheets) and the legacy Taylored layout (TSI PO# header).
"Yusen" and "Taylored Services" are the same vendor — Taylored is the newer name.
