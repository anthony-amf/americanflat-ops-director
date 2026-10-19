#!/usr/bin/env python3
"""
Drayage invoice check — O'Neill Logistics (port → warehouse container moves).

Checks each charge on an O'Neill drayage invoice against the contracted rate
sheet ("Dray_Rates-_Americanflat_4_3_2026.xlsx", on the Notion "Drayage
Rates" page). O'Neill took over from IAS in mid-April 2026; IAS had no set
accessorial rates, so only O'Neill invoices can be rate-checked.

What it checks, per container:
  - Line haul = the lane's all-in base rate (fuel included up to $4.50/gal).
  - Bobtail = half the lane rate.
  - Every accessorial at its sheet rate × quantity (chassis days, storage
    days, detention hours after 2 free, pre-pull, off-dock return, …).
  - Fuel surcharge: none allowed while diesel is at or below $4.50/gal;
    above that, the % must match O'Neill's FSC matrix (see FUEL_NOTE).
  - Per diem passed through from the ocean carrier: the 10% admin fee must be
    exactly 10%; the per diem itself needs the carrier's bill (needs_detail).
  - Pool chassis ($45/day) is allowed but flagged — O'Neill's own chassis
    ($25/day) is the expected case.

Input is either the invoice text (PDF → text) or a JSON list of charges:

    python3 check_drayage.py --text invoice.txt --lane NJ [--diesel 3.89]
    python3 check_drayage.py --charges charges.json --lane CA

Statuses follow the Yusen ledger: valid / discrepancy / needs_detail.
"""

import argparse
import json
import math
import re
import sys
from typing import Optional

# --------------------------------------------------------------------------
# Rate sheet (O'Neill, dated 4/3/2026). Lane keys: NJ = NJ terminals → Edison,
# CA = LA/LB → Fontana, SC = GPA → Hardeeville (lane paused since March 2026).
# --------------------------------------------------------------------------
LANES = {
    "NJ": {"name": "NJ terminals → Edison, NJ", "base": 450.00},
    "CA": {"name": "LA/LB → Fontana, CA", "base": 525.00},
    "SC": {"name": "GPA → Hardeeville, SC", "base": 300.00},
}

# fee -> {lane: rate}; a lane missing from a fee means it is not on that
# lane's sheet. "per" is what one unit is.
FEES = {
    "chassis_oneill":   {"per": "day", "label": "Chassis (O'Neill fleet)", "NJ": 25, "CA": 25, "SC": 25},
    "chassis_pool":     {"per": "day", "label": "Chassis (pool)", "NJ": 45, "CA": 45, "SC": 45},
    "prepull":          {"per": "move", "label": "Pre-pull", "NJ": 125, "CA": 150, "SC": 100},
    "storage":          {"per": "day", "label": "Yard storage", "NJ": 40, "CA": 50, "SC": 30},
    "offdock_return":   {"per": "move", "label": "Off-dock return", "NJ": 150, "CA": 200, "SC": (100, 150)},
    "attempted_pickup": {"per": "attempt", "label": "Attempted pick-up", "NJ": 250, "CA": 250, "SC": 200},
    "detention":        {"per": "hour", "label": "Detention / live unload (after 2 free hours)", "NJ": 85, "CA": 85, "SC": 85},
    "positioning":      {"per": "move", "label": "Empty container/chassis positioning", "NJ": 200, "CA": 200},
    "saturday":         {"per": "driver", "label": "Saturday delivery", "NJ": 250, "CA": 250, "SC": 250},
    "triaxle":          {"per": "day", "label": "Triaxle surcharge", "NJ": 75, "SC": 75},
    "bonded":           {"per": "container", "label": "Bonded freight", "NJ": 75, "SC": 75},
    "ocean_terminal":   {"per": "container", "label": "Ocean terminal surcharge", "SC": 100},
}
FREE_DETENTION_HOURS = 2
PER_DIEM_ADMIN = 0.10   # O'Neill adds 10% to per diem it advances (statement email terms)

# Fuel. The lane sheets say "FSC included up to $4.50 per gallon", but the
# FSC matrix tab in the same workbook starts charging above $3.999 (1.2% per
# 10¢). Until O'Neill confirms which one governs, follow the lane sheets: no
# surcharge at or below $4.50; above it, the matrix % for that price band.
FSC_INCLUDED_UP_TO = 4.50
FSC_MATRIX_BASELINE = 4.00     # matrix: 4.01–4.10 → 1.2%, each further 10¢ +1.2%
FSC_STEP = 0.012
FUEL_NOTE = ("O'Neill's lane sheets include fuel up to $4.50/gal, but the FSC matrix in the "
             "same workbook starts at $4.00 — confirm with O'Neill which governs.")


