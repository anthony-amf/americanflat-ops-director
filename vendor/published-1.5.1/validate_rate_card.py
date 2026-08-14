#!/usr/bin/env python3
"""
Rate Card Validator for Yusen / Taylored Service freight invoices.

Validates the billed amount on an invoice against the contracted rate card.
Rates are NOT hardcoded here — they are loaded from a JSON file so the caller
can supply a fresh copy pulled live from the Notion rate card. When no rates
file is supplied, falls back to the bundled snapshot (and says so loudly).

Validation depth (intentionally header-level for now):
  - Admin   -> weekly fee, pro-rated for partial weeks (5 business days = full week)
  - Storage -> per-pallet rate x pallet count (needs line items for pallet count)
  - VAS / Small Parcel / LTL -> total reported; flagged "needs detail" because a
    real check requires itemized hours/units, which the header row doesn't carry.

Usage:
    python validate_rate_card.py 752857 --rates /tmp/rates.json
    python validate_rate_card.py 752857                 # uses bundled snapshot
    python validate_rate_card.py --list-all --rates /tmp/rates.json
    python validate_rate_card.py 752857 --rates /tmp/rates.json --json
"""

import json
import os
import re
import sys
import argparse
from datetime import date
from pathlib import Path
from typing import Any, Optional

from google.cloud import bigquery

PROJECT = "americanflat"
TABLE = "americanflat.finance.yusen_invoices"
SNAPSHOT = Path(__file__).resolve().parent.parent / "references" / "rate-card-snapshot.json"

# Maps the free-text warehouse value in BigQuery to a rate-card key.
WAREHOUSE_MAP = {
    "fontana": ["fontana", "ts west", "ca west"],
    "new_jersey": ["new jersey", "nj", "ts east"],
    # Taylored's southern DC bills as "SAVANNAH" — same facility as TS South (SC).
    "south_carolina": ["south carolina", "savannah", "ts south", "sc"],
    "canada": ["canada", "yusen ca", "ts canada"],
    "netherlands": ["netherlands", "moerdijk", "benelux", "schiphol", "yusen nl"],
}


def load_rates(rates_path: Optional[str]) -> tuple[dict, str]:
    """Return (rate_card, source_label). Prefer the caller-supplied live file."""
    if rates_path:
        with open(rates_path) as f:
            return json.load(f), f"live ({rates_path})"
    with open(SNAPSHOT) as f:
        return json.load(f), f"BUNDLED SNAPSHOT — may be stale ({SNAPSHOT.name})"


def normalize_warehouse(warehouse_name: str) -> Optional[str]:
    """Map a free-text warehouse value to a rate-card key.

    Short codes (≤3 chars like "sc"/"nj") match only as whole tokens — a naive
    substring match would route "Schiphol" (NL) to south_carolina via "sc".
    Longer aliases still match as substrings so multi-word names work.
    """
    if not warehouse_name:
        return None
    n = warehouse_name.lower().strip()
    tokens = set(re.split(r"[^a-z0-9]+", n))
    for key, aliases in WAREHOUSE_MAP.items():
        for alias in aliases:
            if len(alias) <= 3:
                if alias in tokens:
                    return key
            elif alias in n:
                return key
    return None


def _as_date(value) -> Optional[date]:
    """Coerce a BigQuery date (date object or 'YYYY-MM-DD' string) to a date."""
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def parse_intl_breakdown(notes: str):
    """Parse an international invoice's notes breakdown.

    Format (one row per charge type, EUR for NL / USD for Canada), e.g.:
      'Storage: EUR 13,526.31 | Storage=13,526.31'
      'VAS: USD 9,436.28 | Consumables=212.24, Val=9,224.04'
      'Storage: USD 8,429.00 | Storage Charge - April 2025=6,737.00, Warehouse Charge=1,692.00'

    Returns (currency, total, [(name, value), ...]) or None. Components are
    separated by ', ' (the thousands separator inside amounts has no space, so it
    doesn't collide); each component is 'name=amount'.
    """
    if not notes or "|" not in notes:
        return None
    head, comps = notes.split("|", 1)
    m = re.search(r"\b(EUR|USD|CAD)\b\s*([\d,]+\.\d{2}|[\d,]+)", head)
    if not m:
        return None
    try:
        total = float(m.group(2).replace(",", ""))
    except ValueError:
        return None
    items = []
    for part in comps.split(", "):
        if "=" in part:
            name, val = part.rsplit("=", 1)
            try:
                items.append((name.strip(), float(val.replace(",", "").strip())))
            except ValueError:
                pass
    return (m.group(1), total, items) if items else None


def active_tax_rate(tax: Optional[dict], inv_date: Optional[date]) -> float:
    """Return the labor-tax rate in effect for an invoice date, else 0.0.

    `tax` carries a default `rate` and a list of `active_periods`, each a
    [from, until) interval (from=null → open start, until=null → open-ended). An
    interval may override `rate`. The tax can switch on and off over time — to
    re-activate it later, just add another interval; no code change needed.
    """
    if not (tax and inv_date):
        return 0.0
    default = tax.get("rate", 0.0)
    for p in tax.get("active_periods", []):
        frm = _as_date(p.get("from")) if p.get("from") else None
        until = _as_date(p.get("until")) if p.get("until") else None
        if (frm is None or inv_date >= frm) and (until is None or inv_date < until):
            return p.get("rate", default)
    return 0.0


