#!/usr/bin/env python3
"""
Build the Cost Per SKU shipping dashboard from finance.shipping_orders.

Writes one self-contained HTML file — no external scripts, styles or fonts — so
it can be published as a Claude Artifact or opened straight off disk.

Reads only, so it runs anywhere: on the Mac with gcloud credentials, or in a
cloud session where the proxy signs the BigQuery calls.

The published page lives at
https://claude.ai/code/artifact/f4b62a70-d920-4448-a66b-efea639a93e8 — republish
to that URL, never without it, or a duplicate artifact gets minted and old
bookmarks keep showing stale numbers.

Usage
-----
    # from BigQuery
    python3 scripts/generate_shipping_dashboard.py --out shipping_dashboard.html

    # only rewrite the file when the numbers actually changed (for a schedule)
    python3 scripts/generate_shipping_dashboard.py --out shipping_dashboard.html \
        --fingerprint-file .shipping_dashboard.fingerprint

    # preview from a loader dry run, before anything is in BigQuery
    python3 scripts/load_shipping_orders_to_bq.py --week-dir <dir> --dry-run \
        --out-json /tmp/rows.json
    python3 scripts/generate_shipping_dashboard.py --from-json /tmp/rows.json \
        --out preview.html --banner "Preview only — not real shipments."

When the fingerprint is unchanged the script prints NO_CHANGE and writes
nothing, so a scheduled refresh can skip republishing.

The page template lives in this file on purpose. The Yusen artifact keeps its
template in a separate snapshot file, and that snapshot silently fell behind the
live page more than once; one file cannot drift from itself.
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bq_read  # noqa: E402
from safe_write import safe_write_text  # noqa: E402

TABLE = "americanflat.finance.shipping_orders"

# Present in every page this script generates. A write to an existing file that
# does not contain it is refused, so a mistyped --out cannot destroy anything.
PAGE_MARKER = "<title>Cost Per SKU — Shipping · Americanflat</title>"
FINGERPRINT_MARKER = "# shipping dashboard fingerprint"

# Fixed slot order — a marketplace keeps its hue no matter which ones are on
# screen. Volume order, largest first.
MARKETPLACE_ORDER = ["Target", "Shopify", "Michaels", "Macy's"]

AGG_SQL = f"""
SELECT
  FORMAT_DATE('%Y-%m-%d', week_start) AS w,
  marketplace AS m,
  IFNULL(warehouse, 'Unknown') AS h,
  cost_status AS s,
  COUNT(*) AS n,
  SUM(IFNULL(units, 0)) AS u,
  CAST(ROUND(SUM(IFNULL(shipping_cost, 0)), 2) AS FLOAT64) AS c
FROM `{TABLE}`
WHERE week_start IS NOT NULL
GROUP BY w, m, h, s
ORDER BY w
"""

ROWS_SQL = f"""
SELECT
  IFNULL(FORMAT_DATE('%Y-%m-%d', ship_date), '') AS d,
  marketplace AS m,
  IFNULL(warehouse, '') AS h,
  IFNULL(order_number, '') AS o,
  IFNULL(po_number, '') AS p,
  IFNULL(tracking, '') AS t,
  IFNULL(consignee, '') AS g,
  IFNULL(carrier, '') AS r,
  IFNULL(units, 0) AS u,
  CAST(shipping_cost AS FLOAT64) AS c,
  cost_status AS s,
  IFNULL(carrier_source, '') AS cs,
  IFNULL(match_method, '') AS mm,
  IFNULL(is_additional_package, FALSE) AS ap,
  IFNULL(source_week, '') AS sw
FROM `{TABLE}`
ORDER BY ship_date DESC, marketplace, order_number
LIMIT {{limit}}
"""

META_SQL = f"""
SELECT
  COUNT(*) AS rows_total,
  IFNULL(FORMAT_DATE('%Y-%m-%d', MIN(ship_date)), '') AS first_ship,
  IFNULL(FORMAT_DATE('%Y-%m-%d', MAX(ship_date)), '') AS last_ship,
  IFNULL(FORMAT_TIMESTAMP('%Y-%m-%d %H:%M', MAX(loaded_at)), '') AS last_loaded
