-- Follow-up: 4 VAS invoices missed by the 2026-08-05 sweep backfill.
-- Their validation_status was NULL, and the original guard
-- (validation_status != 'disputed') evaluates to NULL for NULL rows, so
-- BigQuery skipped them. Guard corrected with IFNULL.
-- Run ONCE from the Mac:
--   bq query --use_legacy_sql=false < sql/backfill_vas_validation_fixup_2026-08-05.sql

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '755985' AND IFNULL(validation_status,'') != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 12 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '756498' AND IFNULL(validation_status,'') != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '756525' AND IFNULL(validation_status,'') != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 11 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '756527' AND IFNULL(validation_status,'') != 'disputed';