# "4,101 x 0.9173 recv carton" / "82 X 31.2981" / "173 @ $10.00 pallet all-in"
_DETAIL_LINE = re.compile(
    r"^\s*([\d,]+(?:\.\d+)?)\s*(?:[xX×@]|@)\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(.*?)\s*$")


def parse_detail(text: str) -> list[tuple[float, float, str]]:
    """Parse 'QTY x RATE [label]' items separated by ; or newline into triples.

    Raises ValueError naming the offending item, because a silently dropped line
    would under-count the expected total and read as an overbilling.
    """
    out = []
    for raw in re.split(r"[;\n]+", text or ""):
        item = raw.strip().rstrip(".,")
        if not item:
            continue
        m = _DETAIL_LINE.match(item)
        if not m:
            raise ValueError(
                f"can't read '{item}' — expected 'QTY x RATE [label]', e.g. '4101 x 0.9173 recv carton'")
        qty = float(m.group(1).replace(",", ""))
        rate = float(m.group(2).replace(",", ""))
        out.append((qty, rate, m.group(3).strip()))
    if not out:
        raise ValueError("no line items found")
    return out


def _compare_rates_to_card(lines, rates: dict, t: str, wh: str) -> list[str]:
    """Note supplied rates that sit off the card. Storage only, where the card
    carries a single unambiguous per-pallet number; the per-fee tables are keyed
    by fee name and can't be matched from a free-text label without guessing.

    Below the card is a STALE-CARD flag, not a dispute — US storage was cut in
    ~May 2026 and the Notion page still shows the old numbers. Above the card is
    the one that needs a human.
    """
    if t != "storage":
        return []
    card = (rates.get("storage") or {}).get(wh)
    if not isinstance(card, (int, float)):
        return []
    # Only the line carrying the most dollars — a storage invoice also has ancillary
    # lines on a different basis (per-bin at $0.73), and holding those up against a
    # per-pallet card rate produces confident nonsense.
    qty, rate, label = max(lines, key=lambda l: l[0] * l[1])
    if abs(rate - card) <= 0.005:
        return []
    where = f" on the {label} line" if label else ""
    if rate < card:
        return [f"Rate card: billed ${rate:,.6g}/pallet{where} is BELOW the card's ${card:,.2f} — "
                f"expected (US storage was cut ~May 2026 and the Notion card still shows the old "
                f"number). Stale card, not a dispute."]
    return [f"Rate card: billed ${rate:,.6g}/pallet{where} is ABOVE the card's ${card:,.2f} "
            f"on {qty:,.6g} pallets — verify against the signed rate sheet before paying."]


