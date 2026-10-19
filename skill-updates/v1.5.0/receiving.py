#!/usr/bin/env python3
"""
Receiving-invoice line check for the US Yusen / Taylored warehouses (v1.5.0).

A receiving ("inbound processing") invoice bills a handful of per-unit fees:
cartons handled in, an admin fee per container, sortation per SKU, LTL / air
freight cartons (with a per-delivery minimum) and container storage per day.
NJ invoices dated before 2026-04-27 also add a 5% "NJ Bill of Rights"
surcharge on the labor lines.

The generic MSA line pass in validate_rate_card.py checks a printed rate
against one flat table of every MSA rate. For receiving that misses three
things this module checks:

  1. **Which warehouse a rate belongs to.** 0.9173 is Fontana's handling-in
     rate; on a New Jersey invoice it is the wrong rate, not a valid one.
  2. **Which rate period applies.** US receiving rates were cut ~8% for the
     June 2026 billing weeks. Before that every receiving rate was 1.087x the
     June rate, which the flat table doesn't know — so all twelve pre-June
     receiving invoices (~$55.9K) sat on needs_detail. After the cut, an old
     rate is an overcharge.
  3. **The NJ surcharge.** Its base must equal the labor lines it sits on, and
     it may only appear while the NJ labor tax was in effect.

Pure stdlib and no BigQuery, so it can be tested on saved invoice text:

    python3 receiving.py <invoice_text_file> <warehouse> <invoice_date> <amount> [notes]
"""

import math
import re
import sys
from datetime import date, datetime, timedelta
from typing import Optional

# --------------------------------------------------------------------------
# Rates — source: Notion "Yusen / Taylored Service — Rate Card 2026",
# "Receiving & handling-in" (June 2026+, = the MSA) and "Rate history —
# pre-June 2026" (receiving rows added 2026-08-12, confirmed to the cent on
# 749279 NJ and 752320 Fontana).
# --------------------------------------------------------------------------
FEE_LABELS = {
    "handling_in": "Handling in",
    "container_admin": "Container admin",
    "sortation": "Sortation",
    "ltl_carton": "LTL/air delivery",
    "ltl_minimum": "LTL/air minimum",
    "container_storage": "Container storage",
}
FEE_UNITS = {
    "handling_in": "cartons", "container_admin": "containers", "sortation": "SKUs",
    "ltl_carton": "cartons", "ltl_minimum": "deliveries", "container_storage": "spot-days",
}

RATES_JUNE_2026 = {
    "fontana": {"handling_in": 0.9173, "container_admin": 52.8831, "sortation": 31.2981,
                "ltl_carton": 0.7728, "ltl_minimum": 72.45, "container_storage": 43.47},
    "new_jersey": {"handling_in": 0.9467, "container_admin": 47.334, "sortation": 29.946,
                   "ltl_carton": 0.7728, "ltl_minimum": 72.45, "container_storage": 43.47},
    "south_carolina": {"handling_in": 0.7728, "container_admin": 47.288, "sortation": 24.15,
                       "ltl_carton": 0.7728, "ltl_minimum": 72.45, "container_storage": 43.47},
}
RATES_PRE_JUNE = {
    # Fontana sortation: the Notion card says 34.0198, but Yusen's own worksheet
    # prints 34.0197 and only 34.0197 reproduces every line to the cent (17 SKUs
    # = $578.33 on 750792; 113 = $3,844.23 on 752320). 34.0198 is a cent high.
    "fontana": {"handling_in": 0.9971, "container_admin": 57.4816, "sortation": 34.0197},
    "new_jersey": {"handling_in": 1.0290, "container_admin": 51.45, "sortation": 32.55},
    "south_carolina": {"handling_in": 0.8400, "container_admin": 51.4021, "sortation": 26.2511},
}
PRE_JUNE_FACTOR = 1.087
# Pre-June rates nobody has seen on a real invoice yet. The card marks all of
# South Carolina's as derived; LTL / minimum / storage were never on the old
# card, so they are derived here the same way. A line that only matches one of
# these is reported but can't make an invoice `valid` on its own.
for _wh, _june in RATES_JUNE_2026.items():
    for _fee in ("ltl_carton", "ltl_minimum", "container_storage"):
        RATES_PRE_JUNE[_wh].setdefault(_fee, round(_june[_fee] * PRE_JUNE_FACTOR, 4))
PROVISIONAL = {("south_carolina", "pre", fee) for fee in RATES_PRE_JUNE["south_carolina"]} | {
    (wh, "pre", fee) for wh in RATES_PRE_JUNE for fee in ("ltl_carton", "ltl_minimum", "container_storage")}