FROM `{TABLE}`
"""


# ── data ──────────────────────────────────────────────────────────────────


def table_missing(exc: Exception) -> bool:
    """True when the failure is just that the table has not been created yet."""
    text = str(exc)
    return "Not found: Table" in text or "notFound" in text


def from_bigquery(limit: int) -> tuple[list, list, dict, bool]:
    try:
        agg = bq_read.query(AGG_SQL)
        rows = bq_read.query(ROWS_SQL.format(limit=limit))
        meta = (bq_read.query(META_SQL) or [{}])[0]
    except Exception as exc:
        if not table_missing(exc):
            raise
        print(f"⚠ {TABLE} does not exist yet — run sql/create_shipping_orders_table.sql")
        return [], [], {"rows_total": 0}, True
    return agg, rows, meta, False


def from_json(path: Path, limit: int) -> tuple[list, list, dict]:
    """Build the same shapes from load_shipping_orders_to_bq.py --out-json."""
    loaded = json.loads(path.read_text())
    # The loader wraps its rows in an envelope; a bare list is also accepted.
    raw = loaded["rows"] if isinstance(loaded, dict) else loaded

    buckets: dict[tuple, dict] = {}
    for r in raw:
        if not r.get("week_start"):
            continue
        key = (r["week_start"], r["marketplace"], r.get("warehouse") or "Unknown", r["cost_status"])
        agg = buckets.setdefault(key, {"n": 0, "u": 0, "c": 0.0})
        agg["n"] += 1
        agg["u"] += r.get("units") or 0
        agg["c"] += r.get("shipping_cost") or 0.0

    agg_rows = [
        {"w": k[0], "m": k[1], "h": k[2], "s": k[3], "n": v["n"], "u": v["u"], "c": round(v["c"], 2)}
        for k, v in sorted(buckets.items())
    ]

    detail = sorted(raw, key=lambda r: (r.get("ship_date") or "", r["marketplace"]), reverse=True)
    rows = [
        {
            "d": r.get("ship_date") or "",
            "m": r["marketplace"],
            "h": r.get("warehouse") or "",
            "o": r.get("order_number") or "",
            "p": r.get("po_number") or "",
            "t": r.get("tracking") or "",
            "g": r.get("consignee") or "",
            "r": r.get("carrier") or "",
            "u": r.get("units") or 0,
            "c": r.get("shipping_cost"),
            "s": r["cost_status"],
            "cs": r.get("carrier_source") or "",
            "mm": r.get("match_method") or "",
            "ap": bool(r.get("is_additional_package")),
            "sw": r.get("source_week") or "",
        }
        for r in detail[:limit]
    ]

    ship_dates = [r["ship_date"] for r in raw if r.get("ship_date")]
    loaded = [r["loaded_at"] for r in raw if r.get("loaded_at")]
    meta = {
        "rows_total": len(raw),
        "first_ship": min(ship_dates) if ship_dates else "",
        "last_ship": max(ship_dates) if ship_dates else "",
        "last_loaded": max(loaded)[:16] if loaded else "",
    }
    return agg_rows, rows, meta


def fingerprint(agg: list, meta: dict) -> str:
    """Identity of the numbers on the page — detail rows follow the aggregates."""
    payload = json.dumps([agg, meta], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


# ── render ────────────────────────────────────────────────────────────────


def render(agg: list, rows: list, meta: dict, banner: str, source: str, needs_table: bool = False) -> str:
    payload = {
        "agg": agg,
        "rows": rows,
        "meta": meta,
        "order": MARKETPLACE_ORDER,
        "banner": banner,
        "source": source,
        "needs_table": needs_table,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    return TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser(description="Build the Cost Per SKU shipping dashboard")
    ap.add_argument("--out", default="shipping_dashboard.html", help="HTML file to write")
    ap.add_argument("--from-json", help="Render from a loader --out-json file instead of BigQuery")
    ap.add_argument("--max-rows", type=int, default=20000, help="Shipments embedded in the page")
    ap.add_argument("--banner", default="", help="Notice shown across the top of the page")
    ap.add_argument("--fingerprint-file", help="Skip writing when the numbers are unchanged")
    ap.add_argument("--force", action="store_true", help="Write even if unchanged")
    args = ap.parse_args()

    missing = False
    if args.from_json:
        agg, rows, meta = from_json(Path(args.from_json).expanduser(), args.max_rows)
        source = f"preview from {Path(args.from_json).name}"
    else:
        agg, rows, meta, missing = from_bigquery(args.max_rows)
        source = TABLE + (" (not created yet)" if missing else "")

    fp = fingerprint(agg, meta)
    fp_path = Path(args.fingerprint_file).expanduser() if args.fingerprint_file else None
    if fp_path and fp_path.exists() and not args.force:
        if fp in fp_path.read_text():
            print("NO_CHANGE")
            return

    html = render(agg, rows, meta, args.banner, source, needs_table=missing)
    out = Path(args.out).expanduser()
    safe_write_text(out, html, PAGE_MARKER, "dashboard page")
    if fp_path:
        safe_write_text(fp_path, f"{FINGERPRINT_MARKER}\n{fp}\n", FINGERPRINT_MARKER, "fingerprint")

    units = sum(r["u"] for r in agg)
    cost = sum(r["c"] for r in agg if r["s"] == "matched")
    matched_units = sum(r["u"] for r in agg if r["s"] == "matched")
    cpu = cost / matched_units if matched_units else 0.0
    print(f"✓ {out}  ({out.stat().st_size / 1024:.0f} KB)")
    print(f"  {meta.get('rows_total', 0):,} shipments · {units:,} units · ${cost:,.2f} · ${cpu:.2f}/unit")
    print(f"  ship dates {meta.get('first_ship') or '—'} → {meta.get('last_ship') or '—'}")
    if not agg:
        print("  table is empty — run the loader from the Mac first")


# ── the page ──────────────────────────────────────────────────────────────

TEMPLATE = r"""<title>Cost Per SKU — Shipping · Americanflat</title>
<style>
/* Americanflat design tokens. Brand face (Glacial Indifference) cannot be
   embedded here — an artifact may not fetch a font CDN — so the stack falls
   through to the closest geometric system sans. One family, two weights. */
:root {
  --font: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;

  --ground:     #FFFFFF;
  --surface:    #FFFFFF;
  --surface-2:  #FAFAFA;
  --ink:        #0F0F0F;
  --ink-2:      #666666;
  --ink-3:      #8C8C8C;
  --line:       #E6E6E6;
  --line-2:     #B3B3B3;

  --alert:      #CE0E2D;
  --alert-bg:   #FCEBEE;

  /* Categorical slots, fixed order, validated for both themes. */
  --s-1: #2A6FD6;  /* Target   */
  --s-2: #0E8A78;  /* Shopify  */
  --s-3: #B07A00;  /* Michaels */
  --s-4: #7A5BC4;  /* Macy's   */

  --grid:       #EDEDED;
  --tip-bg:     #0F0F0F;
  --tip-ink:    #FFFFFF;

  --r-sm: 4px;
  --r-md: 8px;
  --r-pill: 9999px;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:    #0F0F0F;
    --surface:   #151515;
    --surface-2: #1A1A1A;
    --ink:       #F2F2F2;
    --ink-2:     #A6A6A6;
    --ink-3:     #808080;
    --line:      #2B2B2B;
    --line-2:    #3D3D3D;
    --alert:     #F0637A;
    --alert-bg:  #2A1418;
    --s-1: #5F95DE;
    --s-2: #1B8F7C;
    --s-3: #B58818;
    --s-4: #A084D2;
    --grid:      #242424;
    --tip-bg:    #F2F2F2;
    --tip-ink:   #0F0F0F;
  }
}

:root[data-theme="dark"] {
  --ground:    #0F0F0F;
  --surface:   #151515;
  --surface-2: #1A1A1A;
  --ink:       #F2F2F2;
  --ink-2:     #A6A6A6;
  --ink-3:     #808080;
  --line:      #2B2B2B;
  --line-2:    #3D3D3D;
  --alert:     #F0637A;
  --alert-bg:  #2A1418;
  --s-1: #5F95DE;
  --s-2: #1B8F7C;
  --s-3: #B58818;
  --s-4: #A084D2;
  --grid:      #242424;
  --tip-bg:    #F2F2F2;
  --tip-ink:   #0F0F0F;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--ground);
  color: var(--ink);
  font-family: var(--font);
  font-size: 16px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

.page {
  max-width: 1240px;
  margin: 0 auto;
  padding: 40px 32px 96px;
  display: flex;
  flex-direction: column;
  gap: 48px;
}

/* ── header ─────────────────────────────────────────────────────────── */

.masthead {
  display: flex;
  justify-content: center;
  padding-bottom: 32px;
  border-bottom: 1px solid var(--line);
}
/* Wordmark set in text: the brand face can't be embedded in an artifact, and a
   fixed-width SVG recreation collides with its own ® in a fallback face. */
.wordmark {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: 0.04em;
  line-height: 1;
  color: var(--ink);
}
.wordmark sup {
  font-size: 0.3em;
  font-weight: 400;
  vertical-align: super;
  margin-left: 3px;
}

.titles { display: flex; flex-direction: column; gap: 12px; }
.eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--ink-2);
}
h1 {
  margin: 0;
  font-size: clamp(2rem, 4.5vw, 3rem);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.015em;
  text-wrap: balance;
}
.lede {
  margin: 0;
  max-width: 68ch;
  font-size: 1.125rem;
  color: var(--ink-2);
}