def validate(invoice: dict, rates: dict) -> dict:
    """Compare one invoice's billed amount to the rate card."""
    invoice_number = invoice["invoice_number"]
    invoice_type = (invoice.get("type_of_invoice") or "").strip()
    warehouse_raw = invoice.get("warehouse") or ""
    amount = float(invoice.get("amount") or 0)
    period_text = invoice.get("bill_period") or ""

    wh = normalize_warehouse(warehouse_raw)
    result = {
        "invoice_number": invoice_number,
        "invoice_type": invoice_type,
        "warehouse_raw": warehouse_raw,
        "warehouse": wh,
        "period": period_text,
        "date": str(invoice.get("date") or ""),
        "billed_amount": amount,
        "expected_amount": None,
        "variance": None,
        "variance_percent": None,
        "status": "valid",
        "paid_at": str(invoice["paid_at"]) if invoice.get("paid_at") else None,
        "discrepancies": [],
    }

    if not wh:
        result["status"] = "error"
        result["discrepancies"].append(f"Unknown warehouse: '{warehouse_raw}' — not in rate card")
        return result

    # ---- Supplied line detail (--detail) ----
    # Every invoice family here bills the same shape: a sum of quantity x rate. The
    # header row carries only the total, which is the sole reason 66 rows sit at
    # needs_detail. When someone reads the lines off the worksheet and hands them
    # over, validate against those instead of the header and the row can close.
    #
    # Deliberately qty AND rate, never qty alone: US storage has billed BELOW the
    # Notion card since ~May 2026 (NJ 4.34 vs card 5.98, Fontana 4.47 vs 5.90), so
    # multiplying a supplied pallet count by the card rate would invent a ~25%
    # discrepancy on every storage invoice. The supplied rate is what was billed;
    # comparing it to the card is a separate, clearly-labelled line below.
    if invoice.get("_detail_lines"):
        lines = invoice["_detail_lines"]
        expected = round(sum(q * r for q, r, _ in lines), 2)
        _set_variance(result, amount, expected)
        shown = "; ".join(
            f"{q:,.6g} x {r:,.6g}{(' ' + lbl) if lbl else ''} = ${q * r:,.2f}" for q, r, lbl in lines)
        result["detail_lines"] = shown
        verb = "reconciles to" if result["status"] == "valid" else "does NOT match"
        result["discrepancies"].append(
            f"Supplied detail {verb} the billed total: {len(lines)} line(s) summing to "
            f"${expected:,.2f} vs billed ${amount:,.2f}. {shown}")
        for note in _compare_rates_to_card(lines, rates, invoice_type.lower(), wh):
            result["discrepancies"].append(note)
        return result

    # International invoices (Yusen NL = EUR, Yusen Canada = USD) come one row per
    # charge type with a breakdown in `notes`, in their own currency. The flat
    # USD rate-card math doesn't apply; instead verify internal consistency — the
    # breakdown components must sum to the billed amount. Per-unit rate checks
    # need counts (pallet-weeks / admin hours / cartons) the header lacks, so a
    # consistent invoice is needs_detail, an inconsistent one is a discrepancy.
    if wh in ("canada", "netherlands"):
        sym = {"EUR": "€", "USD": "$", "CAD": "C$"}
        default_cur = "EUR" if wh == "netherlands" else "USD"
        bd = parse_intl_breakdown(invoice.get("notes"))
        if bd:
            cur, total, items = bd
            s = sym.get(cur, "")
            comp_sum = round(sum(v for _, v in items), 2)
            breakdown_str = ", ".join(f"{n}={s}{v:,.2f}" for n, v in items)
            if abs(comp_sum - total) > 0.01 or abs(total - amount) > 0.01:
                result["status"] = "discrepancy"
                result["expected_amount"] = comp_sum
                result["variance"] = round(amount - comp_sum, 2)
                result["discrepancies"].append(
                    f"{invoice_type} ({cur}): breakdown [{breakdown_str}] sums to {s}{comp_sum:,.2f}, "
                    f"notes total {s}{total:,.2f}, billed {s}{amount:,.2f} — mismatch.")
            else:
                result["status"] = "needs_detail"
                vat_note = " NL totals are EUR + 21% VAT." if wh == "netherlands" else ""
                result["discrepancies"].append(
                    f"{invoice_type} ({cur}): breakdown sums correctly to {s}{amount:,.2f} "
                    f"[{breakdown_str}]. Per-unit rate check needs counts "
                    f"(pallet-weeks / admin hours / cartons).{vat_note}")
        else:
            result["status"] = "needs_detail"
            result["discrepancies"].append(
                f"{invoice_type} — {default_cur} intl invoice with no parseable breakdown in notes; "
                f"validate against the contract detail.")
        return result

    t = invoice_type.lower()

    # ---- Admin: flat weekly fee. NJ carried a 5% labor tax before May 2026.
    # The bill_period text can't be trusted for duration (single dates carry none;
    # even "Week of May 25" was a 4-day week — May 25 2026 is Memorial Day). So we
    # only call an exact full-week match `valid`; anything BELOW is needs_detail
    # (partial week / holiday — unprovable from the header), and only billing
    # ABOVE a full week is a real discrepancy (overbilling). ----
    if t == "admin":
        adm = rates.get("admin_vas", {}).get(wh) or {}
        base_weekly = adm.get("weekly")
        if base_weekly is None:
            result["status"] = "error"
            result["discrepancies"].append(f"No admin weekly rate for {wh}")
            return result

        # Labor tax that switches on/off over time (e.g. NJ 5%, dropped 2026-04-27).
        expected = base_weekly
        tax = adm.get("labor_tax")
        tax_note = ""
        rate = active_tax_rate(tax, _as_date(invoice.get("date")))
        if rate:
            expected = round(base_weekly * (1 + rate), 2)
            tax_note = f" (incl. {rate * 100:.0f}% labor tax)"

        if abs(amount - expected) <= 0.01:
            _set_variance(result, amount, expected)  # exact full week → valid
        elif amount > expected + 0.01:
            _set_variance(result, amount, expected)  # over a full week → discrepancy
            result["discrepancies"].append(
                f"Admin: billed ${amount:,.2f} exceeds full week ${expected:,.2f}{tax_note} — overbilled.")
        else:
            # Below a full week: partial week, holiday, or (for NJ) a missing tax.
            # Can't confirm billed days from the header → needs_detail, not a flag.
            result["expected_amount"] = expected
            result["variance"] = round(amount - expected, 2)
            result["variance_percent"] = round(result["variance"] / expected * 100, 1) if expected else 0.0
            result["status"] = "needs_detail"
            daily = base_weekly / 5
            if tax_note and abs(amount - base_weekly) <= 0.01:
                result["discrepancies"].append(
                    f"Admin: billed ${amount:,.2f} = full base week WITHOUT the {rate * 100:.0f}% labor tax "
                    f"that applied for this date (expected ${expected:,.2f}). Confirm whether tax applies.")
            else:
                implied = amount / daily if daily else 0
                result["discrepancies"].append(
                    f"Admin: billed ${amount:,.2f} vs full week ${expected:,.2f}{tax_note}; "
                    f"≈ {implied:.1f} business days at ${daily:,.2f}/day. Period '{period_text}' doesn't "
                    f"confirm duration — verify billed days (partial weeks/holidays are common).")
        return result

    # ---- Storage: per-pallet x count (count comes from line items) ----
    if t == "storage":
        rate = rates.get("storage", {}).get(wh)
        if rate is None:
            result["status"] = "error"
            result["discrepancies"].append(f"No storage rate for {wh}")
            return result
        pallets = invoice.get("pallet_count")
        if not pallets:
            result["status"] = "needs_detail"
            result["discrepancies"].append(
                f"Storage rate is ${rate:,.2f}/pallet for {wh}, but pallet count is "
                f"not on the invoice header. Provide pallet_count (from the invoice "
                f"detail) to validate ${amount:,.2f}."
            )
            return result
        expected = round(pallets * rate, 2)
        _set_variance(result, amount, expected)
        if result["status"] == "discrepancy":
            result["discrepancies"].append(
                f"Storage: {pallets} pallets x ${rate:,.2f} = ${expected:,.2f}, billed ${amount:,.2f}"
            )
        return result

    # ---- VAS / Small Parcel / LTL: header total only ----
    # A real check needs itemized hours (VAS) or per-fee units (SP/LTL), which
    # the header row doesn't carry. Report rather than guess.
    result["status"] = "needs_detail"
    hint = {
        "vas": "VAS bills at an hourly rate; provide hours from the invoice detail.",
        "smlprcl/ltl": "Small Parcel/LTL bills per fee (carton, pick, pallet, BOL); provide itemized counts.",
    }.get(t, "Provide itemized invoice detail to validate this charge against per-fee rates.")
    result["discrepancies"].append(
        f"{invoice_type}: header total ${amount:,.2f} recorded. {hint}"
    )
    return result


