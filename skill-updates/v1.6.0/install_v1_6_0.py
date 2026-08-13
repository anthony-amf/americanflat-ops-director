#!/usr/bin/env python3
"""Install v1.6.0's code changes into a 1.5.x validate_rate_card.py.

Why this and not the .patch: `patch` matches on line numbers, and 1.5.1 was
developed separately, so its line numbers drifted from the 1.5.0 this release was
built against. On the Mac, hunk 6 of 6 failed for exactly that reason. This script
finds each spot by the code around it instead, so drift cannot break it.

Every change is an INSERT. Nothing is deleted, nothing is rewritten, and mark_paid
is not touched on a single line. Running it twice is safe — anything already there
is reported as "already present" and left alone.

  python3 install_v1_6_0.py <path-to-validate_rate_card.py>            # dry run
  python3 install_v1_6_0.py <path-to-validate_rate_card.py> --write

--write makes a timestamped backup next to the file before changing it.
"""
import re
import shutil
import sys
from datetime import datetime

NEW_FUNCTIONS = 'AF9_PALLET_ALL_IN = 10.00   # MSA AF-9: $10.00/pallet, pallet AND stretch wrap included\n\n# Savannah bills pallets as VAS work orders rather than on the SP/LTL invoice:\n#   "WORK ORDER 5001859 PALLETS (Savannah) - 7 PALLETS W/SHRINKWRAP @ $10.00/PALLET"\n#   "WORK ORDER 5001786 PALLETS - 48 pallets w/shrinkwrap @ $14.317"\n#   "WORK ORDER 5001727 PALLETS - 57 pallets @ $11.74"\n# Anchored on PALLET so the work-order number can never be read as a quantity.\n_VAS_PALLET_LINE = re.compile(\n    r"(?<![\\d.])(\\d{1,5}(?:\\.\\d+)?)\\s+PALLETS?\\b[^@$]*?@\\s*\\$?\\s*([\\d,]+(?:\\.\\d+)?)", re.I)\n\n\ndef apply_vas_pallet_check(invoice: dict, result: dict) -> None:\n    """Judge a Savannah VAS pallet work order: recompute, then rate vs AF-9.\n\n    These are pallet charges wearing a VAS document. The generic VAS logic cannot\n    resolve them — it has no per-unit basis to check — so they parked at\n    `needs_detail` indefinitely even when billed exactly right. This reads the\n    quantity and rate straight out of `notes`, which matters because SC VAS PDFs\n    are scanned images: no OCR is needed to reach a verdict.\n\n    Two stages, and the second is the one that protects the money:\n\n    1. **Recompute.** pallets x printed rate must equal the invoice total.\n    2. **Judge the rate against AF-9\'s $10.00 all-in.** Arithmetic alone is not\n       enough — 48 x $14.317 = $687.22 recomputes perfectly, and validating on\n       that would stamp an AF-9 overcharge `valid` and silently drop a live claim.\n\n    Rate handling (Anthony, 2026-08-12): the MSA rate is the yardstick, and the\n    pre-MSA $11.74 SC rate is NOT grandfathered — anything above $10.00 is\n    disputed for the excess, whatever era it came from.\n\n    Reclassifying these as SMLPRCL/LTL was considered and rejected: SP/LTL carries\n    the Stedi shipping gate, these work orders have no order numbers to match, so\n    reclassifying would park them at `needs_detail` permanently — the opposite of\n    the goal — and would misdescribe the document in the ledger.\n    """\n    if (invoice.get("type_of_invoice") or "").strip().upper() != "VAS":\n        return\n    if result.get("_settled") or result.get("status") == "error":\n        return\n    m = _VAS_PALLET_LINE.search(invoice.get("notes") or "")\n    if not m:\n        return\n\n    pallets = float(m.group(1))\n    rate = float(m.group(2).replace(",", ""))\n    amount = result.get("billed_amount")\n    if amount is None:\n        amount = float(invoice.get("amount") or 0)\n    expected = round(pallets * rate, 2)\n    payable = round(pallets * AF9_PALLET_ALL_IN, 2)\n\n    # Marks this row as judged by the pallet rule so the generic conflict\n    # detector and the PDF line pass do not re-judge the same charge.\n    result["_pallet_rule"] = True\n\n    # AF-9 has an effective date. An invoice billed before it at the documented\n    # pre-June rate is correct, not disputed — and this guard is what stops a\n    # re-sweep from silently reversing that. A `disputed` result counts as an\n    # escalation downstream and overrides an existing `valid` stamp, so without\n    # the date test these rows would flip back every night.\n    eff = ((result.get("_rates") or {}).get("ltl") or {}).get("_af9_effective_from")\n    inv_date = str(invoice.get("date") or "")[:10]\n    if eff and inv_date and inv_date < eff:\n        if abs(expected - amount) <= 0.01:\n            result["status"] = "valid"\n            result["expected_amount"] = expected\n            result["variance"] = 0.0\n            result["variance_percent"] = 0.0\n            result["line_report"] = (\n                f"{pallets:g} pallets x ${rate:,.4f} = ${amount:,.2f}, exact. Billed "\n                f"{inv_date}, before AF-9 took effect ({eff}), so the pre-June rate applies "\n                f"— correct as billed, nothing disputed.")\n            return\n\n    if abs(expected - amount) > 0.01:\n        result["status"] = "discrepancy"\n        result["expected_amount"] = expected\n        result["variance"] = round(amount - expected, 2)\n        result["discrepancies"].append(\n            f"{pallets:g} pallets x ${rate:,.4f} = ${expected:,.2f} but the invoice bills "\n            f"${amount:,.2f} — the pallet line does not recompute")\n        return\n\n    if abs(rate - AF9_PALLET_ALL_IN) < 0.005:\n        result["status"] = "valid"\n        result["expected_amount"] = expected\n        result["variance"] = 0.0\n        result["variance_percent"] = 0.0\n        result["line_report"] = (\n            f"VALID vs MSA AF-9: {pallets:g} pallets x ${rate:,.2f} = ${amount:,.2f}, exact. "\n            f"All-in pallet rate, wrap included — no markup, nothing disputed.")\n        return\n\n    if rate > AF9_PALLET_ALL_IN:\n        over = round((rate - AF9_PALLET_ALL_IN) * pallets, 2)\n        result["status"] = "disputed"\n        result["variance"] = over\n        result["variance_percent"] = round(over / amount * 100, 1) if amount else None\n        era = (f"the pre-MSA SC pallet rate of ${rate:,.2f}"\n               if abs(rate - 11.74) < 0.005 else f"${rate:,.4f}/pallet")\n        result["discrepancies"].append(\n            f"AF-9: {pallets:g} pallets billed at {era}; the MSA all-in rate is "\n            f"${AF9_PALLET_ALL_IN:,.2f} incl. stretch wrap, so {pallets:g} x "\n            f"${rate - AF9_PALLET_ALL_IN:,.4f} = ${over:,.2f} is disputed and "\n            f"${payable:,.2f} is payable")\n        return\n\n    result["status"] = "discrepancy"\n    result["variance"] = round((rate - AF9_PALLET_ALL_IN) * pallets, 2)\n    result["discrepancies"].append(\n        f"{pallets:g} pallets x ${rate:,.4f} = ${amount:,.2f}, below the AF-9 $10.00 all-in "\n        f"— unrecognised pallet rate, needs a human look")\n\n\n# "MAY 2026 CONSOLIDATION PROJECT - 24.49 HRS", "55 hrs @ $53.55", "2 hrs"\n_VAS_HOURS = re.compile(r"(?<![\\d.])(\\d{1,4}(?:\\.\\d+)?)\\s*(?:HRS?|HOURS?)\\b", re.I)\n\n\n# Role keywords -> the row of the MSA hourly table. Order matters: the specific\n# activities are tested before general_labor, which is the catch-all the MSA itself\n# defines broadly ("equipment operator, office, admin, returns, photography, floor\n# loading, oversize, QA, routing").\n_ROLE_WORDS = [\n    ("stock_consolidation", ("consolidat",)),\n    ("physical_inventory",  ("physical inventory", "inventory count", "cycle count",\n                             "stock count")),\n    ("salaried_supervisor", ("supervisor", "salaried")),\n    ("clerical",            ("clerical",)),\n    ("material_handler",    ("material handler",)),\n    ("dray_admin_fee",      ("dray",)),\n    ("qa",                  ("qa ", " qa", "quality assurance")),\n]\n\n\ndef _vas_role(notes: str) -> str:\n    low = (notes or "").lower()\n    for role, words in _ROLE_WORDS:\n        if any(w in low for w in words):\n            return role\n    return "general_labor"\n\n\ndef apply_vas_labor_check(invoice: dict, result: dict) -> None:\n    """Judge an hourly VAS project against the MSA hourly table: role x site.\n\n    A VAS job described as a project plus hours ("MAY 2026 CONSOLIDATION PROJECT -\n    24.49 HRS") carries everything needed for a verdict, but parked at `needs_detail`\n    because nothing derived the rate. This divides the total by the hours, works out\n    which row of the MSA hourly table the work belongs to, and compares.\n\n    **The rate depends on both the site and the kind of work**, which is why a single\n    figure per warehouse was not enough. South Carolina bills general labour at\n    $53.55 but physical inventory and stock consolidation at $63.00, so 755701 —\n    a consolidation project at $63.00/hr — is exactly on contract, and reading it\n    against a lone "SC hourly" number made a correct invoice look overbilled.\n\n    When the derived rate matches no row for that site, it is only disputed if it is\n    ABOVE every rate in the site\'s column; the amount claimed is the excess over the\n    highest contracted rate, which is the most defensible figure. A rate at 1.5x the\n    matched role is reported as apparent overtime for a human rather than disputed,\n    since the MSA carries no overtime multiplier.\n    """\n    if (invoice.get("type_of_invoice") or "").strip().upper() != "VAS":\n        return\n    if result.get("_settled") or result.get("status") == "error":\n        return\n    if result.get("_pallet_rule"):     # a pallet work order, not a labour job\n        return\n    m = _VAS_HOURS.search(invoice.get("notes") or "")\n    if not m:\n        return\n    hours = float(m.group(1))\n    if hours <= 0:\n        return\n\n    wh = result.get("warehouse")\n    card = ((result.get("_rates") or {}).get("admin_vas") or {}).get(wh) or {}\n    roles = card.get("hourly_roles") or {}\n    if not roles:\n        return                          # pre-v1.6.0 snapshot: no role table to judge against\n\n    notes = invoice.get("notes") or ""\n    role = _vas_role(notes)\n    msa_rate = roles.get(role) or card.get("vas_hourly")\n    if not msa_rate:\n        return\n\n    amount = result.get("billed_amount")\n    if amount is None:\n        amount = float(invoice.get("amount") or 0)\n    derived = round(amount / hours, 4)\n    result["_labor_rule"] = True\n    # validate() left a "provide hours from the invoice detail" placeholder because it\n    # could not see the hours. We just supplied them, so drop it — leaving it in makes\n    # a row read "valid" and "needs more detail" at once.\n    result["discrepancies"] = [d for d in (result.get("discrepancies") or [])\n                               if "hourly rate" not in str(d)]\n\n    pretty = role.replace("_", " ")\n    # Any row of this site\'s column is a contracted rate. Match the derived rate\n    # against all of them, not just the role we guessed from the wording.\n    exact = [r_ for r_, v in roles.items() if abs(derived - v) < 0.005]\n    if exact:\n        matched = exact[0].replace("_", " ")\n        result["status"] = "valid"\n        result["expected_amount"] = round(hours * derived, 2)\n        result["variance"] = 0.0\n        result["variance_percent"] = 0.0\n        note = (f"VALID vs the MSA hourly table: {hours:g} hrs x ${derived:,.4f} = "\n                f"${amount:,.2f}, exact, at the {wh} {matched} rate.")\n        if exact[0] != role:\n            note += (f" Wording reads as {pretty}; the rate billed is the {matched} row. "\n                     f"Both are contracted for this site.")\n        result["line_report"] = note\n        return\n\n    if derived > msa_rate:\n        # Overtime at 1.5x is agreed (Anthony, 2026-08-12), so it is a contracted rate\n        # like any other. Checked against every role in the column, not just the role\n        # inferred from the wording, so OT on a specialised rate also resolves.\n        mult = card.get("overtime_multiplier")\n        if mult:\n            ot_hits = [r_ for r_, v in roles.items() if abs(derived - round(v * mult, 4)) < 0.01]\n            if ot_hits:\n                base = ot_hits[0]\n                result["status"] = "valid"\n                result["expected_amount"] = round(hours * derived, 2)\n                result["variance"] = 0.0\n                result["variance_percent"] = 0.0\n                result["line_report"] = (\n                    f"VALID vs the MSA hourly table: {hours:g} hrs x ${derived:,.4f} = "\n                    f"${amount:,.2f}, exact, at {mult:g}x overtime on the {wh} "\n                    f"{base.replace(\'_\', \' \')} rate of ${roles[base]:,.4f}. Overtime at "\n                    f"{mult:g}x is agreed.")\n                return\n        ceiling = max(roles.values())\n        if derived > ceiling:\n            over = round((derived - ceiling) * hours, 2)\n            result["status"] = "disputed"\n            result["variance"] = over\n            result["variance_percent"] = round(over / amount * 100, 1) if amount else None\n            result["discrepancies"].append(\n                f"{hours:g} hrs at ${derived:,.4f}/hr is above every contracted {wh} hourly "\n                f"rate (highest is ${ceiling:,.4f}) — ${over:,.2f} above the ceiling; reads as "\n                f"{pretty}, whose rate is ${msa_rate:,.4f}")\n            return\n        result["status"] = "discrepancy"\n        result["variance"] = round((derived - msa_rate) * hours, 2)\n        result["discrepancies"].append(\n            f"{hours:g} hrs at ${derived:,.4f}/hr matches no row of the {wh} hourly table but "\n            f"sits within its range; reads as {pretty} (${msa_rate:,.4f}). Identify the role "\n            f"before paying")\n        return\n\n    result["status"] = "valid"\n    result["variance"] = 0.0\n    result["line_report"] = (\n        f"{hours:g} hrs at ${derived:,.4f}/hr, below the {wh} {pretty} rate of "\n        f"${msa_rate:,.4f} — ${abs(round((msa_rate - derived) * hours, 2)):,.2f} in "\n        f"Americanflat\'s favour, nothing to dispute.")'