.banner {
  padding: 14px 18px;
  border: 1px solid var(--alert);
  border-radius: var(--r-md);
  background: var(--alert-bg);
  color: var(--ink);
  font-size: 15px;
}
.banner strong { color: var(--alert); }

/* ── filters ────────────────────────────────────────────────────────── */

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 20px;
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface-2);
}
.field { display: flex; flex-direction: column; gap: 6px; }
.field > label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.field select, .field input {
  font-family: var(--font);
  font-size: 14px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line-2);
  border-radius: var(--r-sm);
  padding: 7px 10px;
  min-height: 34px;
}
.field input[type="search"] { min-width: 240px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 13px;
  border: 1px solid var(--line-2);
  border-radius: var(--r-pill);
  background: var(--surface);
  color: var(--ink);
  font-family: var(--font);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}
.chip[aria-pressed="false"] { color: var(--ink-3); border-color: var(--line); }
.chip[aria-pressed="false"] .swatch { opacity: 0.3; }
.swatch { width: 10px; height: 10px; border-radius: 2px; background: var(--ink-2); }
.btn {
  font-family: var(--font);
  font-size: 13px;
  font-weight: 700;
  padding: 8px 16px;
  border-radius: var(--r-sm);
  border: 1px solid var(--ink);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
}
.btn-solid { background: var(--ink); color: var(--ground); }
:is(.chip, .btn, select, input):focus-visible {
  outline: 2px solid var(--s-1);
  outline-offset: 2px;
}

/* ── kpis ───────────────────────────────────────────────────────────── */

.kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 16px;
}
.kpi {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 20px;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.kpi-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.kpi-value {
  font-size: 2rem;
  font-weight: 700;
  line-height: 1.05;
  font-variant-numeric: tabular-nums;
}
.kpi-note { font-size: 13px; color: var(--ink-2); }

/* ── sections ───────────────────────────────────────────────────────── */

section { display: flex; flex-direction: column; gap: 16px; }
h2 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}
.sub { margin: 0; font-size: 14px; color: var(--ink-2); max-width: 74ch; }

.panel {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface);
  padding: 20px;
}
.chart-wrap { position: relative; }
.chart-wrap svg { display: block; width: 100%; overflow: visible; }
.legend { display: flex; flex-wrap: wrap; gap: 16px; padding-top: 4px; }
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: var(--ink-2);
}
.legend-key { width: 14px; height: 3px; border-radius: 2px; }
.legend-key.dashed {
  background: repeating-linear-gradient(90deg, var(--ink-3) 0 4px, transparent 4px 7px);
}

.tip {
  position: absolute;
  z-index: 5;
  min-width: 150px;
  padding: 10px 12px;
  background: var(--tip-bg);
  color: var(--tip-ink);
  border-radius: var(--r-sm);
  font-size: 12.5px;
  line-height: 1.45;
  pointer-events: none;
  opacity: 0;
  transition: opacity 120ms ease;
}
.tip[data-show="1"] { opacity: 1; }
.tip-head { font-weight: 700; margin-bottom: 5px; }
.tip-row { display: flex; justify-content: space-between; gap: 14px; font-variant-numeric: tabular-nums; }
/* The reader already knows the series and wants the number: value strong, name secondary. */
.tip-row .k { display: inline-flex; align-items: center; gap: 7px; opacity: 0.78; }
.tip-row .v { font-weight: 700; }
.tip-key { width: 12px; height: 2px; border-radius: 1px; flex: none; }
.tip-key.rect { height: 9px; width: 9px; border-radius: 2px; }
.tip-total { margin-top: 5px; padding-top: 5px; border-top: 1px solid rgba(128,128,128,0.4); }

/* ── tables ─────────────────────────────────────────────────────────── */

.scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td {
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}
th {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-2);
  background: var(--surface-2);
  position: sticky;
  top: 0;
}
th.sortable { cursor: pointer; }
th.sortable[aria-sort="ascending"]::after { content: " \2191"; }
th.sortable[aria-sort="descending"]::after { content: " \2193"; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tbody tr:hover td { background: var(--surface-2); }
tfoot td { font-weight: 700; border-top: 2px solid var(--line-2); border-bottom: none; }
.mp { display: inline-flex; align-items: center; gap: 8px; font-weight: 700; }
.pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 9px;
  border-radius: var(--r-pill);
  font-size: 11.5px;
  font-weight: 700;
  background: var(--line);
  color: var(--ink);
}
.pill-alert { background: var(--alert-bg); color: var(--alert); }
.muted { color: var(--ink-3); }

.tablebar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: var(--ink-2);
}
.pager { display: flex; align-items: center; gap: 10px; }

