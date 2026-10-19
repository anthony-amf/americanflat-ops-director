#!/usr/bin/env python3
"""
Tests for check_drayage.py. No network, no BigQuery.

The invoices here are made-up but laid out the way a TMW/Quantum invoice
usually reads; swap in real O'Neill invoice text (N0185062, N0185063,
N0190164) once we have the PDFs and keep these as the planted-mistake cases.

    python3 test_check_drayage.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_drayage import check_drayage, parse_text  # noqa: E402

failures = 0


def expect(name, r, status, variance=None):
    global failures
    good = r["status"] == status and (variance is None or abs((r["variance"] or 0) - variance) < 0.006)
    print(f"{name:55} {r['status']:13} {'ok' if good else 'FAIL'}")
    if not good:
        failures += 1
        print(f"    expected {status} {variance}; got {r['variance']}\n    {r['report']}")


def run(text, lane, diesel=None):
    charges, total, containers = parse_text(text)
    return check_drayage(charges, lane, total, diesel, containers)


CLEAN_NJ = """O'NEILL LOGISTICS   INVOICE N0190164
Container: MSMU6558953   Port Newark → Edison NJ
LINE HAUL                 1.00   $450.00   $450.00
CHASSIS                   3.00    $25.00    $75.00
TOTAL DUE $525.00
"""
expect("NJ clean: line haul + 3 chassis days", run(CLEAN_NJ, "NJ", diesel=3.89), "valid")

CLEAN_CA = """INVOICE N0185062  Container: OOLU9677160
LINE HAUL                 1.00   $525.00   $525.00
CHASSIS                   4.00    $25.00   $100.00
DETENTION                 1.00    $85.00    $85.00
YARD STORAGE              2.00    $50.00   $100.00
TOTAL DUE $810.00
"""
expect("CA clean: haul, chassis, 1 hr detention, storage", run(CLEAN_CA, "CA", diesel=3.89), "valid")

# Line haul above the lane rate.
expect("CA line haul $575 (lane $525)",
       run(CLEAN_CA.replace("$525.00   $525.00", "$575.00   $575.00").replace("$810.00", "$860.00"), "CA", 3.89),
       "discrepancy", 50.00)

# Fuel billed while diesel is under $4.50.
fuel = CLEAN_NJ.replace("TOTAL DUE $525.00", "FUEL SURCHARGE 6.00% $27.00\nTOTAL DUE $552.00")
expect("fuel billed at $3.89 diesel", run(fuel, "NJ", diesel=3.89), "discrepancy", 27.00)
expect("fuel billed, diesel price unknown", run(fuel, "NJ"), "needs_detail")
# Above $4.50 the matrix applies: $4.62 → 8.4% of $450 = $37.80.
fuel_ok = CLEAN_NJ.replace("TOTAL DUE $525.00", "FUEL SURCHARGE 8.40% $37.80\nTOTAL DUE $562.80")
expect("fuel at $4.62 diesel = 8.4% matrix", run(fuel_ok, "NJ", diesel=4.62), "valid")

# Pool chassis at $45 is on the sheet (flag, not overcharge); chassis at $55 is not.
pool = CLEAN_NJ.replace("CHASSIS                   3.00    $25.00    $75.00",
                        "POOL CHASSIS              3.00    $45.00   $135.00").replace("$525.00\n", "$585.00\n")
expect("pool chassis $45/day (allowed, flagged)", run(pool, "NJ", 3.89), "valid")
dear = CLEAN_NJ.replace("$25.00    $75.00", "$35.00   $105.00").replace("TOTAL DUE $525.00", "TOTAL DUE $555.00")
expect("chassis at $35/day (sheet $25)", run(dear, "NJ", 3.89), "discrepancy", 30.00)

# Bobtail is half rate.
bob = "INVOICE N1\nBOBTAIL 1.00 $262.50 $262.50\nTOTAL DUE $262.50\n"
expect("CA bobtail at half rate", run(bob, "CA", 3.89), "valid")
expect("CA bobtail at full rate",
       run(bob.replace("262.50", "525.00"), "CA", 3.89), "discrepancy", 262.50)

# Per diem pass-through with 10% admin, and with 15%.
pd = ("INVOICE N2\nPER DIEM 1.00 $300.00 $300.00\nPER DIEM ADMIN FEE 1.00 $30.00 $30.00\n"
      "TOTAL DUE $330.00\n")
expect("per diem + 10% admin (needs carrier bill)", run(pd, "NJ"), "needs_detail")
expect("per diem admin at 15%",
       run(pd.replace("$30.00 $30.00", "$45.00 $45.00").replace("$330.00", "$345.00"), "NJ"),
       "discrepancy", 15.00)

# Charge not on that lane's sheet (triaxle isn't on the Fontana sheet).
tri = CLEAN_CA.replace("TOTAL DUE $810.00", "TRIAXLE SURCHARGE 1.00 $75.00 $75.00\nTOTAL DUE $885.00")
expect("triaxle on a Fontana invoice", run(tri, "CA", 3.89), "needs_detail")

# Invoice line math wrong.
bad = CLEAN_NJ.replace("3.00    $25.00    $75.00", "3.00    $25.00    $95.00").replace("$525.00\n", "$545.00\n")
expect("chassis 3 × $25 billed as $95", run(bad, "NJ", 3.89), "discrepancy", 20.00)

# Total doesn't match the lines.
expect("total $25 above the lines", run(CLEAN_NJ.replace("TOTAL DUE $525.00", "TOTAL DUE $550.00"), "NJ", 3.89),
       "needs_detail")

# Unknown charge.
odd = CLEAN_NJ.replace("TOTAL DUE $525.00", "HAZMAT HANDLING 1.00 $90.00 $90.00\nTOTAL DUE $615.00")
expect("unrecognised charge", run(odd, "NJ", 3.89), "needs_detail")

print("ALL PASSED" if not failures else f"{failures} FAILED")
sys.exit(1 if failures else 0)
