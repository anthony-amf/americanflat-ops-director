#!/usr/bin/env python3
"""Build the Ops Projects weekly meeting dashboard (AF-branded HTML).

Fetches all records from the Ops Projects Airtable base and renders a
self-contained HTML page (ops-projects/dashboard.html) that gets published
as a Claude artifact for the weekly Ops Projects meeting.

Usage:
    python3 build_dashboard.py [output.html]

Requests to api.airtable.com are authenticated transparently by the agent proxy.
"""
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

BASE_ID = "appaFuK87Xk9Nn5vR"
TABLE = "Projects"
BASE_URL = f"https://airtable.com/{BASE_ID}"


def fetch_all():
    records, offset = [], None
    while True:
        params = {"pageSize": "100"}
        if offset:
            params["offset"] = offset
        url = f"https://api.airtable.com/v0/{BASE_ID}/{urllib.parse.quote(TABLE)}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(urllib.request.Request(url)) as resp:
            data = json.loads(resp.read())
        records.extend(data["records"])
        offset = data.get("offset")
        if not offset:
            return records


def slim(records):
    out = []
    for r in records:
        f = r["fields"]
        out.append({
            "id": r["id"],
            "name": f.get("Project", ""),
            "status": f.get("Status", "Needs Review"),
            "priority": f.get("Priority"),
            "owners": f.get("Owners", []),
            "category": f.get("Category", "Other"),
            "notes": f.get("Notes", ""),
            "update": f.get("Latest Update", ""),
            "last": f.get("Last Discussed"),
            "target": f.get("Target Date"),
            "days": f.get("Days Since Discussed"),
            "link": f.get("Slack Link"),
        })
    return out