.empty {
  border: 1px dashed var(--line-2);
  border-radius: var(--r-md);
  padding: 40px 28px;
  background: var(--surface-2);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.empty h2 { font-size: 1.25rem; }
.empty code.inline {
  display: inline;
  padding: 1px 6px;
  white-space: normal;
}
.empty code {
  display: block;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12.5px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  padding: 10px 12px;
  overflow-x: auto;
  white-space: pre;
}

footer {
  border-top: 1px solid var(--line);
  padding-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12.5px;
  color: var(--ink-2);
}
footer p { margin: 0; max-width: 84ch; }

@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
</style>

<div class="page">
  <div class="masthead">
    <span class="wordmark">americanflat<sup>&#174;</sup></span>
  </div>

  <div class="titles">
    <p class="eyebrow">Operations &middot; Cost per SKU</p>
    <h1>Shipping we pay for</h1>
    <p class="lede" id="lede"></p>
  </div>

  <div class="banner" id="banner" hidden></div>

  <div id="body"></div>

  <footer>
    <p><strong>Cost per unit</strong> is the invoiced freight divided by the units on shipments we
      could tie to an invoice. Shipments still waiting on their invoice are counted in units shipped
      and in the match rate, but never in cost per unit — that keeps the rate honest while a FedEx
      or Stamps.com invoice is still outstanding.</p>
    <p><strong>Extra packages.</strong> When one order ships in more than one box, the second box
      onward carries its freight but no units, so units are counted once and cost is counted in
      full.</p>
    <p id="prov"></p>
  </footer>
</div>

<script>
const PAYLOAD = __PAYLOAD__;

const SERIES = ["var(--s-1)", "var(--s-2)", "var(--s-3)", "var(--s-4)"];
const colorOf = m => SERIES[PAYLOAD.order.indexOf(m)] || "var(--ink-2)";

const usd = n => "$" + n.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
const usd0 = n => "$" + Math.round(n).toLocaleString("en-US");
const num = n => n.toLocaleString("en-US");
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g,
  c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function prettyDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return MONTHS[m - 1] + " " + d + ", " + y;
}
function weekLabel(iso) {
  const [, m, d] = iso.split("-").map(Number);
  return MONTHS[m - 1] + " " + d;
}

/* ── state ───────────────────────────────────────────────────────────── */

const marketplaces = PAYLOAD.order.filter(m => PAYLOAD.agg.some(r => r.m === m));
const warehouses = [...new Set(PAYLOAD.agg.map(r => r.h))].sort();
const weeks = [...new Set(PAYLOAD.agg.map(r => r.w))].sort();

const state = {
  on: new Set(marketplaces),
  warehouse: "",
  status: "",
  weeks: 0,          // 0 = every week
  q: "",
  page: 0,
  sort: {key: "d", dir: -1},
};

function visibleWeeks() {
  if (!state.weeks || state.weeks >= weeks.length) return weeks;
  return weeks.slice(weeks.length - state.weeks);
}

function aggFiltered() {
  const keep = new Set(visibleWeeks());
  return PAYLOAD.agg.filter(r =>
    state.on.has(r.m) &&
    keep.has(r.w) &&
    (!state.warehouse || r.h === state.warehouse) &&
    (!state.status || r.s === state.status));
}

function rollup(rows) {
  const t = {shipments: 0, units: 0, cost: 0, matchedShipments: 0, matchedUnits: 0};
  for (const r of rows) {
    t.shipments += r.n;
    t.units += r.u;
    if (r.s === "matched") {
      t.cost += r.c;
      t.matchedShipments += r.n;
      t.matchedUnits += r.u;
    }
  }
  t.cpu = t.matchedUnits ? t.cost / t.matchedUnits : 0;
  t.matchRate = t.shipments ? 100 * t.matchedShipments / t.shipments : 0;
  return t;
}

/* ── shell ───────────────────────────────────────────────────────────── */

function boot() {
  const meta = PAYLOAD.meta || {};
  const intro = "Every package the 3PLs shipped for Target, Shopify, Michaels and Macy's — the "
    + "four channels where we cover the freight — with the FedEx or Stamps.com charge matched onto it.";
  document.getElementById("lede").textContent = PAYLOAD.agg.length
    ? intro + " " + prettyDate(meta.first_ship) + " through " + prettyDate(meta.last_ship) + "."
    : PAYLOAD.needs_table
      ? intro + " The database behind it still has to be built — the steps are below."
      : intro + " Nothing has been loaded into the database yet.";

  if (PAYLOAD.banner) {
    const b = document.getElementById("banner");
    b.hidden = false;
    b.innerHTML = "<strong>Note.</strong> " + esc(PAYLOAD.banner);
  }

  document.getElementById("prov").textContent =
    "Source: " + PAYLOAD.source + " · " + num(meta.rows_total || 0) + " shipments in the table, "
    + num((PAYLOAD.rows || []).length) + " loaded into this page · last load "
    + (meta.last_loaded || "—") + " · page built " + PAYLOAD.generated + ".";

  if (!PAYLOAD.agg.length) { renderEmpty(); return; }
  renderApp();
}

function renderEmpty() {
  const step0 = PAYLOAD.needs_table
    ? `<p class="sub"><strong>First</strong>, make the table. It only has to be done once, and
         re-running it is harmless.</p>
       <code>bq query --use_legacy_sql=false --max_rows=100 &lt; sql/create_shipping_orders_table.sql</code>`
    : "";
  document.getElementById("body").innerHTML = `
    <div class="empty">
      <h2>${PAYLOAD.needs_table ? "The table isn't there yet" : "No shipments loaded yet"}</h2>
      ${step0}
      <p class="sub">${PAYLOAD.needs_table ? "Then run" : "Run"} these two commands on the Mac and
        rebuild this page. The first reads a week's 3PL and carrier files and writes the shipments
        to the database; the second redraws this page from it.</p>
      <code>python3 scripts/load_shipping_orders_to_bq.py --week-dir "&lt;weekly staging folder&gt;"
python3 scripts/generate_shipping_dashboard.py --out shipping_dashboard.html</code>
      <p class="sub">To load the history in one pass, point the loader at the folder that holds
        every dated week instead of one week:
        <code class="inline">--backfill-root "&lt;the Weekly Shipping Reports folder&gt;"</code></p>
    </div>`;
}

