#!/usr/bin/env python3
"""Prepare the v1.6.0 release inside a clone of americanflat/skill-yusen-invoice-validator.

Runs the whole local half of the release and stops. It never pushes, never tags, never
opens a PR, never posts to Slack — you do those, after reading what this changed.

    python3 prepare_release.py /path/to/skill-yusen-invoice-validator            # dry run
    python3 prepare_release.py /path/to/skill-yusen-invoice-validator --write

What --write does, in order:

  1. applies install_v1_6_0.py to scripts/validate_rate_card.py
  2. applies merge_rates_into_1_5_1.py to references/rate-card-snapshot.json
  3. bumps [skill].version to 1.6.0
  4. inserts the CHANGELOG-1.6.0.md entry at the top of CHANGELOG.md, with the
     "differ from X" line filled in from whatever version was actually there
  5. corrects the one SKILL.md line that says VAS is always reported needs_detail
  6. documents YUSEN_PDF_CACHE in .env.example, commented out

Every step is additive or an in-place edit with a timestamped backup. Nothing is
deleted. Re-running is safe: anything already applied is reported and skipped.

It refuses to touch the clone unless the manifest says this is
skill-yusen-invoice-validator at 1.5.x — so it cannot be pointed at the wrong repo,
or at a base it was not built against.
"""
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET_VERSION = "1.6.0"

OLD_VAS_LINE = "- **VAS / Small Parcel / LTL** → header total reported as `needs_detail`."
NEW_VAS_LINES = """- **VAS** → two shapes resolve from `notes` alone, with no PDF and no OCR:
  a **pallet work order** ("N PALLETS W/SHRINKWRAP @ $R/PALLET" — how Savannah
  bills pallets) is recomputed and then judged against AF-9's $10.00 all-in, and an
  **hourly project** ("… PROJECT - N HRS @ $R/HR") has its rate derived from
  total ÷ hours and matched against the site's column of the MSA hourly table,
  overtime at 1.5x included. Anything else → header total, `needs_detail`.
- **Small Parcel / LTL** → header total reported as `needs_detail`."""

# Commented out on purpose: an empty YUSEN_PDF_CACHE= resolves to the working
# directory, so a copied .env with a bare entry scatters the cache. Unset, the
# built-in ~/.yusen-pdf-cache default applies.
PDF_CACHE_NOTE = """
# Optional. Where invoice PDFs are cached. Left unset it defaults to
# ~/.yusen-pdf-cache, which is what you want. Uncomment only to move it —
# and give it a real path: an empty value puts the cache in whatever
# directory you happen to run from.
# YUSEN_PDF_CACHE=
"""


def fail(msg):
    print(f"REFUSING: {msg}")
    sys.exit(1)