TEMPLATE = """<title>Ops Projects — Americanflat</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {
  --af-black: #0F0F0F; --af-white: #FFFFFF;
  --af-grey-4: #1A1A1A; --af-grey-3: #666666; --af-grey-2: #B3B3B3; --af-grey-1: #E6E6E6;
  --af-red: #CE0E2D; --af-blue: #003595;
  --bg: var(--af-white); --surface: var(--af-white); --text: var(--af-black);
  --muted: var(--af-grey-3); --border: var(--af-grey-1); --chip: #F5F5F4;
  --alert: var(--af-red); --link: var(--af-blue);
  --font: 'Glacial Indifference', 'DM Sans', 'Inter', system-ui, -apple-system, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: var(--af-black); --surface: var(--af-grey-4); --text: var(--af-white);
    --muted: var(--af-grey-2); --border: #2E2E2E; --chip: #262626;
    --alert: #FF4D6A; --link: #7FA4FF; }
}
:root[data-theme="dark"] { --bg: var(--af-black); --surface: var(--af-grey-4); --text: var(--af-white);
  --muted: var(--af-grey-2); --border: #2E2E2E; --chip: #262626; --alert: #FF4D6A; --link: #7FA4FF; }
:root[data-theme="light"] { --bg: var(--af-white); --surface: var(--af-white); --text: var(--af-black);
  --muted: var(--af-grey-3); --border: var(--af-grey-1); --chip: #F5F5F4; --alert: var(--af-red); --link: var(--af-blue); }

* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--font);
  font-size: 16px; line-height: 1.5; -webkit-font-smoothing: antialiased; }
.wrap { max-width: 1160px; margin: 0 auto; padding: 0 32px 96px; }

header { padding: 48px 0 8px; text-align: center; }
.logo { height: 34px; color: var(--text); }
.title { font-size: 2.6rem; font-weight: 700; letter-spacing: -0.01em; margin: 28px 0 6px; line-height: 1.15; text-wrap: balance; }
.sub { color: var(--muted); margin: 0 0 20px; font-size: 1.05rem; }
.actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; margin-bottom: 12px; }
.btn { display: inline-flex; align-items: center; gap: 8px; padding: 10px 22px; border-radius: 4px;
  font-weight: 700; font-size: 0.95rem; text-decoration: none; cursor: pointer;
  background: var(--text); color: var(--bg); border: 1px solid var(--text);
  transition: opacity 150ms cubic-bezier(0.2,0.8,0.2,1); }
.btn:hover { opacity: 0.85; }
.btn.ghost { background: transparent; color: var(--text); }

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin: 36px 0 8px; }
.kpi { border: 1px solid var(--border); border-radius: 8px; padding: 20px 22px; background: var(--surface); }
.kpi b { display: block; font-size: 2.2rem; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
.kpi span { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; }
.kpi.alert b { color: var(--alert); }

.filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 28px 0 8px;
  padding: 16px 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.filters input, .filters select { font-family: var(--font); font-size: 0.95rem; color: var(--text);
  background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 8px 12px; }
.filters input { flex: 1 1 220px; min-width: 180px; }
.fchip { padding: 6px 14px; border-radius: 9999px; border: 1px solid var(--border); background: transparent;
  color: var(--text); font-family: var(--font); font-size: 0.85rem; cursor: pointer; }
.fchip.on { background: var(--text); color: var(--bg); border-color: var(--text); font-weight: 700; }

h2.section { font-size: 1.6rem; font-weight: 700; margin: 56px 0 4px; letter-spacing: -0.01em; }
p.section-note { color: var(--muted); margin: 0 0 20px; font-size: 0.95rem; }
.count { color: var(--muted); font-weight: 400; font-size: 1.1rem; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.card { border: 1px solid var(--border); border-radius: 8px; background: var(--surface);
  padding: 20px 22px; display: flex; flex-direction: column; gap: 10px; }
.card.stale { border-left: 3px solid var(--alert); }
.card h3 { margin: 0; font-size: 1.08rem; font-weight: 700; line-height: 1.3; }
.meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.pill { padding: 2px 10px; border-radius: 9999px; font-size: 0.7rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.05em; background: var(--chip); color: var(--text); }
.pill.top { background: var(--alert); color: #fff; }
.pill.cat { background: transparent; border: 1px solid var(--border); color: var(--muted); font-weight: 400; }
.owners { display: flex; flex-wrap: wrap; gap: 6px; }
.owner { font-size: 0.8rem; padding: 3px 10px; border-radius: 9999px; background: var(--chip); }
.age { font-size: 0.8rem; color: var(--muted); }
.age.hot { color: var(--alert); font-weight: 700; }
.body-note { font-size: 0.9rem; color: var(--muted); white-space: pre-wrap; margin: 0;
  display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; cursor: pointer; }
.body-note.open { -webkit-line-clamp: unset; }
.card a { color: var(--link); font-size: 0.85rem; text-decoration: none; }
.empty { color: var(--muted); padding: 24px 0; }
details.done summary { cursor: pointer; font-size: 1rem; color: var(--muted); margin-top: 16px; }
footer { margin-top: 80px; text-align: center; color: var(--muted); font-size: 0.75rem;
  border-top: 1px solid var(--border); padding-top: 24px; }
footer a { color: var(--link); }
@media (prefers-reduced-motion: reduce) { .btn { transition: none; } }
</style>
<div class="wrap">
<header>
  <svg class="logo" viewBox="0 0 500 80" role="img" aria-label="americanflat"><text x="10" y="58" style="font-family:var(--font);font-weight:700;font-size:64px;letter-spacing:0.04em" fill="currentColor">americanflat</text></svg>
  <h1 class="title">Ops Projects</h1>
  <p class="sub">Weekly meeting board · data as of __ASOF__</p>
  <div class="actions">
    <a class="btn" href="__BASE_URL__" target="_blank" rel="noopener">Edit in Airtable</a>
  </div>
</header>

<div class="kpis" id="kpis"></div>

<div class="filters">
  <input id="q" type="search" placeholder="Search projects…" aria-label="Search projects">
  <select id="cat" aria-label="Filter by category"><option value="">All categories</option></select>
  <div id="ownerChips" style="display:flex;flex-wrap:wrap;gap:8px"></div>
</div>

<div id="sections"></div>

<footer>
  Migrated from the Slack “Ops Projects” list on __ASOF__ · Source of truth is now
  <a href="__BASE_URL__" target="_blank" rel="noopener">Airtable</a> ·
  Ask Claude to “refresh the ops projects dashboard” to update this page.
</footer>
</div>

<script>
const DATA = __DATA__;
const STALE_DAYS = 21;
const state = { q: "", cat: "", owner: "" };

const fmt = d => d ? new Date(d + "T00:00:00").toLocaleDateString("en-US", {month:"short", day:"numeric", year:"numeric"}) : "";

function kpis() {
  const act = DATA.filter(p => p.status === "In Progress");
  const stale = act.filter(p => (p.days ?? 999) > STALE_DAYS);
  const wins = DATA.filter(p => p.status === "Completed" && (p.days ?? 999) <= 45);
  const items = [
    ["In Progress", act.length, false],
    ["Not Started", DATA.filter(p => p.status === "Not Started").length, false],
    ["Needs Review", DATA.filter(p => p.status === "Needs Review").length, false],
    ["Stale (>" + STALE_DAYS + "d)", stale.length, stale.length > 0],
    ["Done · last 45d", wins.length, false],
  ];
  document.getElementById("kpis").innerHTML = items.map(([l, n, a]) =>
    `<div class="kpi${a ? " alert" : ""}"><b>${n}</b><span>${l}</span></div>`).join("");
}

function card(p) {
  const hot = p.status !== "Completed" && (p.days ?? null) !== null && p.days > STALE_DAYS;
  const age = p.last ? `<span class="age${hot ? " hot" : ""}">${p.status === "Completed" ? "closed" : "last discussed"} ${fmt(p.last)}${p.status !== "Completed" && p.days != null ? ` · ${p.days}d ago` : ""}</span>` : "";
  const note = [p.update, p.notes].filter(Boolean).join("\\n");
  return `<div class="card${hot ? " stale" : ""}">
    <h3>${esc(p.name)}</h3>
    <div class="meta">
      ${p.priority ? `<span class="pill${p.priority === "Top" ? " top" : ""}">${p.priority}</span>` : ""}
      <span class="pill cat">${esc(p.category)}</span>
      ${age}
    </div>
    ${p.owners.length ? `<div class="owners">${p.owners.map(o => `<span class="owner">${esc(o)}</span>`).join("")}</div>` : ""}
    ${note ? `<p class="body-note" onclick="this.classList.toggle('open')">${esc(note)}</p>` : ""}
    ${p.link ? `<a href="${esc(p.link)}" target="_blank" rel="noopener">Slack thread ↗</a>` : ""}
    ${p.target ? `<span class="age">target: ${fmt(p.target)}</span>` : ""}
  </div>`;
}

function esc(s) { return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

function match(p) {
  if (state.cat && p.category !== state.cat) return false;
  if (state.owner && !p.owners.includes(state.owner)) return false;
  if (state.q) {
    const hay = (p.name + " " + p.notes + " " + p.update + " " + p.owners.join(" ")).toLowerCase();
    if (!hay.includes(state.q.toLowerCase())) return false;
  }
  return true;
}

function section(title, note, items, emptyMsg) {
  if (!items.length) return `<h2 class="section">${title} <span class="count">0</span></h2><p class="empty">${emptyMsg}</p>`;
  return `<h2 class="section">${title} <span class="count">${items.length}</span></h2>` +
    (note ? `<p class="section-note">${note}</p>` : "") +
    `<div class="grid">${items.map(card).join("")}</div>`;
}

function render() {
  const f = DATA.filter(match);
  const byAge = (a, b) => (b.days ?? -1) - (a.days ?? -1);
  const inProg = f.filter(p => p.status === "In Progress").sort(byAge);
  const blocked = f.filter(p => p.status === "Blocked").sort(byAge);
  const next = f.filter(p => p.status === "Not Started").sort(byAge);
  const review = f.filter(p => p.status === "Needs Review").sort(byAge);
  const doneRecent = f.filter(p => p.status === "Completed" && (p.days ?? 999) <= 45)
    .sort((a, b) => (a.days ?? 999) - (b.days ?? 999));
  const doneAll = f.filter(p => p.status === "Completed").length;

  let html = "";
  if (blocked.length) html += section("Blocked", "Needs a decision or an unblock — start the meeting here.", blocked, "");
  html += section("In Progress", "Sorted oldest update first — stale projects (red edge, >" + STALE_DAYS + " days since discussed) at the top.", inProg, "Nothing in flight matches the filter.");
  html += section("Up Next", "Not started yet.", next, "Nothing queued matches the filter.");
  html += section("Needs Review", "These had no status in the old Slack list — close them out or claim them.", review, "Triage queue is clear.");
  html += section("Recent Wins", "Completed in the last 45 days.", doneRecent, "No recent completions match the filter.");
  html += `<details class="done"><summary>All completed projects: ${doneAll}</summary></details>`;
  document.getElementById("sections").innerHTML = html;
}

function filters() {
  const cats = [...new Set(DATA.map(p => p.category))].sort();
  document.getElementById("cat").innerHTML += cats.map(c => `<option>${esc(c)}</option>`).join("");
  const active = DATA.filter(p => p.status !== "Completed");
  const owners = [...new Set(active.flatMap(p => p.owners))].sort();
  document.getElementById("ownerChips").innerHTML = owners.map(o =>
    `<button class="fchip" data-o="${esc(o)}">${esc(o)}</button>`).join("");
  document.querySelectorAll(".fchip").forEach(b => b.addEventListener("click", () => {
    state.owner = state.owner === b.dataset.o ? "" : b.dataset.o;
    document.querySelectorAll(".fchip").forEach(x => x.classList.toggle("on", x.dataset.o === state.owner));
    render();
  }));
  document.getElementById("q").addEventListener("input", e => { state.q = e.target.value; render(); });
  document.getElementById("cat").addEventListener("change", e => { state.cat = e.target.value; render(); });
}

kpis(); filters(); render();
</script>
"""


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "dashboard.html")
    records = slim(fetch_all())
    html_page = (TEMPLATE
                 .replace("__DATA__", json.dumps(records, ensure_ascii=False))
                 .replace("__ASOF__", date.today().strftime("%B %d, %Y"))
                 .replace("__BASE_URL__", BASE_URL))
    out.write_text(html_page, encoding="utf-8")
    print(f"wrote {out} ({len(records)} projects)")
