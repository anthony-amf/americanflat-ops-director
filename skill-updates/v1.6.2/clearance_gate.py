#!/usr/bin/env python3
"""Make the green stamp mean "every applicable check passed".

Anthony, 2026-09-22: "The validated section only needs to say Needs detail if
additional checks need to be made. If the verdict is OK to pay, then it should
read the green validated stamp." — resolved as: green where the checks truly
pass, not wherever nothing was flagged.

The contradiction he was looking at is real and it is the note's fault, not the
chip's. `verdict` was the else-branch of compose_report: it printed "OK to pay"
for anything that was not a discrepancy or a dispute, including rows where
nothing had been checked at all. On 2026-09-22 that was 115 rows worth $778,360
reading "OK to pay" under a Needs-detail chip — and on every one of them the
invoice math was unchecked, the rate card was unchecked, and not one carried a
line-level contract result.

So this adds two things:

  * `clearance()` — which axes does this invoice type need, which have produced a
    definite pass, and what is still outstanding. SP/LTL needs contract AND
    shipping; everything else needs contract only.
  * an honest verdict line — "OK to pay" only when clearance() says cleared,
    otherwise "Not cleared — <what is outstanding>".

`apply_clearance()` promotes a row to valid when every axis passes, which is the
promotion rule the Stedi runbook's step 6 table already describes but nothing
implemented. It only ever promotes: it never downgrades a valid, never touches a
disputed, and never invents a pass the evidence does not support.

    python3 clearance_gate.py <path-to-skill-dir>            # dry run
    python3 clearance_gate.py <path-to-skill-dir> --write
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

NEW_CODE = '''
# --- is this invoice actually cleared? --------------------------------------

# Which axes a type must satisfy before it can be called validated. SP/LTL is
# the only two-axis family: its charges are per-order, so "were these orders
# really shipped" is a separate question from "were they priced correctly", and
# both have to be answered. Everything else is priced from the invoice alone.
AXES_BY_TYPE = {
    "smlprcl/ltl": ("contract", "shipping"),
    "storage": ("contract",),
    "receiving": ("contract",),
    "vas": ("contract",),
    "admin": ("contract",),
}

# A pass that actually priced the invoice against the card, rather than merely
# recording its header total. Written by the PDF line pass or a deep review.
_CONTRACT_PASS = re.compile(
    r"at MSA-schedule rates|VALID vs MSA rate schedule|VALID vs the MSA hourly table"
    r"|VALID vs MSA AF-9|Line detail:", re.I)
# A recorded order-level shipping result.
_STEDI_BLOCK = re.compile(r"\\[STEDI \\d{4}-\\d{2}-\\d{2}\\]")


def clearance(invoice: dict, result: dict, prior_report: str = "") -> tuple:
    """(cleared, outstanding) — may this row be stamped valid, and if not, why not.

    Reads the row's accumulated report as well as this pass's result, because no
    single pass sees both axes: the contract answer comes from the daytime sweep
    or a deep review, the shipping answer from the nightly Stedi job, and they
    land on the row days apart. Judging from one pass alone is exactly how a
    clean shipping check could seal an invoice whose rates were never examined.

    Conservative by construction: an axis counts as passed only on positive
    evidence. Silence is "outstanding", never "fine".
    """
    text = (prior_report or "") + "\\n" + (result.get("line_report") or "")
    t = (result.get("invoice_type") or invoice.get("type_of_invoice") or "").strip().lower()
    axes = AXES_BY_TYPE.get(t, ("contract",))
    outstanding = []

    for axis in axes:
        if axis == "contract":
            # This pass priced it, or a line-level/deep pass already did.
            ok = result.get("status") == "valid" or bool(_CONTRACT_PASS.search(text))
            if not ok:
                outstanding.append("rate card and invoice math")
        elif axis == "shipping":
            stedi = _STEDI_BLOCK.search(text)
            if not stedi:
                outstanding.append("order-level shipping check")
            elif "UNMATCHED" in text:
                outstanding.append("shipping gaps still open")
            elif "OVERCHARGE" in text:
                outstanding.append("pick overcharge unresolved")

    return (not outstanding), outstanding


def apply_clearance(invoice: dict, result: dict, prior_report: str = "") -> None:
    """Promote to valid only when every applicable axis has passed.

    Promotion only. A `disputed` or `discrepancy` verdict is a finding and is
    left exactly as it is; a row already valid is left alone. Stamping valid
    drops a row out of the daytime work list permanently, so the bar is that
    every axis the type requires produced a definite pass.
    """
    if result.get("status") in ("disputed", "discrepancy", "error", "valid"):
        return
    cleared, outstanding = clearance(invoice, result, prior_report)
    result["_outstanding"] = outstanding
    if cleared:
        result["status"] = "valid"

'''

VERDICT_OLD = '''    else:
        verdict = "OK to pay"
    line_detail = r.get("line_report")'''

VERDICT_NEW = '''    elif s == "valid":
        verdict = "OK to pay"
    else:
        # "OK to pay" used to print here for anything not actively flagged,
        # including rows where nothing had been checked — 115 rows / $778,360 of
        # them on 2026-09-22, every one with the invoice math and the rate card
        # still unchecked. Say what is outstanding instead, so the line and the
        # chip cannot disagree.
        missing = r.get("_outstanding")
        if missing is None:
            _, missing = clearance({}, r, prior_report)
        verdict = ("Not cleared — still to check: " + "; ".join(missing)) if missing else "OK to pay"
    line_detail = r.get("line_report")'''

SIG_OLD = 'def compose_report(r: dict, paid_date: str = "") -> str:'
SIG_NEW = 'def compose_report(r: dict, paid_date: str = "", prior_report: str = "") -> str:'


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1])
    write = "--write" in sys.argv
    script = root / "scripts" / "validate_rate_card.py"
    if not script.exists():
        print(f"ERROR: not found: {script}")
        return 2
    src = script.read_text(encoding="utf-8")
    applied, already = [], []

    if "def clearance(" in src:
        already.append("clearance/apply_clearance")
    else:
        anchor = "\ndef compose_report("
        if anchor not in src:
            print("REFUSING: cannot find compose_report to place the gate before")
            return 2
        src = src.replace(anchor, "\n" + NEW_CODE.strip("\n") + "\n\n" + anchor.lstrip("\n"), 1)
        applied.append("clearance/apply_clearance")

    for name, old, new in (("compose_report signature", SIG_OLD, SIG_NEW),
                           ("honest verdict line", VERDICT_OLD, VERDICT_NEW)):
        if new.strip().splitlines()[0] in src and name == "compose_report signature" and SIG_NEW in src:
            already.append(name); continue
        if "Not cleared — still to check" in src and name == "honest verdict line":
            already.append(name); continue
        n = src.count(old)
        if n != 1:
            print(f"REFUSING: anchor for {name!r} matched {n} times, expected 1")
            return 2
        src = src.replace(old, new, 1)
        applied.append(name)

    compile(src, str(script), "exec")
    for label, items in (("ADD", applied), ("already present", already)):
        for i in items:
            print(f"  {label:16} {i}")
    print("\nResult compiles cleanly.")
    if not write:
        print("DRY RUN — re-run with --write to apply.")
        return 0
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(script, f"{script}.bak-{stamp}")
    script.write_text(src, encoding="utf-8")
    print(f"\nbackup written (.bak-{stamp}); {script} updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
