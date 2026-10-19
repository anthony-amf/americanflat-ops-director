#!/usr/bin/env python3
"""
Tests for check_customs.py — made-up entries shaped like a CBP 7501, until
we have real WWL entry summaries to replay. No network.

    python3 test_check_customs.py
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_customs import check_entry  # noqa: E402

failures = 0


def expect(name, r, status, variance=None):
    global failures
    good = r["status"] == status and (variance is None or abs((r["variance"] or 0) - variance) < 0.006)
    print(f"{name:55} {r['status']:13} {'ok' if good else 'FAIL'}")
    if not good:
        failures += 1
        print(f"    expected {status} {variance}; got {r['variance']}\n    {r['report']}")


# China MDF frames, $20,000: 3.9% base + 7.5% Sec 301, MPF 0.3464%, HMF 0.125%.
CLEAN = {
    "entry_number": "8NW-1589348-5", "entry_date": "2026-09-10", "port": "2704", "mode": "ocean",
    "lines": [{"hts": "4414.90.0000", "description": "MDF picture frames", "origin": "CN",
               "entered_value": 20000.00,
               "charges": [{"code": "4414.90.0000", "rate_pct": 3.9, "amount": 780.00},
                           {"code": "9903.88.15", "rate_pct": 7.5, "amount": 1500.00}]}],
    "mpf": 69.28, "hmf": 25.00, "total": 2374.28,
}
expect("clean China MDF frame entry", check_entry(CLEAN, bill_amount=2374.28), "valid")


def variant(**changes):
    e = copy.deepcopy(CLEAN)
    for k, v in changes.items():
        e[k] = v
    return e


bad_line = copy.deepcopy(CLEAN)
bad_line["lines"][0]["charges"][1]["amount"] = 1600.00
bad_line["total"] = 2474.28
expect("Sec 301 line $100 over value × rate", check_entry(bad_line), "discrepancy", 100.00)

expect("bill.com $23 above the entry", check_entry(CLEAN, bill_amount=2397.28), "discrepancy", 23.00)
expect("entry total doesn't add up", check_entry(variant(total=2400.00)), "discrepancy", 25.72)

big = copy.deepcopy(CLEAN)
big["lines"][0]["entered_value"] = 250000.00
big["lines"][0]["charges"] = [{"code": "4414.90.0000", "rate_pct": 3.9, "amount": 9750.00},
                              {"code": "9903.88.15", "rate_pct": 7.5, "amount": 18750.00}]
big.update(mpf=651.50, hmf=312.50, total=29464.00)
expect("MPF at the FY2026 cap ($651.50)", check_entry(big), "valid")
expect("MPF billed uncapped ($866.00)", check_entry(dict(big, mpf=866.00, total=29678.50)),
       "discrepancy", 214.50)
expect("FY2027 entry, cap not loaded yet", check_entry(dict(big, entry_date="2026-10-10")), "needs_detail")

air = variant(mode="air")
expect("HMF charged on an air entry", check_entry(air), "discrepancy", 25.00)

mirror = copy.deepcopy(CLEAN)
mirror["lines"] = [{"hts": "7009.92.5091", "origin": "CN", "entered_value": 10000.00,
                    "charges": [{"code": "7009.92.5091", "rate_pct": 6.5, "amount": 650.00}]}]
mirror.update(mpf=34.64, hmf=12.50, total=697.14)
expect("China mirror with no Sec 301 line (sheet 25%)", check_entry(mirror), "needs_detail")

ps = copy.deepcopy(CLEAN)
ps["lines"] = [{"hts": "3924.90.2000", "origin": "CN", "entered_value": 10000.00,
                "charges": [{"code": "3924.90.2000", "rate_pct": 3.4, "amount": 340.00},
                            {"code": "9903.88.03", "rate_pct": 25, "amount": 2500.00}]}]
ps.update(mpf=34.64, hmf=12.50, total=2887.14)
r = check_entry(ps)
expect("PS frame 25% Sec 301 (sheet row says 0%)", r, "needs_detail")
assert "should be 25%" in r["report"], "sheet's own audit note should be shown"

vn = copy.deepcopy(CLEAN)
vn["lines"] = [{"hts": "4414.90.0000", "origin": "VN", "entered_value": 10000.00,
                "charges": [{"code": "4414.90.0000", "rate_pct": 3.9, "amount": 390.00},
                            {"code": "9903.01.25", "rate_pct": 10, "amount": 1000.00}]}]
vn.update(mpf=34.64, hmf=12.50, total=1437.14)
expect("Vietnam frame with 10% reciprocal (sheet: paused)", check_entry(vn), "needs_detail")

unk = copy.deepcopy(mirror)
unk["lines"][0]["hts"] = "9999.99.9999"
unk["lines"][0]["charges"][0]["code"] = "9999.99.9999"
expect("tariff code not on our sheet", check_entry(unk), "needs_detail")

print("ALL PASSED" if not failures else f"{failures} FAILED")
sys.exit(1 if failures else 0)