# ---- MSA-conflict detection (2026 MSA, eff. 01/01/2026) ----
# Charges Yusen keeps billing that conflict with the signed MSA. Detection is
# text-based over the invoice notes/line text, so it catches the VAS-style
# headers that carry line detail ("10 PALLETS W/SHRINKWRAP @ $14.317/PALLET")
# and any richer line text a deep pass stores. Each rule yields a description
# and, where the qty×rate is parseable, the disputed dollar amount.
_QTY = r"([\d,]+)"                      # quantity, possibly comma-grouped
_SEP = r"\s*(?:[X×x@]|@)?\s*\$?"        # "134 x 4.347" / "10 ... @ $14.317"

MSA_CONFLICT_RULES = [
    # AF-9: national pallet rate is $10.00 all-in INCLUDING wrap; a separate
    # NJ stretchwrap line at the 4.34–4.35 wrap rate double-bills the wrap.
    ("new_jersey", re.compile(rf"STRETCH\s*WRAP\W*(?:STD)?\D{{0,30}}?{_QTY}{_SEP}(4\.3[45]\d?)", re.I),
     "AF-9: STRETCHWRAP billed separately — the $10.00 national pallet rate is all-in incl. wrap"),
    # AF-7: Per Pack Out was removed per Yusen 4/28; PACK CARTON @ 0.92 is it.
    ("new_jersey", re.compile(rf"PACK\s*CARTON\D{{0,30}}?{_QTY}{_SEP}(0\.92)", re.I),
     "AF-7: PACK CARTON pack-out charge — removed per Yusen 4/28"),
    # AF-9 (Fontana/SC form): 14.317 pallet rate embeds a 4.317 wrap component.
    ("fontana|south_carolina", re.compile(rf"{_QTY}\s*PALLETS?\s*W/?\s*SHRINK\s*WRAP\s*@?\s*\$?(14\.317)", re.I),
     "AF-9: wrap component embedded in 14.317 pallet rate — $10.00 is all-in"),
]
# Fontana "PICK & PACK ECOM" bills EVERY pick where the MSA line is "Per
# Additional Ecom Pick" — needs an additional-only recompute from the
# supporting worksheet, so it disputes without a computable amount.
_PICK_PACK_ECOM = re.compile(r"PICK\s*&?\s*PACK\s*ECOM", re.I)


def detect_msa_conflicts(text: str, wh: str) -> list[tuple[str, Optional[float]]]:
    """Return [(description, disputed_amount_or_None), ...] for known conflicts."""
    found = []
    if not text:
        return found
    for wh_pat, rx, why in MSA_CONFLICT_RULES:
        if wh not in wh_pat.split("|"):
            continue
        for m in rx.finditer(text):
            qty = float(m.group(1).replace(",", ""))
            rate = float(m.group(2))
            # The disputed piece of a 14.317 pallet line is only the embedded
            # 4.317 wrap component; the other rules dispute the full line.
            per_unit = 4.317 if rate == 14.317 else rate
            amt = round(qty * per_unit, 2)
            found.append((f"{why} — {m.group(1)} × {per_unit} = ${amt:,.2f} disputed", amt))
    if wh == "fontana" and _PICK_PACK_ECOM.search(text):
        found.append((
            "MSA basis: PICK & PACK ECOM billed on every pick, but the MSA line is "
            "'Per Additional Ecom Pick' — recompute additional-only from the supporting "
            "worksheet (single-unit orders with a pick charge = automatic dispute)", None))
    return found


def apply_msa_conflicts(invoice: dict, result: dict) -> None:
    """Stamp `disputed` when the invoice carries known MSA-conflict lines.

    Runs after validate(): a mathematically clean invoice can still contain
    charges the MSA doesn't allow. Doesn't downgrade a discrepancy (math/rate
    mismatches are investigated first) and skips intl warehouses — the MSA
    conflict schedule is US-domestic.
    """
    wh = result.get("warehouse")
    if wh not in ("fontana", "new_jersey", "south_carolina"):
        return
    if result["status"] in ("discrepancy", "error"):
        return
    conflicts = detect_msa_conflicts(invoice.get("notes") or "", wh)
    if not conflicts:
        return
    result["status"] = "disputed"
    total = round(sum(a for _, a in conflicts if a), 2)
    if total:
        # For disputed rows validation_variance carries the disputed $ total —
        # the dashboards render it as "⚑ Disputed $X".
        result["variance"] = total
        billed = result.get("billed_amount") or 0
        result["variance_percent"] = round(total / billed * 100, 1) if billed else None
    for desc, _amt in conflicts:
        result["discrepancies"].append(desc)


