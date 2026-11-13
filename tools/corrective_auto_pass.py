#!/usr/bin/env python3
"""Replace the stale `[AUTO]` blocks the v1.4.0 Mac sweep left on the ledger.

Why this exists
---------------
Until it was unloaded on 2026-09-22 the Mac LaunchAgent swept every row several
times a day on validator v1.4.0 -- pre-MSA rate card, no clearance gate. It left
390 of 396 rows reading `Verdict:       OK to pay` with the invoice-math and
rate-card lines still pending, and storage notes quoting $5.90 / $5.98 / $5.09
where the MSA rates are $4.47 / $4.34 / $3.35. On 754698 it sat directly above a
human "HOLD per Anthony 7/27" note.

Stopping the sweep freezes those verdicts; it does not clear them. A settled row
is never re-swept, so nothing rebuilds them on its own. This is that one pass.

What it does NOT do
-------------------
It is a text correction, not a re-adjudication:

  * Never writes `paid_at`. Payment is human-confirmed only.
  * Never downgrades a `disputed` or human-set stamp -- it mirrors write_result's
    preserve logic, so those rows get a corrected report and keep their status.
  * Never promotes anything on its own: promotion to `valid` happens only through
    the packaged v1.6.2 clearance gate, which requires positive evidence on every
    axis the invoice type needs.
  * Never assigns `validation_report` wholesale. Every write goes through
    `merge_report`, which replaces only the `[AUTO <date>]` block and leaves
    `[MSA DISPUTE]`, `[DEEP PASS]`, `[STEDI]` and `[PAID]` blocks byte-for-byte
    intact. Assigning the field directly is what wiped 754891 and 755265 on
    2026-08-11.

Scope
-----
Unpaid rows only, by default. A paid row's verdict is already spent -- nobody is
deciding anything from it -- while the 145 unpaid ones are what a person reads
before releasing money. `--include-paid` widens it if you want the tidier ledger;
the preserve logic protects those rows either way.

The header pass alone cannot price every row, so rows that stay `needs_detail`
are reported rather than hidden. Run the full sweep runbook (with the PDF line
pass) to actually resolve them; that is a different, heavier job.

Usage
-----
    python3 tools/corrective_auto_pass.py                 # dry run, shows every change
    python3 tools/corrective_auto_pass.py --limit 5       # dry run, first 5
    python3 tools/corrective_auto_pass.py --write         # commit
    python3 tools/corrective_auto_pass.py --write --include-paid

Safe to re-run: merge_report replaces its own block, so a second run is a no-op
on rows already corrected.
"""
import argparse
import json
import re
import subprocess
import sys
import types
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TABLE = "americanflat.finance.yusen_invoices"
BQ_URL = "https://bigquery.googleapis.com/bigquery/v2/projects/americanflat/queries"
CACERT = "/root/.ccr/ca-bundle.crt"
SKILL_DIR = Path("/tmp/skill-corrective")
# The wording the v1.4.0 sweep emitted. Three spaces after the colon is its own
# column alignment -- matching on it keeps this pass off blocks written by
# anything else.
STALE_VERDICT = "Verdict:       OK to pay"
TMP = Path("/tmp/corrective-pass")


def unpack_validator() -> Path:
    """Unzip the committed package and refuse anything older than v1.6.2.

    The gate greps for the functions this script actually calls rather than
    trusting the version string alone: a 1.5.x package passed an earlier
    version-only preflight and then died mid-run having written nothing.
    """
    pkg = REPO / "yusen-invoice-validator.skill"
    if not pkg.exists():
        sys.exit(f"package not found: {pkg}")
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pkg) as z:
        z.extractall(SKILL_DIR)
    root = SKILL_DIR / "yusen-invoice-validator"
    toml = (root / "skill.toml").read_text()
    ver = re.search(r'^version\s*=\s*"([^"]+)"', toml, re.M)
    if not ver:
        sys.exit("could not read a version from skill.toml")
    parts = [int(x) for x in ver.group(1).split(".")[:3]]
    if parts < [1, 6, 2]:
        sys.exit(f"package is v{ver.group(1)}; this pass needs v1.6.2+ "
                 f"(the clearance gate is the whole point)")
    src = (root / "scripts" / "validate_rate_card.py").read_text()
    for fn in ("apply_clearance", "merge_report", "_deferral_block", "compose_report",
               "apply_vas_pallet_check", "apply_vas_labor_check", "apply_msa_conflicts"):
        if f"def {fn}" not in src:
            sys.exit(f"package is missing {fn} -- wrong or truncated build")
    print(f"validator v{ver.group(1)} unpacked")
    return root