function renderApp() {
  document.getElementById("body").innerHTML = `
    <div class="filters" role="group" aria-label="Filters">
      <div class="field">
        <label id="mp-label">Marketplace</label>
        <div class="chips" id="mp-chips" role="group" aria-labelledby="mp-label"></div>
      </div>
      <div class="field">
        <label for="f-wh">Warehouse</label>
        <select id="f-wh"></select>
      </div>
      <div class="field">
        <label for="f-status">Invoice</label>
        <select id="f-status">
          <option value="">Matched and unmatched</option>
          <option value="matched">Matched only</option>
          <option value="unmatched">Unmatched only</option>
        </select>
      </div>
      <div class="field">
        <label for="f-weeks">Period</label>
        <select id="f-weeks"></select>
      </div>
      <div class="field" style="flex:1 1 240px">
        <label for="f-q">Find a shipment</label>
        <input type="search" id="f-q" placeholder="Order, PO, tracking or ship-to">
      </div>
      <button class="btn" id="f-reset" type="button">Reset</button>
    </div>

    <div class="kpis" id="kpis"></div>

    <section>
      <h2>Cost per unit by week</h2>
      <p class="sub">Invoiced freight divided by matched units, week by week. The dashed line is
        every selected marketplace blended together.</p>
      <div class="panel">
        <div class="chart-wrap" id="cpu-wrap">
          <svg id="cpu-chart" role="img" aria-label="Cost per unit by week and marketplace"></svg>
          <div class="tip" id="cpu-tip"></div>
        </div>
        <div class="legend" id="cpu-legend"></div>
      </div>
    </section>

    <section>
      <h2>Units shipped by week</h2>
      <p class="sub">What the cost per unit is spread across.</p>
      <div class="panel">
        <div class="chart-wrap" id="units-wrap">
          <svg id="units-chart" role="img" aria-label="Units shipped by week and marketplace"></svg>
          <div class="tip" id="units-tip"></div>
        </div>
        <div class="legend" id="units-legend"></div>
      </div>
    </section>

    <section>
      <h2>By marketplace</h2>
      <div class="panel scroll">
        <table id="mp-table"></table>
      </div>
    </section>

    <section>
      <h2>Shipments</h2>
      <div class="tablebar">
        <span id="rows-count"></span>
        <div class="pager">
          <button class="btn" id="prev" type="button">Previous</button>
          <span id="page-label"></span>
          <button class="btn" id="next" type="button">Next</button>
          <button class="btn btn-solid" id="csv" type="button">Download CSV</button>
        </div>
      </div>
      <div class="panel scroll" style="max-height:70vh;overflow-y:auto">
        <table id="rows-table"></table>
      </div>
    </section>`;

  // marketplace chips
  const chips = document.getElementById("mp-chips");
  chips.innerHTML = marketplaces.map(m =>
    `<button class="chip" type="button" data-mp="${esc(m)}" aria-pressed="true">
       <span class="swatch" style="background:${colorOf(m)}"></span>${esc(m)}</button>`).join("");
  chips.addEventListener("click", e => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    const m = btn.dataset.mp;
    if (state.on.has(m)) {
      if (state.on.size === 1) return;   // never leave the page blank
      state.on.delete(m);
    } else {
      state.on.add(m);
    }
    btn.setAttribute("aria-pressed", state.on.has(m) ? "true" : "false");
    state.page = 0;
    draw();
  });

  const wh = document.getElementById("f-wh");
  wh.innerHTML = '<option value="">All warehouses</option>'
    + warehouses.map(h => `<option value="${esc(h)}">${esc(h)}</option>`).join("");

  const wk = document.getElementById("f-weeks");
  const spans = [[0, "All weeks"], [4, "Last 4 weeks"], [8, "Last 8 weeks"], [13, "Last 13 weeks"], [26, "Last 26 weeks"]]
    .filter(([n]) => n === 0 || n < weeks.length);
  wk.innerHTML = spans.map(([n, label]) => `<option value="${n}">${label}</option>`).join("");

  wh.addEventListener("change", e => { state.warehouse = e.target.value; state.page = 0; draw(); });
  document.getElementById("f-status").addEventListener("change", e => {
    state.status = e.target.value; state.page = 0; draw();
  });
  wk.addEventListener("change", e => { state.weeks = Number(e.target.value); state.page = 0; draw(); });
  document.getElementById("f-q").addEventListener("input", e => {
    state.q = e.target.value.trim().toLowerCase(); state.page = 0; drawRows();
  });
  document.getElementById("f-reset").addEventListener("click", () => {
    state.on = new Set(marketplaces);
    state.warehouse = ""; state.status = ""; state.weeks = 0; state.q = ""; state.page = 0;
    document.querySelectorAll(".chip").forEach(c => c.setAttribute("aria-pressed", "true"));
    wh.value = ""; wk.value = "0";
    document.getElementById("f-status").value = "";
    document.getElementById("f-q").value = "";
    draw();
  });
  document.getElementById("prev").addEventListener("click", () => { state.page--; drawRows(); });
  document.getElementById("next").addEventListener("click", () => { state.page++; drawRows(); });
  document.getElementById("csv").addEventListener("click", downloadCsv);

  let pending;
  window.addEventListener("resize", () => {
    clearTimeout(pending);
    pending = setTimeout(() => { drawCpu(); drawUnits(); }, 120);
  });

  draw();
}

function draw() { drawKpis(); drawCpu(); drawUnits(); drawMarketplaces(); drawRows(); }

/* ── kpis ────────────────────────────────────────────────────────────── */

function drawKpis() {
  const t = rollup(aggFiltered());
  const shown = visibleWeeks();
  const tiles = [
    ["Units shipped", num(t.units), num(t.shipments) + " packages"],
    ["Freight invoiced", usd0(t.cost), "matched to " + num(t.matchedShipments) + " packages"],
    ["Cost per unit", t.matchedUnits ? usd(t.cpu) : "—", "invoiced cost ÷ matched units"],
    ["Invoice match rate", t.matchRate.toFixed(1) + "%",
      num(t.shipments - t.matchedShipments) + " packages still unmatched"],
    ["Weeks", num(shown.length),
      shown.length ? weekLabel(shown[0]) + " – " + weekLabel(shown[shown.length - 1]) : "—"],
  ];
  document.getElementById("kpis").innerHTML = tiles.map(([label, value, note]) =>
    `<div class="kpi"><span class="kpi-label">${esc(label)}</span>
       <span class="kpi-value">${esc(value)}</span>
       <span class="kpi-note">${esc(note)}</span></div>`).join("");
}

/* ── charts ──────────────────────────────────────────────────────────── */

function seriesByWeek() {
  const wks = visibleWeeks();
  const idx = new Map(wks.map((w, i) => [w, i]));
  const on = [...marketplaces].filter(m => state.on.has(m));
  const cost = {}, units = {}, mUnits = {}, ship = {};
  for (const m of on) {
    cost[m] = new Array(wks.length).fill(0);
    units[m] = new Array(wks.length).fill(0);
    mUnits[m] = new Array(wks.length).fill(0);
    ship[m] = new Array(wks.length).fill(0);
  }
  for (const r of aggFiltered()) {
    const i = idx.get(r.w);
    if (i === undefined || !cost[r.m]) continue;
    units[r.m][i] += r.u;
    ship[r.m][i] += r.n;
    if (r.s === "matched") { cost[r.m][i] += r.c; mUnits[r.m][i] += r.u; }
  }
  const cpu = {};
  for (const m of on) {
    cpu[m] = cost[m].map((c, i) => (mUnits[m][i] ? c / mUnits[m][i] : null));
  }
  const blended = wks.map((_, i) => {
    let c = 0, u = 0;
    for (const m of on) { c += cost[m][i]; u += mUnits[m][i]; }
    return u ? c / u : null;
  });
  return {wks, on, cpu, units, cost, blended, ship};
}

