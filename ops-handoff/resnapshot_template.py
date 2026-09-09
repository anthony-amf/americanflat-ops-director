#!/usr/bin/env python3
"""Rebuild a page template from the live dashboard, mechanically.

A template is just the published page with its two data literals swapped for
placeholders. So when the live page is right and the template is behind, the fix
needs no judgement — re-cut the template from the page:

    python3 resnapshot_template.py <published-page.html> <out-template.html>

<published-page.html> is the file the Artifact read tool saves. The output is
written to a NEW path; nothing is overwritten and nothing is deleted, so point it
somewhere fresh and move it into place yourself once you have looked at it.

Refuses rather than writing anything wrong:
  * both literals must be found exactly once in the page
  * the result must contain both placeholders and no leftover row data
  * `<title>` and a closing `</script>` must both be present

Check FIRST, then re-snapshot. Run check_template.py against the template you
have and read the diff: if the only differences are things the live page has and
the template lacks, re-snapshotting is exactly right. If the template also has
lines the page lacks, it is ahead in some way — re-snapshotting would throw that
away, so merge by hand instead.
"""
import re
import sys

_DATA = re.compile(r"const DATA\s*=\s*\[.*?\]\s*;", re.S)
_KPI = re.compile(r"const KPI\s*=\s*\{.*?\}\s*;", re.S)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src_path, out_path = sys.argv[1], sys.argv[2]

    try:
        with open(src_path, encoding="utf-8") as fh:
            html = fh.read()
    except OSError as exc:
        print(f"ERROR: cannot read {src_path}: {exc}")
        return 2

    # Keep only what was authored — the viewer adds its own doctype/head/body.
    i = html.find("<title>")
    j = html.rfind("</script>")
    if i < 0 or j < 0:
        print("ERROR: no <title> or closing </script> in that file — is it the "
              "saved artifact page?")
        return 2
    page = html[i:j + len("</script>")]

    n_data = len(_DATA.findall(page))
    n_kpi = len(_KPI.findall(page))
    if n_data != 1 or n_kpi != 1:
        print(f"ERROR: expected one `const DATA = [...];` and one "
              f"`const KPI = {{...}};`, found {n_data} and {n_kpi}. Refusing to "
              f"guess — nothing written.")
        return 2

    tpl = _KPI.sub("const KPI = /*KPI*/;", _DATA.sub("const DATA = /*DATA*/;", page, count=1), count=1)

    if "/*DATA*/" not in tpl or "/*KPI*/" not in tpl:
        print("ERROR: placeholders missing after substitution — nothing written.")
        return 2
    # A row-data signature that cannot occur in the design: only JSON writes
    # `"invoice_number":` with the colon. The markup has `data-k="invoice_number"`
    # and the script has `r.invoice_number`, and an earlier version of this check
    # matched the markup and refused on a perfectly good page.
    if '"invoice_number":' in tpl:
        print("ERROR: invoice rows still present after blanking DATA — the literal "
              "is not shaped as expected. Nothing written.")
        return 2

    try:
        with open(out_path, "x", encoding="utf-8") as fh:   # 'x': never overwrite
            fh.write(tpl)
    except FileExistsError:
        print(f"ERROR: {out_path} already exists — pick a new path rather than "
              f"overwriting it.")
        return 2
    except OSError as exc:
        print(f"ERROR: cannot write {out_path}: {exc}")
        return 2

    print(f"template written: {out_path}")
    print(f"  {len(page):,} chars of page -> {len(tpl):,} chars of template")
    print(f"  now confirm it: python3 check_template.py {out_path} {src_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
