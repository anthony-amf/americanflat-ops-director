#!/usr/bin/env python3
"""Build the CX returns portal HTML from references/routing.json.

The portal is a single self-contained file: paste customer details on the left,
get the warehouse email on the right. All parsing happens in the browser, so no
customer data leaves the page.

Run from the skill directory:

    python3 scripts/build_portal.py

Writes portal/cx-returns-portal.html. Re-run after editing routing.json, then
republish the Artifact with the existing url: so it updates in place.
"""

import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ROUTING = SKILL_DIR / "references" / "routing.json"
CSV_CONFIG = SKILL_DIR / "references" / "shipstation-csv.json"
WAREHOUSE_DOC = SKILL_DIR / "references" / "warehouses.md"
PLAYBOOK_DOC = SKILL_DIR / "references" / "playbook.md"
TEMPLATES_DOC = SKILL_DIR / "references" / "templates.md"
OUT = SKILL_DIR / "portal" / "cx-returns-portal.html"


def check_drift(routing: dict) -> list:
    """Warn when the config and the human docs disagree.

    Two failure modes, both seen for real: a contact updated in one file and not
    the other, and a case inserted into routing.json whose name never reaches the
    playbook (the playbook then routes CX to the wrong template).
    """
    warnings = []

    if WAREHOUSE_DOC.exists():
        doc = WAREHOUSE_DOC.read_text().lower()
        for key, wh in routing["warehouses"].items():
            for addr in wh["to"] + wh["cc"] + wh.get("cc_inventory", []):
                if addr.lower() not in doc:
                    warnings.append(f"{key}: {addr} is in routing.json but not warehouses.md")
    else:
        warnings.append("warehouses.md not found — skipped the contact drift check")

    for doc_path in (PLAYBOOK_DOC, TEMPLATES_DOC):
        if not doc_path.exists():
            warnings.append(f"{doc_path.name} not found — skipped the case drift check")
            continue
        text = doc_path.read_text().lower()
        for key, case in routing["cases"].items():
            if case["label"].split("—")[0].strip().lower() not in text:
                warnings.append(
                    f"case '{case['label']}' ({key}) is in routing.json "
                    f"but never named in {doc_path.name}")

    return warnings


def build(routing: dict, csv_config: dict) -> str:
    # The template carries literal braces (CSS, JS), so substitute rather than format.
    return (TEMPLATE
            .replace("__ROUTING_JSON__", json.dumps(routing, indent=2))
            .replace("__CSV_CONFIG_JSON__", json.dumps(csv_config, indent=2)))