RATE_TABLES = {"june": RATES_JUNE_2026, "pre": RATES_PRE_JUNE}
ERA_NAMES = {"june": "June 2026 rates", "pre": "pre-June rates"}
CUTOVER = date(2026, 6, 1)          # first billing week at the new rates
CUTOVER_GRACE = timedelta(days=14)  # an early-June invoice may still bill late-May weeks
WAREHOUSE_NAMES = {"fontana": "Fontana", "new_jersey": "New Jersey", "south_carolina": "South Carolina"}

# Fallback for when the caller doesn't pass the snapshot's labor_tax block:
# active on invoices dated before 2026-04-27 (see rate-card-snapshot.json).
DEFAULT_NJ_LABOR_TAX = {"rate": 0.05, "active_periods": [{"from": None, "until": "2026-04-27"}]}

# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
_N = r"\d[\d,]*(?:\.\d+)?"
# "RECEIVED CARTONS 9,664 @ 1.0290 $ 9,944.26"   /  "13 @32.5500 $ 423.15"
_AT_LINE = re.compile(r"(?<![\d.,])(" + _N + r")\s*@\s*\$?\s*(\d+(?:\.\d+)?)(?:\s*/\s*[A-Z]+)?\s*\$\s*(\d[\d,]*\.\d{2})")
# Page-1 columns "RECEIVING SORTATION 17 34.01 $ 578.33"
_COL_LINE = re.compile(r"(?<![\d.,$])(" + _N + r")\s+(\d+\.\d+)\s+\$\s*(\d[\d,]*\.\d{2})(?![\d,])")
# Per-container worksheet "NUMBER OF ADDITIONAL SKUS 17 $34.02 $578.33"
_PO_LINE = re.compile(r"(?<![\d.,$])(" + _N + r")\s+\$(\d+\.\d+)\s+\$\s*(\d[\d,]*\.\d{2})(?![\d,])")
# Charge summary "17 RECEIVING SORTATION 34.0197 578.33"
_DESC_LINE = re.compile(r"(?<![\d.,$])(" + _N + r")\s+[A-Z][A-Z /&()#-]*?\s+(\d+\.\d+)\s+(\d[\d,]*\.\d{2})(?![\d,])")
# Yusen sometimes prints the rate as this placeholder; the amount is still real.
PLACEHOLDER_RATES = {99.9999, 999.9999, 9999.9999}
# "NJ BILL OF RIGHTS SURCHARGE $10,830.4560 @5.00% $ 541.52"
_PCT_LINE = re.compile(r"\$?\s*(\d[\d,]*\.\d+)\s*@\s*(\d+(?:\.\d+)?)\s*%\s*\$\s*(\d[\d,]*\.\d{2})")
# Worksheet-only surcharge: "Grand PO Total … NJ Bill of Rights Surcharge $302.65"
_WORKSHEET_SURCHARGE = re.compile(r"Bill of Rights Surcharge\s*\$\s*(\d[\d,]*\.\d{2})", re.I)
# "BETWEEN 03/23/2026 AND 03/31/2026" or "BETWEEN 08/16/26 TO 08/22/26"
_PERIOD = re.compile(r"BETWEEN\s+(\d{1,2}/\d{1,2}/\d{2,4})\s+(?:AND|TO|-)\s+(\d{1,2}/\d{1,2}/\d{2,4})", re.I)


def _f(s: str) -> float:
    return float(s.replace(",", ""))


def _d(s: str) -> Optional[date]:
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def service_period(*texts: str) -> tuple[Optional[date], Optional[date]]:
    """First 'BETWEEN mm/dd/yyyy AND mm/dd/yyyy' found in notes or invoice text."""
    for t in texts:
        m = _PERIOD.search(t or "")
        if m:
            return _d(m.group(1)), _d(m.group(2))
    return None, None


def parse_lines(text: str) -> tuple[list, list]:
    """Return (charge_lines, percent_lines).

    charge_lines are (qty, printed_rate, amount, tier): tier 0 is the invoice
    face's "qty @ rate $ amount" layout, 1 the page-1 column layout, 2 the
    per-container worksheet, 3 the charge summary. The same line is often echoed on a supporting page (sometimes with
    the rate printed shorter), so lines are de-duplicated on (qty, amount),
    keeping the lowest tier."""
    pct = [(_f(a), _f(b), _f(c)) for a, b, c in _PCT_LINE.findall(text)]
    pct_amts = {p[2] for p in pct}
    seen, lines = set(), []
    for tier, pat in enumerate((_AT_LINE, _COL_LINE, _PO_LINE, _DESC_LINE)):
        for a, b, c in pat.findall(text):
            qty, rate, amt = _f(a), _f(b), _f(c)
            if qty <= 0 or rate <= 0 or (qty, amt) in seen:
                continue
            if amt in pct_amts and abs(qty * rate - amt) > 0.05:
                continue  # the surcharge line read as a charge line
            seen.add((qty, amt))
            lines.append((qty, rate, amt, tier))
    seen_p, pct_out = set(), []
    for p in pct:
        if p not in seen_p:
            seen_p.add(p)
            pct_out.append(p)
    return lines, pct_out