def _set_variance(result: dict, amount: float, expected: float) -> None:
    result["expected_amount"] = round(expected, 2)
    result["variance"] = round(amount - expected, 2)
    result["variance_percent"] = round((result["variance"] / expected) * 100, 1) if expected else 0.0
    # 1 cent tolerance absorbs rounding; real variances are dollars.
    result["status"] = "discrepancy" if abs(result["variance"]) > 0.01 else "valid"


VALIDATION_COLUMNS = [
    ("validated_at", "TIMESTAMP"),
    ("validation_status", "STRING"),
    ("validation_variance", "FLOAT64"),
    ("validated_by", "STRING"),
    # Payment tracking: set only on explicit user confirmation (--mark-paid).
    ("paid_at", "TIMESTAMP"),
    ("paid_marked_by", "STRING"),
    # The two-axis report card stored at approval time (audit artifact).
    ("validation_report", "STRING"),
]


def compose_report(r: dict, paid_date: str = "") -> str:
    """Build the two-axis report card text stored on the row at approval.

    Auto-composed from the validation result. When Claude has done a deeper
    document-level validation in-conversation (PDF worksheet, NL per-order
    checks), pass that richer text via --report-file instead — the stored
    report should match what the approver actually saw.
    """
    icon = {"valid": "✅", "discrepancy": "🚨", "needs_detail": "⏳", "error": "❌",
            "disputed": "⚑"}
    s = r.get("status", "?")
    d = r.get("discrepancies") or []
    if s == "valid":
        math_line = (f"✅ billed ${r['billed_amount']:,.2f} = expected "
                     f"${r.get('expected_amount') or r['billed_amount']:,.2f} — exact")
        rate_line = "✅ matches contracted rate"
    elif s == "discrepancy":
        math_line = f"🚨 {d[0]}" if d else "🚨 variance vs expected"
        rate_line = f"🚨 variance ${r.get('variance', 0):,.2f} ({r.get('variance_percent', 0):+.1f}%)"
    elif s == "disputed":
        amt = r.get("variance")
        math_line = "✅ line math validated" if not d else f"⚑ {d[-1][:180]}"
        rate_line = (f"⚑ MSA-conflict charges{f' totaling ${amt:,.2f}' if amt else ''}: "
                     + "; ".join(x[:150] for x in d))
    else:
        math_line = f"{icon.get(s, '•')} {d[0][:180]}" if d else f"{icon.get(s, '•')} header total recorded"
        rate_line = "⏳ per-unit rate check needs itemized counts"
    t = (r.get("invoice_type") or "").lower()
    stedi_line = "n/a (no order numbers on this type)" if t not in ("smlprcl/ltl",) \
        else "order-level Stedi check available via supporting Excel"
    if s == "discrepancy":
        verdict = "Hold — discrepancy"
    elif s == "disputed":
        amt = r.get("variance")
        verdict = f"Short-pay/hold — MSA dispute{f' ${amt:,.2f}' if amt else ''}"
    else:
        verdict = "OK to pay"
    lines = [
        f"Invoice {r['invoice_number']} — {r.get('invoice_type')}, {r.get('warehouse')}, {r.get('period')}",
        f"Invoice math:  {math_line}",
        f"Rate card:     {rate_line}",
        f"Stedi:         {stedi_line}",
    ]
    if paid_date:
        lines.append(f"Paid:          ✓ {paid_date}")
    lines.append(f"Verdict:       {verdict}")
    return "\n".join(lines)


# Every automated write stamps this name. Anything else in validated_by means a
# person recorded the verdict, which write_result() treats as sticky.
AUTO_WRITER = "yusen-invoice-validator"


def init_columns(client: bigquery.Client) -> None:
    """Add the validation tracking columns if they don't already exist.

    Idempotent (ADD COLUMN IF NOT EXISTS) and non-destructive — existing rows and
    data are untouched. Run once when pointing the skill at a fresh table so that
    --write has somewhere to record validated_at / validation_status.
    """
    adds = ",\n      ".join(f"ADD COLUMN IF NOT EXISTS {name} {typ}"
                            for name, typ in VALIDATION_COLUMNS)
    q = f"ALTER TABLE `{TABLE}`\n      {adds}"
    client.query(q).result()
    print(f"✓ Validation columns ensured on {TABLE}:")
    for name, typ in VALIDATION_COLUMNS:
        print(f"    {name} {typ}")


def _missing_columns(client: bigquery.Client) -> bool:
    """True if the validation columns are absent from the table schema."""
    table = client.get_table(TABLE)
    present = {f.name for f in table.schema}
    return not all(name in present for name, _ in VALIDATION_COLUMNS)


# One auto-composed report block lives on each row, tagged [AUTO YYYY-MM-DD].
# Re-sweeps replace the previous AUTO block instead of stacking a copy per day;
# every other block (paid report cards, [MSA DISPUTE ...] specs, human notes)
# is preserved verbatim.
_AUTO_BLOCK = re.compile(r"\n*\[AUTO \d{4}-\d{2}-\d{2}\].*?(?=\n\n\[|\Z)", re.S)


