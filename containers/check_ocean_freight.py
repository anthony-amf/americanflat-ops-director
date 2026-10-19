#!/usr/bin/env python3
"""
Ocean freight (container) invoice check — WWL (Worldwide Logistics) FCL.

There is no fixed rate card: WWL sends rate sheets on the 1st and 15th of
each month, one for East Coast and one for West Coast destinations
("Americanflat Ocean Freight Rates 10 15 26 EC.pdf"). WWL's rule, confirmed
by Ariana Ramos on 2026-10-14 for HBL TAO26070091: **the rate is the sheet in
effect on the day the container gated in at the origin port**, for that
carrier and service. A carrier "special rate" can apply instead (TAO26080010,
YML special); those need WWL to name the special.

What this checks on one invoice (one HBL, one or more containers):
  1. Ocean freight per container = the rate-sheet line for the sheet in
     effect on the gate-in date, matching origin, destination, carrier,
     service and container size. Higher → overcharge. Lower → fine, noted.
  2. Containers × rate = billed ocean freight.
  3. Other charges on the invoice are listed; anything that isn't on the
     rate sheet (per diem, demurrage, late fees) is held for review.
  4. Charges add up to the invoice total.

Rate sheets live as CSV rows (one file or many):
    effective_date,coast,origin,destination,carrier,service,size,rate_usd
    2026-08-01,EC,Xingang,New York,YML,regular,40HC,12020

Statuses follow the Yusen ledger: valid / discrepancy / needs_detail.

    python3 check_ocean_freight.py invoice.json rates/*.csv
"""

import argparse
import csv
import json
import sys
from datetime import date
from typing import Optional

CENT = 0.011
EAST = ("NEW YORK", "NEWARK", "NY", "NJ", "SAVANNAH", "CHARLESTON", "NORFOLK", "BALTIMORE")
FREIGHT_WORDS = ("OCEAN FREIGHT", "O/F", "OFR", "FREIGHT")
SIZES = {"40HC": "40HC", "40HQ": "40HC", "40'HC": "40HC", "40H": "40HC", "40": "40GP", "40GP": "40GP",
         "40DV": "40GP", "40ST": "40GP", "20": "20GP", "20GP": "20GP", "20DV": "20GP", "45": "45HC", "45HC": "45HC"}


def _norm(s: str) -> str:
    return " ".join(str(s or "").upper().replace(",", " ").split())


def _size(s: str) -> str:
    k = _norm(s).replace(" ", "")
    return SIZES.get(k, k)


def coast_of(destination: str) -> str:
    d = _norm(destination)
    return "EC" if any(p in d for p in EAST) else "WC"


def load_rates(paths: list) -> list:
    rows = []
    for p in paths:
        with open(p, newline="", encoding="utf-8-sig") as f:
            rows += rate_rows(csv.DictReader(f))
    return rows


def rate_rows(records) -> list:
    rows = []
    for r in records:
        rows.append(dict(effective=date.fromisoformat(r["effective_date"].strip()),
                         coast=_norm(r.get("coast") or ""), origin=_norm(r["origin"]),
                         destination=_norm(r["destination"]), carrier=_norm(r["carrier"]),
                         service=_norm(r.get("service") or "REGULAR"), size=_size(r["size"]),
                         rate=float(str(r["rate_usd"]).replace(",", "").replace("$", ""))))
    return rows


def sheet_rate(rates: list, gate_in: date, origin: str, destination: str, carrier: str,
               service: str, size: str) -> tuple[Optional[float], Optional[date], str]:
    """The rate from the latest sheet effective on or before the gate-in date."""
    coast = coast_of(destination)
    o, d, c, s, z = _norm(origin), _norm(destination), _norm(carrier), _norm(service or "REGULAR"), _size(size)
    sheets = sorted({r["effective"] for r in rates if r["effective"] <= gate_in and (r["coast"] in ("", coast))})
    if not sheets:
        return None, None, f"no {coast} rate sheet on or before {gate_in.isoformat()}"
    eff = sheets[-1]
    hits = [r for r in rates if r["effective"] == eff and r["coast"] in ("", coast) and r["origin"] == o
            and r["destination"] == d and r["carrier"] == c and r["service"] == s and r["size"] == z]
    if not hits:
        return None, eff, (f"the {eff:%m/%d} {coast} sheet has no line for {origin} → {destination}, "
                           f"{carrier} {service or 'regular'}, {size}")
    return hits[0]["rate"], eff, ""


