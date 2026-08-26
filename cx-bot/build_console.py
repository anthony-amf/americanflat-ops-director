#!/usr/bin/env python3
"""
Render the CX product console (a single self-contained HTML page) from the
knowledge base, so CX agents can look products up without Claude or BigQuery.

The page carries the same rules as the skill: titles are the spec, sale price is
the real price, UPCs are not unique, and flagged conflicts block a firm answer.
Its search mirrors cx_lookup.py -- title-weighted, catalogue-common words
discounted, and the same confidence gate -- so both routes agree.

Descriptions are deliberately NOT shipped to the page: 56% are boilerplate
shared across hundreds of products and 547 contradict their own title, so
there is nothing an agent should read off them.

Usage:
    python3 cx-bot/build_kb.py && python3 cx-bot/build_console.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE / "product_kb.json"
OUT = HERE / "cx_console.html"


def compact(kb):
    """Slim each product to what the console renders (keeps the page small)."""
    out = []
    for p in kb["products"]:
        out.append({
            "t": p["title"],
            "c": p["category"],
            "s": p.get("size"),
            "k": p.get("color"),
            "n": p.get("pack", 1),
            "f": list((p.get("features") or {}).values()),
            "p": p.get("current_price"),
            "l": p.get("list_price"),
            "i": 1 if p.get("in_stock") else 0,
            "u": p.get("gtin"),
            "m": p.get("sku"),
            "w": p.get("url"),
            "x": [c["message"] for c in (p.get("conflicts") or [])
              if c.get("level") == "block"],
        "xn": [c["message"] for c in (p.get("conflicts") or [])
               if c.get("level") != "block"],
        })
    return out


TEMPLATE = """<title>Americanflat CX Product Desk</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap">
<style>
/* Americanflat design tokens (Brand Guidelines v5). Glacial Indifference is
   not on Google Fonts and the artifact CSP blocks other font hosts, so the
   brand's documented web fallback DM Sans carries the page. */
:root {
  --af-black:#0F0F0F; --af-white:#FFFFFF;
  --af-grey-3:#666666; --af-grey-2:#B3B3B3; --af-grey-1:#E6E6E6;
  --af-red:#CE0E2D; --af-blue:#003595;
  --bg:var(--af-white); --surface:var(--af-white); --surface-2:#FAFAFA;
  --text:var(--af-black); --muted:var(--af-grey-3); --line:var(--af-grey-1);
  --line-bold:var(--af-grey-2); --alert:var(--af-red); --link:var(--af-blue);
  --chip-bg:#F2F2F2; --alert-bg:#FCEDEF; --shadow:0 1px 2px rgba(15,15,15,.06);
  --font:'DM Sans','Glacial Indifference','Inter',system-ui,sans-serif;
}
:root:not([data-theme="light"]) { }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:#0F0F0F; --surface:#161616; --surface-2:#1A1A1A;
    --text:#F2F2F2; --muted:#9A9A9A; --line:#2A2A2A; --line-bold:#3A3A3A;
    --alert:#FF6B7F; --link:#8FA9E8;
    --chip-bg:#232323; --alert-bg:#2A1417; --shadow:none;
  }
}
:root[data-theme="dark"] {
  --bg:#0F0F0F; --surface:#161616; --surface-2:#1A1A1A;
  --text:#F2F2F2; --muted:#9A9A9A; --line:#2A2A2A; --line-bold:#3A3A3A;
  --alert:#FF6B7F; --link:#8FA9E8;
  --chip-bg:#232323; --alert-bg:#2A1417; --shadow:none;
}

* { box-sizing:border-box; }
body {
  margin:0; background:var(--bg); color:var(--text);
  font-family:var(--font); font-weight:400; line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
.wrap { max-width:1000px; margin:0 auto; padding:40px 24px 96px; }

header { text-align:center; margin-bottom:40px; }
.mark {
  font-weight:700; font-size:15px; letter-spacing:.14em; text-transform:lowercase;
  margin:0 0 28px;
}
h1 { font-size:34px; font-weight:700; letter-spacing:-.01em; margin:0 0 8px; text-wrap:balance; }
.sub { color:var(--muted); font-size:16px; margin:0; }

.searchbar { position:relative; margin:0 0 12px; }
#q {
  width:100%; font-family:var(--font); font-size:19px; color:var(--text);
  background:var(--surface); border:1px solid var(--line-bold);
  border-radius:4px; padding:16px 18px; box-shadow:var(--shadow);
}
#q::placeholder { color:var(--af-grey-2); }
#q:focus { outline:2px solid var(--text); outline-offset:1px; border-color:var(--text); }