def merge_report(prior: Optional[str], new_block: str) -> str:
    base = _AUTO_BLOCK.sub("", prior or "").strip()
    tagged = f"[AUTO {date.today().isoformat()}] {new_block}"
    return f"{base}\n\n{tagged}".strip()


def write_result(r: dict, client: bigquery.Client,
                 invoice: Optional[dict] = None) -> tuple[bool, str]:
    """Persist the validation outcome back onto the invoice row.

    Records validated_at = now plus the status/variance, and stores the
    auto-composed report card in validation_report on every write (replacing
    only its own previous [AUTO] block), so the dashboards always carry a
    current per-invoice spec — not just rows that went through --mark-paid.

    A `disputed` stamp is sticky: a re-sweep that comes back valid/needs_detail
    must NOT clear it (the conflict lives in the line items, which a header
    pass can't see). Disputed clears only when the invoice is re-billed/credited
    or manually cleared. The report block still refreshes.

    A **human stamp is also sticky**, for the same reason: when someone reads the
    itemized detail this header pass can't see and records a verdict, an automated
    re-sweep must not overwrite it — not the status, and not the `validated_by`
    provenance that says a person decided it. Any prior stamp whose `validated_by`
    is not AUTO_WRITER counts as human. Real escalations still win: a sweep that
    finds `disputed`/`discrepancy` overrides a human `valid`, because that is new
    information rather than the absence of information.

    Returns (ok, message). A freshly-ingested row may still be in BigQuery's
    streaming buffer, where UPDATE is not allowed; that's reported, not fatal —
    re-run once the buffer flushes (typically well under an hour).
    """
    prior_status = ((invoice or {}).get("validation_status") or "").strip()
    preserve = prior_status == "disputed" and r["status"] in ("valid", "needs_detail")
    # A paid row explicitly stamped valid (mark-paid user policy) is settled;
    # a later header-level pass coming back needs_detail adds nothing and
    # must not un-check it. Real escalations (discrepancy/disputed) still win.
    if (prior_status == "valid" and (invoice or {}).get("paid_at")
            and r["status"] == "needs_detail"):
        preserve = True
    # A stamp set by a person beats this automated header pass, paid or not: they
    # had the itemized detail (hours, unit counts) that the header lacks, which is
    # exactly why the row reads valid instead of needs_detail. Only escalations
    # get through — see the docstring.
    prior_by = ((invoice or {}).get("validated_by") or "").strip()
    if (prior_status and prior_by and prior_by != AUTO_WRITER
            and r["status"] in ("valid", "needs_detail")):
        preserve = True

    report = merge_report((invoice or {}).get("validation_report"), compose_report(r))
    params = [
        bigquery.ScalarQueryParameter("report", "STRING", report),
        bigquery.ScalarQueryParameter("inv", "STRING", r["invoice_number"]),
    ]
    if preserve:
        # Refresh the timestamp + report only; status/variance/validated_by keep
        # their disputed values.
        setter = "validated_at = CURRENT_TIMESTAMP(), validation_report = @report"
    else:
        setter = ("validated_at = CURRENT_TIMESTAMP(), validation_status = @status, "
                  "validation_variance = @variance, validated_by = @by, "
                  "validation_report = @report")
        # A verdict reached from operator-supplied line detail is a human verdict:
        # it rests on numbers read off the worksheet that no header pass can see.
        # Stamping it AUTO_WRITER would make the next scheduled sweep — which only
        # ever sees the header — revert it straight back to needs_detail, throwing
        # the work away. Recording who supplied it makes it sticky by the rule above.
        writer = f"{AUTO_WRITER} (detail supplied by operator)" if r.get("detail_lines") else AUTO_WRITER
        params += [
            bigquery.ScalarQueryParameter("status", "STRING", r["status"]),
            bigquery.ScalarQueryParameter("variance", "FLOAT64", r["variance"]),
            bigquery.ScalarQueryParameter("by", "STRING", writer),
        ]
    q = f"UPDATE `{TABLE}` SET {setter} WHERE invoice_number = @inv"
    cfg = bigquery.QueryJobConfig(query_parameters=params)
    try:
        client.query(q, job_config=cfg).result()
        return True, f"written ({prior_status} stamp preserved)" if preserve else "written"
    except Exception as e:
        msg = str(e)
        if "streaming buffer" in msg:
            return False, "row still in streaming buffer — re-run later"
        if "validation_status" in msg or "validated_at" in msg or "Unrecognized name" in msg:
            return False, "validation columns missing — run once with --init"
        return False, f"write failed: {msg.splitlines()[0][:120]}"


