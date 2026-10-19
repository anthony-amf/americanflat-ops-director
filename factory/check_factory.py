#!/usr/bin/env python3
"""
Factory invoice check — against the purchase orders in the WIP tab of
*Master Inventory Tracker 2026* (one row per PO line: PO, SKU, factory,
quantity, FOB unit price, shipped quantity, stage).

For each line a factory bills (PO, SKU, quantity, unit price, amount):
  1. The PO exists, the SKU is on it, and the PO belongs to that factory.
  2. Unit price = the FOB on that PO line. Prices for the same SKU change
     from PO to PO (1,192 factory/SKU pairs had more than one price since
     2025), so the check is always against the invoice's own PO.
  3. Quantity billed — together with anything already billed on earlier
     invoices — is not more than was ordered, and not more than has shipped.
  4. The line's own math (qty × price = amount) and the invoice total.

WIP quirks it allows for:
  - Split shipments repeat a PO line on several rows; ordered and shipped
    quantities are summed across them, and the "Total cost" column (which
    repeats the full line total on every split row) is ignored.
  - A PO line on hold, or not yet shipped, can still be billed for a deposit;
    pass `--deposit` for a deposit invoice and only the price/PO checks run.

Statuses follow the Yusen ledger: valid / discrepancy / needs_detail.

    python3 check_factory.py WIP.csv invoice.json [--prior earlier_invoices.json] [--deposit]

invoice.json: {"invoice_number", "factory", "currency": "USD", "total",
               "lines": [{"po", "sku", "qty", "unit_price", "amount"}]}
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from typing import Optional

PRICE_TOL = 0.005      # FOB is quoted to the cent; allow half a cent of rounding
CENT = 0.011


def _num(s) -> Optional[float]:
    s = str(s or "").replace("$", "").replace(",", "").strip()
    if s in ("", "-"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    try:
        v = float(s.strip("()"))
    except ValueError:
        return None
    return -v if neg else v


def _key(s: str) -> str:
    return re.sub(r"\s+", "", str(s or "")).upper()


def load_wip(path: str) -> dict:
    """Read the WIP CSV export; see wip_lines()."""
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        return wip_lines(csv.DictReader(f))


def wip_lines(rows) -> dict:
    """(PO, SKU) -> {factory, ordered, shipped, prices, stages, status, rows}."""
    lines = defaultdict(lambda: dict(factory=set(), ordered=0.0, shipped=0.0, prices=set(),
                                     stages=set(), status=set(), rows=0))
    for r in rows:
        po, sku = _key(r.get("PO (clean)")), _key(r.get("SKU"))
        if not po or not sku:
            continue
        d = lines[(po, sku)]
        d["rows"] += 1
        d["factory"].add((r.get("Factory") or "").strip())
        d["ordered"] += _num(r.get("QTY")) or 0
        shipped = _num(r.get("Shipped QTY (Packing List Tracker + DI Orders)") or
                       next((v for k, v in r.items() if k and k.startswith("Shipped QTY")), None))
        d["shipped"] += shipped or 0
        fob = _num(r.get("FOB"))
        if fob is not None:
            d["prices"].add(round(fob, 4))
        for col, dest in (("Stage", "stages"), ("Status", "status")):
            v = (r.get(col) or "").strip()
            if v:
                d[dest].add(v)
    return dict(lines)


def _money(x: float, cur: str = "USD") -> str:
    return f"${x:,.2f}" if cur == "USD" else f"{x:,.2f} {cur}"


def check_invoice(inv: dict, wip: dict, prior: Optional[list] = None, deposit: bool = False) -> dict:
    cur = (inv.get("currency") or "USD").upper()
    factory = (inv.get("factory") or "").strip()
    already = defaultdict(float)
    for p in prior or []:
        for l in p.get("lines", []):
            already[(_key(l["po"]), _key(l["sku"]))] += float(l["qty"])

    parts = [f"Factory invoice {inv.get('invoice_number', '?')} from {factory or 'unknown factory'}"
             + (" (deposit)" if deposit else "") + "."]
    findings, review, over = [], [], 0.0
    if cur != "USD":
        review.append(f"Invoice is in {cur}; PO prices in the WIP are USD FOB — convert before comparing.")

    billed_total = 0.0
    for i, l in enumerate(inv.get("lines", []), 1):
        po, sku = _key(l["po"]), _key(l["sku"])
        qty, price = float(l["qty"]), float(l["unit_price"])
        amt = round(float(l.get("amount", qty * price)), 2)
        billed_total += amt
        tag = f"Line {i} (PO {l['po']}, {l['sku']})"
        if abs(qty * price - amt) > CENT:
            findings.append(f"{tag}: {qty:,.0f} × {_money(price, cur)} is {_money(qty * price, cur)}, "
                            f"billed {_money(amt, cur)}.")
            over += round(amt - qty * price, 2)

        d = wip.get((po, sku))
        if d is None:
            on_po = any(k[0] == po for k in wip)
            review.append(f"{tag}: {'SKU not on this PO' if on_po else 'PO not in the WIP'} — "
                          "can't confirm price or quantity.")
            continue
        facs = {f for f in d["factory"] if f}
        if factory and facs and not any(factory.lower() in f.lower() or f.lower() in factory.lower() for f in facs):
            review.append(f"{tag}: the WIP lists this PO under {', '.join(sorted(facs))}, not {factory}.")

        # Price
        prices = sorted(d["prices"])
        if prices and cur == "USD":
            if not any(abs(price - p) <= PRICE_TOL for p in prices):
                top = max(prices)
                if price > top:
                    extra = round(qty * (price - top), 2)
                    over += extra
                    findings.append(f"{tag}: billed {_money(price)} each; the PO price is {_money(top)} "
                                    f"— {qty:,.0f} × {_money(price - top)} = {_money(extra)} over.")
                else:
                    review.append(f"{tag}: billed {_money(price)} each, below the PO price {_money(top)}.")
            if len(prices) > 1:
                review.append(f"{tag}: the WIP has more than one price for this PO line "
                              f"({', '.join(_money(p) for p in prices)}) — confirm which is current.")

        # Quantity
        prev = already[(po, sku)]
        cum = prev + qty
        if not deposit:
            if cum > d["ordered"] + 1e-6:
                extra = cum - d["ordered"]
                over += round(min(extra, qty) * price, 2)
                findings.append(f"{tag}: billing {qty:,.0f}"
                                + (f" on top of {prev:,.0f} already billed" if prev else "")
                                + f", but only {d['ordered']:,.0f} were ordered.")
            elif cum > d["shipped"] + 1e-6:
                review.append(f"{tag}: {cum:,.0f} billed so far but the WIP shows {d['shipped']:,.0f} shipped "
                              f"(stage: {', '.join(sorted(d['stages'])) or 'blank'}).")
        if any("hold" in s.lower() for s in d["stages"] | d["status"]):
            review.append(f"{tag}: this PO line is marked on hold in the WIP.")
        parts.append(f"{tag}: {qty:,.0f} × {_money(price, cur)} = {_money(amt, cur)}; ordered "
                     f"{d['ordered']:,.0f}, shipped {d['shipped']:,.0f}"
                     + (f", already billed {prev:,.0f}" if prev else "") + ".")

    billed_total = round(billed_total, 2)
    total = inv.get("total")
    if total is not None and abs(float(total) - billed_total) > CENT:
        findings.append(f"Invoice total {_money(float(total), cur)} but the lines add up to "
                        f"{_money(billed_total, cur)}.")
        over += round(float(total) - billed_total, 2)
    else:
        parts.append(f"Lines add up to {_money(billed_total, cur)}"
                     + (", matching the invoice total." if total is not None else "."))

    parts += findings + list(dict.fromkeys(review))
    over = round(over, 2)
    if over > 0.01:
        status = "discrepancy"
        parts.append(f"Over by {_money(over, cur)}; payable at PO terms {_money((float(total) if total is not None else billed_total) - over, cur)}.")
    elif findings or review or not inv.get("lines"):
        status = "needs_detail"
    else:
        status = "valid"
    return dict(status=status, variance=over if status == "discrepancy" else (0.0 if status == "valid" else None),
                billed=billed_total, report=" ".join(parts), findings=findings, review=review)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wip", help="WIP tab exported as CSV")
    ap.add_argument("invoice", help="factory invoice as JSON")
    ap.add_argument("--prior", help="JSON list of this factory's earlier invoices (to catch double billing)")
    ap.add_argument("--deposit", action="store_true", help="deposit invoice: skip shipped/ordered quantity checks")
    a = ap.parse_args(argv)
    prior = json.load(open(a.prior)) if a.prior else None
    r = check_invoice(json.load(open(a.invoice)), load_wip(a.wip), prior, a.deposit)
    print(f"{r['status'].upper()}  variance={r['variance']}\n{r['report']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
