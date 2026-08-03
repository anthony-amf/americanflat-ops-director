#!/usr/bin/env python3
"""
Netherlands (Yusen Benelux) invoice validator — EUR-native, VAT-aware.

NL invoices differ from US/Canada: priced in EUR with 21% VAT, and they arrive in
two families with different checkable rules:

  • transport   — outbound EU delivery: per order, Transport Outbound + Fuel
                  Surcharge + Amazon Delivery (flat €100). Fully checked here:
                  charges sum to netto, fuel = pct × transport, Amazon Delivery
                  flat, subtotal = Σ netto, VAT = 21%, total = subtotal + VAT.
                  Transport Outbound itself is a variable lane/weight rate and is
                  surfaced, not rate-card-checked.
  • warehousing — Benelux LSA: DTC/B2B fulfilment, storage, tiered admin, VAS,
                  inbound. The per-unit charges need counts the header doesn't
                  carry, so we surface contracted rates, note the €6,222/month
                  minimum, and check VAT — the rest is needs_detail.

Validates in EUR. Converting NL amounts to USD would inject FX error and break the
VAT arithmetic, so we never do that here.

A charge that *cannot* be verified (e.g. a fuel line with no percent) is reported
as needs_detail — never as a clean pass — so an unverifiable line can't be
mistaken for a validated one.

Input is the extraction JSON the invoice-to-bigquery extractor produces for an NL
invoice (it carries the per-order line items the BigQuery header row does not).

Usage:
    python3 validate_nl_invoice.py path/to/extraction.json
    python3 validate_nl_invoice.py path/to/extraction.json --json
"""
import argparse
import json
from datetime import date
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parent.parent / "references" / "rate-card-snapshot.json"
CENTS = 0.011      # exact-cent tolerance for sums/totals
FUEL_TOL = 0.02    # rounding tolerance for fuel = pct × transport
PCT_UNITS = {"%", "percent", "pct"}

TRANSPORT_CODES = {
    "SMALL_PARCEL_TRANSPORT_OUTBOUND",
    "SMALL_PARCEL_FUEL_SURCHARGE",
    "SMALL_PARCEL_AMAZON_DELIVERY",
}


def load_nl_rates() -> dict:
    return json.load(open(SNAPSHOT)).get("netherlands", {})


def eur(x) -> str:
    return f"€{x:,.2f}" if isinstance(x, (int, float)) else str(x)