.controls { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:28px; }
.toggle {
  font-family:var(--font); font-size:13px; color:var(--text);
  background:var(--chip-bg); border:1px solid transparent; border-radius:9999px;
  padding:7px 14px; cursor:pointer;
}
.toggle:hover { border-color:var(--line-bold); }
.toggle[aria-pressed="true"] { background:var(--text); color:var(--bg); }
.toggle:focus-visible { outline:2px solid var(--link); outline-offset:2px; }
.spacer { flex:1 1 auto; }
.count { font-size:13px; color:var(--muted); font-variant-numeric:tabular-nums; }

.notice {
  border-left:3px solid var(--alert); background:var(--alert-bg);
  padding:14px 16px; margin:0 0 24px; font-size:14px; border-radius:0 4px 4px 0;
}
.notice b { font-weight:700; }

.card {
  background:var(--surface); border:1px solid var(--line); border-radius:4px;
  padding:20px 22px; margin-bottom:12px; box-shadow:var(--shadow);
}
.card h2 { font-size:17px; font-weight:700; margin:0 0 10px; line-height:1.35; }
.meta { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; }
.chip {
  font-size:12px; background:var(--chip-bg); color:var(--text);
  padding:4px 10px; border-radius:9999px; white-space:nowrap;
}
.chip.stock-in { background:var(--text); color:var(--bg); font-weight:500; }
.chip.stock-out { background:transparent; color:var(--alert); border:1px solid var(--alert); font-weight:500; }
.price { font-size:20px; font-weight:700; font-variant-numeric:tabular-nums; }
.was { font-size:14px; color:var(--muted); text-decoration:line-through; margin-left:8px; font-weight:400; }
.ids {
  font-size:12px; color:var(--muted); margin-top:10px;
  font-variant-numeric:tabular-nums; display:flex; flex-wrap:wrap; gap:14px;
}
.ids a { color:var(--link); text-decoration:none; }
.ids a:hover { text-decoration:underline; }
.flags { margin:12px 0 0; padding:0; list-style:none; display:flex; flex-direction:column; gap:6px; }
.flags li {
  font-size:13px; color:var(--text); background:var(--alert-bg);
  border-left:3px solid var(--alert); padding:8px 12px; border-radius:0 3px 3px 0;
}
/* Advisory: true but not a reason to stop, so it must not read as an alarm. */
.flags li.note {
  background:var(--surface-2); border-left-color:var(--line-bold); color:var(--muted);
}
.empty { text-align:center; padding:56px 20px; color:var(--muted); }
.empty strong { display:block; color:var(--text); font-size:18px; margin-bottom:8px; font-weight:700; }
footer {
  margin-top:48px; padding-top:20px; border-top:1px solid var(--line);
  font-size:12px; color:var(--muted); display:flex; flex-wrap:wrap; gap:6px 18px;
}
@media (max-width:600px) { .wrap { padding:24px 16px 64px; } h1 { font-size:26px; } }
@media (prefers-reduced-motion:reduce) { * { animation:none !important; transition:none !important; } }
</style>

<div class="wrap">
  <header>
    <p class="mark">americanflat</p>
    <h1>CX Product Desk</h1>
    <p class="sub">Look up any product before you answer a customer.</p>
  </header>

  <div class="searchbar">
    <input id="q" type="search" autocomplete="off" spellcheck="false"
           placeholder="Search a size, colour, UPC, SKU or product name — try 11x14 black with mat">
  </div>

  <div class="controls">
    <button class="toggle" id="t-stock" aria-pressed="false">In stock only</button>
    <button class="toggle" id="t-issues" aria-pressed="false">Only listing issues</button>
    <span class="spacer"></span>
    <span class="count" id="count"></span>
  </div>

  <div class="notice">
    <b>Read the title, not the description.</b> Product descriptions in our feed
    are recycled marketing copy — 547 of them state a different size than the
    product they are on — so this page shows only what a title and the feed
    actually support. A UPC is not unique either: 1,036 of them sit on more than
    one product. <b>Red</b> means check Shopify admin before you quote it; grey
    is context, not a problem.
  </div>

  <div id="results"></div>

  <footer>
    <span id="built"></span>
    <span id="total"></span>
    <span>Source: Google Merchant Center feed via BigQuery</span>
    <span>Prices are feed sale prices — Shopify admin wins</span>
  </footer>
</div>

<script>
const DATA = /*DATA*/;
const META = /*META*/;