DOCSTRING_NOTE = [
    "",
    "    A VAS pallet work order judged by apply_vas_pallet_check is skipped outright.",
    "    Its `notes` carry the full basis (quantity, rate, total) and the verdict is",
    "    already definitive; the PDF adds nothing, and for these invoices it is a",
    "    scanned image that would come back `needs_detail` and demote a sound `valid`.",
]

RATES_LINES = [
    "        # The rate card rides along so later checks (apply_vas_labor_check) can",
    "        # look up a per-warehouse contracted rate without being handed it again.",
    '        "_rates": rates,',
]

LINE_PASS_GUARD = [
    '    if result.get("_pallet_rule"):',
    "        return",
]

MSA_GUARD = [
    "    # A VAS pallet work order already got a verdict from apply_vas_pallet_check,",
    "    # on the same charge. Running the generic detector too would re-judge it and",
    "    # overwrite the variance with a second, differently-derived figure.",
    '    if result.get("_pallet_rule"):',
    "        return",
]


class Abort(Exception):
    pass


def find_one(lines, needle, what):
    hits = [i for i, l in enumerate(lines) if l == needle]
    if len(hits) != 1:
        raise Abort(f"{what}: expected exactly one line {needle!r}, found {len(hits)}")
    return hits[0]


def step_new_functions(lines, report):
    if any(l.startswith("def apply_vas_pallet_check") for l in lines):
        report.append("  already present  the two new check functions")
        return lines
    at = find_one(lines, "def apply_msa_conflicts(invoice: dict, result: dict) -> None:",
                  "new functions")
    report.append(f"  ADD              apply_vas_pallet_check + apply_vas_labor_check "
                  f"({len(NEW_FUNCTIONS.splitlines())} lines) before apply_msa_conflicts, line {at + 1}")
    # two blank lines after, so apply_msa_conflicts keeps its PEP-8 separation
    return lines[:at] + NEW_FUNCTIONS.split("\n") + ["", ""] + lines[at:]