def _all_charge_codes(inv: dict) -> set:
    """Collect every canonical_charge_code anywhere in the invoice tree."""
    found = set()

    def walk(node):
        if isinstance(node, dict):
            if node.get("canonical_charge_code"):
                found.add(node["canonical_charge_code"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(inv)
    return found


def detect_family(inv: dict) -> str:
    """Charge codes are authoritative. Default to warehousing when no transport
    codes are present — the SMALL_PARCEL/LTL invoice_type keyword is NOT a
    reliable transport signal (NL warehousing fulfilment can share it), so we do
    not route on it."""
    return "transport" if (_all_charge_codes(inv) & TRANSPORT_CODES) else "warehousing"


class Checks:
    """Accumulates pass/fail checks, unverifiable items, and notes for the report.

    `unverified` is distinct from `failed`: a line we couldn't check (missing
    data) downgrades the result to needs_detail rather than asserting a problem.
    """

    def __init__(self):
        self.items = []  # {kind: check|unverified|info, name, passed, detail}

    def check(self, name, passed, detail):
        self.items.append({"kind": "check", "name": name, "passed": bool(passed), "detail": detail})

    def unverify(self, detail, name="unverified"):
        self.items.append({"kind": "unverified", "name": name, "passed": None, "detail": detail})

    def info(self, detail, name="note"):
        self.items.append({"kind": "info", "name": name, "passed": None, "detail": detail})

    @property
    def failed(self):
        return [i for i in self.items if i["kind"] == "check" and not i["passed"]]

    @property
    def passed(self):
        return [i for i in self.items if i["kind"] == "check" and i["passed"]]

    @property
    def unverified(self):
        return [i for i in self.items if i["kind"] == "unverified"]


def validate_transport(inv: dict, nl: dict, ck: Checks) -> dict:
    vat_rate = nl.get("vat_rate", 0.21)
    flat = (nl.get("transport") or {}).get("amazon_delivery_flat_eur", 100.0)

    computed_subtotal = 0.0
    for o in inv.get("line_items", []):
        oid = o.get("order_number", "?")
        charges = o.get("line_items", []) or []
        s = round(sum(c.get("billed_amount", 0) or 0 for c in charges), 2)
        netto = round(o.get("netto_eur", s) or s, 2)
        computed_subtotal += netto
        ck.check(f"Order {oid}: charges sum to netto", abs(s - netto) <= CENTS,
                 f"Σ charges {eur(s)} vs netto {eur(netto)}")

        by = {c.get("canonical_charge_code"): c for c in charges}
        amz = by.get("SMALL_PARCEL_AMAZON_DELIVERY")
        if amz is not None:
            ck.check(f"Order {oid}: Amazon Delivery flat {eur(flat)}",
                     abs((amz.get("billed_amount", 0) or 0) - flat) <= CENTS,
                     f"billed {eur(amz.get('billed_amount', 0))}")

        # Fuel = pct × transport. Only valid when transport is present AND the fuel
        # line carries a percent in a %-unit. Otherwise the fuel amount is
        # unconstrained — report needs_detail, never a silent pass.
        fu = by.get("SMALL_PARCEL_FUEL_SURCHARGE")
        tr = by.get("SMALL_PARCEL_TRANSPORT_OUTBOUND")
        if fu is not None:
            pct = fu.get("quantity")
            unit = (fu.get("quantity_unit") or "").strip().lower()
            if tr and pct and unit in PCT_UNITS:
                exp = round((tr.get("billed_amount", 0) or 0) * pct / 100, 2)
                ck.check(f"Order {oid}: fuel = {pct}% × transport",
                         abs((fu.get("billed_amount", 0) or 0) - exp) <= FUEL_TOL,
                         f"fuel {eur(fu.get('billed_amount', 0))} vs {eur(exp)}")
            else:
                ck.unverify(f"Order {oid}: fuel surcharge {eur(fu.get('billed_amount', 0))} present "
                            f"but percent/unit missing (pct={pct!r}, unit={unit!r}) — cannot verify "
                            f"fuel = pct × transport")
        if tr:
            ck.info(f"Order {oid}: Transport Outbound {eur(tr.get('billed_amount', 0))} "
                    f"— variable lane/weight rate, not rate-card checkable")
        _date_sanity(o, oid, ck)

    sub = inv.get("subtotal_eur")
    if sub is not None:
        ck.check("Subtotal = Σ order netto", abs(round(computed_subtotal, 2) - round(sub, 2)) <= CENTS,
                 f"Σ netto {eur(round(computed_subtotal, 2))} vs stated {eur(sub)}")
    sub = round(sub if sub is not None else computed_subtotal, 2)

    # Guard against a vacuous pass: an invoice with no positive billed amount has
    # nothing meaningful to validate (trivial 0 == 0 sums would otherwise "pass").
    stated_total = inv.get("total_eur") or 0
    if sub <= CENTS and stated_total <= CENTS:
        ck.unverify("Transport invoice has no positive billed amount — nothing to validate.")

    vat = inv.get("vat_amount_eur")
    exp_vat = round(sub * vat_rate, 2)
    if vat is not None:
        ck.check(f"VAT = {int(vat_rate * 100)}% of subtotal", abs(vat - exp_vat) <= CENTS,
                 f"stated {eur(vat)} vs {eur(exp_vat)}")
    vat = vat if vat is not None else exp_vat

    tot = inv.get("total_eur")
    exp_tot = round(sub + vat, 2)
    if tot is not None:
        ck.check("Total = subtotal + VAT", abs(tot - exp_tot) <= CENTS,
                 f"stated {eur(tot)} vs {eur(exp_tot)}")

    return {"family": "transport", "currency": "EUR",
            "subtotal_eur": sub, "vat_eur": round(vat, 2),
            "total_eur": round(tot if tot is not None else exp_tot, 2),
            "orders": len(inv.get("line_items", []))}


def validate_warehousing(inv: dict, nl: dict, ck: Checks) -> dict:
    ck.info("NL warehousing invoice — header-level only. Per-unit charges (pallet-weeks, "
            "admin hours/tier, carton counts) need itemised detail to check against the "
            "Benelux rate card; contracted rates are surfaced below.")
    wh = nl.get("warehousing", {})
    if wh:
        tiers = ", ".join(f"≤{t['max_hours']}h {eur(t['eur'])}" for t in wh.get("admin_weekly_tiers", []))
        ck.info(f"DTC {eur(wh.get('small_parcel_dtc', {}).get('e_commerce_orders'))}/carton · "
                f"B2B {eur(wh.get('outbound_b2b', {}).get('ship_carton'))}/carton · "
                f"storage {eur(wh.get('storage_pallet_week'))}/pallet/wk · admin tiers [{tiers}]",
                name="rates")

    vat_rate = nl.get("vat_rate", 0.21)
    minimum = nl.get("monthly_minimum_eur")
    sub = inv.get("subtotal_eur")
    # Being below the monthly minimum is NOT overbilling — it usually means a
    # top-up to the minimum should apply. Surface as a note, not a discrepancy,
    # and don't assume the bill covers a full month.
    if minimum is not None and sub is not None and sub < minimum - CENTS:
        ck.info(f"Warehouse-activity subtotal {eur(sub)} is below the €{minimum:,.0f}/month minimum. "
                f"If this is a full-month warehousing bill, confirm a top-up to the minimum was applied.")
    if sub is not None and inv.get("vat_amount_eur") is not None:
        stated = inv["vat_amount_eur"]
        # Warehousing invoices billed to the US entity are zero-rated: export of
        # services under art. 44 VAT Directive 2006/112/EU (reverse charge).
        # Transport invoices, by contrast, carry 21% NL VAT. Accept either form.
        if abs(stated) <= CENTS:
            ck.check("VAT zero-rated (art. 44 export service)", True,
                     "€0.00 — reverse charge, billed to US entity")
        else:
            exp = round(sub * vat_rate, 2)
            ck.check(f"VAT = {int(vat_rate * 100)}% of subtotal", abs(stated - exp) <= CENTS,
                     f"stated {eur(stated)} vs {eur(exp)}")
    return {"family": "warehousing", "currency": "EUR", "subtotal_eur": sub}


def _date_sanity(order: dict, oid: str, ck: Checks) -> None:
    ld, dd = order.get("loading_date"), order.get("delivery_date")
    if not (ld and dd):
        return
    try:
        l, d = date.fromisoformat(ld), date.fromisoformat(dd)
    except (ValueError, TypeError):
        return
    gap = (d - l).days
    if gap < 0:
        ck.info(f"Order {oid}: delivery {dd} precedes loading {ld} — likely extraction artifact")
    elif dd.endswith("-12-31") and gap > 90:
        ck.info(f"Order {oid}: delivery {dd} looks like a placeholder ({gap}d after loading) — verify")
    elif gap > 120:
        ck.info(f"Order {oid}: delivery {dd} is {gap}d after loading {ld} — verify")


def overall_status(family: str, ck: Checks) -> str:
    if ck.failed:
        return "discrepancy"
    # A transport invoice that produced no actual checks (empty/zeroed) is not a
    # clean pass — there was nothing to validate.
    if family == "transport" and not ck.passed:
        return "needs_detail"
    if ck.unverified:
        return "needs_detail"
    if family == "warehousing":
        return "needs_detail"
    return "valid"


def print_report(inv: dict, result: dict, ck: Checks) -> None:
    status = overall_status(result["family"], ck)
    icon = {"valid": "✅", "discrepancy": "🚨", "needs_detail": "⏳"}.get(status, "•")
    print(f"\n{'=' * 78}")
    print(f"NL INVOICE VALIDATION — {inv.get('invoice_number', '?')}  {icon} {status.upper()}")
    print(f"{'=' * 78}")
    print(f"Carrier:    {inv.get('carrier', 'Yusen')} Benelux · {inv.get('warehouse_location', 'Netherlands')}")
    print(f"Family:     {result['family']}   Currency: EUR   VAT: 21%")
    print(f"Date:       {inv.get('invoice_date', '?')}")
    print(f"{'-' * 78}")
    if result.get("subtotal_eur") is not None:
        print(f"Subtotal:   {eur(result['subtotal_eur'])}")
    if result.get("vat_eur") is not None:
        print(f"VAT:        {eur(result['vat_eur'])}")
    if result.get("total_eur") is not None:
        print(f"Total:      {eur(result['total_eur'])}")
    if result.get("orders"):
        print(f"Orders:     {result['orders']}")
    print(f"{'-' * 78}")
    print(f"Checks: {len(ck.passed)} passed, {len(ck.failed)} failed, {len(ck.unverified)} unverifiable")
    for i in ck.failed:
        print(f"  🚨 {i['name']} — {i['detail']}")
    for i in ck.unverified:
        print(f"  ⚠️  {i['detail']}")
    for i in ck.passed:
        print(f"  ✓ {i['name']}")
    notes = [i for i in ck.items if i["kind"] == "info"]
    if notes:
        print()
        for i in notes:
            print(f"  ℹ️  {i['detail']}")
    print(f"{'=' * 78}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate a Netherlands (Yusen Benelux) invoice (EUR, VAT-aware).")
    ap.add_argument("json_file", help="Path to the NL invoice extraction JSON")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of a text report")
    args = ap.parse_args()

    path = Path(args.json_file)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    inv = json.loads(path.read_text())
    nl = load_nl_rates()
    if not nl:
        raise SystemExit("No 'netherlands' block in the rate card snapshot — cannot validate.")

    ck = Checks()
    family = detect_family(inv)
    result = validate_transport(inv, nl, ck) if family == "transport" else validate_warehousing(inv, nl, ck)
    status = overall_status(family, ck)

    if args.json:
        print(json.dumps({
            "invoice_number": inv.get("invoice_number"),
            "status": status, **result,
            "checks": ck.items,
        }, indent=2, ensure_ascii=False))
    else:
        print_report(inv, result, ck)


if __name__ == "__main__":
    main()