const STOP = new Set(("a an the is are do does did i my me you it this that for of in on with and or to " +
  "can what which how much have has was were be customer asking asked wants want need needs please " +
  "size sized come comes coming get got any there about would will if at from one").split(" "));
const COLORS = new Set(["black","white","gold","silver","natural","walnut","oak","driftwood","gray","grey",
  "brown","cherry","maple","gunmetal","espresso","bronze","copper","ivory","beige","sage","navy","charcoal",
  "clear","turquoise"]);
const SIZE_RE = /\\b(\\d{1,3}(?:\\.\\d)?)\\s*[x×]\\s*(\\d{1,3}(?:\\.\\d)?)\\b/i;
const PACK_RE = /\\b(\\d{1,2})\\s*[- ]?\\s?(?:pack|frames|piece|pc)\\b/i;

const tok = s => (s||"").toLowerCase().split(/[^a-z0-9.]+/)
  .filter(t => t && t.length > 1 && !STOP.has(t));
const normSize = (a,b) => [a,b].map(v => String(parseFloat(v))).join("x");

// Catalogue-common words prove nothing on their own (mirrors build_kb/cx_lookup).
const GENERIC = (() => {
  const df = new Map();
  for (const p of DATA) for (const t of new Set(tok(p.t))) df.set(t, (df.get(t)||0)+1);
  const cut = DATA.length * 0.15, out = new Set();
  for (const [t,c] of df) if (c >= cut) out.add(t);
  return out;
})();

const IDX = DATA.map(p => ({ p, title: new Set(tok(p.t)), cat: new Set(tok(p.c)) }));

function exact(needle) {
  const n = needle.trim().toLowerCase(), bare = n.replace(/^0+/, "");
  if (!/^[0-9]{6,14}$/.test(n)) return null;
  const hits = DATA.filter(p =>
    (p.u && (p.u.toLowerCase() === n || p.u.replace(/^0+/,"") === bare)) ||
    (p.m && p.m.toLowerCase() === n));
  return hits.length ? hits : null;
}

function search(query, opts) {
  let qt = tok(query);
  const ms = SIZE_RE.exec(query || ""), mp = PACK_RE.exec(query || "");
  const wantSize = ms ? normSize(ms[1], ms[2]) : null;
  const wantPack = mp ? parseInt(mp[1], 10) : null;
  const wantColors = qt.filter(t => COLORS.has(t));
  qt = qt.filter(t => !/^[\\d.]+x[\\d.]+$/.test(t) && !/^\\d+$/.test(t));

  // Browse mode: a filter is on but nothing was typed (e.g. "Only listing
  // issues"). Everything passing the filters is a real result.
  const browsing = !qt.length && !wantSize && !wantPack && !wantColors.length;

  const rows = [];
  for (const e of IDX) {
    const p = e.p;
    if (opts.stock && !p.i) continue;
    if (opts.issues && !(p.x && p.x.length)) continue;
    if (browsing) { rows.push([1, 1, p]); continue; }
    let s = 0, strength = 0;
    for (const t of qt) {
      const gen = GENERIC.has(t), w = gen ? 0 : 1;
      if (e.title.has(t))                                    { s += gen ? 2 : 6; strength += w; }
      else if (t.length > 3 && [...e.title].some(x => x.startsWith(t))) { s += 3; strength += w; }
      else if (e.cat.has(t))                                 { s += 4; strength += w; }
    }
    if (wantSize) { if (p.s === wantSize) { s += 14; strength += 2; } else s -= 3; }
    if (wantPack) { if (p.n === wantPack) { s += 8; strength += 1; } else s -= 2; }
    if (wantColors.length && p.k && wantColors.some(c => p.k.toLowerCase().includes(c))) {
      s += 7; strength += 1;
    }
    // Tie-break among things that already matched. Applying this to every
    // in-stock product would make the whole catalogue "match" any query.
    if (s > 0) { if (p.i) s += 0.4; rows.push([s, strength, p]); }
  }
  rows.sort((a,b) => b[0] - a[0] || a[2].t.localeCompare(b[2].t));
  const top = rows.slice(0, 40);
  const specific = qt.filter(t => !GENERIC.has(t));
  const needed = specific.length > 1 ? 2 : 1;
  let confident = top.length > 0 && top[0][1] >= needed;
  if (wantSize && top.length && top[0][2].s !== wantSize) confident = false;
  return { hits: top.map(r => r[2]), confident, total: rows.length };
}

const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));

