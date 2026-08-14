#!/usr/bin/env python3
"""Install v1.6.0 by replacing files outright, after reporting exactly what that costs.

Why this exists: install_v1_6_0.py edits your file in place, which needs your file to
look roughly like the 1.5.0 it was built against. It does not — 1.5.1 has no
`_line_pass_keeping_disputes` at all, so the two releases diverged further back than
either line's version number suggests. A cloud session cannot read the 1.5.1 file to
work out the difference (every GitHub path to americanflat/* is blocked from there),
so this script does the comparison locally and shows you the answer.

It compares your validator against BOTH bundled copies:

  * v1.5.0 — the base this release was built on
  * v1.6.0 — what this release ships

and reports, function by function:

  LOST      in yours, not in v1.6.0        <- the thing that actually matters
  NEW       in v1.6.0, not in yours
  CHANGED   in both, but yours differs from the v1.5.0 baseline (your own work)
  SAME      identical

Then, only if nothing would be LOST, it replaces the files. If anything would be lost
it refuses and prints the names, because that is a merge decision and not a scripted
one. `--accept-losses` overrides, and prints what you accepted.

    python3 install_hardcoded.py /path/to/skill-clone                    # report only
    python3 install_hardcoded.py /path/to/skill-clone --write
    python3 install_hardcoded.py /path/to/skill-clone --write --accept-losses

Files replaced on --write: scripts/validate_rate_card.py,
references/rate-card-snapshot.json. Each is backed up first with a timestamp. Nothing
is deleted. skill.toml, CHANGELOG.md, SKILL.md and .env.example are left to
prepare_release.py, which handles them the same way as before.
"""
import ast
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_VALIDATOR = HERE.parent / "v1.5.0" / "validate_rate_card.py"
NEW_VALIDATOR = HERE / "validate_rate_card.py"
NEW_CARD = HERE / "rate-card-snapshot.json"


def top_level_defs(src: str, label: str) -> dict:
    """{name: normalised source} for every top-level def, and module-level assignments."""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f"REFUSING: {label} does not parse ({e})")
        sys.exit(1)
    lines = src.split("\n")
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            seg = "\n".join(lines[node.lineno - 1:node.end_lineno])
            # ignore pure whitespace/comment drift when deciding "changed"
            out[node.name] = "\n".join(
                l.rstrip() for l in seg.split("\n")
                if l.strip() and not l.strip().startswith("#")
            )
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    repo = Path(sys.argv[1]).expanduser().resolve()
    write = "--write" in sys.argv
    accept = "--accept-losses" in sys.argv

    mine = repo / "scripts" / "validate_rate_card.py"
    card = repo / "references" / "rate-card-snapshot.json"
    for p in (mine, card):
        if not p.exists():
            print(f"REFUSING: {p} is missing — is {repo} a clone of the skill repo?")
            return 1
    for p in (BASE_VALIDATOR, NEW_VALIDATOR, NEW_CARD):
        if not p.exists():
            print(f"REFUSING: {p} is missing from this repo — git pull first.")
            return 1

    yours = top_level_defs(mine.read_text(), str(mine))
    base = top_level_defs(BASE_VALIDATOR.read_text(), "bundled v1.5.0")
    new = top_level_defs(NEW_VALIDATOR.read_text(), "bundled v1.6.0")

    lost = sorted(set(yours) - set(new))
    gained = sorted(set(new) - set(yours))
    changed, same = [], 0
    for name in sorted(set(yours) & set(new)):
        if yours[name] == new[name]:
            same += 1
        elif name in base and yours[name] != base[name]:
            changed.append(name)          # yours diverges from the 1.5.0 baseline
        else:
            changed.append(name)

    print(f"your validator: {mine}")
    print(f"  {len(yours)} top-level definitions, {len(mine.read_text().splitlines())} lines")
    print(f"v1.6.0 ships:   {len(new)} definitions, "
          f"{len(NEW_VALIDATOR.read_text().splitlines())} lines\n")

    print(f"SAME     {same}")
    print(f"NEW      {len(gained)}" + (f"  {', '.join(gained)}" if gained else ""))
    print(f"CHANGED  {len(changed)}" + (f"  {', '.join(changed)}" if changed else ""))
    print(f"LOST     {len(lost)}" + (f"  {', '.join(lost)}" if lost else ""))

    if lost:
        print(f"""
{len(lost)} definition(s) exist in your file and not in v1.6.0. Replacing the file
would remove them:

    {', '.join(lost)}

That is a merge decision. Either tell me these names and I will fold them into
v1.6.0 properly, or re-run with --accept-losses if you are certain they are dead.""")
        if not accept:
            print("\nNothing written.")
            return 1

    if changed:
        print(f"""
{len(changed)} definition(s) differ between your file and v1.6.0. Some of that is
v1.6.0's own work; some may be yours. To see which is which for any one of them:

    diff <(sed -n '/^def {changed[0]}/,/^def /p' {mine}) \\
         <(sed -n '/^def {changed[0]}/,/^def /p' {NEW_VALIDATOR})""")

    if not write:
        print("\nREPORT ONLY — nothing written. Re-run with --write to replace the files.")
        return 0

    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    for src, dest in ((NEW_VALIDATOR, mine), (NEW_CARD, card)):
        shutil.copy2(dest, dest.with_name(f"{dest.name}.bak-{stamp}"))
        shutil.copy2(src, dest)
        print(f"replaced {dest.relative_to(repo)}  (backup .bak-{stamp})")
    if lost and accept:
        print(f"\nACCEPTED the loss of: {', '.join(lost)}")

    print(f"""
Now finish the release — it handles skill.toml, CHANGELOG.md, SKILL.md and
.env.example, and will report the code and rate card as already applied:

  python3 {HERE / 'prepare_release.py'} {repo} --write
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
