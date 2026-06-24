# Rate Card Validation Report
**Generated:** 2026-06-24

## Summary
- **Total Invoices Validated:** 18
- **Valid:** 4
- **Discrepancies Found:** 3
- **Pending Detail (need line items):** 11

---

## 🚨 Discrepancies Requiring Action

### 1. Invoice 752738 (NJ Admin)
- **Status:** ❌ UNDERBILLED
- **Period:** Week of May 25
- **Charged:** $856.80
- **Expected:** $1,124.55 (with 5% labor tax)
- **Variance:** -$267.75 (-23.8%)
- **Action:** Review with NJ warehouse — possible billing error or partial week

### 2. Invoice 752732 (NJ Admin)  
- **Status:** ⚠️ UNDERBILLED
- **Period:** Week of May 4
- **Charged:** $1,071.00
- **Expected:** $1,124.55 (with 5% labor tax)
- **Variance:** -$53.55 (-4.8%)
- **Note:** Charged base rate without 5% NJ labor tax
- **Action:** Add $53.55 tax charge

### 3. Invoice 751542 (NJ Storage)
- **Status:** ⚠️ CANNOT VALIDATE
- **Period:** Week of 05/04/2026
- **Charged:** $36,029.50
- **Issue:** Line item detail needed to validate pallet count
- **Action:** Extract pallet count from invoice detail

---

## ✅ Valid Invoices

| Invoice | Type | Warehouse | Amount | Status |
|---------|------|-----------|--------|--------|
| 752857 | Admin | Fontana | $2,393.11 | ✓ Valid |
| 751471 | Admin | South Carolina | $1,092.00 | ✓ Valid |

---

## 📋 Next Steps

1. **Fix NJ Admin Tax Issue**
   - Invoices 752732 & 752738 missing labor tax
   - Add 5% to $1,071 base = $1,124.55
   - Total adjustment needed: $321.30

2. **Investigate Storage Invoice**
   - Need line item breakdown for 751542
   - Extract pallet quantities and validate rates

3. **Enable Detailed Validation**
   - Parser needs to extract line item quantities
   - Will enable full Small Parcel/LTL/Storage validation
   - Currently 11 invoices in "pending detail" state