// Both charts inset their first and last point by the same amount, so the weeks
// line up between them and edge bars are not clipped by the plot edge.
const INSET = 16;
const xScale = (n, plotW) => i =>
  n === 1 ? plotW / 2 : INSET + (i / (n - 1)) * (plotW - 2 * INSET);

// Park the tooltip on whichever side of the plot the cursor is not on.
function placeTip(tip, wrap, fracAcross) {
  const w = wrap.clientWidth || 900;
  const tw = tip.offsetWidth || 190;
  tip.style.left = (fracAcross < 0.55 ? w - tw - 12 : 12) + "px";
}

function axisTicks(max) {
  if (max <= 0) return [0, 1];
  const raw = max / 4;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(s => s * mag).find(s => s >= raw) || mag * 10;
  const out = [];
  for (let v = 0; v <= max + step / 2; v += step) out.push(v);
  return out;
}

function drawCpu() {
  const {wks, on, cpu, blended, units} = seriesByWeek();
  const svg = document.getElementById("cpu-chart");
  const W = document.getElementById("cpu-wrap").clientWidth || 900;
  const H = 340;
  const pad = {t: 16, r: 96, b: 34, l: 56};
  const plotW = Math.max(80, W - pad.l - pad.r);
  const plotH = H - pad.t - pad.b;

  const all = on.flatMap(m => cpu[m]).concat(blended).filter(v => v != null);
  const max = all.length ? Math.max(...all) : 1;
  const ticks = axisTicks(max);
  const top = ticks[ticks.length - 1];
  const dec = top < 10 ? 2 : 0;      // one format for every label on the axis
  const x = xScale(wks.length, plotW);
  const y = v => plotH - (v / top) * plotH;

  const parts = [];
  parts.push(`<g transform="translate(${pad.l},${pad.t})">`);
  for (const tv of ticks) {
    parts.push(`<line x1="0" y1="${y(tv).toFixed(1)}" x2="${plotW}" y2="${y(tv).toFixed(1)}"
      stroke="var(--grid)" stroke-width="1"/>`);
    parts.push(`<text x="-10" y="${(y(tv) + 4).toFixed(1)}" text-anchor="end" font-size="11"
      fill="var(--ink-3)" font-family="var(--font)">$${tv.toFixed(dec)}</text>`);
  }
  const every = Math.max(1, Math.ceil(wks.length / 12));
  wks.forEach((w, i) => {
    if (i % every && i !== wks.length - 1) return;
    parts.push(`<text x="${x(i).toFixed(1)}" y="${plotH + 20}" text-anchor="middle" font-size="11"
      fill="var(--ink-3)" font-family="var(--font)">${weekLabel(w)}</text>`);
  });

  const path = vals => {
    let d = "", open = false;
    vals.forEach((v, i) => {
      if (v == null) { open = false; return; }
      d += (open ? " L" : " M") + x(i).toFixed(1) + " " + y(v).toFixed(1);
      open = true;
    });
    return d.trim();
  };

  // blended first, so the marketplace lines sit above it
  const bpath = path(blended);
  if (bpath) {
    parts.push(`<path d="${bpath}" fill="none" stroke="var(--ink-3)" stroke-width="2"
      stroke-dasharray="5 4" stroke-linecap="round"/>`);
  }
  for (const m of on) {
    const d = path(cpu[m]);
    if (!d) continue;
    parts.push(`<path d="${d}" fill="none" stroke="${colorOf(m)}" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round"/>`);
    let last = -1;
    cpu[m].forEach((v, i) => { if (v != null) last = i; });
    if (last >= 0) {
      parts.push(`<circle cx="${x(last).toFixed(1)}" cy="${y(cpu[m][last]).toFixed(1)}" r="4.5"
        fill="${colorOf(m)}" stroke="var(--surface)" stroke-width="2"/>`);
      parts.push(`<text x="${(x(last) + 12).toFixed(1)}" y="${(y(cpu[m][last]) + 4).toFixed(1)}"
        font-size="12" font-weight="700" fill="${colorOf(m)}"
        font-family="var(--font)">${esc(m)}</text>`);
    }
  }
  parts.push(`<line class="cross" x1="0" y1="0" x2="0" y2="${plotH}" stroke="var(--line-2)"
    stroke-width="1" opacity="0"/>`);
  parts.push(`<rect x="0" y="0" width="${plotW}" height="${plotH}" fill="transparent"/>`);
  parts.push("</g>");

  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("height", H);
  svg.innerHTML = parts.join("");

  document.getElementById("cpu-legend").innerHTML =
    on.map(m => `<span class="legend-item"><span class="legend-key"
        style="background:${colorOf(m)}"></span>${esc(m)}</span>`).join("")
    + `<span class="legend-item"><span class="legend-key dashed"></span>Blended</span>`;

  // crosshair + tooltip
  const tip = document.getElementById("cpu-tip");
  const cross = svg.querySelector(".cross");
  const wrap = document.getElementById("cpu-wrap");
  svg.onmousemove = ev => {
    const box = svg.getBoundingClientRect();
    const px = (ev.clientX - box.left) * (W / box.width) - pad.l;
    if (px < -8 || px > plotW + 8 || !wks.length) { tip.dataset.show = "0"; cross.setAttribute("opacity", "0"); return; }
    const i = wks.length === 1 ? 0 : Math.round((px / plotW) * (wks.length - 1));
    const k = Math.min(Math.max(i, 0), wks.length - 1);
    cross.setAttribute("opacity", "1");
    cross.setAttribute("x1", x(k).toFixed(1));
    cross.setAttribute("x2", x(k).toFixed(1));
    const rows = on.map(m => `<div class="tip-row"><span class="k">
        <span class="tip-key" style="background:${colorOf(m)}"></span>${esc(m)}</span>
        <span class="v">${cpu[m][k] == null ? "—" : usd(cpu[m][k])}</span></div>`).join("");
    tip.innerHTML = `<div class="tip-head">Week of ${weekLabel(wks[k])}</div>${rows}
      <div class="tip-row tip-total"><span class="k">Blended</span>
        <span class="v">${blended[k] == null ? "—" : usd(blended[k])}</span></div>
      <div class="tip-row"><span class="k">Units</span>
        <span class="v">${num(on.reduce((s, m) => s + units[m][k], 0))}</span></div>`;
    tip.dataset.show = "1";
    tip.style.top = "12px";
    placeTip(tip, wrap, wks.length === 1 ? 0 : k / (wks.length - 1));
  };
  svg.onmouseleave = () => { tip.dataset.show = "0"; cross.setAttribute("opacity", "0"); };
}

