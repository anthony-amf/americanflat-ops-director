#!/usr/bin/env python3
"""
Refresh ~/yusen_invoices_dashboard.html from BigQuery.

Re-pulls every row of americanflat.finance.yusen_invoices (including the
validation columns) into the dashboard's embedded DATA array, and ensures the
table has a sortable "Validated" column with status chips.

Idempotent: safe to run repeatedly. The HTML structure edits only apply if not
already present; the DATA array is always refreshed.

Usage:
    python3 refresh_yusen_dashboard.py
    python3 refresh_yusen_dashboard.py --html /path/to/dashboard.html
"""
import argparse
import json
import re
from decimal import Decimal
from pathlib import Path
from google.cloud import bigquery

TABLE = "americanflat.finance.yusen_invoices"
DEFAULT_HTML = Path.home() / "yusen_invoices_dashboard.html"

CSS_BLOCK = """  .vchip { display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; white-space:nowrap; }
  .v-valid { background:#e7f6ec; color:#16a34a; }
  .v-discrepancy { background:#fdeaea; color:#dc2626; }
  .v-needs_detail { background:#fef3e2; color:#d97706; }
  .v-error { background:#eef0f3; color:#6b7280; }
"""

PAIDCHIP_FN = """function paidChip(r) {
  if (!r.paid_at) return '<span class="dash">—</span>';
  return '<span class="vchip v-valid" title="marked paid ' + esc(r.paid_at) + '">$ paid ' + esc(r.paid_at) + '</span>';
}

"""

VALCHIP_FN = """function valChip(r) {
  const s = r.validation_status;
  if (!s) return '<span class="dash">—</span>';
  const tipText = r.validation_report
    ? r.validation_report
    : (r.validated_at ? 'validated ' + r.validated_at
        + (r.validation_variance != null ? ' \\u00b7 variance $' + r.validation_variance : '') : '');
  const tip = tipText ? ' title="' + esc(tipText) + '"' : '';
  let label = s;
  if (s === 'valid') label = '\\u2713 valid';
  else if (s === 'discrepancy') label = '\\uD83D\\uDEA8 ' + (r.validation_variance != null ? '$' + Number(r.validation_variance).toFixed(2) : 'discrepancy');
  else if (s === 'needs_detail') label = 'needs detail';
  return '<span class="vchip v-' + s + '"' + tip + '>' + esc(label) + '</span>';
}

"""


def fetch_rows(client: bigquery.Client) -> list:
    q = f"""
    SELECT
      FORMAT_DATE('%Y-%m-%d', date) AS date,
      bill_period, invoice_number, type_of_invoice, warehouse, amount, notes,
      pdf_url, supporting_doc_url,
      FORMAT_TIMESTAMP('%Y-%m-%d %H:%M', ingested_at) AS ingested_at,
      validation_status,
      ROUND(validation_variance, 2) AS validation_variance,
      FORMAT_TIMESTAMP('%Y-%m-%d %H:%M', validated_at) AS validated_at,
      FORMAT_TIMESTAMP('%Y-%m-%d', paid_at) AS paid_at,
      validation_report
    FROM `{TABLE}`
    ORDER BY date DESC, ingested_at DESC
    """
    rows = []
    for r in client.query(q).result():
        d = dict(r)
        for k, v in list(d.items()):
            if isinstance(v, Decimal):
                d[k] = float(v)
            elif v is None and k not in ("validation_status", "validation_variance", "validated_at", "paid_at", "validation_report"):
                d[k] = ""
        rows.append(d)
    return rows


def patch_html(html: str, rows: list) -> tuple[str, list]:
    changes = []

    # 1. CSS chip classes (once)
    if ".vchip" not in html:
        html = html.replace("</style>", CSS_BLOCK + "</style>", 1)
        changes.append("added chip CSS")

    # 2. Header columns after Amount (once each)
    if 'data-k="validation_status"' not in html:
        anchor = '        <th data-k="notes">Notes<span class="arrow">▼</span></th>'
        new = ('        <th data-k="validation_status">Validated<span class="arrow">▼</span></th>\n'
               + anchor)
        html = html.replace(anchor, new, 1)
        changes.append("added Validated header")
    if 'data-k="paid_at"' not in html:
        anchor = '        <th data-k="notes">Notes<span class="arrow">▼</span></th>'
        new = ('        <th data-k="paid_at">Paid<span class="arrow">▼</span></th>\n' + anchor)
        html = html.replace(anchor, new, 1)
        changes.append("added Paid header")

    # 3. Row cells after Amount (once each)
    if "${valChip(r)}" not in html:
        anchor = '      <td class="notes" title="${esc(r.notes)}">${esc(r.notes)}</td>'
        new = '      <td>${valChip(r)}</td>\n' + anchor
        html = html.replace(anchor, new, 1)
        changes.append("added Validated cell")
    if "${paidChip(r)}" not in html:
        anchor = '      <td class="notes" title="${esc(r.notes)}">${esc(r.notes)}</td>'
        new = '      <td>${paidChip(r)}</td>\n' + anchor
        html = html.replace(anchor, new, 1)
        changes.append("added Paid cell")

    # 4. chip helpers (once) — and upgrade an older valChip lacking report tooltips
    if "function valChip" not in html:
        html = html.replace("function render() {", VALCHIP_FN + "function render() {", 1)
        changes.append("added valChip() helper")
    elif "r.validation_report" not in html:
        html = re.sub(r"function valChip\(r\) \{.*?\n\}\n\n", VALCHIP_FN, html, count=1, flags=re.S)
        changes.append("upgraded valChip() for report tooltips")
    if "function paidChip" not in html:
        html = html.replace("function render() {", PAIDCHIP_FN + "function render() {", 1)
        changes.append("added paidChip() helper")

    # 5. Refresh DATA array (always)
    data_json = json.dumps(rows, ensure_ascii=False, separators=(", ", ": "))
    html, n = re.subn(r"const DATA = \[.*?\];",
                      "const DATA = " + data_json + ";", html, count=1, flags=re.S)
    if n:
        changes.append(f"refreshed DATA ({len(rows)} rows)")
    else:
        raise SystemExit("ERROR: could not find `const DATA = [...]` to replace.")

    return html, changes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default=str(DEFAULT_HTML))
    args = ap.parse_args()

    path = Path(args.html)
    if not path.exists():
        raise SystemExit(f"Dashboard not found: {path}")

    client = bigquery.Client(project="americanflat")
    rows = fetch_rows(client)
    validated = sum(1 for r in rows if r.get("validated_at"))

    html = path.read_text()
    path.with_suffix(".html.bak").write_text(html)  # backup
    new_html, changes = patch_html(html, rows)
    path.write_text(new_html)

    print(f"✓ Refreshed {path}")
    print(f"  {len(rows)} invoices, {validated} validated")
    print("  changes: " + ", ".join(changes))
    print(f"  backup: {path.with_suffix('.html.bak')}")


if __name__ == "__main__":
    main()
