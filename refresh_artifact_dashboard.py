#!/usr/bin/env python3
"""Fingerprint-gated refresher for the "Yusen Invoices" Claude Artifact.

The artifact at https://claude.ai/code/artifact/23dd148b-1fb0-4219-80e1-53ca8d9d3d97
is the user-facing invoice search UI. It used to be rebuilt and republished on
every weekday firing of a scheduled task, whether or not anything in BigQuery
had actually changed — and over a representative 45-day window only about half
of those firings had any data change behind them. The rest republished
byte-identical data at the cost of a full agent session.

This script makes the republish conditional. It runs one SELECT, fingerprints
the normalized result set, and compares that against the fingerprint recorded at
the last publish. When nothing has moved it prints NO_CHANGE and stops, so the
calling session can exit without invoking the Artifact tool at all.

Output contract (stdout, last line, machine-readable for the calling session):

    NO_CHANGE <fingerprint>            nothing to do — do not republish
    CHANGED <path> <fingerprint>       HTML written to <path> — republish it

Exit status is 0 for both; a non-zero exit means the refresh genuinely failed
and the artifact should be left alone.

The page design is NOT generated here. `dashboard_template.html` is the exact
published page with its `const DATA` / `const KPI` literals swapped for
placeholders, so a refresh only ever changes data — never layout, colors, or
the light/dark theming the artifact host relies on. Editing the design means
editing that template; the row schema below must stay in sync with the fields
the template's render() reads.

BigQuery access works two ways so the same file runs anywhere:
  * REST against bigquery.googleapis.com — used in Claude Code cloud sessions,
    where the agent proxy injects credentials and no gcloud ADC exists.
  * the `bq` CLI — used on a workstation with gcloud ADC configured.
REST is tried first and falls back automatically.

Usage:
    python3 refresh_artifact_dashboard.py                  # gated refresh
    python3 refresh_artifact_dashboard.py --force          # ignore fingerprint
    python3 refresh_artifact_dashboard.py --check-only     # report, write nothing
    python3 refresh_artifact_dashboard.py --out /tmp/d.html --state /tmp/s.json
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT = "americanflat"
TABLE = "americanflat.finance.yusen_invoices"
ARTIFACT_URL = "https://claude.ai/code/artifact/23dd148b-1fb0-4219-80e1-53ca8d9d3d97"

REPO = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = REPO / "dashboard_template.html"
DEFAULT_OUT = REPO / "build" / "yusen_invoices_artifact.html"
DEFAULT_STATE = REPO / ".dashboard-state.json"

# Display-only exclusions. The row stays in BigQuery per the standing
# "never delete" rule; it just doesn't pollute the dashboard totals.
EXCLUDE_INVOICES = {"TEST_DELETE_ME"}

# Some Receiving invoices carry a legal footer as their entire `notes` value.
BOILERPLATE = "No action may be maintained by Client"

QUERY = f"""
SELECT
  FORMAT_DATE('%Y-%m-%d', date) AS date,
  bill_period,
  invoice_number,
  type_of_invoice,
  warehouse,
  CAST(amount AS FLOAT64) AS amount,
  IFNULL(currency, 'USD') AS currency,
  paid_at IS NOT NULL AS paid,
  FORMAT_TIMESTAMP('%Y-%m-%d', paid_at) AS paid_at,
  paid_marked_by,
  notes,
  pdf_url,
  supporting_doc_url,
  -- Validation columns: the finance-visible status the validator writes, plus
  -- the stored per-invoice report the table renders as the chip tooltip. These
  -- ride in the fingerprint too, so a status change (not just a new invoice)
  -- correctly triggers a republish.
  validation_status,
  CAST(validation_variance AS FLOAT64) AS validation_variance,
  validation_report,
  validated_by,
  FORMAT_TIMESTAMP('%Y-%m-%d', validated_at) AS validated_at
