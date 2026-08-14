#!/usr/bin/env python3
"""Build v1.6.0 on the PUBLISHED lineage, in a clone of skill-yusen-invoice-validator.

Use this one. The other three installers in this directory were built against a
different 1.5.0 than the one that was released, which is why all three refused.

What went wrong: this repo's `skill-updates/v1.5.0/` is the report-merge release,
built on a lineage carrying a PDF line-pass subsystem (`apply_line_pass`,
`_download_pdf`, `_parse_charge_lines`, …). The *published* 1.5.0 is a different
release — operator-supplied line detail (`parse_detail`, `_compare_rates_to_card`,
the `--detail` flag). Two 1.5.0s, same number, different code. Patching one with
the other's diff could only ever fail, and replacing wholesale would have deleted
`--detail`.

So this adds only what v1.6.0 is actually about, on top of whatever the published
file already is:

  1. apply_vas_pallet_check, apply_vas_labor_check, _vas_role, and their constants
  2. the rate card on validate()'s result, so the labour check can read it
  3. apply_msa_conflicts stands aside once the pallet rule has judged a charge
  4. both checks wired in after validate(), at both call sites
  5. a guard so neither check overrides a --detail verdict
  6. 13 additive rate-card paths, the version bump, the changelog entry, one SKILL.md line

It does NOT bring over the PDF line pass, `_deferral_block`, or the tagged-block
`merge_report` from the other lineage. Those are real work, but they are not this
release, and shipping 600 unreviewed lines under "two VAS rules" would be wrong.

    python3 release_on_published.py /path/to/skill-clone            # dry run
    python3 release_on_published.py /path/to/skill-clone --write

Purely additive: nothing is deleted, every in-place edit is backed up with a
timestamp, and re-running reports what is already in place and writes nothing. It
never pushes, tags, opens a PR, or posts to Slack.
"""
import ast
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "validate_rate_card.py"          # the reviewed v1.6.0 file
TARGET_VERSION = "1.6.0"

MSA_GUARD = [
    "    # A VAS pallet work order already got a verdict from apply_vas_pallet_check,",
    "    # on the same charge. Running the generic detector too would re-judge it and",
    "    # overwrite the variance with a second, differently-derived figure.",
    '    if result.get("_pallet_rule"):',
    "        return",
]
DETAIL_GUARD = [
    "    # An operator supplied the basis explicitly with --detail, and validate()",
    "    # already judged against it. That is a person reading the worksheet, which",
    "    # outranks anything parsed out of `notes` — stand aside rather than re-judge.",
    '    if result.get("detail_lines"):',
    "        return",
]
RATES_LINES = [
    "        # The rate card rides along so later checks (apply_vas_labor_check) can",
    "        # look up a per-warehouse contracted rate without being handed it again.",
    '        "_rates": rates,',
]
OLD_VAS_LINE = "- **VAS / Small Parcel / LTL** → header total reported as `needs_detail`."
NEW_VAS_LINES = """- **VAS** → two shapes resolve from `notes` alone, with no PDF and no OCR:
  a **pallet work order** ("N PALLETS W/SHRINKWRAP @ $R/PALLET" — how Savannah
  bills pallets) is recomputed and then judged against AF-9's $10.00 all-in, and an
  **hourly project** ("… PROJECT - N HRS @ $R/HR") has its rate derived from
  total ÷ hours and matched against the site's column of the MSA hourly table,
  overtime at 1.5x included. A `--detail` verdict outranks both. Anything else →
  header total, `needs_detail`.
- **Small Parcel / LTL** → header total reported as `needs_detail`."""


def fail(msg):
    print(f"REFUSING: {msg}")
    sys.exit(1)


def backup(p: Path):
    shutil.copy2(p, p.with_name(f"{p.name}.bak-{datetime.now():%Y%m%d-%H%M%S}"))


def new_code_block() -> str:
    """The constants + three new functions, lifted from the reviewed v1.6.0 file."""
    src = SOURCE.read_text()
    lines = src.split("\n")
    tree = ast.parse(src)
    wanted = ("apply_vas_pallet_check", "_vas_role", "apply_vas_labor_check")
    spans = [n for n in tree.body if getattr(n, "name", "") in wanted]
    if len(spans) != 3:
        fail(f"expected 3 new functions in {SOURCE}, found {len(spans)}")
    try:
        first = next(i for i, l in enumerate(lines) if l.startswith("AF9_PALLET_ALL_IN"))
    except StopIteration:
        fail(f"AF9_PALLET_ALL_IN not found in {SOURCE}")
    last = max(n.end_lineno for n in spans)
    return "\n".join(lines[first:last])


