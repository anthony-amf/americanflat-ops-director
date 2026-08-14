-- 755499 — clear a discrepancy that came from a typo, not from the invoice.
--
-- The row reads: status `discrepancy`, variance −$46.20, and it is marked paid.
-- The invoice is correct. Its notes carry the whole basis:
--
--   WORK ORDER 5001840 P65 Cancer Warning Labels (Savannah) - 11 LABELS @ $0.42/LABEL
--
-- 11 × $0.42 = $4.62, which is the header total to the cent. The variance came from
-- a manual `--detail "11 x 4.62"` run on 2026-08-13: the invoice TOTAL was typed
-- where the per-unit RATE goes, so the check expected 11 × $4.62 = $50.82 and
-- reported the $46.20 gap. (The correct entry is `--detail "11 x 0.42"`.)
--
-- Left alone this is a phantom $46.20 claim sitting on a paid invoice, and the row's
-- own report block already says "OK to pay" — status and report disagree.
--
-- Run once, from the Mac. Safe to re-run: the WHERE clause stops matching after the
-- first run. Nothing here touches paid_at. Appends to validation_report, never
-- replaces it.

UPDATE `americanflat.finance.yusen_invoices`
SET validation_status   = 'valid',
    validation_variance = 0,
    validated_at        = CURRENT_TIMESTAMP(),
    validation_report   = CONCAT(IFNULL(validation_report, ''), '''

[DEEP PASS 2026-08-13] Invoice 755499 - VAS, TS South (SC), work order 5001840.
The notes carry the full basis: 11 P65 cancer-warning labels @ $0.42/label = $4.62,
which is the header total to the cent. The -$46.20 variance previously on this row
came from a manual --detail entry of "11 x 4.62" - the invoice TOTAL was typed where
the per-unit RATE goes, so the check expected 11 x $4.62 = $50.82 and reported the
shortfall as a discrepancy. Nothing is wrong with the invoice.
Corrected 2026-08-13: status valid, variance cleared. Payment stands; no claim.
Verdict:       correctly billed''')
WHERE invoice_number = '755499'
  AND validation_status = 'discrepancy';

-- Check afterwards:
-- SELECT invoice_number, validation_status, validation_variance
-- FROM `americanflat.finance.yusen_invoices` WHERE invoice_number = '755499';
-- expect: valid, 0