function drawUnits() {
  const {wks, on, units} = seriesByWeek();
  const svg = document.getElementById("units-chart");
  const W = document.getElementById("units-wrap").clientWidth || 900;
  const H = 200;
  const pad = {t: 12, r: 96, b: 32, l: 56};
  const plotW = Math.max(80, W - pad.l - pad.r);
  const plotH = H - pad.t - pad.b;

  const totals = wks.map((_, i) => on.reduce((s, m) => s + units[m][i], 0));
  const max = Math.max(1, ...totals);
  const ticks = axisTicks(max);
  const top = ticks[ticks.length - 1];
  const bw = Math.max(3, Math.min(28, (plotW - 2 * INSET) / Math.max(wks.length, 1) - 4));
  const x = xScale(wks.length, plotW);
  const h = v => (v / top) * plotH;

  const parts = [`<g transform="translate(${pad.l},${pad.t})">`];
  for (const tv of ticks) {
    parts.push(`<line x1="0" y1="${(plotH - h(tv)).toFixed(1)}" x2="${plotW}"
      y2="${(plotH - h(tv)).toFixed(1)}" stroke="var(--grid)" stroke-width="1"/>`);
    parts.push(`<text x="-10" y="${(plotH - h(tv) + 4).toFixed(1)}" text-anchor="end" font-size="11"
      fill="var(--ink-3)" font-family="var(--font)">${tv >= 1000 ? (tv / 1000) + "k" : tv}</text>`);
  }
  wks.forEach((w, i) => {
    let acc = 0;
    on.forEach(m => {
      const v = units[m][i];
      if (!v) return;
      const bh = h(v);
      // 2px surface gap keeps stacked segments legible
      const gap = acc > 0 ? 2 : 0;
      parts.push(`<rect x="${(x(i) - bw / 2).toFixed(1)}"
        y="${(plotH - acc - bh).toFixed(1)}" width="${bw.toFixed(1)}"
        height="${Math.max(1, bh - gap).toFixed(1)}" fill="${colorOf(m)}" rx="1"/>`);
      acc += bh;
    });
  });
  const every = Math.max(1, Math.ceil(wks.length / 12));
  wks.forEach((w, i) => {
    if (i % every && i !== wks.length - 1) return;
    parts.push(`<text x="${x(i).toFixed(1)}" y="${plotH + 20}" text-anchor="middle" font-size="11"
      fill="var(--ink-3)" font-family="var(--font)">${weekLabel(w)}</text>`);
  });
  // The hovered stack lifts, so the reader sees which bar the readout belongs to.
  parts.push(`<rect class="lift" x="0" y="0" width="${(bw + 4).toFixed(1)}" height="${plotH}"
    fill="none" stroke="var(--line-2)" stroke-width="1" rx="2" opacity="0"/>`);
  parts.push(`<rect x="0" y="0" width="${plotW}" height="${plotH}" fill="transparent"/>`);
  parts.push("</g>");

  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("height", H);
  svg.innerHTML = parts.join("");

  document.getElementById("units-legend").innerHTML =
    on.map(m => `<span class="legend-item"><span class="legend-key"
        style="background:${colorOf(m)};height:10px;width:10px;border-radius:2px"></span>${esc(m)}</span>`).join("");

  const tip = document.getElementById("units-tip");
  const wrap = document.getElementById("units-wrap");
  const lift = svg.querySelector(".lift");
  svg.onmousemove = ev => {
    const box = svg.getBoundingClientRect();
    const px = (ev.clientX - box.left) * (W / box.width) - pad.l;
    if (px < -8 || px > plotW + 8 || !wks.length) {
      tip.dataset.show = "0"; lift.setAttribute("opacity", "0"); return;
    }
    const inner = plotW - 2 * INSET;
    const i = wks.length === 1 ? 0 : Math.round(((px - INSET) / inner) * (wks.length - 1));
    const k = Math.min(Math.max(i, 0), wks.length - 1);
    lift.setAttribute("opacity", "1");
    lift.setAttribute("x", (x(k) - bw / 2 - 2).toFixed(1));
    lift.setAttribute("y", (plotH - h(totals[k]) - 3).toFixed(1));
    lift.setAttribute("height", (h(totals[k]) + 3).toFixed(1));
    const rows = on.map(m => `<div class="tip-row"><span class="k">
        <span class="tip-key rect" style="background:${colorOf(m)}"></span>${esc(m)}</span>
        <span class="v">${num(units[m][k])}</span></div>`).join("");
    tip.innerHTML = `<div class="tip-head">Week of ${weekLabel(wks[k])}</div>${rows}
      <div class="tip-row tip-total"><span class="k">Total units</span>
        <span class="v">${num(totals[k])}</span></div>`;
    tip.dataset.show = "1";
    tip.style.top = "8px";
    placeTip(tip, wrap, wks.length === 1 ? 0 : k / (wks.length - 1));
  };
  svg.onmouseleave = () => { tip.dataset.show = "0"; lift.setAttribute("opacity", "0"); };
}

/* ── marketplace table ───────────────────────────────────────────────── */