def mark_paid(invoice_number: str, client: bigquery.Client, paid: bool = True,
              report_text: Optional[str] = None) -> tuple[bool, str]:
    """Set or clear the paid stamp on an invoice row.

    Only call this after the USER has explicitly confirmed the invoice was paid
    (or that a paid mark was a mistake) — payment status is a human fact the
    validator cannot infer. When marking paid, the two-axis report card is
    stored on the row (validation_report) as the approval-time audit artifact.
    Subject to the same streaming-buffer limitation as write_result.
    """
    if paid:
        setter = ("paid_at = CURRENT_TIMESTAMP(), "
                  "paid_marked_by = 'user-confirmed via yusen-invoice-validator', "
                  "validation_report = COALESCE(@report, validation_report)")
    else:
        setter = "paid_at = NULL, paid_marked_by = NULL"
    q = f"UPDATE `{TABLE}` SET {setter} WHERE invoice_number = @inv"
    params = [bigquery.ScalarQueryParameter("inv", "STRING", invoice_number)]
    if paid:
        params.append(bigquery.ScalarQueryParameter("report", "STRING", report_text))
    cfg = bigquery.QueryJobConfig(query_parameters=params)
    try:
        job = client.query(q, job_config=cfg)
        job.result()
        if job.num_dml_affected_rows == 0:
            return False, "no matching invoice row"
        return True, f"marked {'paid' if paid else 'unpaid'} ({job.num_dml_affected_rows} row(s))"
    except Exception as e:
        msg = str(e)
        if "streaming buffer" in msg:
            return False, "row still in streaming buffer — retry later"
        return False, f"update failed: {msg.splitlines()[0][:120]}"


def fetch_invoice(invoice_number: str, client: bigquery.Client) -> Optional[dict]:
    cfg = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("inv", "STRING", invoice_number)]
    )
    base = ("SELECT invoice_number, type_of_invoice, warehouse, amount, date, bill_period, notes{extra} "
            f"FROM `{TABLE}` WHERE invoice_number = @inv LIMIT 1")
    # Tracking columns ride along so --write can preserve a disputed stamp and
    # merge the report instead of clobbering it.
    # validated_by rides along so write_result() can tell a human stamp from an
    # automated one and leave the human's verdict alone.
    tracked = (", paid_at, validation_status, validation_variance, validation_report,"
               " validated_by")
    try:
        rows = list(client.query(base.format(extra=tracked), job_config=cfg).result())
    except Exception as e:
        if not any(c in str(e) for c in ("paid_at", "validation_", "Unrecognized name")):
            raise
        # Table not yet provisioned with tracking columns (run --init) — degrade gracefully.
        rows = list(client.query(base.format(extra=""), job_config=cfg).result())
    return dict(rows[0]) if rows else None