def fsc_matrix_pct(diesel: float) -> float:
    """The matrix % for a diesel price ($4.01–4.10 → 1.2%, $4.41–4.50 → 6.0%, …)."""
    if diesel <= FSC_MATRIX_BASELINE:
        return 0.0
    band = math.ceil(round((diesel - FSC_MATRIX_BASELINE) / 0.10, 6))
    return round(band * FSC_STEP, 4)


def expected_fsc_pct(diesel: Optional[float]) -> Optional[float]:
    if diesel is None:
        return None
    return 0.0 if diesel <= FSC_INCLUDED_UP_TO else fsc_matrix_pct(diesel)


# --------------------------------------------------------------------------
# Charge classification — O'Neill bills from Quantum (TMW); descriptions are
# matched loosely so a re-worded line still lands on the right fee.
# --------------------------------------------------------------------------
CLASSIFY = [
    ("bobtail", r"BOB\s*TAIL"),
    ("fsc", r"FUEL|\bFSC\b"),
    ("per_diem_admin", r"PER\s*DIEM.*(ADMIN|FEE)|ADMIN.*PER\s*DIEM"),
    ("per_diem", r"PER\s*DIEM|DEMURRAGE|DETENTION\s*-\s*CARRIER"),
    ("chassis_pool", r"POOL\s*CHASSIS|CHASSIS.*(POOL|DCLI|TRAC|FLEXI)"),
    ("chassis_oneill", r"CHASSIS"),
    ("prepull", r"PRE\s*-?\s*PULL"),
    ("storage", r"STORAGE"),
    ("offdock_return", r"OFF\s*-?\s*DOCK|DROP\s*RETURN"),
    ("attempted_pickup", r"ATTEMPT|DRY\s*RUN"),
    ("detention", r"DETENTION|WAIT(ING)?\s*TIME|LIVE\s*UNLOAD"),
    ("positioning", r"POSITION|REPOSITION"),
    ("saturday", r"SATURDAY|WEEKEND"),
    ("triaxle", r"TRI\s*-?\s*AXLE"),
    ("bonded", r"BOND"),
    ("ocean_terminal", r"OCEAN\s*TERMINAL|TERMINAL\s*SURCHARGE"),
    ("line_haul", r"LINE\s*HAUL|DRAYAGE|FREIGHT|BASE\s*RATE|FLAT\s*RATE"),
]


def classify(desc: str) -> str:
    d = (desc or "").upper()
    for fee, pat in CLASSIFY:
        if re.search(pat, d):
            return fee
    return "unknown"


# --------------------------------------------------------------------------
# Text parsing
# --------------------------------------------------------------------------
_CONTAINER = re.compile(r"\b([A-Z]{3}[UJZ]\d{7})\b")
_MONEY = r"\$?\s*(\d[\d,]*\.\d{2})"
# "CHASSIS  3.00  25.00  75.00"  /  "LINE HAUL 1 $450.00 $450.00"
_QTY_RATE_AMT = re.compile(r"^\s*([A-Za-z][A-Za-z /&()#'.-]*?)\s+(\d+(?:\.\d+)?)\s+" + _MONEY + r"\s+" + _MONEY + r"\s*$", re.M)
# "FUEL SURCHARGE 6.00% $27.00"
_PCT_AMT = re.compile(r"^\s*([A-Za-z][A-Za-z /&()#'.-]*?)\s+(\d+(?:\.\d+)?)\s*%\s+" + _MONEY + r"\s*$", re.M)
# "LINE HAUL  $450.00"
_DESC_AMT = re.compile(r"^\s*([A-Za-z][A-Za-z /&()#'.-]*?)\s+" + _MONEY + r"\s*$", re.M)
_TOTAL = re.compile(r"(?:INVOICE\s+)?TOTAL(?:\s+DUE)?\s*:?\s*" + _MONEY, re.I)