def _plausible(qty: float, printed: float, amt: float) -> bool:
    """A real charge line: a card rate reproduces it, or its own math does."""
    if _candidates(qty, printed, amt):
        return True
    if printed in PLACEHOLDER_RATES:
        return bool(_candidates(qty, amt / qty, amt))
    return abs(qty * printed - amt) <= max(0.02, qty * 0.006)


def select_lines(lines: list, pct_lines: list, amount: float) -> list:
    """Pick the set of lines that is the invoice, not its supporting pages.

    Supporting pages repeat charges per container ("NUMBER OF ADDITIONAL SKUS
    19 $34.02 $646.37") underneath the page-1 total, so taking every line
    double-counts. Try the invoice face alone, then add each further layout in
    turn, and use the first set that adds up to the billed total. If none
    does, fall back to the invoice face + page-1 columns and let the residual
    show."""
    surcharge = sum(p[2] for p in pct_lines)
    tiers = []
    for top in (0, 1, 2, 3):
        tiers.append([(q, r, a) for q, r, a, t in lines if t <= top and _plausible(q, r, a)])
    for chosen in tiers:
        if chosen and abs(sum(a for *_x, a in chosen) + surcharge - amount) <= 0.05:
            return chosen
    return tiers[1]


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------
def _printed_as(full: float, printed: float) -> bool:
    """Yusen prints rates in full, truncated to 2dp, or rounded to 2dp."""
    return (abs(printed - full) <= 0.0006
            or abs(math.floor(full * 100) / 100 - printed) <= 0.0011
            or abs(round(full, 2) - printed) <= 0.0011)


LINE_TOLERANCE = 0.011  # qty x full rate must round to the printed amount


def _candidates(qty: float, printed: float, amt: float) -> list:
    """Every (warehouse, era, fee, full_rate) whose qty x rate reproduces the line."""
    out = []
    for era, table in RATE_TABLES.items():
        for wh, fees in table.items():
            for fee, full in fees.items():
                if _printed_as(full, printed) and abs(qty * full - amt) <= LINE_TOLERANCE:
                    out.append((wh, era, fee, full))
    return out


def expected_eras(start: Optional[date], end: Optional[date], inv_date: Optional[date]) -> set:
    if start and end:
        if start >= CUTOVER:
            return {"june"}
        if end < CUTOVER:
            return {"pre"}
        return {"june", "pre"}
    if inv_date:
        if inv_date < CUTOVER:
            return {"pre"}
        if inv_date >= CUTOVER + CUTOVER_GRACE:
            return {"june"}
    return {"june", "pre"}


def labor_tax_rate(labor_tax: Optional[dict], inv_date: Optional[date]) -> float:
    """Same [from, until) rule as validate_rate_card.active_tax_rate()."""
    if not (labor_tax and inv_date):
        return 0.0
    default = labor_tax.get("rate", 0.0)
    for p in labor_tax.get("active_periods", []):
        frm = date.fromisoformat(p["from"]) if p.get("from") else None
        until = date.fromisoformat(p["until"]) if p.get("until") else None
        if (frm is None or inv_date >= frm) and (until is None or inv_date < until):
            return p.get("rate", default)
    return 0.0


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _rate(x: float) -> str:
    """$0.9173, $32.55, $51.45 — full precision without trailing zeros."""
    whole, frac = f"{x:,.4f}".split(".")
    return f"${whole}.{frac.rstrip('0').ljust(2, '0')}"


