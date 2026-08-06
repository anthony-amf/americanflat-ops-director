-- Invoice 754889 (SC storage, wk ending 07/05/2026): stamp the completed
-- validation. Evidence (session 2026-08-05): PDF exact — peak day 06/30,
-- 2,346 pallets @ $3.3500 = $7,859.10; $3.35 is the verified post-May-2026
-- SC rate (Notion card $5.09 is stale, not a dispute). Pallet-count GO:
-- AF Taylored Storage Cost model shows 2,353 for the same week (-0.3%);
-- cube model on invoice-week inventory (168K units, 99.3% dim coverage)
-- justifies ~2,800 positions, billed ~16% below. Already marked paid.
UPDATE `americanflat.finance.yusen_invoices` SET
  validation_status = 'valid',
  validated_at = CURRENT_TIMESTAMP(),
  validated_by = 'storage-deep-check-2026-08-05',
  validation_variance = 0.0,
  validation_report = TRIM(CONCAT(IFNULL(validation_report,''), '\n\n',
    '[STORAGE DEEP CHECK 2026-08-05] VALID: PDF exact — peak day 06/30/2026, 2,346 pallets @ $3.3500/pallet = $7,859.10 (verified post-May SC rate; below stale Notion card, not a dispute). Pallet-count GO vs AF Taylored Storage Cost model: model 2,353 same week (-0.3%); cube model on invoice-week inventory justifies ~2,800 positions. Utilization ~36% vs 53% target logged for MSA pallet-methodology negotiation.'), '\n ')
WHERE invoice_number = '754889'
  AND (validation_status IS NULL OR validation_status != 'disputed');
