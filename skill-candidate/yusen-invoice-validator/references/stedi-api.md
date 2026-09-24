# Stedi EDI API — order validation

Used by `scripts/validate_stedi.py` to confirm that order numbers on an invoice
actually correspond to EDI transactions Stedi processed.

## Endpoint & auth

- Base URL: `https://core.us.stedi.com`
- Path: `/2023-08-01/transactions`
- Auth header: `Authorization: <API_KEY>` (the raw key — Stedi also accepts the
  legacy `Key <API_KEY>` prefix, but the raw key is current).
- The key is read from the `STEDI_API_KEY` environment variable. It is **not**
  embedded in the skill, so the skill is safe to share. Set it before running:
  ```bash
  export STEDI_API_KEY=<your production key>
  ```

A quick connectivity check (should return HTTP 200):
```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: $STEDI_API_KEY" \
  "https://core.us.stedi.com/2023-08-01/transactions?transaction_type=945&businessIdentifier=TEST"
```

## Query pattern

Filter transactions by type and business identifier (the order number):
```
GET /2023-08-01/transactions?transaction_type=945&businessIdentifier=<order_id>
```
Response shape: `{ "items": [ { ... }, ... ], "next_page_token": "..." }`.
A non-empty `items` array means the order was found.

Business identifiers live in `items[].businessIdentifiers[]` — typically
`BSN-02` (Shipment Identification) and `PRF-01` (Purchase Order Number), both
usually equal to the order number.

## 945 vs 940 — check both

The validator checks **945 first, then 940**:

- **945 — Warehouse Shipping Advice** → the order *shipped*. This is the success
  case; carries shipment/tracking detail.
- **940 — Warehouse Order** → the order was *received by the warehouse* but a 945
  hasn't been issued yet (not shipped, or shipment not transmitted). Found in 940
  but not 945 = "in warehouse, not yet shipped."
- **Found in neither** → genuinely missing. Investigate: order still in transit,
  not yet transmitted to Stedi, or an order-ID mismatch (leading apostrophes,
  trailing suffixes like `_1`/`R`, casing) between the invoice file and Stedi.

If a 945 search returns nothing, **always** fall back to 940 before calling an
order missing — the script does this automatically.

## Order-ID hygiene

Order numbers exported from Excel often arrive with a leading apostrophe
(`'102003276483843`) that Excel uses to force text. The script strips a leading
`'` and surrounding whitespace before querying. If match rates are low, inspect
the raw IDs for other artifacts (suffixes, R-returns, padded zeros).
