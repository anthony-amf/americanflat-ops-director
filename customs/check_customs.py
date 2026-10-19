#!/usr/bin/env python3
"""
Customs entry check — CBP 7501 entry summaries filed by WWL (Worldwide
Logistics), our customs broker.

How customs is billed today: for each container WWL emails the ACE cargo
release, the CBP Form 7501 entry summary and its own brokerage (CHB) invoice
(CLA… numbers). The duty itself is paid to CBP through bill.com as a bill
from "Bureau of Customs and Border Protection" keyed by the entry number
(8NW-…, NYS-…), approved by Mahjoub.

What this checks on one entry:
  1. Line math — each duty line = entered value × the rate printed beside it
     (the product's own tariff code, and any Chapter 99 add-on: Sec 301
     9903.88.xx, reciprocal 9903.01.xx, …).
  2. Port fees — MPF = 0.3464% of the total entered value, inside the
     fiscal-year minimum and maximum; HMF = 0.125% of value (ocean only).
  3. Totals — duty + fees on the 7501 = its stated total = the bill.com bill.
  4. Rates against our duty sheet (customs/us_duty_rates.csv, from the
     "Inbound Customs Data" tab) — the product's base rate and, for China,
     the Sec 301 rate. A difference here is reported for review, not as an
     overcharge: the official tariff schedule wins over our sheet, and the
     sheet itself flags several of its own rows as wrong.

Statuses follow the Yusen ledger: valid / discrepancy / needs_detail.
A math or total error is a discrepancy; a rate that differs from our sheet,
or anything we can't confirm, is needs_detail.

Input is a JSON entry (see test_check_customs.py for the shape):

    python3 check_customs.py entry.json [--bill 4040.79]
"""

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
MPF_RATE = 0.003464
HMF_RATE = 0.00125
# MPF minimum / maximum per formal entry, by US government fiscal year
# (Oct 1 – Sep 30). CBP republishes these every year — add the new year
# when it is announced; until then an entry in an unknown year is checked
# against the rate only and a fee at either cap is flagged for review.
MPF_LIMITS = {
    2025: (32.71, 634.62),
    2026: (33.58, 651.50),
}
CENT = 0.011


def _fy(d: date) -> int:
    return d.year + 1 if d.month >= 10 else d.year


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _norm_hts(h: str) -> str:
    digits = "".join(ch for ch in (h or "") if ch.isdigit())
    return f"{digits[:4]}.{digits[4:6]}.{digits[6:10]}" if len(digits) >= 8 else (h or "").strip()


