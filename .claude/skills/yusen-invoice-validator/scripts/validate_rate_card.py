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
    icon = {"valid": "✅", "discrepancy": "🚨", "needs_detail": "⏳", "error": "❌"}
    s = r.get("status", "?")
    d = r.get("discrepancies") or []
    if s == "valid":
        math_line = (f"✅ billed ${r['billed_amount']:,.2f} = expected "
                     f"${r.get('expected_amount') or r['billed_amount']:,.2f} — exact")
        rate_line = "✅ matches contracted rate"
    elif s == "discrepancy":
        math_line = f"🚨 {d[0]}" if d else "🚨 variance vs expected"
        rate_line = f"🚨 variance ${r.get('variance', 0):,.2f} ({r.get('variance_percent', 0):+.1f}%)"
    else:
        math_line = f"{icon.get(s, '•')} {d[0][:180]}" if d else f"{icon.get(s, '•')} header total recorded"
        rate_line = "⏳ per-unit rate check needs itemized counts"
    t = (r.get("invoice_type") or "").lower()
    stedi_line = "n/a (no order numbers on this type)" if t not in ("smlprcl/ltl",) \
        else "order-level Stedi check available via supporting Excel"
    verdict = "Hold — discrepancy" if s == "discrepancy" else "OK to pay"
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


def write_result(r: dict, client: bigquery.Client) -> tuple[bool, str]:
    """Persist the validation outcome back onto the invoice row.

    Records validated_at = now plus the status/variance, so a dashboard or query
    can show what's been checked off. Safe to re-run — it overwrites the prior
    result for that invoice (validation is a fresh judgment each time).

    Returns (ok, message). A freshly-ingested row may still be in BigQuery's
    streaming buffer, where UPDATE is not allowed; that's reported, not fatal —
    re-run once the buffer flushes (typically well under an hour).
    """
    q = f"""
    UPDATE `{TABLE}`
    SET validated_at = CURRENT_TIMESTAMP(),
        validation_status = @status,
        validation_variance = @variance,
        validated_by = @by
    WHERE invoice_number = @inv
    """
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("status", "STRING", r["status"]),
        bigquery.ScalarQueryParameter("variance", "FLOAT64", r["variance"]),
        bigquery.ScalarQueryParameter("by", "STRING", "yusen-invoice-validator"),
        bigquery.ScalarQueryParameter("inv", "STRING", r["invoice_number"]),
    ])
    try:
        client.query(q, job_config=cfg).result()
        return True, "written"
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
    try:
        rows = list(client.query(base.format(extra=", paid_at"), job_config=cfg).result())
    except Exception as e:
        if "paid_at" not in str(e):
            raise
        # Table not yet provisioned with payment columns (run --init) — degrade gracefully.
        rows = list(client.query(base.format(extra=""), job_config=cfg).result())
    return dict(rows[0]) if rows else None


def print_report(r: dict) -> None:
    icon = {"valid": "✅", "discrepancy": "🚨", "needs_detail": "⏳", "error": "❌"}.get(r["status"], "•")
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
            if args.report_file:
                report = Path(args.report_file).read_text().strip()
            else:
                inv = fetch_invoice(args.invoice_number, client)
                if inv:
                    rates0, _ = load_rates(args.rates)
                    from datetime import date as _d
                    report = compose_report(validate(inv, rates0), paid_date=_d.today().isoformat())
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
                if args.write:
                    r["_written"], r["_write_msg"] = write_result(r, client)
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

    r = validate(inv, rates)
    if args.write:
        ok, msg = write_result(r, client)
        r["_written"], r["_write_msg"] = ok, msg
    if args.json:
        print(json.dumps({"rate_source": source, **r}, indent=2))
    else:
        print_report(r)
        if args.write:
            print(f"{'✓ Written to' if r['_written'] else '⚠️  Not written ('+r['_write_msg']+') —'} "
                  f"validated_at / validation_status on the invoice row.")


def _print_rollup(results: list) -> None:
    by = {"valid": 0, "discrepancy": 0, "needs_detail": 0, "error": 0}
    for r in results:
        by[r["status"]] = by.get(r["status"], 0) + 1
    print(f"\n{'='*78}\nSUMMARY: {len(results)} invoices")
    print(f"  ✅ valid {by['valid']}   🚨 discrepancy {by['discrepancy']}   "
          f"⏳ needs detail {by['needs_detail']}   ❌ error {by['error']}\n{'='*78}")
    flagged = [r for r in results if r["status"] == "discrepancy"]
    if flagged:
        print("\nDISCREPANCIES:")
        for r in flagged:
            print(f"  🚨 {r['invoice_number']} ({r['invoice_type']}, {r['warehouse']}): "
                  f"${r['variance']:,.2f} ({r['variance_percent']:+.1f}%)")

    if any("_written" in r for r in results):
        wrote = sum(1 for r in results if r.get("_written"))
        buffered = [r["invoice_number"] for r in results if r.get("_written") is False]
        print(f"\nPERSISTED: {wrote} written to BigQuery.")
        if buffered:
            print(f"  ⚠️  {len(buffered)} still in streaming buffer (re-run later): "
                  f"{', '.join(buffered)}")


if __name__ == "__main__":
    main()
