#!/usr/bin/env python3
"""Make the storage and admin notes say which rate schedule they used.

Anthony, 2026-09-17: "The MSA rates are live — change the validator to reflect
that in the validated notes. Storage rates are where I'm seeing it the most."

The validator's card has held the MSA rates since v1.6.0, so the number in a
fresh note is already right. What was missing is provenance. The note read

    Storage rate is $5.90/pallet for fontana, ...

and it reads exactly the same shape whether $5.90 came from a superseded card or
$4.47 came from the live one. That ambiguity is not cosmetic: 70 storage rows
have been carrying pre-MSA rates written by an out-of-date writer, and nothing in
the text said so. Naming the schedule makes a stale note self-identifying.

The PDF line pass already did this ("VALID vs MSA rate schedule", "at
MSA-schedule rates"). This brings the two header-level checks people actually
read — storage and admin — into line with it.

Every change is to note text and to added card keys. No rate value moves, no
verdict changes, nothing is removed.

    python3 name_the_msa_in_notes.py <path-to-skill-dir>            # dry run
    python3 name_the_msa_in_notes.py <path-to-skill-dir> --write
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Recorded in the card's own _pending_review prose since 2026-08-05; lifted into
# machine-readable keys so a note can cite them instead of hardcoding.
MSA_EFFECTIVE_FROM = "2026-05-04"
PRE_MSA_STORAGE = {"fontana": 5.9055, "new_jersey": 5.98, "south_carolina": 5.0925}

HELPER = '''
# --- where a quoted rate came from -----------------------------------------

def _msa_provenance(card: dict, site: str = None) -> tuple:
    """(effective-date phrase, superseded phrase) for a note that quotes a rate.

    A note is the only place a reader sees which schedule priced an invoice, and
    until 2026-09-17 it did not say. "Storage rate is $5.90/pallet" and "Storage
    rate is $4.47/pallet" are the same sentence; one is the live MSA and one is a
    superseded card, and no one could tell them apart without knowing the numbers
    by heart. Saying the schedule out loud makes a stale note identify itself.

    Both halves degrade to empty strings, so a card without these keys still
    produces a sentence that reads correctly — just without the provenance.
    """
    eff = card.get("_msa_effective_from")
    eff_phrase = f", live from {eff}" if eff else ""
    prior = (card.get("_pre_msa") or {}).get(site) if site else None
    sup_phrase = f" Supersedes the pre-MSA ${prior:,.2f}." if prior else ""
    return eff_phrase, sup_phrase

'''

EDITS = [
    # ---- storage: the one Anthony sees most --------------------------------
    (
        "storage note (no pallet count)",
        '''                f"Storage rate is ${rate:,.2f}/pallet for {wh}, but pallet count is "
                f"not on the invoice header. Provide pallet_count (from the invoice "
                f"detail) to validate ${amount:,.2f}."''',
        '''                f"Storage at the MSA rate of ${rate:,.2f}/pallet for {wh}{_eff}."
                f"{_sup} Pallet count is not on the invoice header, so provide "
                f"pallet_count (from the invoice detail) to validate ${amount:,.2f}."''',
    ),
    (
        "storage discrepancy line",
        '''                f"Storage: {pallets} pallets x ${rate:,.2f} = ${expected:,.2f}, billed ${amount:,.2f}"''',
        '''                f"Storage: {pallets} pallets x ${rate:,.2f} MSA{_eff} = ${expected:,.2f}, "
                f"billed ${amount:,.2f}"''',
    ),
    # ---- admin: the other header check that quotes a card rate --------------
    (
        "admin overbilled line",
        '''                f"Admin: billed ${amount:,.2f} exceeds full week ${expected:,.2f}{tax_note} — overbilled.")''',
        '''                f"Admin: billed ${amount:,.2f} exceeds the MSA full week ${expected:,.2f}"
                f"{tax_note}{_adm_eff} — overbilled.")''',
    ),
    (
        "admin partial-week line",
        '''                    f"Admin: billed ${amount:,.2f} vs full week ${expected:,.2f}{tax_note}; "''',
        '''                    f"Admin: billed ${amount:,.2f} vs the MSA full week ${expected:,.2f}{tax_note}{_adm_eff}; "''',
    ),
    (
        "admin missing-tax line",
        '''                    f"Admin: billed ${amount:,.2f} = full base week WITHOUT the {rate * 100:.0f}% labor tax "''',
        '''                    f"Admin: billed ${amount:,.2f} = the MSA full base week WITHOUT the {rate * 100:.0f}% labor tax "''',
    ),
    # ---- bind the provenance strings at each site --------------------------
    (
        "storage: read the provenance",
        '''        pallets = invoice.get("pallet_count")''',
        '''        _eff, _sup = _msa_provenance(rates.get("storage", {}), wh)
        pallets = invoice.get("pallet_count")''',
    ),
    (
        "admin: read the provenance",
        '''        # Labor tax that switches on/off over time (e.g. NJ 5%, dropped 2026-04-27).''',
        '''        _adm_eff, _ = _msa_provenance(rates.get("admin_vas", {}))
        # Labor tax that switches on/off over time (e.g. NJ 5%, dropped 2026-04-27).''',
    ),
]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1])
    write = "--write" in sys.argv
    script = root / "scripts" / "validate_rate_card.py"
    card_path = root / "references" / "rate-card-snapshot.json"
    for p in (script, card_path):
        if not p.exists():
            print(f"ERROR: not found: {p}")
            return 2

    src = script.read_text(encoding="utf-8")
    card = json.loads(card_path.read_text(encoding="utf-8"))

    # --- the code -----------------------------------------------------------
    applied, already, missing = [], [], []
    if "_msa_provenance" in src:
        already.append("helper _msa_provenance")
    else:
        anchor = "# ---- Storage: per-pallet x count"
        if anchor not in src:
            print("REFUSING: cannot find the storage section to insert the helper above")
            return 2
        # place it above validate()'s body, at module level, before the first use
        marker = "\ndef validate("
        if marker not in src:
            print("REFUSING: cannot find validate() to place the helper before")
            return 2
        src = src.replace(marker, "\n" + HELPER.strip("\n") + "\n\n" + marker.lstrip("\n"), 1)
        applied.append("helper _msa_provenance")

    for name, old, new in EDITS:
        if new.strip() in src:
            already.append(name)
            continue
        n = src.count(old)
        if n != 1:
            missing.append(f"{name} (anchor matched {n} times)")
            continue
        src = src.replace(old, new, 1)
        applied.append(name)

    if missing:
        print("REFUSING — these anchors did not match exactly once:")
        for m in missing:
            print("   ", m)
        return 2

    # --- the card: machine-readable provenance, added not replaced ----------
    card_changes = []
    st = card.setdefault("storage", {})
    if st.get("_msa_effective_from") != MSA_EFFECTIVE_FROM:
        st["_msa_effective_from"] = MSA_EFFECTIVE_FROM
        card_changes.append("storage._msa_effective_from")
    if st.get("_pre_msa") != PRE_MSA_STORAGE:
        st["_pre_msa"] = PRE_MSA_STORAGE
        card_changes.append("storage._pre_msa")
    av = card.setdefault("admin_vas", {})
    if av.get("_msa_effective_from") != MSA_EFFECTIVE_FROM:
        av["_msa_effective_from"] = MSA_EFFECTIVE_FROM
        card_changes.append("admin_vas._msa_effective_from")

    # nothing may be lost from the card
    for site, val in (("fontana", 4.47), ("new_jersey", 4.34), ("south_carolina", 3.35)):
        if st.get(site) != val:
            print(f"REFUSING: storage.{site} is {st.get(site)}, expected the MSA {val} — "
                  f"this script does not move rates, only labels them")
            return 2

    compile(src, str(script), "exec")

    for label, items in (("ADD", applied), ("already present", already)):
        for i in items:
            print(f"  {label:16} {i}")
    for c in card_changes:
        print(f"  {'CARD ADD':16} {c}")
    print("\nResult compiles cleanly.")

    if not write:
        print("DRY RUN — re-run with --write to apply.")
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(script, f"{script}.bak-{stamp}")
    shutil.copy2(card_path, f"{card_path}.bak-{stamp}")
    script.write_text(src, encoding="utf-8")
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    print(f"\nbackups written (.bak-{stamp}); files updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