function card(p) {
  const chips = [];
  chips.push(p.i ? '<span class="chip stock-in">In stock</span>'
                 : '<span class="chip stock-out">Out of stock</span>');
  if (p.s) chips.push(`<span class="chip">${esc(p.s)} in</span>`);
  if (p.k) chips.push(`<span class="chip">${esc(p.k)}</span>`);
  if (p.n > 1) chips.push(`<span class="chip">${p.n}-pack</span>`);
  chips.push(`<span class="chip">${esc(p.c)}</span>`);
  for (const f of p.f || []) chips.push(`<span class="chip">${esc(f)}</span>`);

  const price = p.p != null
    ? `<span class="price">$${p.p.toFixed(2)}</span>` +
      (p.l ? `<span class="was">$${p.l.toFixed(2)}</span>` : "")
    : '<span class="price">—</span><span class="was">no price in feed</span>';

  const ids = [];
  if (p.u) ids.push(`UPC ${esc(p.u)}`);
  if (p.m) ids.push(`SKU ${esc(p.m)}`);
  if (p.w) ids.push(`<a href="${esc(p.w)}" target="_blank" rel="noopener">Product page ↗</a>`);

  const flags = (p.x || []).map(f => `<li>${esc(f)}</li>`).join("");
  const notes = (p.xn || []).map(f => `<li class="note">${esc(f)}</li>`).join("");

  return `<article class="card">
    <h2>${esc(p.t)}</h2>
    <div class="meta">${chips.join("")}</div>
    <div>${price}</div>
    ${ids.length ? `<div class="ids">${ids.map(x => `<span>${x}</span>`).join("")}</div>` : ""}
    ${flags || notes ? `<ul class="flags">${flags}${notes}</ul>` : ""}
  </article>`;
}

const qEl = document.getElementById("q");
const resEl = document.getElementById("results");
const countEl = document.getElementById("count");
const tStock = document.getElementById("t-stock");
const tIssues = document.getElementById("t-issues");
const opts = { stock:false, issues:false };

function render() {
  const query = qEl.value.trim();
  if (!query && !opts.issues && !opts.stock) {
    resEl.innerHTML = `<div class="empty"><strong>Start typing to find a product</strong>
      A size like 11x14, a colour, a UPC from the customer's order, or words from the product name.</div>`;
    countEl.textContent = "";
    return;
  }
  const ex = query ? exact(query) : null;
  let hits, confident = true, total;
  if (ex) { hits = ex; total = ex.length; }
  else {
    const r = search(query, opts);
    hits = r.hits; confident = r.confident; total = r.total;
  }
  if (opts.stock) hits = hits.filter(p => p.i);
  if (opts.issues) hits = hits.filter(p => p.x && p.x.length);

  countEl.textContent = total ? `${hits.length} shown of ${total} match${total===1?"":"es"}` : "";

  if (!hits.length) {
    resEl.innerHTML = `<div class="empty"><strong>Nothing matches that</strong>
      Not being in this feed doesn't mean we stopped selling it — check Shopify admin
      before telling a customer it doesn't exist.</div>`;
    return;
  }
  let head = "";
  if (ex && ex.length > 1) {
    head = `<div class="notice"><b>This UPC is on ${ex.length} different products.</b>
      Ask the customer for their order number or a photo — don't pick one.</div>`;
  } else if (!confident) {
    head = `<div class="notice"><b>Nothing here clearly matches.</b> Treat these as
      guesses: confirm the product with the customer before quoting anything.</div>`;
  }
  resEl.innerHTML = head + hits.map(card).join("");
}

let timer;
qEl.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(render, 90); });
for (const [btn, key] of [[tStock,"stock"], [tIssues,"issues"]]) {
  btn.addEventListener("click", () => {
    opts[key] = !opts[key];
    btn.setAttribute("aria-pressed", String(opts[key]));
    render();
  });
}
document.getElementById("built").textContent = "Catalogue built " + META.generated_at;
document.getElementById("total").textContent = META.product_count.toLocaleString() + " products";
render();
qEl.focus();
</script>
"""


def main():
    kb = json.loads(KB.read_text())
    data = compact(kb)
    meta = {"generated_at": kb["generated_at"], "product_count": kb["product_count"]}
    html = (TEMPLATE
            .replace("/*DATA*/", json.dumps(data, separators=(",", ":")))
            .replace("/*META*/", json.dumps(meta, separators=(",", ":"))))
    OUT.write_text(html)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1_048_576:.2f} MB, "
          f"{len(data)} products)")


if __name__ == "__main__":
    main()