FROM `{TABLE}`
ORDER BY date DESC, invoice_number DESC
"""


# --------------------------------------------------------------------------
# BigQuery
# --------------------------------------------------------------------------

def _rest_request(url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data else "GET",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _decode(schema: list, rows: list) -> list:
    """Turn BigQuery's {f:[{v:...}]} wire format into plain dicts."""
    names = [f["name"] for f in schema]
    types = [f["type"] for f in schema]
    out = []
    for row in rows:
        rec = {}
        for name, typ, cell in zip(names, types, row["f"]):
            v = cell.get("v")
            if v is None:
                rec[name] = None
            elif typ in ("INTEGER", "INT64"):
                rec[name] = int(v)
            elif typ in ("FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"):
                rec[name] = float(v)
            elif typ in ("BOOLEAN", "BOOL"):
                rec[name] = str(v).lower() == "true"
            else:
                rec[name] = v
        out.append(rec)
    return out


def fetch_rows_rest() -> list:
    """Query via the REST API. Works where the agent proxy injects credentials."""
    base = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}"
    resp = _rest_request(f"{base}/queries", {
        "query": QUERY, "useLegacySql": False, "maxResults": 5000,
        "timeoutMs": 60000,
    })
    if not resp.get("jobComplete"):
        raise RuntimeError("BigQuery job did not complete within the timeout")

    schema = resp["schema"]["fields"]
    rows = _decode(schema, resp.get("rows", []))

    # Page through anything beyond the first response.
    job_id = resp["jobReference"]["jobId"]
    location = resp["jobReference"].get("location", "US")
    token = resp.get("pageToken")
    while token:
        page = _rest_request(
            f"{base}/queries/{job_id}?location={location}"
            f"&maxResults=5000&pageToken={token}"
        )
        rows.extend(_decode(schema, page.get("rows", [])))
        token = page.get("pageToken")

    return rows


def fetch_rows_bq() -> list:
    """Query via the `bq` CLI. Used on a workstation with gcloud ADC."""
    env = dict(os.environ)
    sdk_bin = env.get("CLOUDSDK_BIN_PATH", "")
    if sdk_bin:
        env["PATH"] = sdk_bin + ":" + env.get("PATH", "")
    # --max_rows is mandatory: `bq` silently truncates at 100 rows without it.
    out = subprocess.run(
        ["bq", "query", "--use_legacy_sql=false", "--format=prettyjson",
         "--max_rows=100000", QUERY],
        capture_output=True, text=True, env=env, check=True,
    )
    return json.loads(out.stdout)


def fetch_rows() -> list:
    try:
        return fetch_rows_rest()
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, KeyError) as exc:
        print(f"  REST path unavailable ({exc}); falling back to the bq CLI",
              file=sys.stderr)
        return fetch_rows_bq()


# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------

# Rows written before 2026-07-13 hold legacy docs.google.com links. BigQuery is
# deliberately not backfilled, so every renderer rewrites them at display time.
_DOC_ID = re.compile(r"docs\.google\.com/[^/]+/d/([A-Za-z0-9_-]+)")


def drive_url(url: str) -> str:
    if not url:
        return ""
    m = _DOC_ID.search(url)
    return f"https://drive.google.com/file/d/{m.group(1)}/view" if m else url


def normalize(rows: list) -> list:
    """Project BigQuery rows onto exactly the fields the template renders."""
    clean = []
    for r in rows:
        if (r.get("invoice_number") or "") in EXCLUDE_INVOICES:
            continue
        notes = r.get("notes") or ""
        if notes.startswith(BOILERPLATE):
            notes = "(no line-item description — see PDF)"
        amount = r.get("amount")
        clean.append({
            "date": r.get("date") or "",
            "bill_period": r.get("bill_period") or "",
            "invoice_number": r.get("invoice_number") or "",
            "type_of_invoice": r.get("type_of_invoice") or "",
            "warehouse": r.get("warehouse") or "",
            "amount": float(amount) if amount not in (None, "") else 0.0,
            "currency": r.get("currency") or "USD",
            "paid": str(r.get("paid")).lower() == "true",
            "paid_at": r.get("paid_at") or "",
            "paid_marked_by": r.get("paid_marked_by") or "",
            "notes": notes,
            "pdf_url": r.get("pdf_url") or "",
            "supporting_doc_url": drive_url(r.get("supporting_doc_url") or ""),
            # Validation axis. Empty status renders as an em-dash ("not checked
            # yet"), so a row is never implied to have passed. variance stays
            # None rather than 0.0 — the chip only shows a figure when there
            # genuinely is one (the disputed dollars).
            "validation_status": r.get("validation_status") or "",
            "validation_variance": (float(r["validation_variance"])
                                    if r.get("validation_variance") not in (None, "") else None),
            "validation_report": r.get("validation_report") or "",
            "validated_by": r.get("validated_by") or "",
            "validated_at": r.get("validated_at") or "",
        })
    return clean