def body_insert_at(fn) -> int:
    """0-based index to insert at: the top of fn's body, past any docstring.

    Taken from the AST rather than by scanning for `\"\"\"` lines. Scanning is what
    broke the first version of this script: a docstring opening with text on the
    same line (`\"\"\"Judge a pallet work order...`) never equals `\"\"\"`, so the scan
    ran past the closing quote into the *next* function and put the guard there.
    """
    first = fn.body[0]
    if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) \
            and isinstance(first.value.value, str):
        return first.end_lineno          # 1-based last docstring line == index after it
    return first.lineno - 1              # no docstring: insert before the first statement


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    repo = Path(sys.argv[1]).expanduser().resolve()
    write = "--write" in sys.argv

    toml_p = repo / "skill.toml"
    val_p = repo / "scripts" / "validate_rate_card.py"
    card_p = repo / "references" / "rate-card-snapshot.json"
    cl_p = repo / "CHANGELOG.md"
    md_p = repo / "SKILL.md"
    for p in (toml_p, val_p, card_p, cl_p, md_p):
        if not p.exists():
            fail(f"{p} is missing — is {repo} a clone of the skill repo?")

    toml = toml_p.read_text()
    name = re.search(r'^name\s*=\s*"([^"]+)"', toml, re.M)
    ver = re.search(r'^version\s*=\s*"([^"]+)"', toml, re.M)
    if not name or not ver:
        fail("skill.toml has no name or version line")
    if name.group(1) != "skill-yusen-invoice-validator":
        fail(f"this clone is {name.group(1)}, not skill-yusen-invoice-validator")
    base = ver.group(1)

    src = val_p.read_text()
    if "def parse_detail" not in src:
        fail("this file has no parse_detail — it is not the published lineage. "
             "Do not use this script on it.")

    print(f"repo:    {repo}")
    print(f"base:    {base}" + (f"  ->  {TARGET_VERSION}" if base != TARGET_VERSION else ""))
    print(f"mode:    {'WRITE' if write else 'dry run'}\n")

    lines = src.split("\n")
    steps = []

    # 1 — the three new definitions, before apply_msa_conflicts
    if "def apply_vas_pallet_check" in src:
        steps.append("already present  the two new checks")
    else:
        anchor = next((i for i, l in enumerate(lines)
                       if l.startswith("def apply_msa_conflicts(")), None)
        if anchor is None:
            fail("could not find `def apply_msa_conflicts(` to insert before")
        block = new_code_block().split("\n")
        lines = lines[:anchor] + block + ["", ""] + lines[anchor:]
        steps.append(f"ADD              the two new checks + _vas_role ({len(block)} lines)")

    # 2 — carry the rate card on validate()'s result
    if any(l.strip() == '"_rates": rates,' for l in lines):
        steps.append("already present  the rate card on validate()'s result")
    else:
        hits = [i for i, l in enumerate(lines) if l.strip() == '"discrepancies": [],']
        if len(hits) != 1:
            fail(f'expected one `"discrepancies": [],`, found {len(hits)}')
        lines = lines[:hits[0] + 1] + RATES_LINES + lines[hits[0] + 1:]
        steps.append("ADD              the rate card on validate()'s result")

    # 3 — apply_msa_conflicts stands aside; 5 — both checks respect --detail
    for fname, guard, label in (
        ("apply_msa_conflicts", MSA_GUARD, "apply_msa_conflicts stands aside for pallet rows"),
        ("apply_vas_pallet_check", DETAIL_GUARD, "pallet check respects a --detail verdict"),
        ("apply_vas_labor_check", DETAIL_GUARD, "labour check respects a --detail verdict"),
    ):
        tree = ast.parse("\n".join(lines))
        fn = next((n for n in tree.body if getattr(n, "name", "") == fname), None)
        if fn is None:
            fail(f"{fname} is not in the file after step 1 — stopping")
        body = "\n".join(lines[fn.lineno - 1:fn.end_lineno])
        if guard[3].strip() in body:
            steps.append(f"already present  {label}")
            continue
        at = body_insert_at(fn)
        lines = lines[:at] + guard + lines[at:]
        steps.append(f"ADD              {label}")

    # 4 — the call sites
    out, added, present = [], 0, 0
    for l in lines:
        out.append(l)
        if l.strip() == "r = validate(inv, rates)":
            pad = l[:len(l) - len(l.lstrip())]
            present += 1
            out.append(f"{pad}apply_vas_pallet_check(inv, r)")
            out.append(f"{pad}apply_vas_labor_check(inv, r)")
            added += 1
    if "apply_vas_pallet_check(inv, r)" in src:
        steps.append("already present  both call sites")
    elif added != 2:
        fail(f"expected 2 `r = validate(inv, rates)` call sites, found {added}")
    else:
        lines = out
        steps.append(f"ADD              both checks wired in at {added} call sites")

    for s in steps:
        print("  " + s)

    result = "\n".join(lines)
    try:
        compile(result, str(val_p), "exec")
    except SyntaxError as e:
        fail(f"the result would not compile ({e}). Nothing written.")
    print("\n  result compiles cleanly")

    # nothing from the published file may disappear
    before = {n.name for n in ast.parse(src).body if hasattr(n, "name")}
    after = {n.name for n in ast.parse(result).body if hasattr(n, "name")}
    if before - after:
        fail(f"this would remove {', '.join(sorted(before - after))} — stopping")
    print(f"  nothing removed (kept all {len(before)}, added "
          f"{', '.join(sorted(after - before)) or 'none'})")

    if write and result != src:
        backup(val_p)
        val_p.write_text(result)
        print(f"  written: {val_p.relative_to(repo)}")

    # 6 — rate card, version, changelog, SKILL.md
    print("\n--- rate card ---")
    cmd = [sys.executable, str(HERE / "merge_rates_into_1_5_1.py"), str(card_p)]
    r = subprocess.run(cmd + (["--write"] if write else []), capture_output=True, text=True)
    print("\n".join("  " + l for l in (r.stdout or r.stderr).rstrip().split("\n")))
    if r.returncode != 0:
        fail("the rate-card merge refused — nothing further attempted")

    print("\n--- skill.toml / CHANGELOG.md / SKILL.md ---")
    if base == TARGET_VERSION:
        print(f"  already at {TARGET_VERSION}")
    elif write:
        backup(toml_p)
        toml_p.write_text(re.sub(rf'^version\s*=\s*"{re.escape(base)}"',
                                 f'version = "{TARGET_VERSION}"', toml, count=1, flags=re.M))
        print(f"  version {base} -> {TARGET_VERSION}")
    else:
        print(f"  would set version {base} -> {TARGET_VERSION}")

    cl = cl_p.read_text()
    if f"## {TARGET_VERSION} " in cl:
        print(f"  CHANGELOG already carries a {TARGET_VERSION} entry")
    else:
        entry = (HERE / f"CHANGELOG-{TARGET_VERSION}.md").read_text().replace("__BASE__", base)
        if write:
            backup(cl_p)
            cl_p.write_text(cl.replace("# Changelog\n\n", "# Changelog\n\n" + entry + "\n", 1))
            print(f'  CHANGELOG entry inserted, "differ from {base}"')
        else:
            print(f'  would insert the CHANGELOG entry, "differ from {base}"')

    md = md_p.read_text()
    if "two shapes resolve from `notes` alone" in md:
        print("  SKILL.md already describes the two VAS shapes")
    elif OLD_VAS_LINE in md:
        if write:
            backup(md_p)
            md_p.write_text(md.replace(OLD_VAS_LINE, NEW_VAS_LINES, 1))
            print("  SKILL.md VAS line updated")
        else:
            print("  would update the SKILL.md VAS line")
    else:
        print("  SKILL.md VAS line not found as expected — check by hand:")
        print("    grep -n 'header total reported' SKILL.md")

    if not write:
        print("\nDRY RUN — nothing written. Re-run with --write to apply.")
        return 0

    print(f"""
Applied. Nothing pushed.

  cd {repo}
  git switch -c v1.6.0-vas-rules
  git add SKILL.md CHANGELOG.md skill.toml scripts/validate_rate_card.py
  git add -f references/rate-card-snapshot.json
  git diff --cached --stat
  git commit
  git push -u origin v1.6.0-vas-rules

The .bak-* files are your undo and are deliberately not staged. Description for the
PR: skill-updates/v1.6.0/PR-BODY.md — check for a PR template first.

One thing this release deliberately does NOT touch: your rate card holds pre-MSA
storage and LTL numbers (storage NJ $5.98, LTL pallet $6.13, stretchwrap $4.72)
where the rebuilt card says $4.34, $10.00 all-in and no separate wrap. 31 rates
differ. The merge above only ADDED paths, so every one of those is untouched — but
it is a real disagreement and wants its own decision, not a silent ride-along.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