def print_report(r: dict) -> None:
    icon = {"valid": "✅", "discrepancy": "🚨", "needs_detail": "⏳", "error": "❌",
            "disputed": "⚑"}.get(r["status"], "•")
    print(f"\n{'='*78}")
    print(f"RATE CARD VALIDATION — Invoice {r['invoice_number']}  {icon} {r['status'].upper()}")
    print(f"{'='*78}")
    print(f"Type:       {r['invoice_type']}")
    print(f"Warehouse:  {r['warehouse_raw']}" + (f"  ->  {r['warehouse']}" if r['warehouse'] else ""))
    print(f"Period:     {r['period']}")
    print(f"{'-'*78}")
    print(f"Billed:     ${r['billed_amount']:,.2f}")
    if r["expected_amount"] is not None:
        print(f"Expected:   ${r['expected_amount']:,.2f}")
        print(f"Variance:   ${r['variance']:,.2f} ({r['variance_percent']:+.1f}%)")
    # Show the Paid line only when marked — "not marked paid" is noise; the
    # ask-if-paid step covers the unpaid case (user preference, 2026-07-09).
    if r.get("paid_at"):
        print(f"Paid:       ✓ {r['paid_at'][:16]}")
    for d in r["discrepancies"]:
        print(f"\n  → {d}")
    print(f"{'='*78}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate Yusen/Taylored invoices against the rate card.")
    ap.add_argument("invoice_number", nargs="?", help="Invoice number to validate")
    ap.add_argument("--rates", help="Path to a rates JSON pulled live from Notion (recommended)")
    ap.add_argument("--detail", metavar="LINES",
                    help="Itemized lines read off the invoice worksheet, as "
                         "'QTY x RATE [label]' separated by ';' — e.g. "
                         "\"4101 x 0.9173 recv carton; 82 x 31.2981 sortation\". "
                         "Validates the sum against the billed total, which is what "
                         "the header row alone can't do. Supply the rate as billed, "
                         "not the card rate.")
    ap.add_argument("--list-all", action="store_true", help="Validate the 20 most recent invoices")
    ap.add_argument("--limit", type=int, default=20, help="How many invoices for --list-all")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of a text report")
    ap.add_argument("--write", action="store_true",
                    help="Persist the result to validated_at/validation_status on the invoice row")
    ap.add_argument("--init", action="store_true",
                    help="Add the validation tracking columns if missing, then continue/exit")
    ap.add_argument("--mark-paid", action="store_true",
                    help="Mark the invoice paid (only after the user explicitly confirms payment)")
    ap.add_argument("--unmark-paid", action="store_true",
                    help="Clear a paid mark set by mistake")
    ap.add_argument("--report-file",
                    help="With --mark-paid: store this file's text as the approval report "
                         "(use when a richer document-level validation was performed); "
                         "omitted → a report is auto-composed from the validation result")
    args = ap.parse_args()

    client = bigquery.Client(project=PROJECT)

    if args.mark_paid or args.unmark_paid:
        if not args.invoice_number:
            ap.error("--mark-paid/--unmark-paid require an invoice_number")
        if _missing_columns(client):
            init_columns(client)
        report = None
        if args.mark_paid:
            # Merge onto whatever is already stored, never replace it. The report
            # written here is a fresh HEADER pass, which is thinner than the deep
            # passes that accumulate on a row (MSA reval, worksheet recompute,
            # Stedi evidence). Replacing meant approving an invoice destroyed the
            # audit trail that justified the approval — 754891 and 755265 lost
            # ~900 characters each that way on 2026-08-11.
            inv = fetch_invoice(args.invoice_number, client)
            prior = (inv or {}).get("validation_report")
            if args.report_file:
                report = merge_report(prior, Path(args.report_file).read_text().strip())
            elif inv:
                rates0, _ = load_rates(args.rates)
                from datetime import date as _d
                report = merge_report(
                    prior, compose_report(validate(inv, rates0), paid_date=_d.today().isoformat()))
        ok, msg = mark_paid(args.invoice_number, client, paid=args.mark_paid, report_text=report)
        print(f"{'✓' if ok else '⚠️ '} {args.invoice_number}: {msg}"
              + (" + report stored" if (ok and report) else ""))
        if not (args.write or args.list_all):
            return

    # Provision the tracking columns. Explicit via --init; also auto-run if a
    # --write was requested but the columns aren't there yet (self-provisioning).
    if args.init:
        init_columns(client)
        if not (args.invoice_number or args.list_all):
            return
    elif args.write and _missing_columns(client):
        print("ℹ️  Validation columns missing — adding them (one-time setup)…")
        init_columns(client)

    rates, source = load_rates(args.rates)
    if "SNAPSHOT" in source and not args.json:
        print(f"⚠️  Using {source}.\n   Pull the live Notion rate card for an authoritative check (see SKILL.md).")

    if args.list_all:
        q = f"SELECT DISTINCT invoice_number FROM `{TABLE}` ORDER BY invoice_number DESC LIMIT {args.limit}"
        results = []
        for row in client.query(q).result():
            inv = fetch_invoice(row["invoice_number"], client)
            if inv:
                r = validate(inv, rates)
                apply_msa_conflicts(inv, r)
                if args.write:
                    r["_written"], r["_write_msg"] = write_result(r, client, inv)
                results.append(r)
                if not args.json:
                    print_report(r)
        if args.json:
            print(json.dumps({"rate_source": source, "results": results}, indent=2))
        else:
            _print_rollup(results)
        return

    if not args.invoice_number:
        ap.error("provide an invoice_number or --list-all")

    inv = fetch_invoice(args.invoice_number, client)
    if not inv:
        msg = {"invoice_number": args.invoice_number, "status": "error",
               "error": "Invoice not found in yusen_invoices"}
        print(json.dumps(msg, indent=2) if args.json else f"❌ Invoice {args.invoice_number} not found.")
        sys.exit(1)

    # Line detail read off the worksheet, supplied by a person. Parsed here rather
    # than inside validate() so a malformed line fails before anything is written.
    if args.detail:
        try:
            inv["_detail_lines"] = parse_detail(args.detail)
        except ValueError as e:
            ap.error(f"--detail: {e}")

    r = validate(inv, rates)
    apply_msa_conflicts(inv, r)
    if args.write:
        ok, msg = write_result(r, client, inv)
        r["_written"], r["_write_msg"] = ok, msg
    if args.json:
        print(json.dumps({"rate_source": source, **r}, indent=2))
    else:
        print_report(r)
        if args.write:
            print(f"{'✓ Written to' if r['_written'] else '⚠️  Not written ('+r['_write_msg']+') —'} "
                  f"validated_at / validation_status on the invoice row.")


def _print_rollup(results: list) -> None:
    by = {"valid": 0, "discrepancy": 0, "disputed": 0, "needs_detail": 0, "error": 0}
    for r in results:
        by[r["status"]] = by.get(r["status"], 0) + 1
    print(f"\n{'='*78}\nSUMMARY: {len(results)} invoices")
    print(f"  ✅ valid {by['valid']}   🚨 discrepancy {by['discrepancy']}   "
          f"⚑ disputed {by['disputed']}   ⏳ needs detail {by['needs_detail']}   "
          f"❌ error {by['error']}\n{'='*78}")
    flagged = [r for r in results if r["status"] == "discrepancy"]
    if flagged:
        print("\nDISCREPANCIES:")
        for r in flagged:
            print(f"  🚨 {r['invoice_number']} ({r['invoice_type']}, {r['warehouse']}): "
                  f"${r['variance']:,.2f} ({r['variance_percent']:+.1f}%)")
    disputed = [r for r in results if r["status"] == "disputed"]
    if disputed:
        print("\nMSA DISPUTES (short-pay/hold):")
        for r in disputed:
            amt = f"${r['variance']:,.2f}" if r.get("variance") else "amount needs worksheet recompute"
            print(f"  ⚑ {r['invoice_number']} ({r['invoice_type']}, {r['warehouse']}): {amt}")

    if any("_written" in r for r in results):
        wrote = sum(1 for r in results if r.get("_written"))
        buffered = [r["invoice_number"] for r in results if r.get("_written") is False]
        print(f"\nPERSISTED: {wrote} written to BigQuery.")
        if buffered:
            print(f"  ⚠️  {len(buffered)} still in streaming buffer (re-run later): "
                  f"{', '.join(buffered)}")


if __name__ == "__main__":
    main()