def backup(path: Path):
    dest = path.with_name(f"{path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(path, dest)
    return dest


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    repo = Path(sys.argv[1]).expanduser().resolve()
    write = "--write" in sys.argv

    toml_path = repo / "skill.toml"
    validator = repo / "scripts" / "validate_rate_card.py"
    card = repo / "references" / "rate-card-snapshot.json"
    changelog = repo / "CHANGELOG.md"
    skillmd = repo / "SKILL.md"

    for p in (toml_path, validator, card, changelog, skillmd):
        if not p.exists():
            fail(f"{p} is missing — is {repo} a clone of the skill repo?")

    toml = toml_path.read_text()
    name = re.search(r'^name\s*=\s*"([^"]+)"', toml, re.M)
    ver = re.search(r'^version\s*=\s*"([^"]+)"', toml, re.M)
    if not name or not ver:
        fail("skill.toml has no name or version line")
    if name.group(1) != "skill-yusen-invoice-validator":
        fail(f"this clone is {name.group(1)}, not skill-yusen-invoice-validator")
    base = ver.group(1)
    if base == TARGET_VERSION:
        print(f"{repo} is already at {TARGET_VERSION}.")
        print("Nothing to prepare. If a step below is missing, apply it by hand —")
        print("this script will not re-bump a released version.")
        return 0
    if not base.startswith("1.5."):
        fail(f"this clone is at {base}; v1.6.0 was built against 1.5.x. "
             "Check the branch before going further.")

    print(f"repo:    {repo}")
    print(f"base:    {base}  ->  {TARGET_VERSION}")
    print(f"mode:    {'WRITE' if write else 'dry run'}\n")

    # ---- 1 + 2: the two generated changes, each with its own dry run/apply -------
    for script, target, label in (
        ("install_v1_6_0.py", validator, "validator code"),
        ("merge_rates_into_1_5_1.py", card, "rate card"),
    ):
        cmd = [sys.executable, str(HERE / script), str(target)] + (["--write"] if write else [])
        print(f"--- {label}: {script} ---")
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(r.stdout.rstrip() or r.stderr.rstrip())
        if r.returncode != 0:
            fail(f"{script} refused. Nothing further was attempted — send me its output.")
        print()

    # ---- 3: version bump --------------------------------------------------------
    print("--- skill.toml version ---")
    if write:
        backup(toml_path)
        toml_path.write_text(
            re.sub(rf'^version\s*=\s*"{re.escape(base)}"',
                   f'version = "{TARGET_VERSION}"', toml, count=1, flags=re.M))
        print(f"  set to {TARGET_VERSION}")
    else:
        print(f"  would set {base} -> {TARGET_VERSION}")
    print()

    # ---- 4: changelog entry -----------------------------------------------------
    print("--- CHANGELOG.md ---")
    cl = changelog.read_text()
    if f"## {TARGET_VERSION} " in cl:
        print(f"  already carries a {TARGET_VERSION} entry — left alone")
    else:
        entry = (HERE / f"CHANGELOG-{TARGET_VERSION}.md").read_text().replace("__BASE__", base)
        if not cl.startswith("# Changelog"):
            fail("CHANGELOG.md does not start with '# Changelog' — insert the entry by hand")
        if write:
            backup(changelog)
            changelog.write_text(cl.replace("# Changelog\n\n",
                                            "# Changelog\n\n" + entry + "\n", 1))
            print(f"  {TARGET_VERSION} entry inserted ({entry.count(chr(10)) + 1} lines), "
                  f'"differ from {base}"')
        else:
            print(f"  would insert the {TARGET_VERSION} entry "
                  f'({entry.count(chr(10)) + 1} lines), "differ from {base}"')
    print()

    # ---- 5: the one stale SKILL.md line ----------------------------------------
    print("--- SKILL.md ---")
    md = skillmd.read_text()
    if "two shapes resolve from `notes` alone" in md:
        print("  already describes the two VAS shapes — left alone")
    elif OLD_VAS_LINE in md:
        if write:
            backup(skillmd)
            skillmd.write_text(md.replace(OLD_VAS_LINE, NEW_VAS_LINES, 1))
            print("  VAS line updated — it claimed VAS is always needs_detail")
        else:
            print("  would update the VAS line — it claims VAS is always needs_detail")
    else:
        print("  the VAS line differs from what 1.5.0 had. Not guessing — check by hand:")
        print("    grep -n 'needs_detail' SKILL.md")

    # ---- 6: document the second environment variable ---------------------------
    print("\n--- .env.example ---")
    envx = repo / ".env.example"
    if not envx.exists():
        print("  no .env.example in this clone — skipped")
    else:
        ex = envx.read_text()
        if "YUSEN_PDF_CACHE" in ex:
            print("  already mentions YUSEN_PDF_CACHE — left alone")
        elif "STEDI_API_KEY=" not in ex:
            print("  does not look like the 1.5.x file — skipped, add it by hand if you want it")
        else:
            if write:
                backup(envx)
                envx.write_text(ex.rstrip("\n") + "\n" + PDF_CACHE_NOTE)
                print("  YUSEN_PDF_CACHE documented, commented out")
            else:
                print("  would document YUSEN_PDF_CACHE, commented out")

    if not write:
        print("\nDRY RUN — nothing written. Re-run with --write to apply.")
        return 0

    print(f"""
Applied. Nothing has been pushed.

Next, from {repo}:

  git switch -c v1.6.0-vas-rules
  git status                 # expect 4 changed files, plus .bak-* files to leave out
  git add SKILL.md CHANGELOG.md skill.toml scripts/validate_rate_card.py
  git add -f references/rate-card-snapshot.json
  git diff --cached --stat
  git commit
  git push -u origin v1.6.0-vas-rules

The .bak-* files this run wrote are deliberately not staged — leave them untracked,
they are your undo. `git add -f` on the rate card is because a blanket *.json rule
silently unstages it in the ops-director repo; check whether this repo has one too
before assuming it landed.

Then open the PR, and check for a PR template first
(.github/pull_request_template.md) — fill its sections rather than writing over them.
After it merges, tag main and ask the Governors to update the registry:

  git switch main && git pull && git tag v1.6.0 && git push origin v1.6.0
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