def parse_text(text: str) -> tuple[list, Optional[float], list]:
    """Return (charges, invoice_total, containers) from invoice text."""
    charges, used = [], set()
    for m in _QTY_RATE_AMT.finditer(text):
        used.add(m.start())
        charges.append(dict(desc=m.group(1).strip(), qty=float(m.group(2)),
                            rate=float(m.group(3).replace(",", "")), amount=float(m.group(4).replace(",", ""))))
    for m in _PCT_AMT.finditer(text):
        used.add(m.start())
        charges.append(dict(desc=m.group(1).strip(), pct=float(m.group(2)) / 100,
                            amount=float(m.group(3).replace(",", ""))))
    for m in _DESC_AMT.finditer(text):
        if m.start() in used or re.search(r"TOTAL|BALANCE|SUBTOTAL|AMOUNT DUE|PAID", m.group(1), re.I):
            continue
        charges.append(dict(desc=m.group(1).strip(), amount=float(m.group(2).replace(",", ""))))
    tm = _TOTAL.findall(text)
    total = float(tm[-1].replace(",", "")) if tm else None
    containers = sorted(set(_CONTAINER.findall(text)))
    return charges, total, containers


# --------------------------------------------------------------------------
# Check
# --------------------------------------------------------------------------
def _money(x: float) -> str:
    return f"${x:,.2f}"