def load_sheet(path: Optional[Path] = None) -> dict:
    """hts -> list of sheet rows (several products can share one code)."""
    sheet = {}
    with open(path or HERE / "us_duty_rates.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sheet.setdefault(_norm_hts(r["hts"]), []).append(r)
    return sheet


def check_entry(entry: dict, bill_amount: Optional[float] = None, sheet: Optional[dict] = None) -> dict:
    sheet = sheet if sheet is not None else load_sheet()
    findings, review, notes = [], [], []
    over = 0.0
    entry_no = entry.get("entry_number", "?")
    try:
        entry_date = date.fromisoformat(entry["entry_date"]) if entry.get("entry_date") else None
    except ValueError:
        entry_date = None
    ocean = (entry.get("mode") or "ocean").lower() == "ocean"
    parts = [f"Customs entry {entry_no}"
             + (f", {entry_date.isoformat()}" if entry_date else "")
             + (f", port {entry['port']}" if entry.get("port") else "") + "."]

    total_value, total_duty = 0.0, 0.0
    for i, line in enumerate(entry.get("lines", []), 1):
        value = float(line["entered_value"])
        total_value += value
        hts = _norm_hts(line.get("hts", ""))
        origin = (line.get("origin") or "").upper()
        line_duty = 0.0
        charged = {}
        for ch in line.get("charges", []):
            code = _norm_hts(ch.get("code") or hts)
            rate = float(ch.get("rate_pct", 0)) / 100
            amt = round(float(ch["amount"]), 2)
            line_duty += amt
            charged[code] = rate
            should = round(value * rate, 2)
            if abs(amt - should) > CENT + 0.005:
                findings.append(f"Line {i} ({hts}) {code}: {rate:.2%} of {_money(value)} is {_money(should)}, "
                                f"entry shows {_money(amt)}.")
                over += round(amt - should, 2)
        total_duty += line_duty
        desc = line.get("description", "")
        parts.append(f"Line {i}: {hts}{' ' + desc if desc else ''}, {origin or 'origin ?'}, value "
                     f"{_money(value)}, duty {_money(line_duty)} ("
                     + ", ".join(f"{c} {r:.2%}" for c, r in charged.items()) + ").")

        # Rates vs our duty sheet.
        rows = sheet.get(hts)
        if not rows:
            review.append(f"Line {i}: tariff code {hts} isn't on our duty sheet — confirm the product and rate.")
            continue
        names = ", ".join(r["product_type"] for r in rows)
        mfn = float(rows[0]["mfn_pct"]) / 100
        if hts in charged and abs(charged[hts] - mfn) > 0.0001:
            review.append(f"Line {i}: {hts} ({names}) charged at {charged[hts]:.2%}; our sheet says {mfn:.2%}.")
        if origin in ("CN", "CHINA"):
            s301 = float(rows[0]["sec301_china_pct"]) / 100
            billed_301 = sum(r for c, r in charged.items() if c.startswith("9903.88"))
            if abs(billed_301 - s301) > 0.0001:
                review.append(f"Line {i}: Sec 301 charged at {billed_301:.2%}; our sheet says {s301:.2%} for "
                              f"{names}.")
        recip = {c: r for c, r in charged.items() if c.startswith("9903.01") or c.startswith("9903.02")}
        if recip:
            review.append(f"Line {i}: reciprocal (IEEPA) tariff charged — "
                         + ", ".join(f"{c} {r:.2%}" for c, r in recip.items())
                         + ". Our sheet lists these as paused; confirm they apply on this entry date.")
        for r in rows:
            if r.get("sheet_note"):
                notes.append(f"{r['product_type']}: {r['sheet_note']}")

    # ---- Port fees -----------------------------------------------------------
    mpf = entry.get("mpf")
    if mpf is not None:
        mpf = round(float(mpf), 2)
        raw = total_value * MPF_RATE
        limits = MPF_LIMITS.get(_fy(entry_date)) if entry_date else None
        if limits:
            should = round(min(max(raw, limits[0]), limits[1]), 2)
            if abs(mpf - should) > CENT + 0.005:
                findings.append(f"MPF {_money(mpf)}; 0.3464% of {_money(total_value)} within the "
                                f"{_money(limits[0])}–{_money(limits[1])} limits is {_money(should)}.")
                over += round(mpf - should, 2)
            else:
                parts.append(f"MPF {_money(mpf)} = 0.3464% of {_money(total_value)}"
                             + (" (at the cap)" if should in limits else "") + ".")
        else:
            if abs(mpf - round(raw, 2)) <= CENT + 0.005:
                parts.append(f"MPF {_money(mpf)} = 0.3464% of {_money(total_value)}.")
            elif mpf < raw:
                review.append(f"MPF {_money(mpf)} is below 0.3464% of {_money(total_value)} "
                              f"({_money(raw)}) — probably the yearly cap; this fiscal year's cap isn't loaded.")
            else:
                review.append(f"MPF {_money(mpf)} is above 0.3464% of {_money(total_value)} "
                              f"({_money(raw)}) — probably the yearly minimum; this year's limits aren't loaded.")
    hmf = entry.get("hmf")
    if hmf is not None:
        hmf = round(float(hmf), 2)
        if not ocean:
            findings.append(f"HMF {_money(hmf)} charged on a non-ocean entry.")
            over += hmf
        else:
            should = round(total_value * HMF_RATE, 2)
            if abs(hmf - should) > CENT + 0.005:
                findings.append(f"HMF {_money(hmf)}; 0.125% of {_money(total_value)} is {_money(should)}.")
                over += round(hmf - should, 2)
            else:
                parts.append(f"HMF {_money(hmf)} = 0.125% of {_money(total_value)}.")
    elif ocean:
        notes.append("No HMF on an ocean entry — fine if CBP waived it, otherwise the entry is incomplete.")

    computed = round(total_duty + (mpf or 0) + (hmf or 0), 2)
    stated = entry.get("total")
    if stated is not None and abs(float(stated) - computed) > CENT:
        findings.append(f"Entry total {_money(float(stated))} but duty + fees add up to {_money(computed)}.")
        over += round(float(stated) - computed, 2)
    else:
        parts.append(f"Duty {_money(total_duty)} + fees = {_money(computed)}"
                     + (", matching the entry total." if stated is not None else "."))
    if bill_amount is not None:
        base = float(stated) if stated is not None else computed
        if abs(bill_amount - base) > CENT:
            diff = round(bill_amount - base, 2)
            findings.append(f"bill.com bill {_money(bill_amount)} vs entry total {_money(base)} — "
                            f"{'over' if diff > 0 else 'under'} by {_money(abs(diff))}.")
            if diff > 0:
                over += diff
        else:
            parts.append(f"bill.com bill {_money(bill_amount)} matches the entry.")

    parts += findings + review + list(dict.fromkeys(notes))
    over = round(over, 2)
    if findings and over > 0.01:
        status = "discrepancy"
        parts.append(f"Over by {_money(over)}.")
    elif findings or review or not entry.get("lines"):
        status = "needs_detail"
    else:
        status = "valid"
    return dict(status=status, variance=over if status == "discrepancy" else (0.0 if status == "valid" else None),
                entered_value=round(total_value, 2), duty=round(total_duty, 2),
                report=" ".join(parts), findings=findings, review=review)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entry", help="JSON file with one entry")
    ap.add_argument("--bill", type=float, help="the bill.com amount for this entry number")
    a = ap.parse_args(argv)
    r = check_entry(json.load(open(a.entry)), a.bill)
    print(f"{r['status'].upper()}  variance={r['variance']}\n{r['report']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
