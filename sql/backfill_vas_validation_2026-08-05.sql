-- Backfill: VAS validation sweep per Anthony's 2026-08-05 policy
--
-- Policy: a VAS invoice is VALID when its math verifies AND the invoice PDF
-- itself carries supporting documentation (work order, email approval trail,
-- worksheets). needs_detail is reserved for no-documentation or errors.
-- All 75 US VAS invoices were combed (SC scanned PDFs OCR'd): 70 valid,
-- 5 left disputed (AF-9 wrap components - NOT touched here).
--
-- Run from the Mac (cloud BigQuery credential is read-only):
--   bq query --use_legacy_sql=false < sql/backfill_vas_validation_2026-08-05.sql
-- Run ONCE - the report append is not idempotent.

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: amount self-consistent at 0.4575/label x 1,562 (rate printed truncated as 0.45); email approval trail in PDF. PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '724793' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 16 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '749214' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 4 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 7 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '749455' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '749457' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 4 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 14 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '749458' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 4 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 7 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '749460' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 4 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '749462' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 3 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 4 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '749464' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '749465' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 4 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '749466' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: qty x rate = invoiced amount; evidence in PDF (work order/approval docs). PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '750206' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 16 LABELS x 0.42 = 6.72 exact (OCR split qty line; verified by inspection); work-order pages attached. PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '750255' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 2 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 6 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '750403' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 9 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '750404' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: qty x rate = invoiced amount; evidence in PDF (work order/approval docs). PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '750576' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '750984' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 4 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '751047' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 5 line(s) verified qty x rate; evidence in PDF (work order/approval docs). PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '751140' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (work order/approval docs). PDF: 9 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '751148' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 4 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '751174' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 11 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '751176' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 4 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '751211' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (work order/approval docs). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '751351' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '751353' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 4 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 7 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '751354' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 8 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '751355' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752056' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752058' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 4 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752059' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 4 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752061' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 2 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 9 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752103' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 11 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752123' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: qty x rate = invoiced amount; evidence in PDF (work order/approval docs). PDF: 4 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752344' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752352' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 7 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752361' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 4 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752621' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 4 line(s) verified qty x rate; evidence in PDF (work order/approval docs). PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752902' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 11 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752916' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '752998' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '753000' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 6 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '753001' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 8 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754284' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 6 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754338' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 6 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754339' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 4 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754368' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: qty x rate = invoiced amount; evidence in PDF (work order/approval docs). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754372' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (work order/approval docs). PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754418' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: qty x rate = invoiced amount; evidence in PDF (work order/approval docs). PDF: 4 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754466' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 2 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754592' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754593' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 19 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754594' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 5 line(s) verified qty x rate; evidence in PDF (work order/approval docs). PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754742' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 2 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 6 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754754' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754755' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 6 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754756' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 6 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754757' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 4 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '754855' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '755109' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 7 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '755110' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 14 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '755111' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '755112' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 3 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '755875' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 6 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '755876' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 4 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '755877' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 10 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '755878' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 5 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 6 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '755879' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '755985' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 12 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '756498' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 5 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '756525' AND validation_status != 'disputed';

UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'vas-sweep-2026-08-05',
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n', '[VAS SWEEP 2026-08-05] VALID per VAS documentation policy: 1 line(s) verified qty x rate; evidence in PDF (email approval trail). PDF: 11 pages incl. supporting documentation.'), '\n ')
WHERE invoice_number = '756527' AND validation_status != 'disputed';