def check_drayage(charges: list, lane: str, total: Optional[float] = None,
                  diesel: Optional[float] = None, containers: Optional[list] = None) -> dict:
    """Check one invoice's charges against the lane's rate sheet."""
    lane = lane.upper()
    if lane not in LANES:
        return dict(status="needs_detail", variance=None, findings=[],
                    report=f"Unknown lane '{lane}' — expected NJ, CA or SC.")
    base = LANES[lane]["base"]
    parts = [f"Drayage check, {LANES[lane]['name']} (base {_money(base)} per container, fuel included "
             f"up to ${FSC_INCLUDED_UP_TO:.2f}/gal)."]
    if containers:
        parts.append(f"Container(s): {', '.join(containers)}.")
    findings, notes, over, unexplained = [], [], 0.0, []
    line_haul_total, line_haul_count = 0.0, 0
    per_diem_total, per_diem_admin_billed = 0.0, None
    fsc_lines = []

    for c in charges:
        fee = classify(c.get("desc", ""))
        amt = round(float(c["amount"]), 2)
        qty = c.get("qty")
        rate = c.get("rate")
        if qty is None:
            qty = 1.0
        if rate is None and "pct" not in c:
            rate = round(amt / qty, 4) if qty else amt
        desc = c.get("desc", "?")

        # Line math on the invoice itself.
        if "pct" not in c and abs(qty * rate - amt) > 0.011:
            findings.append(f"{desc}: {qty:g} × {_money(rate)} is {_money(qty * rate)}, billed {_money(amt)}.")
            over += round(amt - qty * rate, 2)

        if fee == "line_haul":
            line_haul_total += amt
            line_haul_count += qty
            if rate > base + 0.005:
                extra = round(qty * (rate - base), 2)
                over += extra
                findings.append(f"Line haul billed at {_money(rate)}; the {lane} lane rate is {_money(base)} "
                                f"— overcharge {_money(extra)}.")
            elif rate < base - 0.005:
                notes.append(f"Line haul billed at {_money(rate)}, below the {_money(base)} lane rate.")
            parts.append(f"Line haul: {qty:g} × {_money(rate)} = {_money(amt)}.")
        elif fee == "bobtail":
            should = base / 2
            if rate > should + 0.005:
                extra = round(qty * (rate - should), 2)
                over += extra
                findings.append(f"Bobtail billed at {_money(rate)}; half the lane rate is {_money(should)} "
                                f"— overcharge {_money(extra)}.")
            parts.append(f"Bobtail: {qty:g} × {_money(rate)} = {_money(amt)} (half rate is {_money(should)}).")
        elif fee == "fsc":
            fsc_lines.append(amt)   # checked after the loop, once line haul is known
        elif fee == "per_diem":
            per_diem_total += amt
            unexplained.append(f"Per diem {_money(amt)} passed through from the ocean carrier — needs the "
                               "carrier's bill to confirm.")
        elif fee == "per_diem_admin":
            per_diem_admin_billed = (per_diem_admin_billed or 0) + amt
        elif fee in FEES:
            spec = FEES[fee]
            sheet = spec.get(lane)
            if sheet is None:
                unexplained.append(f"{spec['label']} {_money(amt)} — not on the {lane} lane's rate sheet.")
                continue
            allowed = sheet if isinstance(sheet, tuple) else (sheet,)
            if fee == "detention":
                notes.append(f"Detention: {qty:g} hour(s) billed — the first {FREE_DETENTION_HOURS} hours are "
                             "free; confirm the hours exclude them (needs arrival/release times).")
            if fee == "chassis_pool":
                notes.append("Pool chassis billed — O'Neill's own chassis ($25/day) is the expected case; "
                             "ask why a pool chassis was needed.")
            if not any(abs(rate - a) <= 0.005 for a in allowed):
                top = max(allowed)
                if rate > top:
                    extra = round(qty * (rate - top), 2)
                    over += extra
                    findings.append(f"{spec['label']} billed at {_money(rate)}/{spec['per']}; sheet rate is "
                                    f"{_money(top)} — overcharge {_money(extra)}.")
                else:
                    notes.append(f"{spec['label']} billed at {_money(rate)}, below the {_money(top)} sheet rate.")
            unit = spec["per"] if qty == 1 else spec["per"] + "s"
            parts.append(f"{spec['label']}: {qty:g} {unit} × {_money(rate)} = {_money(amt)}.")
        else:
            unexplained.append(f"Unrecognised charge '{desc}' {_money(amt)}.")

    for amt in fsc_lines:
        exp_pct = expected_fsc_pct(diesel)
        if diesel is None:
            unexplained.append(f"Fuel surcharge {_money(amt)} billed — need the EIA diesel price for that "
                               f"week to check it (none is due at or below ${FSC_INCLUDED_UP_TO:.2f}/gal).")
        elif exp_pct == 0:
            over += amt
            findings.append(f"Fuel surcharge {_money(amt)} billed, but diesel was ${diesel:.2f}/gal — at or "
                            f"below ${FSC_INCLUDED_UP_TO:.2f} fuel is included in the lane rate.")
        else:
            should = round(line_haul_total * exp_pct, 2)
            if amt > should + 0.011:
                over += round(amt - should, 2)
                findings.append(f"Fuel surcharge {_money(amt)}; at ${diesel:.2f}/gal the matrix gives "
                                f"{exp_pct:.1%} of {_money(line_haul_total)} line haul = {_money(should)}.")
            else:
                parts.append(f"Fuel surcharge: {_money(amt)} (matrix {exp_pct:.1%} at ${diesel:.2f}/gal).")
        notes.append(FUEL_NOTE)

    if per_diem_admin_billed is not None:
        should = round(per_diem_total * PER_DIEM_ADMIN, 2)
        if per_diem_admin_billed > should + 0.011:
            over += round(per_diem_admin_billed - should, 2)
            findings.append(f"Per diem admin fee {_money(per_diem_admin_billed)}; 10% of {_money(per_diem_total)} "
                            f"per diem is {_money(should)}.")
        else:
            parts.append(f"Per diem admin fee {_money(per_diem_admin_billed)} = 10% of {_money(per_diem_total)}.")
    if line_haul_count == 0 and not any(classify(c.get("desc", "")) == "bobtail" for c in charges):
        notes.append("No line-haul charge on this invoice (accessorial-only bill).")
    if containers and line_haul_count and len(containers) != round(line_haul_count):
        notes.append(f"{len(containers)} container number(s) on the invoice but {line_haul_count:g} "
                     "line-haul move(s) billed.")

    billed = round(sum(float(c["amount"]) for c in charges), 2)
    if total is not None and abs(billed - total) > 0.011:
        unexplained.append(f"Charges add up to {_money(billed)} but the invoice total is {_money(total)}.")
    elif total is not None:
        parts.append(f"Charges add up to {_money(billed)}, which matches the invoice total.")

    parts.extend(findings)
    parts.extend(unexplained)
    parts.extend(dict.fromkeys(notes))   # de-duplicate, keep order
    over = round(over, 2)
    if over > 0.01:
        status = "discrepancy"
        parts.append(f"Overcharge {_money(over)}; payable at contract rates {_money((total or billed) - over)}.")
    elif unexplained or not charges:
        status = "needs_detail"
    else:
        status = "valid"
    return dict(status=status, variance=over if status == "discrepancy" else (0.0 if status == "valid" else None),
                billed=billed, report=" ".join(parts), findings=findings)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="invoice text file (PDF converted to text)")
    src.add_argument("--charges", help="JSON file: [{desc, qty, rate, amount}, …]")
    ap.add_argument("--lane", required=True, choices=["NJ", "CA", "SC", "nj", "ca", "sc"])
    ap.add_argument("--total", type=float, help="invoice total (read from the text when omitted)")
    ap.add_argument("--diesel", type=float, help="EIA national diesel price for the billing week")
    a = ap.parse_args(argv)
    containers = None
    if a.text:
        charges, total, containers = parse_text(open(a.text, encoding="utf-8", errors="replace").read())
        total = a.total if a.total is not None else total
    else:
        charges, total = json.load(open(a.charges)), a.total
    r = check_drayage(charges, a.lane, total, a.diesel, containers)
    print(f"{r['status'].upper()}  variance={r['variance']}\n{r['report']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