def import_validator(root: Path):
    """Import the skill script without a BigQuery client.

    The module imports google.cloud.bigquery at top level for its type hints and
    for write_result, none of which this pass uses -- it issues its own UPDATEs
    over REST. A stub that raises on construction keeps the import working and
    makes any accidental client use loud instead of silent.
    """
    for m in ("google", "google.cloud", "google.cloud.bigquery"):
        sys.modules.pop(m, None)
    g, gc, bq = (types.ModuleType(n) for n in ("google", "google.cloud", "google.cloud.bigquery"))

    class _NoClient:
        def __init__(self, *a, **k):
            raise RuntimeError("this pass writes over REST, not through a BigQuery client")

    class _Param:
        def __init__(self, name, type_, value):
            self.name, self.type_, self.value = name, type_, value

    bq.Client = _NoClient
    bq.ScalarQueryParameter = _Param
    bq.QueryJobConfig = lambda **k: None
    gc.bigquery = bq
    g.cloud = gc
    sys.modules.update({"google": g, "google.cloud": gc, "google.cloud.bigquery": bq})
    sys.path.insert(0, str(root / "scripts"))
    import validate_rate_card as V
    return V


def bq_query(sql, params=None, label="q"):
    body = {"query": sql, "useLegacySql": False, "maxResults": 2000}
    if params:
        body["parameterMode"] = "NAMED"
        body["queryParameters"] = params
    TMP.mkdir(parents=True, exist_ok=True)
    p = TMP / f"_{label}.json"
    p.write_text(json.dumps(body))
    r = subprocess.run(["curl", "-s", "-X", "POST", BQ_URL,
                        "-H", "Content-Type: application/json",
                        "--cacert", CACERT, "-d", f"@{p}"],
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        sys.exit(f"BigQuery returned non-JSON:\n{r.stdout[:400]}\n{r.stderr[:400]}")


def sparam(name, value, type_="STRING"):
    return {"name": name, "parameterType": {"type": type_},
            "parameterValue": {"value": None if value is None else str(value)}}


def fetch_targets(include_paid: bool):
    cols = ("invoice_number, date, bill_period, type_of_invoice, warehouse, amount, notes, "
            "pdf_url, supporting_doc_url, validation_status, validation_variance, "
            "validated_by, currency, paid_at, validation_report")
    where = [f"validation_report LIKE '%{STALE_VERDICT}%'"]
    if not include_paid:
        where.append("paid_at IS NULL")
    d = bq_query(f"SELECT {cols} FROM `{TABLE}` WHERE {' AND '.join(where)} "
                 f"ORDER BY invoice_number", label="targets")
    if "error" in d:
        sys.exit("BigQuery error: " + d["error"]["message"])
    names = [f["name"] for f in d["schema"]["fields"]]
    return [dict(zip(names, [c["v"] for c in row["f"]])) for row in d.get("rows", [])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="commit the changes")
    ap.add_argument("--include-paid", action="store_true", help="also correct paid rows")
    ap.add_argument("--limit", type=int, help="only process the first N rows")
    args = ap.parse_args()

    V = import_validator(unpack_validator())
    rates = json.load(open(SKILL_DIR / "yusen-invoice-validator" /
                           "references" / "rate-card-snapshot.json"))

    rows = fetch_targets(args.include_paid)
    if args.limit:
        rows = rows[:args.limit]
    if not rows:
        print("nothing to correct")
        return 0
    print(f"{len(rows)} row(s) carrying the stale verdict"
          f"{'' if args.include_paid else ' (unpaid only)'}\n")

    changes, skipped = [], []
    for inv in rows:
        prior = inv.get("validation_report") or ""
        r = V.validate(inv, rates)
        V.apply_vas_pallet_check(inv, r)
        V.apply_vas_labor_check(inv, r)
        V.apply_msa_conflicts(inv, r)
        V.apply_clearance(inv, r, prior)

        if r.get("_settled"):
            skipped.append((inv["invoice_number"], f"settled: {r['_settled']}"))
            continue

        # Mirror write_result: a disputed stamp, a paid+valid row and any
        # human-set stamp all keep their status. The report still refreshes --
        # that is the entire point of this pass.
        prior_status = (inv.get("validation_status") or "").strip()
        prior_by = (inv.get("validated_by") or "").strip()
        preserve = (
            (prior_status == "disputed" and r["status"] in ("valid", "needs_detail"))
            or (prior_status == "valid" and inv.get("paid_at") and r["status"] == "needs_detail")
            or (prior_status and prior_by and prior_by != V.AUTO_WRITER
                and r["status"] in ("valid", "needs_detail"))
        )
        block = (V._deferral_block(r, prior)
                 if r["status"] == "needs_detail" and V._DEEPER_BLOCK.search(prior)
                 else V.compose_report(r))
        merged = V.merge_report(prior, block)
        if merged == prior:
            skipped.append((inv["invoice_number"], "already correct"))
            continue
        changes.append({"inv": inv["invoice_number"], "type": inv.get("type_of_invoice"),
                        "prior_status": prior_status, "new_status": r["status"],
                        "preserve": preserve, "variance": r.get("variance"),
                        "outstanding": r.get("_outstanding") or [],
                        "merged": merged, "deferral": "header-level re-check only" in block})

    print(f"{'invoice':22}{'type':13}{'status':30}{'block':10}outstanding")
    for c in changes:
        st = (f"{c['prior_status'] or '-'} -> kept" if c["preserve"]
              else f"{c['prior_status'] or '-'} -> {c['new_status']}")
        print(f"{c['inv'][:21]:22}{(c['type'] or '')[:12]:13}{st:30}"
              f"{'deferral' if c['deferral'] else 'card':10}"
              f"{'; '.join(c['outstanding'])[:40]}")
    if skipped:
        print(f"\n{len(skipped)} skipped: "
              + ", ".join(f"{i} ({w})" for i, w in skipped[:8])
              + (" ..." if len(skipped) > 8 else ""))

    promotions = [c for c in changes if not c["preserve"] and c["new_status"] == "valid"
                  and c["prior_status"] != "valid"]
    print(f"\n{len(changes)} row(s) to correct, {len(promotions)} promoted to valid "
          f"by the clearance gate")
    for c in promotions:
        print(f"    PROMOTED {c['inv']} ({c['type']}): every axis passed on positive "
              f"evidence -- this drops it out of the work list permanently.")

    if not args.write:
        if changes:
            print("\n--- sample corrected AUTO block ---")
            m = V._AUTO_BLOCK.search(changes[0]["merged"])
            print((m.group(0) if m else changes[0]["merged"][-500:]).strip())
        print("\nDRY RUN -- nothing written. Re-run with --write.")
        return 0

    print()
    ok = fail = 0
    for c in changes:
        sets = ["validated_at = CURRENT_TIMESTAMP()", "validation_report = @rep"]
        params = [sparam("rep", c["merged"]), sparam("inv", c["inv"])]
        if not c["preserve"]:
            sets += ["validation_status = @st", "validation_variance = @var",
                     "validated_by = @by"]
            params += [sparam("st", c["new_status"]),
                       sparam("var", c["variance"] if c["variance"] is not None else 0, "FLOAT64"),
                       sparam("by", V.AUTO_WRITER)]
        # paid_at is never in the SET list, and the guard keeps this off rows a
        # person settled while the pass was running.
        sql = (f"UPDATE `{TABLE}` SET {', '.join(sets)} "
               f"WHERE invoice_number = @inv")
        d = bq_query(sql, params, label="upd")
        if "error" in d:
            fail += 1
            print(f"  {c['inv']}  FAIL  {d['error']['message'][:110]}")
        else:
            ok += 1
    print(f"\n{ok} written, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
