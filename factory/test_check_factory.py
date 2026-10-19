#!/usr/bin/env python3
"""
Tests for check_factory.py on a small made-up WIP (no real supplier prices
in the repo). Shaped like the WIP tab, including a split PO line.

    python3 test_check_factory.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_factory import check_invoice, wip_lines  # noqa: E402

SHIPPED = "Shipped QTY (Packing List Tracker + DI Orders)"
WIP = wip_lines([
    # PO 9001 — Nisensi, two SKUs, fully shipped
    {"PO (clean)": "9001", "SKU": "FRAME-BLK-1114", "Factory": "Nisensi", "QTY": "1,000", "FOB": "$2.34 ",
     SHIPPED: "1,000", "Stage": "Received In-Full", "Status": ""},
    {"PO (clean)": "9001", "SKU": "FRAME-WHT-0810", "Factory": "Nisensi", "QTY": "500", "FOB": "$1.52 ",
     SHIPPED: "500", "Stage": "In Transit", "Status": ""},
    # PO 9002 — Jinlida, one SKU split over two rows, half shipped
    {"PO (clean)": "9002", "SKU": "MIRROR-2436", "Factory": "Jinlida", "QTY": "104", "FOB": "$8.79 ",
     SHIPPED: "104", "Stage": "Partially received", "Status": ""},
    {"PO (clean)": "9002", "SKU": "MIRROR-2436", "Factory": "Jinlida", "QTY": "108", "FOB": "$8.79 ",
     SHIPPED: "0", "Stage": "On hold", "Status": "on hold"},
])

failures = 0


def expect(name, r, status, variance=None):
    global failures
    good = r["status"] == status and (variance is None or abs((r["variance"] or 0) - variance) < 0.006)
    print(f"{name:55} {r['status']:13} {'ok' if good else 'FAIL'}")
    if not good:
        failures += 1
        print(f"    expected {status} {variance}; got {r['variance']}\n    {r['report']}")


def inv(*lines, factory="Nisensi", total=None, number="INV-1"):
    ls = [dict(po=po, sku=sku, qty=q, unit_price=p, amount=round(q * p, 2)) for po, sku, q, p in lines]
    return dict(invoice_number=number, factory=factory, currency="USD",
                total=round(sum(l["amount"] for l in ls), 2) if total is None else total, lines=ls)


clean = inv(("9001", "FRAME-BLK-1114", 1000, 2.34), ("9001", "FRAME-WHT-0810", 500, 1.52))
expect("clean Nisensi invoice, two lines", check_invoice(clean, WIP), "valid")

expect("price 10¢ above the PO", check_invoice(inv(("9001", "FRAME-BLK-1114", 1000, 2.44)), WIP),
       "discrepancy", 100.00)
expect("price below the PO (flag, not overcharge)",
       check_invoice(inv(("9001", "FRAME-BLK-1114", 1000, 2.20)), WIP), "needs_detail")
expect("more than ordered", check_invoice(inv(("9001", "FRAME-WHT-0810", 600, 1.52)), WIP),
       "discrepancy", 152.00)

prior = [inv(("9001", "FRAME-BLK-1114", 600, 2.34), number="INV-0")]
expect("second invoice pushes past ordered (double billing)",
       check_invoice(inv(("9001", "FRAME-BLK-1114", 600, 2.34)), WIP, prior), "discrepancy", 468.00)
expect("second invoice for the remainder", check_invoice(inv(("9001", "FRAME-BLK-1114", 400, 2.34)), WIP, prior),
       "valid")

# Split line: 212 ordered, 104 shipped, the other 108 on hold.
expect("split line, billing only what shipped",
       check_invoice(inv(("9002", "MIRROR-2436", 104, 8.79), factory="Jinlida"), WIP), "needs_detail")
expect("split line, billing all 212 before it ships",
       check_invoice(inv(("9002", "MIRROR-2436", 212, 8.79), factory="Jinlida"), WIP), "needs_detail")
expect("deposit invoice on the held line (price check only)",
       check_invoice(inv(("9002", "MIRROR-2436", 212, 8.79), factory="Jinlida"), WIP, deposit=True),
       "needs_detail")   # still flagged: the line is on hold

expect("PO billed by the wrong factory",
       check_invoice(inv(("9001", "FRAME-BLK-1114", 1000, 2.34), factory="Kimtoon"), WIP), "needs_detail")
expect("PO not in the WIP", check_invoice(inv(("9999", "FRAME-BLK-1114", 10, 2.34)), WIP), "needs_detail")
expect("SKU not on that PO", check_invoice(inv(("9001", "NOT-A-SKU", 10, 2.34)), WIP), "needs_detail")

bad_total = inv(("9001", "FRAME-BLK-1114", 1000, 2.34), total=2400.00)
expect("invoice total $60 above its lines", check_invoice(bad_total, WIP), "discrepancy", 60.00)

bad_math = inv(("9001", "FRAME-BLK-1114", 1000, 2.34))
bad_math["lines"][0]["amount"] = 2370.00
bad_math["total"] = 2370.00
expect("line amount ≠ qty × price", check_invoice(bad_math, WIP), "discrepancy", 30.00)

print("ALL PASSED" if not failures else f"{failures} FAILED")
sys.exit(1 if failures else 0)