def _money(x: float) -> str:
    return f"${x:,.2f}"


def check_invoice(inv: dict, rates: list) -> dict:
    hbl = inv.get("hbl", "?")
    containers = inv.get("containers") or []
    n = len(containers) or int(inv.get("container_count") or 1)
    size = inv.get("size", "40HC")
    service = inv.get("service") or "regular"
    try:
        gate_in = date.fromisoformat(inv["gate_in_date"]) if inv.get("gate_in_date") else None
    except ValueError:
        gate_in = None
    parts = [f"Ocean freight, HBL {hbl}"
             + (f" ({inv['invoice_number']})" if inv.get("invoice_number") else "")
             + f": {n} × {size} {inv.get('origin', '?')} → {inv.get('destination', '?')}, "
             f"{inv.get('carrier', '?')} {service}"
             + (f", gated in {gate_in:%m/%d/%Y}" if gate_in else "") + "."]
    if containers:
        parts.append(f"Container(s): {', '.join(containers)}.")
    findings, review, over = [], [], 0.0

    freight = [c for c in inv.get("charges", []) if any(w in _norm(c["desc"]) for w in FREIGHT_WORDS)]
    other = [c for c in inv.get("charges", []) if c not in freight]
    billed_freight = round(sum(float(c["amount"]) for c in freight), 2)

    if not freight:
        review.append("No ocean freight line on this invoice.")
    elif gate_in is None:
        review.append("No origin gate-in date — can't tell which rate sheet applies (WWL bills by gate-in date).")
    else:
        rate, eff, why = sheet_rate(rates, gate_in, inv.get("origin", ""), inv.get("destination", ""),
                                    inv.get("carrier", ""), service, size)
        if rate is None:
            review.append(f"Can't price this move: {why}.")
        else:
            should = round(rate * n, 2)
            parts.append(f"Rate sheet in effect at gate-in: {eff:%m/%d/%Y} {coast_of(inv.get('destination', ''))} — "
                         f"{_money(rate)} per container × {n} = {_money(should)}; billed {_money(billed_freight)}.")
            if billed_freight > should + CENT:
                over += round(billed_freight - should, 2)
                findings.append(f"Ocean freight {_money(billed_freight)} is {_money(billed_freight - should)} above "
                                f"the {eff:%m/%d} sheet ({_money(should)}).")
            elif billed_freight < should - CENT:
                parts.append(f"Billed {_money(should - billed_freight)} below the sheet — likely a carrier special "
                             "rate; no action needed.")
        if service.lower() != "regular":
            review.append(f"Billed on a '{service}' rate — confirm WWL's special-rate reference.")

    for c in other:
        d = _norm(c["desc"])
        amt = float(c["amount"])
        if "PER DIEM" in d or "DEMURRAGE" in d or "DETENTION" in d:
            review.append(f"{c['desc']} {_money(amt)} — pass-through from the carrier; needs the carrier's bill "
                          "and the free-time dates.")
        else:
            review.append(f"{c['desc']} {_money(amt)} — not on the rate sheet; confirm it was agreed.")

    billed = round(sum(float(c["amount"]) for c in inv.get("charges", [])), 2)
    total = inv.get("total")
    if total is not None and abs(float(total) - billed) > CENT:
        findings.append(f"Invoice total {_money(float(total))} but the charges add up to {_money(billed)}.")
        over += round(float(total) - billed, 2)
    elif total is not None:
        parts.append(f"Charges add up to {_money(billed)}, matching the invoice total.")

    parts += findings + review
    over = round(over, 2)
    if over > 0.01:
        status = "discrepancy"
        parts.append(f"Over by {_money(over)}.")
    elif findings or review:
        status = "needs_detail"
    else:
        status = "valid"
    return dict(status=status, variance=over if status == "discrepancy" else (0.0 if status == "valid" else None),
                billed=billed, report=" ".join(parts), findings=findings, review=review)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("invoice", help="invoice as JSON")
    ap.add_argument("rates", nargs="+", help="rate sheet CSV file(s)")
    a = ap.parse_args(argv)
    r = check_invoice(json.load(open(a.invoice)), load_rates(a.rates))
    print(f"{r['status'].upper()}  variance={r['variance']}\n{r['report']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