TEMPLATE = r"""<title>Returns Desk</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700&display=swap">
<style>
/* Americanflat design tokens — Brand Guidelines v5 (Feb 2025).
   Glacial Indifference is not on a CSP-permitted host, so DM Sans (the
   documented web fallback) is loaded from Google Fonts instead. */
:root {
  --af-black:#0F0F0F; --af-white:#FFFFFF;
  --af-grey-4:#1A1A1A; --af-grey-3:#666666; --af-grey-2:#B3B3B3; --af-grey-1:#E6E6E6;
  --af-red:#CE0E2D; --af-blue:#003595;

  --bg:var(--af-white);
  --surface:var(--af-white);
  --surface-sunk:#F7F7F6;
  --text:var(--af-black);
  --text-muted:var(--af-grey-3);
  --border:var(--af-grey-1);
  --border-bold:var(--af-grey-2);
  --alert:var(--af-red);
  --link:var(--af-blue);
  --field-empty:#F7F7F6;
  --shadow:0 1px 2px rgba(15,15,15,.04);

  --font:'DM Sans','Glacial Indifference','Inter',system-ui,sans-serif;
  --mono:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace;

  --s1:.25rem; --s2:.5rem; --s3:1rem; --s4:1.5rem; --s5:2rem; --s6:3rem;
  --r:4px; --r-lg:8px;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:var(--af-grey-4);
    --surface:#232323;
    --surface-sunk:#1C1C1C;
    --text:#F2F2F1;
    --text-muted:#9A9A9A;
    --border:#333333;
    --border-bold:#4A4A4A;
    --alert:#F2647C;
    --link:#8FAEE8;
    --field-empty:#1C1C1C;
    --shadow:none;
  }
}
:root[data-theme="dark"] {
  --bg:var(--af-grey-4);
  --surface:#232323;
  --surface-sunk:#1C1C1C;
  --text:#F2F2F1;
  --text-muted:#9A9A9A;
  --border:#333333;
  --border-bold:#4A4A4A;
  --alert:#F2647C;
  --link:#8FAEE8;
  --field-empty:#1C1C1C;
  --shadow:none;
}

*,*::before,*::after { box-sizing:border-box; }
/* .block sets display:flex, which outranks the UA [hidden] rule — without this
   a hidden pane still renders. */
[hidden] { display:none !important; }
body {
  margin:0; background:var(--bg); color:var(--text);
  font-family:var(--font); font-size:15px; line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
:focus-visible { outline:2px solid var(--link); outline-offset:2px; }
@media (prefers-reduced-motion:reduce) { *{transition:none!important;animation:none!important;} }

.wrap { max-width:1240px; margin:0 auto; padding:var(--s5) var(--s4) var(--s6); }

header.masthead {
  display:flex; align-items:flex-end; justify-content:space-between;
  gap:var(--s4); flex-wrap:wrap;
  padding-bottom:var(--s3); border-bottom:1px solid var(--border);
}
.brand { display:flex; flex-direction:column; gap:var(--s2); }
.brand svg { height:26px; width:auto; color:var(--text); display:block; }
.masthead h1 {
  margin:0; font-size:1.5rem; font-weight:700; line-height:1.15;
  letter-spacing:-.01em; text-wrap:balance;
}
.masthead p { margin:0; color:var(--text-muted); font-size:.875rem; max-width:52ch; }

.cols { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:var(--s5); margin-top:var(--s5); }
@media (max-width:940px) { .cols { grid-template-columns:minmax(0,1fr); } }

.eyebrow {
  font-size:.6875rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase;
  color:var(--text-muted); margin:0 0 var(--s2);
}
.panel { display:flex; flex-direction:column; gap:var(--s4); }
.block { display:flex; flex-direction:column; gap:var(--s2); }

textarea#paste {
  width:100%; min-height:190px; resize:vertical; padding:var(--s3);
  font-family:var(--mono); font-size:.8125rem; line-height:1.6;
  color:var(--text); background:var(--surface-sunk);
  border:1px solid var(--border-bold); border-radius:var(--r);
}
textarea#paste::placeholder { color:var(--text-muted); }

.cases { display:grid; grid-template-columns:repeat(auto-fit,minmax(148px,1fr)); gap:var(--s2); }
.case {
  text-align:left; cursor:pointer; padding:var(--s2) var(--s3);
  background:var(--surface); color:var(--text);
  border:1px solid var(--border-bold); border-radius:var(--r);
  font-family:inherit; font-size:.8125rem; line-height:1.35;
  transition:border-color 150ms, background 150ms;
}
.case:hover { border-color:var(--text); }
.case[aria-pressed="true"] { background:var(--text); color:var(--bg); border-color:var(--text); }
.case .cn { display:block; font-weight:700; }
.case .cb { display:block; font-size:.75rem; opacity:.7; margin-top:2px; }
.case.suggested::after {
  content:"likely"; float:right; font-size:.625rem; letter-spacing:.08em;
  text-transform:uppercase; color:var(--alert); font-weight:700;
}
.case[aria-pressed="true"].suggested::after { color:var(--bg); }

.fields { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:var(--s2) var(--s3); }
.field { display:flex; flex-direction:column; gap:2px; }
.field label {
  font-size:.6875rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase;
  color:var(--text-muted);
}
.field input, .field select, .field textarea {
  font-family:var(--mono); font-size:.8125rem; padding:6px 8px;
  color:var(--text); background:var(--surface);
  border:1px solid var(--border); border-radius:var(--r); width:100%;
}
.field select { font-family:var(--font); }
.field input:placeholder-shown { background:var(--field-empty); }
.field.need input:placeholder-shown, .field.need select:invalid {
  border-color:var(--alert);
}
.field .hint { font-size:.6875rem; color:var(--text-muted); }
.field.check { flex-direction:row; align-items:center; gap:var(--s2); grid-column:1/-1; }
.field.check label { text-transform:none; letter-spacing:0; font-size:.8125rem; font-weight:400; color:var(--text); order:2; }
.field.check input { width:auto; margin:0; accent-color:var(--text); }

.mail {
  border:1px solid var(--border-bold); border-radius:var(--r-lg);
  background:var(--surface); box-shadow:var(--shadow); overflow:hidden;
}
.mail-head { padding:var(--s3); border-bottom:1px solid var(--border); background:var(--surface-sunk); }
.mail-row { display:grid; grid-template-columns:44px minmax(0,1fr); gap:var(--s2); padding:3px 0; align-items:baseline; }
.mail-row dt {
  font-size:.6875rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase;
  color:var(--text-muted);
}
.mail-row dd { margin:0; font-family:var(--mono); font-size:.75rem; word-break:break-word; }
.mail-row.subject dd { font-family:var(--font); font-size:.9375rem; font-weight:700; }
.mail-body {
  margin:0; padding:var(--s3); font-family:var(--mono); font-size:.8125rem;
  line-height:1.65; white-space:pre-wrap; word-break:break-word; overflow-x:auto;
}
.mail.incomplete { border-color:var(--alert); }

.tabs { display:flex; gap:2px; padding:2px; border:1px solid var(--border-bold); border-radius:var(--r); width:fit-content; }
.tabs button {
  font-family:inherit; font-size:.75rem; font-weight:700; cursor:pointer;
  padding:5px 12px; border:0; border-radius:2px; background:transparent; color:var(--text-muted);
}
.tabs button[aria-selected="true"] { background:var(--text); color:var(--bg); }
.tabs button:disabled { opacity:.4; cursor:not-allowed; }

.csvwrap { border:1px solid var(--border-bold); border-radius:var(--r-lg); background:var(--surface); overflow:hidden; }
.csvwrap .hd {
  padding:var(--s2) var(--s3); border-bottom:1px solid var(--border); background:var(--surface-sunk);
  font-size:.6875rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--text-muted);
  display:flex; justify-content:space-between; gap:var(--s2);
}
.csvtable { overflow-x:auto; }
.csvtable table { border-collapse:collapse; font-family:var(--mono); font-size:.6875rem; white-space:nowrap; }
.csvtable th, .csvtable td { padding:5px 10px; border-bottom:1px solid var(--border); text-align:left; }
.csvtable th { font-weight:700; color:var(--text-muted); background:var(--surface-sunk); position:sticky; top:0; }
.csvtable td { font-variant-numeric:tabular-nums; }
.csvtable tr:last-child td { border-bottom:0; }

.bar { display:flex; gap:var(--s2); flex-wrap:wrap; align-items:center; }
button.act {
  font-family:inherit; font-size:.8125rem; font-weight:700; cursor:pointer;
  padding:8px 14px; border-radius:var(--r); border:1px solid var(--text);
  background:var(--text); color:var(--bg);
  transition:opacity 150ms;
}
button.act.ghost { background:transparent; color:var(--text); }
button.act:hover { opacity:.82; }
button.act:disabled { opacity:.4; cursor:not-allowed; }

.flag {
  display:flex; gap:var(--s2); padding:var(--s2) var(--s3);
  border-left:3px solid var(--alert); background:var(--surface-sunk);
  font-size:.8125rem; border-radius:0 var(--r) var(--r) 0;
}
.flag.quiet { border-left-color:var(--border-bold); color:var(--text-muted); }
.flag ul { margin:0; padding-left:1.1em; }

details.handoff summary {
  cursor:pointer; font-size:.8125rem; font-weight:700; color:var(--link);
}
details.handoff pre {
  margin:var(--s2) 0 0; padding:var(--s3); background:var(--surface-sunk);
  border:1px solid var(--border); border-radius:var(--r);
  font-family:var(--mono); font-size:.75rem; line-height:1.6;
  white-space:pre-wrap; overflow-x:auto;
}

footer.foot {
  margin-top:var(--s6); padding-top:var(--s3); border-top:1px solid var(--border);
  font-size:.75rem; color:var(--text-muted);
  display:flex; justify-content:space-between; gap:var(--s3); flex-wrap:wrap;
}
.aside {
  margin:0; font-size:.75rem; line-height:1.55; color:var(--text-muted);
  padding-left:var(--s3); border-left:1px solid var(--border-bold);
}
.aside strong { color:var(--text); font-weight:700; }
.sr { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
</style>

<div class="wrap">
  <header class="masthead">
    <div class="brand">
      <svg viewBox="0 0 480 80" role="img" aria-label="Americanflat">
        <text x="0" y="58" style="font-family:var(--font);font-weight:700;font-size:64px;letter-spacing:.04em;fill:currentColor">americanflat</text>
      </svg>
      <h1>Returns Desk</h1>
    </div>
    <p>Paste what the customer sent, pick the case, and get either the warehouse
       email or a ShipStation CSV that places the replacement.
       Nothing you paste leaves this page.</p>
  </header>

  <div class="cols">
    <section class="panel" aria-label="Case intake">
      <div class="block">
        <p class="eyebrow">1 &middot; Paste the customer details</p>
        <textarea id="paste" spellcheck="false" placeholder="Paste the Zendesk ticket, the forwarded email, or the order details.

Example:
Customer Sarah Whitfield, Shopify order #22397, says she is missing
MW0808WH44 x 1 and MW1114WH57 x 2. Tracking 525499496652."></textarea>
        <div id="readout" class="flag quiet"><span>Waiting for a paste.</span></div>
        <p class="aside">Working from <strong>screenshots</strong> of the Shopify order and the
          Zendesk ticket? This page can only read text. Drag the images into Claude and ask for
          the returns portal skill — it reads them directly, so nothing gets retyped.</p>
      </div>

      <div class="block">
        <p class="eyebrow">2 &middot; What kind of case is this?</p>
        <div class="cases" id="cases" role="group" aria-label="Case type"></div>
      </div>

      <div class="block">
        <p class="eyebrow">3 &middot; Check the fields</p>
        <div class="fields" id="fields"></div>
      </div>
    </section>

    <section class="panel" aria-label="Generated warehouse email">
      <div class="block">
        <div class="tabs" id="tabs" role="tablist" aria-label="Output">
          <button type="button" id="tab-email" role="tab" aria-selected="true">Warehouse email</button>
          <button type="button" id="tab-csv" role="tab" aria-selected="false">ShipStation CSV</button>
        </div>
      </div>

      <div class="block" id="pane-email">
        <p class="eyebrow">The warehouse email</p>
        <div class="mail" id="mail">
          <div class="mail-head">
            <dl style="margin:0">
              <div class="mail-row"><dt>To</dt><dd id="m-to">&mdash;</dd></div>
              <div class="mail-row"><dt>Cc</dt><dd id="m-cc">&mdash;</dd></div>
              <div class="mail-row subject"><dt>Subj</dt><dd id="m-subject">&mdash;</dd></div>
            </dl>
          </div>
          <pre class="mail-body" id="m-body">Pick a case type to build the email.</pre>
        </div>
      </div>

      <div class="block" id="pane-csv" hidden>
        <p class="eyebrow">ShipStation order import</p>
        <div class="csvwrap">
          <div class="hd"><span id="csv-title">Replacement order</span><span id="csv-rows"></span></div>
          <div class="csvtable" id="csv-preview"></div>
        </div>
        <p class="aside" id="csv-note"></p>
      </div>

      <div id="gaps"></div>

      <div class="bar">
        <button class="act" id="copy-all" type="button">Copy email</button>
        <button class="act ghost" id="copy-rcpt" type="button">Copy recipients</button>
        <button class="act" id="save-csv" type="button" hidden>Save CSV</button>
        <button class="act ghost" id="copy-csv" type="button" hidden>Copy CSV</button>
        <button class="act ghost" id="reset" type="button">Clear</button>
        <span id="status" role="status" aria-live="polite" style="font-size:.8125rem;color:var(--text-muted)"></span>
      </div>

      <details class="handoff">
        <summary>Or hand it to Claude to draft in Gmail</summary>
        <pre id="claude-prompt">Fill the fields first.</pre>
        <div class="bar" style="margin-top:.5rem">
          <button class="act ghost" id="copy-prompt" type="button">Copy prompt</button>
        </div>
      </details>
    </section>
  </div>

  <footer class="foot">
    <span>Contacts verified <strong id="verified"></strong>. Update <code>references/routing.json</code> and re-run <code>build_portal.py</code> when a warehouse contact changes.</span>
    <span>Replacement orders are the original number + <strong>RS</strong>.</span>
  </footer>
</div>

<script>
const ROUTING = __ROUTING_JSON__;
const CSVCFG = __CSV_CONFIG_JSON__;

/* Cases that create a shipment. Everything else is a question, which a CSV
   cannot ask, so those stay as warehouse emails. */
const CSV_CASES = new Set(['reship', 'damaged']);

/* ---------- parsing -------------------------------------------------- */
/* Everything runs locally. Order of the checks matters: tracking numbers and
   AF style codes both look like alphanumeric blobs, so tracking is claimed
   first and its matches are excluded from the SKU sweep. */

const NOT_A_SKU = new Set(['SHOPIFY','AMAZON','WALMART','TARGET','MICHAELS','MACYS','WAYFAIR',
  'FEDEX','USPS','STAMPS','TRACKING','ORDER','CUSTOMER','REPLACEMENT','MISSING','DAMAGED',
  'RETURN','PLEASE','THANKS','REGARDS','SUBJECT','WAREHOUSE','GROUND','DELIVERED','PACKAGE']);

function carrierOf(num) {
  if (/^1Z[0-9A-Z]{16}$/i.test(num)) return 'UPS';
  if (/^JJD\d{15,22}$/i.test(num)) return 'DHL';
  if (/^9\d{19,21}$/.test(num)) return 'USPS';
  if (/^\d{12}$|^\d{15}$/.test(num)) return 'FedEx';
  return '';
}

/* A 12-13 digit code is ambiguous: it is a FedEx number or an EAN. When the
   surrounding words call it an item, believe them — NL returns quote EANs. */
function looksLikeItemCode(t, index) {
  const before = t.slice(Math.max(0, index - 30), index).toLowerCase();
  return /(item|ean|upc|sku|barcode|style|pcs of|pieces of|units of)\D{0,12}$/.test(before);
}

function findTracking(t) {
  const labelled = t.match(/track(?:ing)?\s*(?:#|no\.?|number)?\s*[:#]?\s*([A-Z0-9]{10,25})\b/i);
  if (labelled) {
    const num = labelled[1].toUpperCase();
    const carrier = carrierOf(num);
    if (carrier) return { tracking: num, carrier };
  }
  const pats = [
    /\b1Z[0-9A-Z]{16}\b/i,
    /\bJJD\d{15,22}\b/i,
    /\b9[0-9]{19,21}\b/,
    /\b\d{15}\b/,
    /\b\d{12}\b/,
  ];
  for (const re of pats) {
    const m = re.exec(t);
    if (!m) continue;
    if (/^\d{12,13}$/.test(m[0]) && looksLikeItemCode(t, m.index)) continue;
    return { tracking: m[0].toUpperCase(), carrier: carrierOf(m[0].toUpperCase()) };
  }
  return { tracking: '', carrier: '' };
}

function findOrders(t) {
  const out = { order: '', rs: '' };
  const rs = t.match(/\b(\d{3,6})\s*RS\b/i);
  if (rs) { out.rs = rs[1] + 'RS'; out.order = rs[1]; }

  const prefixed = t.match(/\bAM[ES]\s*\*\s*([A-Z0-9-]+)/i);
  if (prefixed && !out.order) out.order = prefixed[1].toUpperCase();

  if (!out.order) {
    const labelled = t.match(/(?:order|po)\s*(?:#|no\.?|number)?\s*#?\s*(\d{4,6})\b/i);
    if (labelled) out.order = labelled[1];
  }
  if (!out.order) {
    const hashed = t.match(/#\s*(\d{4,6})\b/);
    if (hashed) out.order = hashed[1];
  }
  if (!out.order) {
    const macys = t.match(/\b(\d{10}-[A-Z])\b/);
    if (macys) out.order = macys[1];
  }
  return out;
}

function findSkus(t, exclude) {
  const found = [];
  const seen = new Set();
  const push = (code, qty) => {
    const c = code.toUpperCase();
    if (seen.has(c) || exclude.has(c) || NOT_A_SKU.has(c)) return;
    if (!/[0-9]/.test(c) && !c.includes('-')) return;  // needs a digit or a hyphen
    if (/^\d+$/.test(c) && c.length !== 12 && c.length !== 13) return;  // digits only = EAN or noise
    seen.add(c);
    found.push({ sku: c, qty: qty || '' });
  };

  // Strongest signal: "MW0808WH44 x 2" — the shape the ops emails already use.
  const withQty = /\b([A-Z][A-Z0-9]{3,}(?:-[A-Z0-9]+)*)\s*(?:x|×)\s*(\d{1,3})\b/gi;
  let m;
  while ((m = withQty.exec(t)) !== null) push(m[1], m[2]);

  // ...and the other way round: "8 x MW1114WH57".
  const qtyFirst = /\b(\d{1,3})\s*(?:x|×)\s*([A-Z][A-Z0-9]{3,}(?:-[A-Z0-9]+)*)\b/gi;
  while ((m = qtyFirst.exec(t)) !== null) push(m[2], m[1]);

  // Bare style codes: letters then digits, or hyphenated part numbers.
  const bare = /\b(?:[A-Z]{2,4}\d{3,6}[A-Z0-9]{0,6}|[A-Z]{2,4}(?:-[A-Z0-9]{2,6}){1,3})\b/g;
  while ((m = bare.exec(t)) !== null) push(m[0], '');

  // EANs, which NL needs to identify a return.
  const ean = /\b\d{12,13}\b/g;
  while ((m = ean.exec(t)) !== null) push(m[0], '');

  return found;
}

function findMarketplace(t) {
  const map = [
    [/\bshopify\b/i, 'Shopify'], [/amazon\s*(vc|vendor)/i, 'Amazon VC'],
    [/amazon\s*(df|direct)/i, 'Amazon DF'], [/\bamazon\b/i, 'Amazon'],
    [/walmart/i, 'Walmart 1P'], [/\btarget\b/i, 'Target'],
    [/michaels/i, 'Michaels'], [/macy'?s/i, "Macy's"],
    [/wayfair/i, 'Wayfair'], [/\bfaire\b/i, 'Faire'], [/kohl'?s/i, "Kohl's"],
  ];
  for (const [re, name] of map) if (re.test(t)) return name;
  return '';
}

function findName(t) {
  const labelled = t.match(/(?:customer|client|buyer|ship\s*to|name)\s*[:\-]\s*([A-Z][a-z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,2})/);
  if (labelled) return labelled[1].trim();
  const inline = t.match(/\bcustomer\s+([A-Z][a-z'\-]+\s+[A-Z][a-zA-Z'\-]+)/);
  if (inline) return inline[1].trim();
  const signed = t.match(/(?:^|\n)\s*(?:-{1,2}|—)\s*([A-Z][a-z'\-]+\s+[A-Z][a-zA-Z'\-]+)\s*$/m);
  if (signed) return signed[1].trim();
  return '';
}

function findWarehouse(t, order) {
  if (/AME\s*\*/i.test(t) || /^AME-/i.test(order)) return 'nj';
  if (/AMS\s*\*/i.test(t) || /^AMS-/i.test(order)) return 'sc';
  if (/fontana/i.test(t)) return 'fontana';
  if (/\b(new jersey|\bnj\b|edison)\b/i.test(t)) return 'nj';
  if (/(south carolina|hardeeville|\bsc\b)/i.test(t)) return 'sc';
  if (/(canada|brampton|ontario)/i.test(t)) return 'ca';
  if (/(netherlands|moerdijk|schiphol|benelux)/i.test(t)) return 'nl';
  return '';
}

function suggestCase(t) {
  if (/\b(cancel|no longer needed|found it|turned up|arrived after all)\b/i.test(t)) return 'cancel';
  if (/\b(damaged|broken|shattered|cracked|smashed|dented)\b/i.test(t)) return 'damaged';
  if (/(partially fulfilled|still unfulfilled|unfulfilled \(|balance of the order|rest was never shipped|never shipped the rest)/i.test(t)) return 'balance';
  if (/\b(missing|short|incomplete|only received|not received in full|came up short)\b/i.test(t)) return 'missing';
  if (/(received a return|return received|returned to the warehouse|came back to the warehouse|sent it back|we have received a return)/i.test(t)) return 'return';
  if (/(cannot track|can'?t track|unable to track|tracking[\s\S]{0,40}(invalid|not valid|wrong|incorrect|never scanned|no scans|not moving|no updates|stuck)|(invalid|bad|wrong|no)[\s\S]{0,20}tracking)/i.test(t)) return 'tracking';
  if (/\b(reship|replacement|resend|send another)\b/i.test(t)) return 'reship';
  return '';
}

function findPII(t) {
  const pii = [];
  const email = t.match(/[\w.+-]+@[\w-]+\.[\w.]+/);
  if (email && !/americanflat\.com|yusen-logistics|tpservices/i.test(email[0])) pii.push('an email address');
  if (/\b(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b/.test(t)) pii.push('a phone number');
  return pii;
}

function parse(text) {
  const t = text || '';
  const { tracking, carrier } = findTracking(t);
  const { order, rs } = findOrders(t);
  const exclude = new Set([tracking.toUpperCase(), order.toUpperCase(), rs.toUpperCase()].filter(Boolean));
  return {
    order, rs, tracking, carrier,
    skus: findSkus(t, exclude),
    marketplace: findMarketplace(t),
    customer: findName(t),
    warehouse: findWarehouse(t, order),
    suggested: suggestCase(t),
    hasReplacement: !!rs || /replacement[\s\S]{0,30}(already )?(placed|created|opened|raised)/i.test(t),
    pii: findPII(t),
  };
}

/* ---------- state ---------------------------------------------------- */

const state = {
  caseType: '', warehouse: '', order: '', rs: '', tracking: '', carrier: '',
  marketplace: '', customer: '', skus: '', deadline: 'EOD today',
  packMode: 'carton', disposition: 'restock', sender: '', title: 'Customer Experience',
  hasReplacement: false, outputMode: 'email',
  shipName: '', shipCompany: '', address1: '', address2: '',
  city: '', stateRegion: '', postal: '', country: 'US', phone: '',
  reason: '', ticket: '',
  touched: new Set(),
};

try {
  const saved = JSON.parse(localStorage.getItem('af-returns-sender') || '{}');
  if (saved.sender) state.sender = saved.sender;
  if (saved.title) state.title = saved.title;
} catch (e) { /* private window or blocked storage — defaults are fine */ }

function saveSender() {
  try {
    localStorage.setItem('af-returns-sender', JSON.stringify({ sender: state.sender, title: state.title }));
  } catch (e) { /* nothing to do; the field still works this session */ }
}

/* ---------- templates ------------------------------------------------ */
/* Mirrors references/templates.md. Change both together. */

function skuLines(raw, bullet) {
  const lines = (raw || '').split(/\n|,(?![^(]*\))/).map(s => s.trim()).filter(Boolean);
  if (!lines.length) return bullet + '(SKU and quantity needed)';
  return lines.map(s => bullet + s).join('\n');
}

function buildBody(wh) {
  const greet = wh ? wh.greeting : 'team';
  const mk = state.marketplace ? state.marketplace + ' ' : '';
  const ord = state.order || '(order #)';
  const rs = state.rs || '(RS order #)';
  const sign = '\n\nThank you,\n' + (state.sender || '(your name)') +
               (state.title ? '\n' + state.title : '') + '\namericanflat.com';
  const signWarm = '\n\nThanks in advance!\n\nBest,\n' + (state.sender || '(your name)') +
               (state.title ? '\n' + state.title : '') + '\namericanflat.com';

  switch (state.caseType) {
    case 'reship': {
      const pick = state.packMode === 'units'
        ? 'This replacement is a loose-unit pick — please pick only the individual units\n' +
          'listed below. It does not need to ship as a full master carton.\n\n' +
          skuLines(state.skus, '  - ') + '\n\n'
        : 'This replacement must ship as one full master carton. Please do not piece-pick\n' +
          'individual units or split the shipment.\n\n';
      return 'Hi ' + greet + ',\n\n' +
        'Please prioritize replacement order #' + rs + ' for shipment by ' + (state.deadline || 'EOD today') + '.\n\n' +
        pick +
        'We are currently dealing with an unhappy customer on the original order, so it’s\n' +
        'important that this replacement is processed correctly and leaves the warehouse today.\n\n' +
        'Once shipped, please send me the tracking number or ensure tracking is properly\n' +
        'placed on the order so my team can retrieve it.' + signWarm;
    }

    case 'missing':
      return 'Hi ' + greet + ',\n\n' +
        'Could you please review ' + mk + 'Order #' + ord + '?\n' +
        'The customer is reporting that the order was not received in full.\n\n' +
        'They specifically state they are missing:\n\n' +
        skuLines(state.skus, '  - ') + '\n\n' +
        'Could you please confirm:\n\n' +
        '  - What quantities physically shipped for each SKU?\n' +
        '  - Whether any additional cartons/packages were shipped separately\n' +
        '  - Any additional tracking numbers associated with this order' +
        (state.hasReplacement
          ? '\n\nA replacement has already been placed for the customer, but we need to\n' +
            'understand what happened with the original shipment and confirm whether\n' +
            'this was a warehouse short-ship.'
          : '') +
        sign;

    case 'balance':
      return 'Hi ' + greet + ',\n\n' +
        (mk ? mk : '') + 'Order #' + ord + ' shows part of the order still unfulfilled,\n' +
        'and the customer has only received what shipped so far.\n\n' +
        'Still owed:\n\n' +
        skuLines(state.skus, '  - ') + '\n\n' +
        'Could you please confirm the balance is allocated and when it will ship?' +
        (state.deadline && state.touched.has('deadline')
          ? '\nThe customer needs it by ' + state.deadline + ', so if there is a stock issue\n' +
            'on this style please tell me today and we will source it from another site.'
          : '') +
        sign;

    case 'tracking':
      return 'Hi ' + greet + ',\n\n' +
        'Could you please review ' + mk + 'Order #' + ord + ' and verify the tracking\n' +
        'number entered for the shipment?\n\n' +
        'Tracking: ' + (state.tracking || '(tracking #)') + ' is coming back as invalid\n' +
        'in ' + (state.carrier || 'the carrier system') + ', and the customer cannot track their package.\n\n' +
        'Could you please confirm the correct tracking number and that the shipment\n' +
        'physically left the building?' + sign;

    case 'cancel':
      return 'Hi team,\n\n' +
        'Please cancel PO # ' + rs + ' -- this is a replacement order that is no longer\n' +
        'needed, thank you!\n\nBest,\n' + (state.sender || '(your name)') +
        (state.title ? '\n' + state.title : '') + '\namericanflat.com';

    case 'return': {
      const disp = {
        restock: 'restock this into sellable inventory',
        discard: 'discard for damage -- I have logged it from my side',
        hold: 'hold this aside and send photos before we decide',
      }[state.disposition] || 'restock this into sellable inventory';
      return 'Hi ' + greet + ',\n\n' +
        'Thank you for flagging the return received' +
        (state.tracking ? ' under tracking ' + state.tracking : '') + '.\n\n' +
        'Item:\n' + skuLines(state.skus, '  - ') + '\n\n' +
        'Please ' + disp + '.\n\n' +
        'If the item number doesn’t resolve in your system, the codes above are the AF\n' +
        'style code and the EAN.' + sign;
    }

    case 'damaged':
      return 'Hi ' + greet + ',\n\n' +
        'The customer on ' + mk + 'Order #' + ord + ' received their order damaged.\n\n' +
        'Item:\n' + skuLines(state.skus, '  - ') + '\n' +
        (state.tracking ? 'Shipped under tracking: ' + state.tracking + '\n' : '') + '\n' +
        'A replacement has been placed under #' + rs + ' — please prioritize it for\n' +
        'shipment by ' + (state.deadline || 'EOD today') + ' and send tracking back on this thread.\n\n' +
        'Separately, could you please check:\n\n' +
        '  - How this order was packed (carton size, void fill, corner protection)\n' +
        '  - Whether other units of the same style in that location show damage\n\n' +
        'We want to know whether this is a packing issue or an inbound one.' + sign;

    default:
      return 'Pick a case type to build the email.';
  }
}

function buildSubject(wh) {
  if (!wh || !state.caseType) return '—';
  const p = wh.subject_prefix;
  const mk = state.marketplace ? state.marketplace + ' ' : '';
  const ord = state.order || '(order #)';
  const rs = state.rs || '(RS order #)';
  switch (state.caseType) {
    case 'reship':   return p + ' Request to Prioritize Replacement order # ' + rs;
    case 'missing':  return p + ' ' + mk + 'Order #' + ord + ' – Missing Units Verification';
    case 'balance':  return p + ' ' + mk + 'Order #' + ord + ' – Unshipped Balance';
    case 'tracking': return p + ' ' + mk + 'Order #' + ord + ' – Tracking Verification';
    case 'cancel':   return p + ' Request to Cancel ' + rs;
    case 'return':   return p + ' Return ' + (state.tracking || ord) + ' – Disposition';
    case 'damaged':  return p + ' ' + mk + 'Order #' + ord + ' – Damaged on Arrival';
    default: return '—';
  }
}

function recipients(wh) {
  if (!wh) return { to: [], cc: [] };
  const spec = ROUTING.cases[state.caseType];
  const cc = wh.cc.slice();
  if (spec && spec.inventory_cc) {
    for (const a of (wh.cc_inventory || [])) if (!cc.includes(a)) cc.push(a);
  }
  return { to: wh.to.slice(), cc };
}

function missingFields(wh) {
  const gaps = [];
  if (!state.caseType) return ['Pick a case type.'];
  if (!wh) gaps.push('Pick a warehouse — this decides who gets the email.');
  const spec = ROUTING.cases[state.caseType];
  const labels = { rs_order:'the RS order number', order:'the order number',
                   tracking:'the tracking number', skus:'the SKU and quantity',
                   deadline:'a ship deadline' };
  const needs = new Set(spec ? spec.needs : []);
  if (state.caseType === 'reship' && state.packMode === 'units') needs.add('skus');
  for (const need of needs) {
    const val = { rs_order:state.rs, order:state.order, tracking:state.tracking,
                  skus:state.skus, deadline:state.deadline }[need];
    if (!val || !String(val).trim()) gaps.push('Add ' + labels[need] + '.');
  }
  if (needs.has('skus') && String(state.skus || '').trim()) {
    const noQty = String(state.skus).split('\n').map(l => l.trim()).filter(Boolean)
      .filter(l => !/(?:x|×)\s*\d/i.test(l));
    if (noQty.length) gaps.push('Add a quantity to each SKU — "' + noQty[0] + '" has no number.');
  }
  if (!state.sender) gaps.push('Add your name so the warehouse knows who to reply to.');
  // Backstop: any unresolved placeholder means the email is not sendable, even
  // if the per-case checks above happened not to cover that field.
  const draft = buildSubject(wh) + ' ' + buildBody(wh);
  if (/\((?:order #|RS order #|tracking #|SKU and quantity needed|your name)\)/.test(draft)
      && !gaps.some(g => /Add /.test(g))) {
    gaps.push('The draft still has a blank in it — fill the fields above.');
  }
  return gaps;
}

/* ---------- ShipStation CSV ------------------------------------------ */
/* Mirrors scripts/build_reship_csv.py. Both read references/shipstation-csv.json,
   so a corrected header only has to be fixed in one place. */

function csvEscape(v) {
  const s = v === undefined || v === null ? '' : String(v);
  return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function today() {
  const d = new Date();
  const p = n => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
}

function skuPairs(raw) {
  return (raw || '').split('\n').map(l => l.trim()).filter(Boolean).map(line => {
    const m = line.match(/^(.+?)\s*(?:x|×)\s*(\d+)$/i);
    return m ? { sku: m[1].trim().toUpperCase(), qty: m[2] }
             : { sku: line.toUpperCase(), qty: '' };
  });
}

function csvNotes() {
  const bits = ['Replacement for #' + (state.order || '(order #)')];
  if (state.reason) bits.push(state.reason);
  if (state.ticket) bits.push('Zendesk ' + state.ticket);
  bits.push(state.packMode === 'units'
    ? 'Loose-unit pick - individual units only'
    : 'PICK AS SEALED MASTER CARTON - do not split');
  bits.push('No charge - replacement, do not invoice');
  return bits.join(' | ');
}

function csvRows() {
  const d = CSVCFG.defaults || {};
  const shared = {
    order_number: state.rs || ((state.order || '') && state.order + 'RS'),
    order_date: today(),
    order_status: d.order_status || 'awaiting_shipment',
    shipping_service: d.shipping_service || '',
    ship_name: state.shipName,
    ship_company: state.shipCompany,
    address1: state.address1,
    address2: state.address2,
    city: state.city,
    state: state.stateRegion,
    postal: state.postal,
    country: state.country || d.country || 'US',
    phone: state.phone,
    unit_price: d.unit_price || '0.00',
    notes: csvNotes(),
  };
  return skuPairs(state.skus).map(it =>
    Object.assign({}, shared, { sku: it.sku, item_name: '', qty: it.qty }));
}

function csvText(rows) {
  const cols = CSVCFG.columns;
  const lines = [cols.map(c => csvEscape(c.header)).join(',')];
  for (const r of rows) lines.push(cols.map(c => csvEscape(r[c.field])).join(','));
  return lines.join('\r\n') + '\r\n';
}

function csvFilename() {
  const n = (state.rs || state.order || 'reship').replace(/[^A-Za-z0-9-]/g, '');
  return 'shipstation-' + (n || 'reship') + '.csv';
}

function renderCsv(rows) {
  const cols = CSVCFG.columns;
  const host = $('csv-preview');
  const head = '<tr>' + cols.map(c => '<th>' + c.header + '</th>').join('') + '</tr>';
  const body = rows.map(r => '<tr>' + cols.map(c => {
    const v = r[c.field] === undefined || r[c.field] === null ? '' : String(r[c.field]);
    const cell = v.length > 42 ? v.slice(0, 42) + '…' : v;
    return '<td>' + cell.replace(/&/g, '&amp;').replace(/</g, '&lt;') + '</td>';
  }).join('') + '</tr>').join('');
  host.innerHTML = '<table>' + head + (body || '') + '</table>';
  $('csv-rows').textContent = rows.length + (rows.length === 1 ? ' line item' : ' line items');
  $('csv-title').textContent = 'Order ' + (rows[0] ? rows[0].order_number : '—');

  const notes = [];
  if (!CSVCFG.verified_against_real_import) {
    notes.push('Headers have not been checked against a real ShipStation import yet — do one test import first.');
  }
  notes.push('The picker sees the carton-or-loose instruction in Internal Notes; ShipStation has no field for it.');
  if (rows.some(r => !r.item_name)) {
    notes.push('Item Name is blank — this page has no catalogue access and ShipStation matches on SKU. ' +
      'Run scripts/build_reship_csv.py if you need the names filled from BigQuery.');
  }
  $('csv-note').innerHTML = notes.join(' ');
}

function csvGaps() {
  const gaps = [];
  if (!state.rs && !state.order) gaps.push('Add the order number so the RS number can be built.');
  const pairs = skuPairs(state.skus);
  if (!pairs.length) gaps.push('Add the SKUs and quantities being replaced.');
  else if (pairs.some(p => !p.qty)) gaps.push('Every SKU needs a quantity.');
  const addr = [
    [state.shipName, 'the recipient name'],
    [state.address1, 'address line 1'],
    [state.city, 'the city'],
    [state.stateRegion, 'the state'],
    [state.postal, 'the postal code'],
  ].filter(([v]) => !String(v || '').trim()).map(([, label]) => label);
  if (addr.length) {
    gaps.push('Add ' + addr.join(', ') + ' — copy it from the Shopify order screen, it is not in BigQuery.');
  }
  return gaps;
}

/* ---------- rendering ------------------------------------------------ */

const $ = id => document.getElementById(id);

function renderCases(suggested) {
  const host = $('cases');
  host.innerHTML = '';
  for (const [key, c] of Object.entries(ROUTING.cases)) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'case' + (key === suggested ? ' suggested' : '');
    b.setAttribute('aria-pressed', String(state.caseType === key));
    b.innerHTML = '<span class="cn"></span><span class="cb"></span>';
    b.querySelector('.cn').textContent = c.label;
    b.querySelector('.cb').textContent = c.blurb;
    b.addEventListener('click', () => { state.caseType = key; render(); });
    host.appendChild(b);
  }
}

function field(key, label, opts) {
  opts = opts || {};
  const wrap = document.createElement('div');
  wrap.className = 'field' + (opts.need ? ' need' : '') + (opts.checkbox ? ' check' : '');
  const id = 'f-' + key;
  const lab = document.createElement('label');
  lab.setAttribute('for', id);
  lab.textContent = label;
  wrap.appendChild(lab);

  let el;
  if (opts.options) {
    el = document.createElement('select');
    for (const [v, t] of opts.options) {
      const o = document.createElement('option');
      o.value = v; o.textContent = t;
      if (String(state[key]) === v) o.selected = true;
      el.appendChild(o);
    }
  } else if (opts.multiline) {
    el = document.createElement('textarea');
    el.rows = 3;
    el.value = state[key] || '';
    el.placeholder = opts.placeholder || '';
  } else if (opts.checkbox) {
    el = document.createElement('input');
    el.type = 'checkbox';
    el.checked = !!state[key];
    el.style.width = 'auto';
  } else {
    el = document.createElement('input');
    el.type = 'text';
    el.value = (opts.value !== undefined ? opts.value : state[key]) || '';
    el.placeholder = opts.placeholder || '';
  }
  el.id = id;
  el.addEventListener(opts.checkbox ? 'change' : 'input', e => {
    state[key] = opts.checkbox ? e.target.checked : e.target.value;
    state.touched.add(key);
    if (key === 'sender' || key === 'title') saveSender();
    render(true);
  });
  wrap.appendChild(el);
  if (opts.hint) {
    const h = document.createElement('span');
    h.className = 'hint';
    h.textContent = opts.hint;
    wrap.appendChild(h);
  }
  return wrap;
}

function renderFields() {
  const host = $('fields');
  const active = document.activeElement ? document.activeElement.id : null;
  host.innerHTML = '';
  const spec = ROUTING.cases[state.caseType];
  const needs = new Set(spec ? spec.needs : []);
  if (state.caseType === 'reship' && state.packMode === 'units') needs.add('skus');

  const whOpts = [['', 'Choose…']].concat(
    Object.entries(ROUTING.warehouses).map(([k, w]) => [k, w.label]));
  host.appendChild(field('warehouse', 'Warehouse', { options: whOpts, need: !state.warehouse }));
  host.appendChild(field('order', 'Order #', { placeholder: '22397', need: needs.has('order') }));
  host.appendChild(field('rs', 'Replacement (RS) #', { placeholder: '22397RS', need: needs.has('rs_order'),
    hint: 'Original number + RS' }));
  host.appendChild(field('marketplace', 'Marketplace', { placeholder: 'Shopify' }));
  host.appendChild(field('tracking', 'Tracking', { placeholder: '525499496652', need: needs.has('tracking') }));
  const skuHint = {
    balance: 'The quantity still UNFULFILLED, not the quantity ordered',
    missing: 'The quantity the customer is missing, not the quantity ordered',
  }[state.caseType] || 'One per line';
  host.appendChild(field('skus', 'SKUs & quantity', { multiline: true, placeholder: 'MW0808WH44 x 1\nMW1114WH57 x 2',
    need: needs.has('skus'), hint: skuHint }));

  if (state.caseType === 'reship' || state.caseType === 'damaged' || state.caseType === 'balance') {
    const isBalance = state.caseType === 'balance';
    host.appendChild(field('deadline',
      isBalance ? 'Customer needs by' : 'Ship by',
      {
        placeholder: isBalance ? 'e.g. Saturday 8/29 — optional' : 'EOD today',
        value: isBalance && !state.touched.has('deadline') ? '' : undefined,
        need: needs.has('deadline'),
        hint: isBalance ? 'Only included if you fill it in' : undefined,
      }));
  }
  if (state.caseType === 'reship' || (state.outputMode === 'csv' && CSV_CASES.has(state.caseType))) {
    host.appendChild(field('packMode', 'Pick as', { options: [
      ['carton', 'Full master carton — do not split'],
      ['units', 'Individual units — loose pick'],
    ], hint: state.packMode === 'units' ? 'Units are listed in the email' : 'Sets shipped as one sealed case' }));
  }
  if (state.caseType === 'missing') {
    host.appendChild(field('hasReplacement', 'Replacement already placed', { checkbox: true }));
  }
  if (state.caseType === 'return') {
    host.appendChild(field('disposition', 'Disposition', { options: [
      ['restock', 'Restock as sellable'],
      ['discard', 'Discard — damaged'],
      ['hold', 'Hold, send photos first'],
    ]}));
  }
  if (state.outputMode === 'csv' && CSV_CASES.has(state.caseType)) {
    // The street address exists on the Shopify screen and nowhere in BigQuery.
    host.appendChild(field('shipName', 'Recipient', { placeholder: 'Sarah Whitfield', need: !state.shipName }));
    host.appendChild(field('address1', 'Address 1', { placeholder: '1842 Larkin St', need: !state.address1 }));
    host.appendChild(field('address2', 'Address 2', { placeholder: 'Apt 4' }));
    host.appendChild(field('city', 'City', { placeholder: 'San Francisco', need: !state.city }));
    host.appendChild(field('stateRegion', 'State', { placeholder: 'CA', need: !state.stateRegion }));
    host.appendChild(field('postal', 'Postal code', { placeholder: '94109', need: !state.postal }));
    host.appendChild(field('country', 'Country', { placeholder: 'US' }));
    host.appendChild(field('phone', 'Phone', { placeholder: 'optional' }));
    host.appendChild(field('reason', 'Reason', { placeholder: 'damaged on arrival', hint: 'Goes in Internal Notes' }));
    host.appendChild(field('ticket', 'Zendesk ticket', { placeholder: '#48213', hint: 'Internal notes only' }));
  } else {
    host.appendChild(field('sender', 'Your name', { placeholder: 'Jane Doe', need: !state.sender }));
    host.appendChild(field('title', 'Your title', { placeholder: 'Customer Experience' }));
  }

  if (active) { const el = $(active); if (el) { el.focus();
    if (el.setSelectionRange && el.type === 'text') { const n = el.value.length; el.setSelectionRange(n, n); } } }
}

function renderReadout(p) {
  const host = $('readout');
  const bits = [];
  if (p.order) bits.push('order ' + p.order);
  if (p.rs) bits.push('replacement ' + p.rs);
  if (p.customer) bits.push(p.customer);
  if (p.marketplace) bits.push(p.marketplace);
  if (p.skus.length) bits.push(p.skus.length + ' SKU' + (p.skus.length > 1 ? 's' : ''));
  if (p.tracking) bits.push(p.carrier + ' ' + p.tracking);

  host.className = 'flag quiet';
  if (p.pii.length) {
    host.className = 'flag';
    host.innerHTML = '<span><strong>Found ' + p.pii.join(' and ') +
      '.</strong> Left out of the warehouse email on purpose — the 3PL doesn’t need it.' +
      (bits.length ? ' Also read: ' + bits.join(' · ') + '.' : '') + '</span>';
  } else if (bits.length) {
    host.innerHTML = '<span>Read: ' + bits.join(' · ') + '. Correct anything below.</span>';
  } else {
    host.innerHTML = '<span>Waiting for a paste.</span>';
  }
}

function renderGaps(gaps) {
  const host = $('gaps');
  if (!gaps.length) { host.innerHTML = ''; return; }
  const items = gaps.map(g => '<li>' + g + '</li>').join('');
  host.innerHTML = '<div class="flag"><div><strong>Before you send</strong><ul>' + items + '</ul></div></div>';
}

function renderPrompt(wh, subject, body, rcpt) {
  if (!state.caseType || !wh) { $('claude-prompt').textContent = 'Fill the fields first.'; return; }
  $('claude-prompt').textContent =
    'Using the cx-returns-portal skill, create a Gmail draft — do not send it.\n\n' +
    'To: ' + rcpt.to.join(', ') + '\n' +
    'Cc: ' + rcpt.cc.join(', ') + '\n' +
    'Subject: ' + subject + '\n\n' + body;
}

function render(skipFields) {
  const p = parse($('paste').value);

  // Parsed values fill a field until someone edits it by hand.
  const adopt = (key, val) => { if (val && !state.touched.has(key)) state[key] = val; };
  adopt('order', p.order);
  adopt('rs', p.rs);
  adopt('tracking', p.tracking);
  adopt('carrier', p.carrier);
  adopt('marketplace', p.marketplace);
  adopt('customer', p.customer);
  adopt('warehouse', p.warehouse);
  if (p.skus.length && !state.touched.has('skus')) {
    state.skus = p.skus.map(s => s.sku + (s.qty ? ' x ' + s.qty : '')).join('\n');
  }
  if (p.hasReplacement && !state.touched.has('hasReplacement')) state.hasReplacement = true;
  if (!state.caseType && p.suggested) state.caseType = p.suggested;

  const wh = ROUTING.warehouses[state.warehouse] || null;
  const rcpt = recipients(wh);
  const subject = buildSubject(wh);
  const body = buildBody(wh);
  const gaps = missingFields(wh);

  const csvMode = state.outputMode === 'csv' && CSV_CASES.has(state.caseType);
  renderReadout(p);
  renderCases(p.suggested);
  if (!skipFields) renderFields();

  // A CSV creates a shipment; it cannot ask a question, so the investigative
  // cases stay on the email tab.
  const csvAllowed = CSV_CASES.has(state.caseType);
  $('tab-csv').disabled = !csvAllowed;
  $('tab-csv').title = csvAllowed ? '' :
    'A CSV creates a replacement order. This case asks the warehouse a question, so it goes by email.';
  if (!csvAllowed && state.outputMode === 'csv') state.outputMode = 'email';
  $('tab-email').setAttribute('aria-selected', String(!csvMode));
  $('tab-csv').setAttribute('aria-selected', String(csvMode));
  $('pane-email').hidden = csvMode;
  $('pane-csv').hidden = !csvMode;
  $('copy-all').hidden = csvMode;
  $('copy-rcpt').hidden = csvMode;
  $('save-csv').hidden = !csvMode;
  $('copy-csv').hidden = !csvMode;

  $('m-to').textContent = rcpt.to.join(', ') || '—';
  $('m-cc').textContent = rcpt.cc.join(', ') || '—';
  $('m-subject').textContent = subject;
  $('m-body').textContent = body;
  $('mail').classList.toggle('incomplete', gaps.length > 0 && !!state.caseType);
  $('copy-all').disabled = !state.caseType || !wh;
  $('copy-rcpt').disabled = !wh;

  if (csvMode) {
    const rows = csvRows();
    renderCsv(rows);
    window.__csv = { text: csvText(rows), filename: csvFilename(), rows: rows.length };
    const cg = csvGaps();
    renderGaps(cg);
    $('save-csv').disabled = cg.length > 0;
    $('copy-csv').disabled = cg.length > 0;
  } else {
    renderGaps(gaps);
    window.__csv = null;
  }
  renderPrompt(wh, subject, body, rcpt);

  window.__mail = { to: rcpt.to.join(', '), cc: rcpt.cc.join(', '), subject, body };
}

/* ---------- actions -------------------------------------------------- */

function flash(msg) {
  const s = $('status');
  s.textContent = msg;
  setTimeout(() => { if (s.textContent === msg) s.textContent = ''; }, 2600);
}

async function copy(text, msg) {
  try {
    await navigator.clipboard.writeText(text);
    flash(msg);
  } catch (e) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); flash(msg); }
    catch (e2) { flash('Couldn’t copy — select the text and copy manually.'); }
    document.body.removeChild(ta);
  }
}

$('paste').addEventListener('input', () => render());
$('copy-all').addEventListener('click', () => {
  const m = window.__mail;
  copy('To: ' + m.to + '\nCc: ' + m.cc + '\nSubject: ' + m.subject + '\n\n' + m.body,
       'Email copied. Paste into Gmail and read it before sending.');
});
$('copy-rcpt').addEventListener('click', () => {
  const m = window.__mail;
  copy(m.to + (m.cc ? ', ' + m.cc : ''), 'Recipients copied.');
});
$('copy-prompt').addEventListener('click', () => copy($('claude-prompt').textContent, 'Prompt copied.'));

$('tab-email').addEventListener('click', () => { state.outputMode = 'email'; render(); });
$('tab-csv').addEventListener('click', () => { state.outputMode = 'csv'; render(); });
$('copy-csv').addEventListener('click', () => {
  if (window.__csv) copy(window.__csv.text, 'CSV copied. Paste into a file and import it.');
});

/* The viewer sandbox makes <a download> inert, so a real save has to go through
   the downloads capability. It may be absent (page opened outside the viewer) and
   .csv may not be enabled, so fall back in two steps before giving up. */
let downloadsNs;
async function getDownloads() {
  if (downloadsNs === undefined) {
    downloadsNs = (window.claude && window.claude.use)
      ? await window.claude.use('downloads').catch(() => null)
      : null;
  }
  return downloadsNs;
}

$('save-csv').addEventListener('click', async () => {
  if (!window.__csv) return;
  const { text, filename } = window.__csv;
  const dl = await getDownloads();
  if (!dl) {
    await copy(text, 'Saving is not available here — CSV copied instead.');
    return;
  }
  flash('Waiting for you to confirm the save…');
  try {
    await dl.save({ filename, data: text });
    flash('Saved ' + filename + '. Import it in ShipStation.');
  } catch (e) {
    const code = e && e.code;
    if (code === 'declined') { flash('Save cancelled.'); return; }
    if (code === 'extension_not_enabled' || code === 'rejected_extension') {
      try {
        const alt = filename.replace(/\.csv$/, '.txt');
        await dl.save({ filename: alt, data: text });
        flash('Saved as ' + alt + ' — rename it to .csv before importing.');
        return;
      } catch (e2) {
        if (e2 && e2.code === 'declined') { flash('Save cancelled.'); return; }
      }
    }
    if (code === 'rate_limited') { flash('Too many save prompts — wait a moment and try again.'); return; }
    await copy(text, 'Could not save the file — CSV copied instead.');
  }
});
$('reset').addEventListener('click', () => {
  $('paste').value = '';
  Object.assign(state, { caseType:'', warehouse:'', order:'', rs:'', tracking:'', carrier:'',
    marketplace:'', customer:'', skus:'', deadline:'EOD today', packMode:'carton',
    disposition:'restock', hasReplacement:false, outputMode:'email',
    shipName:'', shipCompany:'', address1:'', address2:'', city:'', stateRegion:'',
    postal:'', country:'US', phone:'', reason:'', ticket:'' });
  state.touched = new Set();
  render();
  flash('Cleared.');
});

$('verified').textContent = ROUTING.verified;
render();
</script>
"""


def main() -> int:
    routing = json.loads(ROUTING.read_text())
    csv_config = json.loads(CSV_CONFIG.read_text())
    for w in check_drift(routing):
        print(f"  warning: {w}", file=sys.stderr)
    if not csv_config.get("verified_against_real_import"):
        print("  note: ShipStation CSV headers are still unverified "
              "(references/shipstation-csv.md)", file=sys.stderr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = build(routing, csv_config)
    OUT.write_text(html)
    print(f"wrote {OUT.relative_to(SKILL_DIR)} ({len(html):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