def step_rates(lines, report):
    if any(l.strip() == '"_rates": rates,' for l in lines):
        report.append("  already present  the rate card on validate()'s result")
        return lines
    at = find_one(lines, '        "discrepancies": [],', "carry the rate card")
    report.append(f"  ADD              carry the rate card on validate()'s result, line {at + 2}")
    return lines[:at + 1] + RATES_LINES + lines[at + 1:]


def step_line_pass(lines, report):
    at = find_one(lines, '    was_disputed = result["status"] == "disputed"',
                  "line-pass guard")
    # already guarded?
    window = lines[max(0, at - 8):at]
    if any('result.get("_pallet_rule")' in l for l in window):
        report.append("  already present  the line-pass skip for pallet work orders")
        return lines
    report.append(f"  ADD              _line_pass_keeping_disputes skips pallet rows, line {at + 1}")
    lines = lines[:at] + LINE_PASS_GUARD + lines[at:]
    # the explanatory paragraph goes at the end of that function's docstring,
    # which is the closing triple-quote immediately above the guard we just added
    close = at - 1
    while close >= 0 and lines[close].strip() != '"""':
        close -= 1
    if close >= 0:
        lines = lines[:close] + DOCSTRING_NOTE + lines[close:]
        report.append("                   (plus the matching note in its docstring)")
    return lines


