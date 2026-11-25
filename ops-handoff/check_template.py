#!/usr/bin/env python3
"""Does this page template still match the live dashboard's design?

Stands alone on purpose: no imports beyond the standard library, no assumptions
about where it sits in a repo, nothing to configure. Drop it anywhere and run it.

    python3 check_template.py <template.html> <published-page.html>

    exit 0   the template's design matches the page — a refresh from it would
             change data only, which is the whole point of a template
    exit 1   they differ — the diff is printed. A template BEHIND the page means
             publishing from it deletes whatever the page has gained; a template
             AHEAD of the page means a design change nobody has reviewed is
             about to ship. Both are worth stopping for.
    exit 2   one of the files could not be read

<published-page.html> is the file the Artifact read tool saves — the same path the
refresh job already passes as --published.

Why this exists: on 2026-09-03 a refresh published an older copy of the design
over the live page and silently deleted the sticky column headers and the whole
mark-paid basket. Nothing compared the two, so it went unnoticed for six days
while the job reported success every weekday.
"""
import difflib
import re
import sys

# `const DATA = [...];` and `const KPI = {...};` — the only two things a data
# refresh is allowed to change. Everything else in the file is design.
_DATA_LIT = re.compile(r"const DATA\s*=\s*(?:/\*DATA\*/|\[.*?\])\s*;", re.S)
_KPI_LIT = re.compile(r"const KPI\s*=\s*(?:/\*KPI\*/|\{.*?\})\s*;", re.S)


def page_shell(html: str) -> str:
    """The page with both data literals blanked and the viewer's wrapper stripped.

    The artifact viewer wraps a published page in its own doctype/head/body, so
    keep only what was authored: `<title>` through the last `</script>`.
    """
    i = html.find("<title>")
    j = html.rfind("</script>")
    if i > -1 and j > -1:
        html = html[i:j + len("</script>")]
    html = _DATA_LIT.sub("const DATA = /*DATA*/;", html, count=1)
    html = _KPI_LIT.sub("const KPI = /*KPI*/;", html, count=1)
    return html.strip()


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError as exc:
        print(f"ERROR: cannot read {path}: {exc}")
        raise SystemExit(2)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    template_path, published_path = sys.argv[1], sys.argv[2]
    tpl = page_shell(read(template_path))
    live = page_shell(read(published_path))

    if tpl == live:
        print("MATCH — the template carries the live page's design "
              "(data literals aside). Safe to refresh from.")
        return 0

    diff = list(difflib.unified_diff(
        live.splitlines(), tpl.splitlines(),
        fromfile=f"live page ({published_path})",
        tofile=f"template ({template_path})",
        lineterm="", n=1,
    ))
    behind = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
    ahead = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
    print(f"DRIFT — {behind} line(s) on the live page are missing from the template, "
          f"{ahead} line(s) in the template are not on the live page.\n")
    print("\n".join(diff))
    print("\nA '-' line is something the live page has and the template would delete.")
    print("A '+' line is something the template would add to the live page.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