def fingerprint(rows: list) -> str:
    """Stable hash of everything the dashboard renders.

    Covers only the projected fields, so a re-ingest that touches no visible
    value does not force a republish, and the generated-at stamp — which
    changes every run — is deliberately excluded. Sorting makes the hash
    independent of BigQuery's row ordering.
    """
    key = sorted(rows, key=lambda r: (r["invoice_number"], r["date"]))
    blob = json.dumps(key, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def build_html(template: str, rows: list) -> str:
    totals: dict = {}
    for r in rows:
        totals[r["currency"]] = round(totals.get(r["currency"], 0.0) + r["amount"], 2)
    dates = sorted(r["date"] for r in rows if r["date"])
    kpi = {
        "totals": totals,
        "n": len(rows),
        "n_pdf": sum(1 for r in rows if r["pdf_url"]),
        "n_doc": sum(1 for r in rows if r["supporting_doc_url"]),
        "date_lo": dates[0] if dates else "—",
        "date_hi": dates[-1] if dates else "—",
        "generated": datetime.now(ZoneInfo("America/New_York")).strftime("%b %d, %Y %H:%M"),
    }
    html = (template
            .replace("/*DATA*/", json.dumps(rows, ensure_ascii=False))
            .replace("/*KPI*/", json.dumps(kpi, ensure_ascii=False)))
    if "/*DATA*/" in html or "/*KPI*/" in html:
        raise SystemExit("ERROR: template placeholders were not fully substituted")
    return html


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE),
                    help="published page with /*DATA*/ and /*KPI*/ placeholders")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help="where to write the rendered HTML")
    ap.add_argument("--state", default=str(DEFAULT_STATE),
                    help="fingerprint file recording the last publish")
    ap.add_argument("--force", action="store_true",
                    help="render even when the fingerprint is unchanged")
    ap.add_argument("--check-only", action="store_true",
                    help="report whether a republish is needed; write nothing")
    args = ap.parse_args()

    template_path = Path(args.template)
    if not template_path.exists():
        raise SystemExit(f"ERROR: template not found: {template_path}")

    state_path = Path(args.state)
    previous = load_state(state_path)

    rows = normalize(fetch_rows())
    if not rows:
        raise SystemExit("ERROR: query returned no rows — refusing to publish an empty dashboard")

    fp = fingerprint(rows)
    paid = sum(1 for r in rows if r["paid"])
    print(f"  {len(rows)} invoices · {paid} paid "
          f"(artifact last held {previous.get('rows', '?')})")
    print(f"  fingerprint {fp} (last published {previous.get('fingerprint', 'never')})")

    if fp == previous.get("fingerprint") and not args.force:
        print(f"NO_CHANGE {fp}")
        return

    if args.check_only:
        print(f"WOULD_CHANGE {fp}")
        return

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_html(template_path.read_text(encoding="utf-8"), rows),
                        encoding="utf-8")

    state_path.write_text(json.dumps({
        "fingerprint": fp,
        "rows": len(rows),
        "paid": paid,
        "artifact_url": ARTIFACT_URL,
    }, indent=2) + "\n", encoding="utf-8")

    print(f"CHANGED {out_path} {fp}")


if __name__ == "__main__":
    main()