function drawMarketplaces() {
  const rows = aggFiltered();
  const by = new Map();
  for (const r of rows) {
    const t = by.get(r.m) || {shipments: 0, units: 0, cost: 0, mShip: 0, mUnits: 0};
    t.shipments += r.n;
    t.units += r.u;
    if (r.s === "matched") { t.cost += r.c; t.mShip += r.n; t.mUnits += r.u; }
    by.set(r.m, t);
  }
  const order = marketplaces.filter(m => by.has(m));
  const body = order.map(m => {
    const t = by.get(m);
    return `<tr>
      <td><span class="mp"><span class="swatch" style="background:${colorOf(m)}"></span>${esc(m)}</span></td>
      <td class="num">${num(t.shipments)}</td>
      <td class="num">${num(t.units)}</td>
      <td class="num">${usd(t.cost)}</td>
      <td class="num">${t.mUnits ? usd(t.cost / t.mUnits) : "—"}</td>
      <td class="num">${t.shipments ? (100 * t.mShip / t.shipments).toFixed(1) + "%" : "—"}</td>
    </tr>`;
  }).join("");
  const t = rollup(rows);
  document.getElementById("mp-table").innerHTML = `
    <thead><tr>
      <th>Marketplace</th><th class="num">Packages</th><th class="num">Units</th>
      <th class="num">Freight</th><th class="num">Cost / unit</th><th class="num">Matched</th>
    </tr></thead>
    <tbody>${body}</tbody>
    <tfoot><tr>
      <td>All selected</td><td class="num">${num(t.shipments)}</td><td class="num">${num(t.units)}</td>
      <td class="num">${usd(t.cost)}</td>
      <td class="num">${t.matchedUnits ? usd(t.cpu) : "—"}</td>
      <td class="num">${t.matchRate.toFixed(1)}%</td>
    </tr></tfoot>`;
}

/* ── shipment table ──────────────────────────────────────────────────── */

const COLS = [
  {key: "d", label: "Ship date", fmt: r => prettyDate(r.d)},
  {key: "m", label: "Marketplace",
   fmt: r => `<span class="mp"><span class="swatch" style="background:${colorOf(r.m)}"></span>${esc(r.m)}</span>`},
  {key: "h", label: "Warehouse"},
  {key: "o", label: "Order"},
  {key: "p", label: "PO"},
  {key: "t", label: "Tracking"},
  {key: "g", label: "Ship to"},
  {key: "r", label: "Carrier"},
  {key: "u", label: "Units", num: true, fmt: r => r.ap ? '<span class="muted">extra box</span>' : num(r.u)},
  {key: "c", label: "Freight", num: true, fmt: r => r.c == null ? '<span class="muted">—</span>' : usd(r.c)},
  {key: "cpu", label: "Cost / unit", num: true,
   fmt: r => (r.c != null && r.u > 0) ? usd(r.c / r.u) : '<span class="muted">—</span>',
   val: r => (r.c != null && r.u > 0) ? r.c / r.u : -1},
  {key: "s", label: "Invoice",
   fmt: r => r.s === "matched"
     ? `<span class="pill" title="${esc(r.mm)}">${esc(r.cs || "matched")}</span>`
     : '<span class="pill pill-alert">unmatched</span>'},
];

const PAGE = 100;

function filteredRows() {
  const keepWeeks = new Set(visibleWeeks());
  const inWeek = d => {
    if (!state.weeks) return true;
    if (!d) return false;
    // a ship date belongs to the Monday of its week
    const dt = new Date(d + "T00:00:00Z");
    const monday = new Date(dt);
    monday.setUTCDate(dt.getUTCDate() - ((dt.getUTCDay() + 6) % 7));
    return keepWeeks.has(monday.toISOString().slice(0, 10));
  };
  const q = state.q;
  return (PAYLOAD.rows || []).filter(r =>
    state.on.has(r.m) &&
    (!state.warehouse || r.h === state.warehouse) &&
    (!state.status || r.s === state.status) &&
    inWeek(r.d) &&
    (!q || (r.o + " " + r.p + " " + r.t + " " + r.g).toLowerCase().includes(q)));
}

function sortRows(rows) {
  const col = COLS.find(c => c.key === state.sort.key) || COLS[0];
  const val = col.val || (r => r[col.key]);
  const dir = state.sort.dir;
  return rows.slice().sort((a, b) => {
    const av = val(a), bv = val(b);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
    return String(av).localeCompare(String(bv)) * dir;
  });
}

function drawRows() {
  const all = sortRows(filteredRows());
  const pages = Math.max(1, Math.ceil(all.length / PAGE));
  state.page = Math.min(Math.max(state.page, 0), pages - 1);
  const slice = all.slice(state.page * PAGE, state.page * PAGE + PAGE);

  const head = COLS.map(c =>
    `<th class="sortable${c.num ? " num" : ""}" data-key="${c.key}"
       ${state.sort.key === c.key ? `aria-sort="${state.sort.dir === 1 ? "ascending" : "descending"}"` : ""}
       >${esc(c.label)}</th>`).join("");
  const body = slice.map(r =>
    "<tr>" + COLS.map(c =>
      `<td${c.num ? ' class="num"' : ""}>${c.fmt ? c.fmt(r) : esc(r[c.key])}</td>`).join("") + "</tr>").join("");

  const table = document.getElementById("rows-table");
  table.innerHTML = `<thead><tr>${head}</tr></thead><tbody>${body || `<tr><td colspan="${COLS.length}"
    class="muted">Nothing matches these filters.</td></tr>`}</tbody>`;
  table.querySelectorAll("th.sortable").forEach(th => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      state.sort = {key, dir: state.sort.key === key ? -state.sort.dir : (key === "d" ? -1 : 1)};
      drawRows();
    });
  });

  const embedded = (PAYLOAD.rows || []).length;
  const total = (PAYLOAD.meta || {}).rows_total || embedded;
  document.getElementById("rows-count").textContent =
    num(all.length) + " of " + num(embedded) + " shipments on this page"
    + (embedded < total ? " (the " + num(embedded) + " most recent of " + num(total) + " in the table)" : "");
  document.getElementById("page-label").textContent = (state.page + 1) + " / " + pages;
  document.getElementById("prev").disabled = state.page === 0;
  document.getElementById("next").disabled = state.page >= pages - 1;
}

function downloadCsv() {
  const rows = sortRows(filteredRows());
  const head = ["ship_date", "marketplace", "warehouse", "order", "po", "tracking", "ship_to",
    "carrier", "units", "freight", "cost_per_unit", "invoice", "carrier_source", "match_method",
    "extra_box", "source_week"];
  const cell = v => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const lines = [head.join(",")];
  for (const r of rows) {
    lines.push([r.d, r.m, r.h, r.o, r.p, r.t, r.g, r.r, r.u,
      r.c == null ? "" : r.c.toFixed(2),
      (r.c != null && r.u > 0) ? (r.c / r.u).toFixed(2) : "",
      r.s, r.cs, r.mm, r.ap ? "yes" : "", r.sw].map(cell).join(","));
  }
  const blob = new Blob([lines.join("\n")], {type: "text/csv"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "shipping_orders.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

boot();
</script>
"""


if __name__ == "__main__":
    main()
