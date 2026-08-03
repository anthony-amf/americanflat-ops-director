# Changelog

All notable changes to this skill will be documented in this file.

## [0.1.0] - 2026-06-19

### Added
- Initial release.
- Warm-up that checks for the `gcloud` CLI and offers to install it for the
  operator (per-platform commands in `references/install_gcloud.md`), plus an
  upfront heads-up that the operator must sign off on the invoice total.
- Deterministic text extraction from invoice PDFs via PyMuPDF
  (`scripts/extract_text.py`), with a clear signal when a PDF is scanned and
  needs OCR instead.
- A fixed BigQuery schema (`references/bq_schema.json`) that handles variable
  line-item counts via a repeated `line_items` record and preserves anything
  unmapped in a `raw_extraction` JSON-string column — so unfamiliar vendor
  layouts load losslessly.
- Two-phase load (`scripts/load_to_bq.py`): a cloud-free `review` that prints
  stated total vs. summed line items for human sign-off, then a `load` that
  writes via service-account impersonation (no key files), refusing silent
  duplicates and totals mismatches and stamping provenance.
- Config via committed `config.json` with environment-variable overrides.
- Performs no IAM/permission operations; on permission-denied it tells the
  operator to request impersonation access from the admin. Admin-only setup
  (service account, dataset, table, grants) documented in
  `references/admin_setup.md`.