def step_msa_guard(lines, report):
    start = find_one(lines, "def apply_msa_conflicts(invoice: dict, result: dict) -> None:",
                     "apply_msa_conflicts guard")
    body = lines[start:start + 40]
    if any('result.get("_pallet_rule")' in l for l in body):
        report.append("  already present  apply_msa_conflicts standing aside")
        return lines
    rel = next((k for k, l in enumerate(body) if l == '    wh = result.get("warehouse")'), None)
    if rel is None:
        raise Abort("apply_msa_conflicts guard: could not find its "
                    '`wh = result.get("warehouse")` line')
    at = start + rel
    report.append(f"  ADD              apply_msa_conflicts stands aside for pallet rows, line {at + 1}")
    return lines[:at] + MSA_GUARD + lines[at:]


def step_call_sites(lines, report):
    out, added, present = [], 0, 0
    i = 0
    while i < len(lines):
        out.append(lines[i])
        m = re.match(r"^(\s*)r = validate\(inv, rates\)\s*$", lines[i])
        if m:
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if "apply_vas_pallet_check" in nxt:
                present += 1
            elif nxt.strip() == "apply_msa_conflicts(inv, r)":
                pad = m.group(1)
                out.append(f"{pad}apply_vas_pallet_check(inv, r)")
                out.append(f"{pad}apply_vas_labor_check(inv, r)")
                added += 1
                report.append(f"  ADD              both checks wired in after validate(), line {i + 1}")
            else:
                raise Abort(f"call site at line {i + 1}: expected "
                            f"`apply_msa_conflicts(inv, r)` on the next line, found {nxt.strip()!r}")
        i += 1
    if present:
        report.append(f"  already present  {present} call site(s) already wired")
    if added + present != 2:
        raise Abort(f"expected 2 call sites, handled {added + present}")
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path, write = sys.argv[1], "--write" in sys.argv
    src = open(path).read()
    lines = src.split("\n")

    for marker, why in [("def apply_msa_conflicts", "this does not look like validate_rate_card.py"),
                        ("def merge_report", "this file predates 1.5.0 — install 1.5.x first")]:
        if marker not in src:
            print(f"REFUSING: {why} ({marker} not found in {path})")
            return 1

    report = []
    try:
        for step in (step_new_functions, step_rates, step_line_pass,
                     step_msa_guard, step_call_sites):
            lines = step(lines, report)
    except Abort as e:
        print(f"REFUSING to change anything — {e}")
        print("\nNothing was written. Send me this message and the output of:")
        print(f"  grep -n 'r = validate(inv, rates)' {path}")
        return 1

    print(f"{path}")
    for r in report:
        print(r)

    out = "\n".join(lines)
    if out == src:
        print("\nNothing to do — v1.6.0 is already installed.")
        return 0

    try:
        compile(out, path, "exec")
    except SyntaxError as e:
        print(f"\nREFUSING: the result would not compile ({e}). Nothing written.")
        return 1
    print("\nResult compiles cleanly.")

    if not write:
        print("DRY RUN — re-run with --write to apply.")
        return 0

    backup = f"{path}.bak-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(path, backup)
    open(path, "w").write(out)
    print(f"backup written: {backup}")
    print(f"updated: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