def check_receiving(text: str, warehouse: str, inv_date: Optional[date], amount: float,
                    notes: str = "", labor_tax: Optional[dict] = None) -> dict:
    """Check one US receiving invoice's lines against its own warehouse's rates.

    Returns {status, variance, expected_amount, line_report, findings}; status is
    valid / discrepancy / needs_detail in the ledger's vocabulary."""
    wh_name = WAREHOUSE_NAMES.get(warehouse, warehouse)
    if warehouse not in RATES_JUNE_2026:
        return dict(status="needs_detail", variance=None, expected_amount=None, findings=[],
                    line_report=f"No US receiving rates for warehouse '{warehouse}'.")
    if labor_tax is None and warehouse == "new_jersey":
        labor_tax = DEFAULT_NJ_LABOR_TAX

    start, end = service_period(notes, text)
    eras = expected_eras(start, end, inv_date)
    raw_lines, pct_lines = parse_lines(text)
    lines = select_lines(raw_lines, pct_lines, amount)

    ok, findings, over, unknown, provisional, anomalies = [], [], 0.0, [], [], 0
    placeholder_lines = 0
    for qty, printed, amt in lines:
        cands = _candidates(qty, printed, amt)
        if not cands and printed in PLACEHOLDER_RATES:
            # Match on the amount alone: which card rate reproduces it exactly?
            cands = [c for c in _candidates(qty, amt / qty, amt)]
            if cands:
                placeholder_lines += 1
        if not cands:
            if abs(qty * printed - amt) <= 0.02:
                unknown.append(f"{qty:,.0f} @ {printed} = {_money(amt)} (rate not on the receiving card)")
            continue
        own_ok = [c for c in cands if c[0] == warehouse and c[1] in eras]
        own_other_era = [c for c in cands if c[0] == warehouse and c[1] not in eras]
        if own_ok:
            # Prefer a confirmed rate over a derived one when both reproduce the line.
            own_ok.sort(key=lambda c: (c[0], c[1], c[2]) in PROVISIONAL)
            wh, era, fee, full = own_ok[0]
            ok.append((qty, full, amt, fee, era))
            if (wh, era, fee) in PROVISIONAL:
                provisional.append(f"{FEE_LABELS[fee].lower()} at {_rate(full)} ({ERA_NAMES[era]}, derived — not yet confirmed on a real invoice)")
            continue
        if own_other_era:
            wh, era, fee, full = own_other_era[0]
            ok.append((qty, full, amt, fee, era))
            should = RATE_TABLES[sorted(eras)[0]][warehouse].get(fee)
            if era == "pre" and should is not None:
                extra = round(qty * (full - should), 2)
                over += extra
                findings.append(
                    f"{FEE_LABELS[fee]} billed at the old pre-June rate {_rate(full)} instead of "
                    f"{_rate(should)} — {qty:,.0f} {FEE_UNITS[fee]}, overcharge {_money(extra)}.")
            else:
                findings.append(
                    f"{FEE_LABELS[fee]} billed at the lower June rate {_rate(full)} on a pre-June "
                    f"period — billed below the card, no action needed.")
            continue
        # Only another warehouse's rate reproduces the line.
        wh, era, fee, full = cands[0]
        ok.append((qty, full, amt, fee, era))
        # When either period could apply, compare against the higher of the two.
        owns = [RATE_TABLES[e][warehouse][fee] for e in eras if fee in RATE_TABLES[e][warehouse]]
        should = max(owns) if owns else None
        if should is not None and full > should + 1e-9:
            extra = round(qty * (full - should), 2)
            over += extra
            findings.append(
                f"{FEE_LABELS[fee]} billed at {WAREHOUSE_NAMES.get(wh, wh)}'s rate {_rate(full)}; "
                f"{wh_name}'s rate is {_rate(should)} — {qty:,.0f} {FEE_UNITS[fee]}, overcharge {_money(extra)}.")
        else:
            # Cheaper than our own rate, so not an overcharge — but another site's
            # rate usually means the invoice is filed under the wrong warehouse.
            anomalies += 1
            findings.append(
                f"{FEE_LABELS[fee]} billed at {WAREHOUSE_NAMES.get(wh, wh)}'s rate {_rate(full)} "
                f"(below {wh_name}'s {_rate(should) if should else 'n/a'}) — check the warehouse on this invoice.")

    # ---- NJ surcharge -------------------------------------------------------
    labor_base = sum(q * f for q, f, _a, _fee, _e in ok)
    surcharge_total, tax_rate = 0.0, labor_tax_rate(labor_tax, inv_date) if warehouse == "new_jersey" else 0.0
    surcharge_note = ""
    for base, pct, amt in pct_lines:
        surcharge_total += amt
        if not tax_rate or abs(pct / 100 - tax_rate) > 1e-6:
            when = inv_date.isoformat() if inv_date else "this date"
            findings.append(f"{pct:g}% surcharge of {_money(amt)} billed, but no NJ labor surcharge applies "
                            f"for {wh_name} on {when} (it ended with invoices dated 2026-04-27).")
            over += amt
            continue
        if abs(round(base * pct / 100, 2) - amt) > 0.011:
            findings.append(f"Surcharge math is off: {pct:g}% of {_money(base)} is "
                            f"{_money(base * pct / 100)}, billed {_money(amt)}.")
            over += round(amt - base * pct / 100, 2)
        elif abs(base - labor_base) > 0.05:
            findings.append(f"Surcharge base {_money(base)} doesn't match the receiving lines "
                            f"({_money(labor_base)}).")
            over += round(amt - labor_base * pct / 100, 2)
        else:
            surcharge_note = (f"NJ labor surcharge {pct:g}% of {_money(base)} = {_money(amt)} "
                              f"(in effect for this invoice date).")
    ws = _WORKSHEET_SURCHARGE.search(text)
    if ws and not pct_lines:
        surcharge_note = (f"The worksheet shows an NJ Bill of Rights surcharge of {_money(_f(ws.group(1)))}, "
                          "but it is not on the invoice and not in the total — not billed.")
    if tax_rate and not pct_lines and ok:
        findings.append(f"No {tax_rate * 100:g}% NJ labor surcharge on this invoice although it was in effect "
                        f"for this date — billed below the card, no action needed.")

    explained = round(sum(a for _q, _r, a, _fee, _e in ok) + surcharge_total, 2)
    residual = round(amount - explained, 2)

    # ---- Report --------------------------------------------------------------
    period = (f"{start:%m/%d}–{end:%m/%d/%Y}" if start and end else
              (inv_date.isoformat() if inv_date else "period unknown"))
    era_txt = " or ".join(ERA_NAMES[e] for e in sorted(eras))
    parts = [f"Receiving check for {wh_name}, {period}, against {era_txt}."]
    for q, f, a, fee, era in sorted(ok, key=lambda z: -z[2]):
        unit = FEE_UNITS[fee] if q != 1 else FEE_UNITS[fee].rstrip("s").replace("deliverie", "delivery")
        parts.append(f"{FEE_LABELS[fee]}: {q:,.0f} {unit} × {_rate(f)} = {_money(a)}.")
    if surcharge_note:
        parts.append(surcharge_note)
    cartons = sum(q for q, _f2, _a, fee, _e in ok if fee == "handling_in")
    containers = sum(q for q, _f2, _a, fee, _e in ok if fee == "container_admin")
    if placeholder_lines:
        parts.append(f"The invoice prints the rate as 99.9999 on {placeholder_lines} line(s); "
                     "each amount was matched to the card rate that reproduces it exactly.")
    fees_billed = {fee for *_x, fee, _e in ok}
    if {"ltl_carton", "ltl_minimum"} <= fees_billed:
        parts.append("Both the LTL/air minimum and per-carton LTL charges are billed — fine if they are "
                     "different deliveries; the minimum replaces the per-carton charge for a single delivery.")
    if cartons and containers:
        parts.append(f"About {cartons / containers:,.0f} cartons per container.")
    for u in unknown:
        parts.append(f"Unrecognised line: {u}.")
    for p in provisional:
        parts.append(f"Provisional rate used: {p}.")
    parts.extend(findings)
    if not ok and not pct_lines:
        parts.append("No receiving charge lines could be read from the invoice.")
    elif abs(residual) <= 0.05:
        parts.append(f"Lines add up to {_money(explained)}, which matches the billed total.")
    else:
        parts.append(f"Lines add up to {_money(explained)} but the invoice total is {_money(amount)} — "
                     f"{_money(abs(residual))} {'unexplained' if residual > 0 else 'more in lines than billed'}.")

    over = round(over, 2)
    if over > 0.01:
        status, variance = "discrepancy", over
        parts.append(f"Overcharge {_money(over)}; payable at contract rates {_money(amount - over)}.")
    elif not ok or abs(residual) > 0.05 or unknown or provisional or anomalies:
        status, variance = "needs_detail", None
    else:
        status, variance = "valid", 0.0
    return dict(status=status, variance=variance,
                expected_amount=round(amount - over, 2) if status != "needs_detail" else None,
                line_report=" ".join(parts), findings=findings)


def main(argv: list) -> int:
    if len(argv) < 5:
        print(__doc__)
        return 2
    path, wh, d, amt = argv[1:5]
    notes = argv[5] if len(argv) > 5 else ""
    text = open(path, encoding="utf-8", errors="replace").read()
    r = check_receiving(text, wh, date.fromisoformat(d), float(amt), notes)
    print(f"{r['status'].upper()}  variance={r['variance']}\n{r['line_report']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
