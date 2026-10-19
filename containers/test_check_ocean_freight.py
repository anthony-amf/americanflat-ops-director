#!/usr/bin/env python3
"""
Tests for check_ocean_freight.py. The rate-sheet numbers are made up except
that they mirror the real case Mahjoub raised on 2026-10-14: HBL TAO26070091,
1×40HC Xingang → New York on Yang Ming, gated in 8/05 and billed $12,020 off
the 8/01 sheet, while TAO26080010 on the same lane gated in 8/20 under the
8/15 sheet at a YML special rate of $10,460.

    python3 test_check_ocean_freight.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_ocean_freight import check_invoice, rate_rows  # noqa: E402

RATES = rate_rows([
    {"effective_date": "2026-08-01", "coast": "EC", "origin": "Xingang", "destination": "New York",
     "carrier": "YML", "service": "regular", "size": "40HC", "rate_usd": "12,020"},
    {"effective_date": "2026-08-15", "coast": "EC", "origin": "Xingang", "destination": "New York",
     "carrier": "YML", "service": "regular", "size": "40HC", "rate_usd": "11,200"},
    {"effective_date": "2026-08-15", "coast": "EC", "origin": "Xingang", "destination": "New York",
     "carrier": "YML", "service": "special", "size": "40HC", "rate_usd": "10,460"},
    {"effective_date": "2026-08-15", "coast": "WC", "origin": "Qingdao", "destination": "Long Beach",
     "carrier": "ONE", "service": "regular", "size": "40HC", "rate_usd": "6,350"},
])
failures = 0


def expect(name, r, status, variance=None):
    global failures
    good = r["status"] == status and (variance is None or abs((r["variance"] or 0) - variance) < 0.006)
    print(f"{name:58} {r['status']:13} {'ok' if good else 'FAIL'}")
    if not good:
        failures += 1
        print(f"    expected {status} {variance}; got {r['variance']}\n    {r['report']}")


def inv(amount, gate_in="2026-08-05", service="regular", containers=("TLLU4085229",), extra=(), total=None,
        origin="Xingang", destination="New York", carrier="YML"):
    charges = [{"desc": "Ocean Freight", "amount": amount}] + [{"desc": d, "amount": a} for d, a in extra]
    return {"invoice_number": "LAX261000727", "hbl": "TAO26070091", "containers": list(containers),
            "size": "40HC", "origin": origin, "destination": destination, "carrier": carrier, "service": service,
            "gate_in_date": gate_in, "charges": charges,
            "total": round(sum(c["amount"] for c in charges), 2) if total is None else total}


expect("TAO26070091: gated 8/05, 8/01 sheet $12,020", check_invoice(inv(12020), RATES), "valid")
expect("same move billed at $12,500", check_invoice(inv(12500), RATES), "discrepancy", 480.00)
expect("gated 8/20 but billed the old 8/01 rate", check_invoice(inv(12020, gate_in="2026-08-20"), RATES),
       "discrepancy", 820.00)
expect("TAO26080010: 8/20, YML special $10,460",
       check_invoice(inv(10460, gate_in="2026-08-20", service="special"), RATES), "needs_detail")
expect("billed below the sheet (fine)", check_invoice(inv(11000, gate_in="2026-08-20"), RATES), "valid")
expect("two containers, $12,020 each",
       check_invoice(inv(24040, containers=("TLLU4085229", "MCDU1787820")), RATES), "valid")
expect("West Coast lane uses the WC sheet",
       check_invoice(inv(6350, gate_in="2026-08-25", origin="Qingdao", destination="Long Beach", carrier="ONE"),
                     RATES), "valid")
expect("lane not on the sheet", check_invoice(inv(9000, origin="Ningbo"), RATES), "needs_detail")
expect("gated in before the first sheet", check_invoice(inv(12020, gate_in="2026-07-20"), RATES), "needs_detail")
expect("no gate-in date", check_invoice(inv(12020, gate_in=None), RATES), "needs_detail")
expect("per diem added to the invoice",
       check_invoice(inv(12020, extra=[("Per Diem", 450.00)]), RATES), "needs_detail")
expect("unexplained extra charge",
       check_invoice(inv(12020, extra=[("Congestion surcharge", 300.00)]), RATES), "needs_detail")
expect("total $100 above the charges", check_invoice(inv(12020, total=12120.00), RATES), "discrepancy", 100.00)

print("ALL PASSED" if not failures else f"{failures} FAILED")
sys.exit(1 if failures else 0)
