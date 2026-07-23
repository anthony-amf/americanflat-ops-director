#!/usr/bin/env python3
"""Build the Ops Projects weekly meeting dashboard (AF-branded HTML).

Fetches all records from the Ops Projects Airtable base and renders a
self-contained HTML page (ops-projects/dashboard.html) that gets published
as a Claude artifact for the weekly Ops Projects meeting.

The page is also an editor: status/priority/owner/category edits, update
notes, and new projects queue up client-side (persisted in localStorage) and
are exported as a change list that Claude applies back to Airtable.

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

TEAM_DEFAULTS = [
    "Anthony", "Kent", "Jasmine", "John N.", "Maria C.", "Bart", "Mahjoub",
    "Ivan", "Carlos D.", "Carlos T.", "Carolina", "Olivier", "Nica", "Raja",
    "Angela", "Paul T. (Surpass)",
]

CATEGORIES = [
    "3PL & Warehouses", "Marketplaces & EDI", "Shipping & Carriers",
    "Finance & Billing", "AI & Data", "IT & Systems", "People & HR",
    "Lean & Culture", "Other",
]


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
            "focus": bool(f.get("90 Day Focus")),
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
  --alert: var(--af-red); --link: var(--af-blue); --scrim: rgba(15,15,15,0.45);
  --font: 'Glacial Indifference', 'DM Sans', 'Inter', system-ui, -apple-system, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: var(--af-black); --surface: var(--af-grey-4); --text: var(--af-white);
    --muted: var(--af-grey-2); --border: #2E2E2E; --chip: #262626;
    --alert: #FF4D6A; --link: #7FA4FF; --scrim: rgba(0,0,0,0.6); }
}
:root[data-theme="dark"] { --bg: var(--af-black); --surface: var(--af-grey-4); --text: var(--af-white);
  --muted: var(--af-grey-2); --border: #2E2E2E; --chip: #262626; --alert: #FF4D6A; --link: #7FA4FF; --scrim: rgba(0,0,0,0.6); }
:root[data-theme="light"] { --bg: var(--af-white); --surface: var(--af-white); --text: var(--af-black);
  --muted: var(--af-grey-3); --border: var(--af-grey-1); --chip: #F5F5F4; --alert: var(--af-red); --link: var(--af-blue); --scrim: rgba(15,15,15,0.45); }

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
  background: var(--text); color: var(--bg); border: 1px solid var(--text); font-family: var(--font);
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
.filters input { flex: 1 1 200px; min-width: 160px; }
.fchip { padding: 6px 14px; border-radius: 9999px; border: 1px solid var(--border); background: transparent;
  color: var(--text); font-family: var(--font); font-size: 0.85rem; cursor: pointer; }
.fchip.on { background: var(--text); color: var(--bg); border-color: var(--text); font-weight: 700; }

h2.section { font-size: 1.6rem; font-weight: 700; margin: 56px 0 4px; letter-spacing: -0.01em; }
p.section-note { color: var(--muted); margin: 0 0 20px; font-size: 0.95rem; }
.count { color: var(--muted); font-weight: 400; font-size: 1.1rem; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.card { position: relative; border: 1px solid var(--border); border-radius: 8px; background: var(--surface);
  padding: 20px 22px; display: flex; flex-direction: column; gap: 10px; cursor: pointer; }
.card:hover { border-color: var(--muted); }
.card.stale { border-left: 3px solid var(--alert); }
.card h3 { margin: 0 26px 0 0; font-size: 1.08rem; font-weight: 700; line-height: 1.3; }
.editbtn { position: absolute; top: 12px; right: 12px; background: none; border: none; cursor: pointer;
  color: var(--muted); font-size: 1rem; padding: 4px; line-height: 1; font-family: var(--font); }
.editbtn:hover { color: var(--text); }
.starbtn { position: absolute; top: 10px; right: 38px; background: none; border: none; cursor: pointer;
  color: var(--muted); font-size: 1.15rem; padding: 4px; line-height: 1; }
.starbtn:hover { color: #D4A017; }
.starbtn.on { color: #D4A017; }
.meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.pill { padding: 2px 10px; border-radius: 9999px; font-size: 0.7rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.05em; background: var(--chip); color: var(--text); }
.pill.top { background: var(--alert); color: #fff; }
.pill.cat { background: transparent; border: 1px solid var(--border); color: var(--muted); font-weight: 400; }
.pill.new { background: var(--text); color: var(--bg); }
.pill.pend { background: transparent; border: 1px dashed var(--muted); color: var(--muted); font-weight: 400; }
.owners { display: flex; flex-wrap: wrap; gap: 6px; }
.owner { font-size: 0.8rem; padding: 3px 10px; border-radius: 9999px; background: var(--chip); }
.age { font-size: 0.8rem; color: var(--muted); }
.age.hot { color: var(--alert); font-weight: 700; }
.body-note { font-size: 0.9rem; color: var(--muted); white-space: pre-wrap; margin: 0;
  display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; cursor: pointer; }
.body-note.open { -webkit-line-clamp: unset; }
.card a { color: var(--link); font-size: 0.85rem; text-decoration: none; }
.empty { color: var(--muted); padding: 24px 0; }
footer { margin-top: 80px; text-align: center; color: var(--muted); font-size: 0.75rem;
  border-top: 1px solid var(--border); padding-top: 24px; }
footer a { color: var(--link); }
@media (prefers-reduced-motion: reduce) { .btn { transition: none; } .meet-bar b { transition: none; } }

/* ---- Meeting mode ---- */
.meet { position: fixed; inset: 0; background: var(--bg); z-index: 50; display: none; flex-direction: column; }
.meet.on { display: flex; }
.meet-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 14px 24px; }
.meet-prog { color: var(--muted); font-size: 0.9rem; font-variant-numeric: tabular-nums; }
.meet-bar { height: 3px; background: var(--border); }
.meet-bar b { display: block; height: 100%; width: 0; background: var(--text); transition: width 200ms cubic-bezier(0.2,0.8,0.2,1); }
.meet-main { flex: 1; overflow-y: auto; display: flex; align-items: center; justify-content: center; padding: 24px; }
.meet-card { max-width: 720px; width: 100%; border: 1px solid var(--border); border-radius: 16px;
  background: var(--surface); padding: 36px 40px; display: flex; flex-direction: column; gap: 14px; }
.meet-card h3 { margin: 0; font-size: 1.8rem; font-weight: 700; line-height: 1.2; text-wrap: balance; }
.prev-notes { white-space: pre-wrap; color: var(--muted); font-size: 0.95rem; margin: 0; max-height: 200px; overflow-y: auto; }
.meet-note-in { width: 100%; min-height: 68px; font-family: var(--font); font-size: 0.95rem; padding: 10px 12px;
  border: 1px solid var(--border); border-radius: 8px; background: var(--bg); color: var(--text); resize: vertical; }
.chiprow { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.chiprow .lbl { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); width: 62px; }
.schip { padding: 7px 15px; border-radius: 9999px; border: 1px solid var(--border); background: transparent;
  color: var(--text); font-family: var(--font); font-size: 0.88rem; cursor: pointer; }
.schip.sel { background: var(--text); color: var(--bg); border-color: var(--text); font-weight: 700; }
.meet-actions { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; padding: 16px 24px 26px; border-top: 1px solid var(--border); }
.meet-hint { width: 100%; text-align: center; color: var(--muted); font-size: 0.75rem; }
.recap-box { width: 100%; min-height: 260px; font-family: ui-monospace, monospace; font-size: 0.82rem;
  padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); color: var(--text); }
.donebadge { color: var(--muted); font-size: 0.8rem; }

/* ---- Editor modal & changes tray ---- */
.modal { position: fixed; inset: 0; background: var(--scrim); z-index: 60; display: none;
  align-items: flex-start; justify-content: center; padding: 5vh 20px; overflow-y: auto; }
.modal.on { display: flex; }
.modal-card { max-width: 640px; width: 100%; border: 1px solid var(--border); border-radius: 16px;
  background: var(--surface); padding: 30px 34px; display: flex; flex-direction: column; gap: 16px; }
.modal-card h3 { margin: 0; font-size: 1.4rem; font-weight: 700; }
.f-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); margin-bottom: 6px; display: block; }
.f-input, .f-select, .f-area { width: 100%; font-family: var(--font); font-size: 0.95rem; color: var(--text);
  background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 9px 12px; }
.f-area { min-height: 64px; resize: vertical; }
.modal-foot { display: flex; gap: 10px; justify-content: flex-end; flex-wrap: wrap; }
.tray-btn { position: fixed; right: 24px; bottom: 24px; z-index: 45; display: none;
  box-shadow: 0 4px 12px rgba(15,15,15,0.18); }
.tray-btn.on { display: inline-flex; }
</style>
<div class="wrap">
<header>
  <svg class="logo" viewBox="0 0 500 80" role="img" aria-label="americanflat"><text x="10" y="58" style="font-family:var(--font);font-weight:700;font-size:64px;letter-spacing:0.04em" fill="currentColor">americanflat</text></svg>
  <h1 class="title">Ops Projects</h1>
  <p class="sub">Weekly meeting board · data as of __ASOF__</p>
  <div class="actions">
    <button class="btn" id="meetBtn">Start meeting ▸</button>
    <button class="btn ghost" id="addBtn">+ New project</button>
    <a class="btn ghost" href="__BASE_URL__" target="_blank" rel="noopener">Airtable</a>
  </div>
</header>

<div class="kpis" id="kpis"></div>

<div class="filters">
  <input id="q" type="search" placeholder="Search projects…" aria-label="Search projects">
  <select id="statusF" aria-label="Filter by status"><option value="">All statuses</option>
    <option>In Progress</option><option>Blocked</option><option>Not Started</option>
    <option>Needs Review</option><option>Completed</option></select>
  <select id="priF" aria-label="Filter by priority"><option value="">All priorities</option>
    <option>Top</option><option>Mid</option><option>Low</option><option>Ad Hoc</option></select>
  <select id="cat" aria-label="Filter by category"><option value="">All categories</option></select>
  <select id="sortF" aria-label="Sort">
    <option value="stale">Sort: stalest first</option>
    <option value="priority">Sort: priority</option>
    <option value="recent">Sort: recently discussed</option>
    <option value="az">Sort: A–Z</option></select>
  <div id="ownerChips" style="display:flex;flex-wrap:wrap;gap:8px"></div>
</div>

<div id="sections"></div>

<footer>
  Source of truth:
  <a href="__BASE_URL__" target="_blank" rel="noopener">Airtable</a> ·
  Edits made here queue in the Changes tray — paste them to Claude to apply ·
  Ask Claude to “refresh the ops projects dashboard” to update this page.
</footer>
</div>

<button class="btn tray-btn" id="trayBtn">Changes (0)</button>

<div class="meet" id="meet" role="dialog" aria-modal="true" aria-label="Meeting mode">
  <div class="meet-top">
    <span class="meet-prog" id="meetProg"></span>
    <div style="display:flex;gap:10px">
      <button class="btn ghost" id="meetRecapBtn">Recap</button>
      <button class="btn ghost" id="meetExit">Exit</button>
    </div>
  </div>
  <div class="meet-bar"><b id="meetBarFill"></b></div>
  <div class="meet-main" id="meetMain"></div>
  <div class="meet-actions" id="meetActs"></div>
</div>

<div class="modal" id="editModal" role="dialog" aria-modal="true" aria-label="Edit project">
  <div class="modal-card" id="editCard"></div>
</div>

<div class="modal" id="trayModal" role="dialog" aria-modal="true" aria-label="Pending changes">
  <div class="modal-card" id="trayCard"></div>
</div>

<script>
const DATA = __DATA__;
const TEAM = __TEAM__;
const CATS = __CATS__;
const STALE_DAYS = 21;
const STATUSES = ["Not Started", "In Progress", "Blocked", "Completed", "Needs Review"];
const PRIORITIES = ["Top", "Mid", "Low", "Ad Hoc"];
const PRI_RANK = {"Top": 0, "Mid": 1, "Low": 2, "Ad Hoc": 3};
const LS_KEY = "opsProjectsPending.v1";

const state = { q: "", cat: "", owner: "", status: "", priority: "", sort: "stale" };
let pending = { edits: {}, adds: [], deletes: [] };
const discussedIds = new Set();
let deck = [], deckTotal = 0, inRecap = false, focusMode = false;

const $ = id => document.getElementById(id);
const fmt = d => d ? new Date(d + "T00:00:00").toLocaleDateString("en-US", {month: "short", day: "numeric", year: "numeric"}) : "";
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])); }

// ---- pending changes (persisted in localStorage) ----
function savePending() {
  try { localStorage.setItem(LS_KEY, JSON.stringify({edits: pending.edits, adds: pending.adds, deletes: pending.deletes, discussed: [...discussedIds]})); } catch (e) {}
}
function loadPending() {
  try {
    const s = JSON.parse(localStorage.getItem(LS_KEY) || "{}");
    pending.edits = s.edits || {};
    pending.adds = s.adds || [];
    pending.deletes = s.deletes || [];
    (s.discussed || []).forEach(i => discussedIds.add(i));
  } catch (e) {}
  // auto-reconcile: drop pending values the base data already reflects (i.e. applied + republished)
  for (const [id, e] of Object.entries(pending.edits)) {
    const p = DATA.find(x => x.id === id);
    if (!p) { delete pending.edits[id]; continue; }
    for (const k of Object.keys(e)) {
      if (k === "note") { if (p.update && e.note && p.update.includes(e.note)) delete e.note; continue; }
      if (JSON.stringify(p[k]) === JSON.stringify(e[k])) delete e[k];
    }
    if (!Object.keys(e).length) delete pending.edits[id];
  }
  pending.adds = pending.adds.filter(a => !DATA.some(p => p.name.toLowerCase() === a.name.toLowerCase()));
  pending.deletes = pending.deletes.filter(id => DATA.some(p => p.id === id));
  savePending();
}
function pendingCount() { return Object.keys(pending.edits).length + pending.adds.length + pending.deletes.length; }
function eff(p) { const e = pending.edits[p.id]; return e ? Object.assign({}, p, e, {note: e.note}) : p; }
function allProjects() { return DATA.filter(p => !pending.deletes.includes(p.id)).map(eff).concat(pending.adds); }
function byId(id) { if (pending.deletes.includes(id)) return undefined; const p = DATA.find(x => x.id === id); return p ? eff(p) : pending.adds.find(a => a.id === id); }
function updateTray() {
  const n = pendingCount();
  $("trayBtn").textContent = "Changes (" + n + ")";
  $("trayBtn").classList.toggle("on", n > 0);
}

// ---- board ----
function kpis() {
  const all = allProjects();
  const act = all.filter(p => p.status === "In Progress");
  const stale = act.filter(p => (p.days ?? 999) > STALE_DAYS);
  const wins = all.filter(p => p.status === "Completed" && (p.days ?? 999) <= 45);
  const items = [
    ["In Progress", act.length, false],
    ["Not Started", all.filter(p => p.status === "Not Started").length, false],
    ["Needs Review", all.filter(p => p.status === "Needs Review").length, false],
    ["Stale (>" + STALE_DAYS + "d)", stale.length, stale.length > 0],
    ["Done · last 45d", wins.length, false],
  ];
  $("kpis").innerHTML = items.map(([l, n, a]) =>
    `<div class="kpi${a ? " alert" : ""}"><b>${n}</b><span>${l}</span></div>`).join("");
}

function match(p) {
  if (state.cat && p.category !== state.cat) return false;
  if (state.owner && !(p.owners || []).includes(state.owner)) return false;
  if (state.status && p.status !== state.status) return false;
  if (state.priority && p.priority !== state.priority) return false;
  if (state.q) {
    const hay = (p.name + " " + (p.notes || "") + " " + (p.update || "") + " " + (p.owners || []).join(" ")).toLowerCase();
    if (!hay.includes(state.q.toLowerCase())) return false;
  }
  return true;
}

function sorter() {
  if (state.sort === "priority") return (a, b) => (PRI_RANK[a.priority] ?? 9) - (PRI_RANK[b.priority] ?? 9) || (b.days ?? -1) - (a.days ?? -1);
  if (state.sort === "recent") return (a, b) => (a.days ?? 999) - (b.days ?? 999);
  if (state.sort === "az") return (a, b) => a.name.localeCompare(b.name);
  return (a, b) => (b.days ?? -1) - (a.days ?? -1);
}

function card(p) {
  const hot = p.status !== "Completed" && (p.days ?? null) !== null && p.days > STALE_DAYS;
  const age = p.id.startsWith("new-")
    ? `<span class="age">added this session</span>`
    : p.last ? `<span class="age${hot ? " hot" : ""}">${p.status === "Completed" ? "closed" : "last discussed"} ${fmt(p.last)}${p.status !== "Completed" && p.days != null ? ` · ${p.days}d ago` : ""}</span>` : "";
  const note = [p.update, p.notes].filter(Boolean).join("\\n");
  const edited = pending.edits[p.id];
  return `<div class="card${hot ? " stale" : ""}" data-open="${p.id}" role="button" tabindex="0" aria-label="Open ${esc(p.name)}">
    <button class="starbtn${p.focus ? " on" : ""}" data-star="${p.id}" title="${p.focus ? "Remove from" : "Add to"} 90 Day Focus" aria-label="${p.focus ? "Remove from" : "Add to"} 90 Day Focus: ${esc(p.name)}" aria-pressed="${p.focus ? "true" : "false"}">${p.focus ? "★" : "☆"}</button>
    <button class="editbtn" data-edit="${p.id}" title="Full editor (rename, owners, delete)" aria-label="Edit ${esc(p.name)}">✎</button>
    <h3>${esc(p.name)}</h3>
    <div class="meta">
      ${p.id.startsWith("new-") ? `<span class="pill new">New</span>` : ""}
      ${edited ? `<span class="pill pend">pending edit</span>` : ""}
      ${p.priority ? `<span class="pill${p.priority === "Top" ? " top" : ""}">${p.priority}</span>` : ""}
      <span class="pill cat">${esc(p.category)}</span>
      ${age}
    </div>
    ${(p.owners || []).length ? `<div class="owners">${p.owners.map(o => `<span class="owner">${esc(o)}</span>`).join("")}</div>` : ""}
    ${edited && edited.note ? `<p class="body-note open">📝 ${esc(edited.note)}</p>` : ""}
    ${note ? `<p class="body-note">${esc(note)}</p>` : ""}
    ${p.link ? `<a href="${esc(p.link)}" target="_blank" rel="noopener">Slack thread ↗</a>` : ""}
    ${p.target ? `<span class="age">target: ${fmt(p.target)}</span>` : ""}
  </div>`;
}

function section(title, note, items, emptyMsg) {
  if (!items.length) return emptyMsg ? `<h2 class="section">${title} <span class="count">0</span></h2><p class="empty">${emptyMsg}</p>` : "";
  return `<h2 class="section">${title} <span class="count">${items.length}</span></h2>` +
    (note ? `<p class="section-note">${note}</p>` : "") +
    `<div class="grid">${items.map(card).join("")}</div>`;
}

function render() {
  const f = allProjects().filter(match);
  const srt = sorter();
  const pick = s => f.filter(p => p.status === s).sort(srt);
  let html = "";
  const starred = f.filter(p => p.focus && p.status !== "Completed").sort(srt);
  if (starred.length) html += section("★ 90 Day Focus", "Starred projects in the current 90 day focus.", starred, "");
  const blocked = pick("Blocked");
  if (blocked.length) html += section("Blocked", "Needs a decision or an unblock — start the meeting here.", blocked, "");
  if (!state.status || state.status === "In Progress")
    html += section("In Progress", state.sort === "stale" ? "Sorted oldest update first — stale projects (red edge, >" + STALE_DAYS + " days since discussed) at the top." : "", pick("In Progress"), "Nothing in flight matches the filter.");
  if (!state.status || state.status === "Not Started")
    html += section("Up Next", "Not started yet.", pick("Not Started"), state.status ? "Nothing queued matches the filter." : "");
  if (!state.status || state.status === "Needs Review")
    html += section("Needs Review", "These had no status in the old Slack list — close them out or claim them.", pick("Needs Review"), state.status ? "Triage queue is clear." : "");
  const doneAll = f.filter(p => p.status === "Completed");
  if (state.status === "Completed") {
    html += section("Completed", "", doneAll.sort((a, b) => (a.days ?? 999) - (b.days ?? 999)), "No completed projects match the filter.");
  } else if (!state.status) {
    const recent = doneAll.filter(p => (p.days ?? 999) <= 45).sort((a, b) => (a.days ?? 999) - (b.days ?? 999));
    html += section("Recent Wins", "Completed in the last 45 days. Filter status to “Completed” to see all " + doneAll.length + ".", recent, "");
  }
  $("sections").innerHTML = html || `<p class="empty">Nothing matches the current filters.</p>`;
  document.querySelectorAll("[data-edit]").forEach(b => b.addEventListener("click", e => { e.stopPropagation(); openEditor(b.dataset.edit); }));
  document.querySelectorAll("[data-star]").forEach(b => b.addEventListener("click", e => { e.stopPropagation(); toggleFocus(b.dataset.star); }));
  document.querySelectorAll("[data-open]").forEach(c => {
    c.addEventListener("click", e => { if (e.target.closest("a,button")) return; openFocus(c.dataset.open); });
    c.addEventListener("keydown", e => { if (e.key === "Enter" && e.target === c) openFocus(c.dataset.open); });
  });
}

function filters() {
  $("cat").innerHTML += CATS.map(c => `<option>${esc(c)}</option>`).join("");
  const owners = [...new Set(allProjects().filter(p => p.status !== "Completed").flatMap(p => p.owners || []))].sort();
  $("ownerChips").innerHTML = owners.map(o => `<button class="fchip" data-o="${esc(o)}">${esc(o)}</button>`).join("");
  document.querySelectorAll(".fchip").forEach(b => b.addEventListener("click", () => {
    state.owner = state.owner === b.dataset.o ? "" : b.dataset.o;
    document.querySelectorAll(".fchip").forEach(x => x.classList.toggle("on", x.dataset.o === state.owner));
    render();
  }));
  $("q").addEventListener("input", e => { state.q = e.target.value; render(); });
  $("cat").addEventListener("change", e => { state.cat = e.target.value; render(); });
  $("statusF").addEventListener("change", e => { state.status = e.target.value; render(); });
  $("priF").addEventListener("change", e => { state.priority = e.target.value; render(); });
  $("sortF").addEventListener("change", e => { state.sort = e.target.value; render(); });
}

function toggleFocus(id) {
  const base = DATA.find(x => x.id === id);
  const cur = byId(id);
  if (!cur) return;
  const newVal = !cur.focus;
  if (base) {
    const e = pending.edits[id] = pending.edits[id] || {};
    if (base.focus === newVal) delete e.focus; else e.focus = newVal;
    if (!Object.keys(e).length) delete pending.edits[id];
  } else {
    const a = pending.adds.find(x => x.id === id);
    if (a) a.focus = newVal;
  }
  savePending(); refresh();
}

// ---- editor ----
function chiprowHTML(name, options, selected, multi) {
  return options.map(o => `<button type="button" class="schip${(multi ? (selected || []).includes(o) : selected === o) ? " sel" : ""}" data-grp="${name}" data-v="${esc(o)}">${esc(o)}</button>`).join("");
}
function openEditor(id) {
  const isNew = !id;
  const p = id ? byId(id) : {name: "", status: "Not Started", priority: null, owners: [], category: "Other", notes: ""};
  if (!p) return;
  $("editCard").innerHTML = `
    <h3>${isNew ? "New project" : "Edit project"}</h3>
    <div><span class="f-label">Project</span><input class="f-input" id="eName" value="${esc(p.name)}"></div>
    <div><span class="f-label">Status</span><div class="chiprow" id="eStatus">${chiprowHTML("status", STATUSES.filter(s => s !== "Needs Review" || p.status === "Needs Review"), p.status, false)}</div></div>
    <div><span class="f-label">Priority</span><div class="chiprow" id="ePri">${chiprowHTML("pri", PRIORITIES, p.priority, false)}</div></div>
    <div><span class="f-label">Owners</span><div class="chiprow" id="eOwn">${chiprowHTML("own", TEAM, p.owners, true)}</div></div>
    <div><span class="f-label">Category</span><select class="f-select" id="eCat">${CATS.map(c => `<option${c === p.category ? " selected" : ""}>${esc(c)}</option>`).join("")}</select></div>
    <div><span class="f-label">Target date</span><input class="f-input" id="eTarget" type="date" value="${p.target || ""}"></div>
    ${isNew ? `<div><span class="f-label">Notes</span><textarea class="f-area" id="eNotes"></textarea></div>`
            : `<div><span class="f-label">Add update note</span><textarea class="f-area" id="eNote">${esc((pending.edits[id] || {}).note || "")}</textarea></div>`}
    <div class="modal-foot">
      ${isNew ? "" : `<button class="btn ghost" id="eDelete" style="color:var(--alert);border-color:var(--alert);margin-right:auto">Delete…</button>`}
      ${!isNew && pending.edits[id] ? `<button class="btn ghost" id="eRevert">Discard pending edits</button>` : ""}
      <button class="btn ghost" id="eCancel">Cancel</button>
      <button class="btn" id="eSave">${isNew ? "Add project" : "Save"}</button>
    </div>`;
  const sel = {status: p.status, pri: p.priority, own: [...(p.owners || [])]};
  document.querySelectorAll('#editCard .schip').forEach(b => b.addEventListener("click", () => {
    const g = b.dataset.grp, v = b.dataset.v;
    if (g === "own") {
      const i = sel.own.indexOf(v); i >= 0 ? sel.own.splice(i, 1) : sel.own.push(v);
      b.classList.toggle("sel");
    } else {
      sel[g] = sel[g] === v ? null : v;
      document.querySelectorAll(`#editCard .schip[data-grp="${g}"]`).forEach(x => x.classList.toggle("sel", x.dataset.v === sel[g]));
    }
  }));
  $("eCancel").addEventListener("click", closeEditor);
  const del = $("eDelete");
  if (del) del.addEventListener("click", () => {
    if (!confirm('Delete "' + p.name + '"? It will be removed from Airtable when the changes are applied.')) return;
    const ai = pending.adds.findIndex(x => x.id === id);
    if (ai >= 0) pending.adds.splice(ai, 1);
    else { if (!pending.deletes.includes(id)) pending.deletes.push(id); delete pending.edits[id]; discussedIds.delete(id); }
    savePending(); closeEditor(); refresh();
  });
  const rev = $("eRevert");
  if (rev) rev.addEventListener("click", () => { delete pending.edits[id]; savePending(); closeEditor(); refresh(); });
  $("eSave").addEventListener("click", () => {
    const name = $("eName").value.trim();
    if (!name) { $("eName").focus(); return; }
    if (isNew) {
      pending.adds.push({id: "new-" + Math.random().toString(36).slice(2, 9), name,
        status: sel.status || "Not Started", priority: sel.pri, owners: sel.own,
        category: $("eCat").value, notes: $("eNotes").value.trim(), update: "",
        last: null, target: $("eTarget").value || null, days: null, link: null});
    } else {
      const base = DATA.find(x => x.id === id);
      const e = pending.edits[id] = pending.edits[id] || {};
      const set = (k, v) => { if (base && JSON.stringify(base[k]) === JSON.stringify(v)) delete e[k]; else e[k] = v; };
      if (base) {
        set("name", name); set("status", sel.status || base.status); set("priority", sel.pri);
        set("owners", sel.own); set("category", $("eCat").value); set("target", $("eTarget").value || null);
        const n = $("eNote").value.trim(); if (n) e.note = n; else delete e.note;
        if (!Object.keys(e).length) delete pending.edits[id];
      } else {
        const a = pending.adds.find(x => x.id === id);
        if (a) Object.assign(a, {name, status: sel.status || a.status, priority: sel.pri, owners: sel.own,
          category: $("eCat").value, target: $("eTarget").value || null});
      }
    }
    savePending(); closeEditor(); refresh();
  });
  $("editModal").classList.add("on");
}
function closeEditor() { $("editModal").classList.remove("on"); }

// ---- changes tray ----
function changesText() {
  const lines = ["# Ops Projects changes — " + new Date().toLocaleDateString("en-US", {month: "long", day: "numeric", year: "numeric"}), ""];
  const editedIds = Object.keys(pending.edits);
  if (editedIds.length) {
    lines.push("## Edits to apply in Airtable");
    for (const id of editedIds) {
      const p = DATA.find(x => x.id === id); if (!p) continue;
      const e = pending.edits[id], bits = [];
      if (e.name && e.name !== p.name) bits.push('rename to: "' + e.name + '"');
      if (e.status && e.status !== p.status) bits.push("status: " + p.status + " → " + e.status);
      if ("priority" in e && e.priority !== p.priority) bits.push("priority: " + (p.priority || "none") + " → " + (e.priority || "none"));
      if (e.owners && JSON.stringify(e.owners) !== JSON.stringify(p.owners)) bits.push("owners: " + (e.owners.join(", ") || "none"));
      if (e.category && e.category !== p.category) bits.push("category: " + e.category);
      if ("target" in e && e.target !== p.target) bits.push("target: " + (e.target || "none"));
      if ("focus" in e && e.focus !== p.focus) bits.push(e.focus ? "add to 90 Day Focus ★" : "remove from 90 Day Focus");
      if (e.note) bits.push('update: "' + e.note + '"');
      if (bits.length) lines.push("- **" + p.name + "** [" + id + "] — " + bits.join("; "));
    }
    lines.push("");
  }
  if (pending.adds.length) {
    lines.push("## New projects to create");
    for (const a of pending.adds) {
      const bits = ["status: " + a.status];
      if (a.priority) bits.push("priority: " + a.priority);
      if ((a.owners || []).length) bits.push("owners: " + a.owners.join(", "));
      bits.push("category: " + a.category);
      if (a.target) bits.push("target: " + a.target);
      if (a.focus) bits.push("90 Day Focus: ★ yes");
      if (a.notes) bits.push('notes: "' + a.notes + '"');
      lines.push("- **" + a.name + "** — " + bits.join("; "));
    }
    lines.push("");
  }
  if (pending.deletes.length) {
    lines.push("## Projects to delete from Airtable");
    for (const id of pending.deletes) {
      const p = DATA.find(x => x.id === id);
      if (p) lines.push("- **" + p.name + "** [" + id + "]");
    }
    lines.push("");
  }
  if (discussedIds.size) {
    const changedSet = new Set(editedIds);
    const noChange = [...discussedIds].map(byId).filter(Boolean).filter(p => !changedSet.has(p.id));
    lines.push("Discussed " + discussedIds.size + " project(s) this meeting.");
    if (noChange.length) lines.push("", "## Discussed, no changes", ...noChange.map(p => "- " + p.name));
    lines.push("");
  }
  if (!editedIds.length && !pending.adds.length && !pending.deletes.length) lines.push("(no pending changes)", "");
  lines.push("_Paste this to Claude to apply everything to Airtable (and log the meeting if one was held)._");
  return lines.join("\\n");
}
function openTray() {
  $("trayCard").innerHTML = `
    <h3>Pending changes</h3>
    <p class="prev-notes">These live only in this browser until applied. Copy and paste to Claude — after Claude applies them to Airtable and refreshes the page, this queue clears itself.</p>
    <textarea class="recap-box" id="trayBox">${esc(changesText())}</textarea>
    <div class="modal-foot">
      <button class="btn ghost" id="trayClear">Clear all</button>
      <button class="btn ghost" id="trayClose">Close</button>
      <button class="btn" id="trayCopy">Copy for Claude</button>
    </div>`;
  $("trayClose").addEventListener("click", () => $("trayModal").classList.remove("on"));
  $("trayClear").addEventListener("click", () => {
    if (!confirm("Discard all pending changes?")) return;
    pending = {edits: {}, adds: [], deletes: []}; discussedIds.clear(); savePending();
    $("trayModal").classList.remove("on"); refresh();
  });
  $("trayCopy").addEventListener("click", () => {
    const box = $("trayBox"); box.select();
    (navigator.clipboard ? navigator.clipboard.writeText(box.value) : Promise.reject())
      .then(() => { $("trayCopy").textContent = "Copied ✓"; })
      .catch(() => { document.execCommand && document.execCommand("copy"); $("trayCopy").textContent = "Copied ✓"; });
  });
  $("trayModal").classList.add("on");
}

// ---- meeting mode ----
function openFocus(id) {
  if (!byId(id)) return;
  focusMode = true;
  deck = [id]; deckTotal = 1;
  $("meet").classList.add("on");
  document.body.style.overflow = "hidden";
  inRecap = false;
  showCard();
}

function startMeeting() {
  focusMode = false;
  const rank = s => s === "Blocked" ? 0 : s === "In Progress" ? 1 : s === "Needs Review" ? 2 : 3;
  const srt = sorter();
  deck = allProjects().filter(match).filter(p => p.status !== "Completed")
    .sort((a, b) => rank(a.status) - rank(b.status) || srt(a, b)).map(p => p.id);
  deckTotal = deck.length;
  if (!deck.length) { alert("No active projects match the current filters."); return; }
  $("meet").classList.add("on");
  document.body.style.overflow = "hidden";
  inRecap = false;
  showCard();
}
function progress() {
  if (focusMode) {
    $("meetProg").textContent = "Quick edit — changes queue in the Changes tray";
    $("meetBarFill").style.width = "0%";
    return;
  }
  const done = [...discussedIds].filter(id => byId(id)).length;
  $("meetProg").textContent = done + " of " + deckTotal + " discussed";
  $("meetBarFill").style.width = (deckTotal ? Math.min(100, done / deckTotal * 100) : 0) + "%";
}
function showCard() {
  inRecap = false;
  if (!deck.length) { showRecap(true); return; }
  const p = byId(deck[0]);
  if (!p) { deck.shift(); showCard(); return; }
  progress();
  const note = [p.update, p.notes].filter(Boolean).join("\\n");
  const hot = (p.days ?? null) !== null && p.days > STALE_DAYS;
  $("meetMain").innerHTML = `<div class="meet-card">
    <div class="meta">
      <span class="pill cat">${esc(p.category)}</span>
      ${p.last ? `<span class="age${hot ? " hot" : ""}">last discussed ${fmt(p.last)}${p.days != null ? ` · ${p.days}d ago` : ""}</span>` : `<span class="age">never discussed</span>`}
      ${discussedIds.has(p.id) ? `<span class="donebadge">✓ discussed this meeting</span>` : ""}
    </div>
    <h3>${esc(p.name)}</h3>
    ${(p.owners || []).length ? `<div class="owners">${p.owners.map(o => `<span class="owner">${esc(o)}</span>`).join("")}</div>` : ""}
    ${note ? `<p class="prev-notes">${esc(note)}</p>` : ""}
    <div class="chiprow"><span class="lbl">Status</span>${chiprowHTML("mStatus", STATUSES.filter(s => s !== "Needs Review"), p.status, false)}</div>
    <div class="chiprow"><span class="lbl">Priority</span>${chiprowHTML("mPri", PRIORITIES, p.priority, false)}</div>
    <div class="chiprow"><span class="lbl">Category</span>${chiprowHTML("mCat", CATS, p.category, false)}</div>
    <textarea class="meet-note-in" id="meetNote" placeholder="Add an update from this discussion…">${esc((pending.edits[p.id] || {}).note || "")}</textarea>
    ${p.link ? `<a href="${esc(p.link)}" target="_blank" rel="noopener">Slack thread ↗</a>` : ""}
  </div>`;
  document.querySelectorAll('#meetMain .schip').forEach(b => b.addEventListener("click", () => {
    const g = b.dataset.grp, v = b.dataset.v, base = DATA.find(x => x.id === p.id);
    const key = g === "mStatus" ? "status" : g === "mCat" ? "category" : "priority";
    const e = pending.edits[p.id] = pending.edits[p.id] || {};
    const cur = document.querySelector(`#meetMain .schip[data-grp="${g}"].sel`);
    const newVal = (cur && cur.dataset.v === v) ? (key === "priority" ? null : base ? base[key] : v) : v;
    if (base && JSON.stringify(base[key]) === JSON.stringify(newVal)) delete e[key]; else e[key] = newVal;
    if (!base) { const a = pending.adds.find(x => x.id === p.id); if (a) a[key] = newVal; }
    if (!Object.keys(e).length) delete pending.edits[p.id];
    savePending(); updateTray();
    document.querySelectorAll(`#meetMain .schip[data-grp="${g}"]`).forEach(x => x.classList.toggle("sel", x.dataset.v === newVal));
  }));
  if (focusMode) {
    $("meetActs").innerHTML = `
      <button class="btn ghost" id="fullEditBtn">Full editor ▸</button>
      <button class="btn" id="doneBtn">Save & close ✓</button>
      <span class="meet-hint">Esc or Save & close returns to the board · changes queue in the Changes tray</span>`;
    $("doneBtn").addEventListener("click", () => { saveMeetNote(); exitMeeting(); });
    $("fullEditBtn").addEventListener("click", () => { const id = deck[0]; saveMeetNote(); exitMeeting(); openEditor(id); });
  } else {
    $("meetActs").innerHTML = `
      <button class="btn ghost" id="skipBtn">Skip ▸</button>
      <button class="btn" id="nextBtn">Discussed — next ▸</button>
      <span class="meet-hint">Space / → = discussed · S = skip · discussed cards fall to the back of the deck</span>`;
    $("skipBtn").addEventListener("click", () => nextCard(false));
    $("nextBtn").addEventListener("click", () => nextCard(true));
  }
}
function saveMeetNote() {
  const el = $("meetNote");
  if (!el || !deck.length) return;
  const id = deck[0], base = DATA.find(x => x.id === id);
  const v = el.value.trim();
  const e = pending.edits[id] = pending.edits[id] || {};
  if (v) e.note = v; else delete e.note;
  if (!base) { const a = pending.adds.find(x => x.id === id); if (a && v) a.notes = (a.notes ? a.notes + "\\n" : "") + ""; }
  if (!Object.keys(e).length) delete pending.edits[id];
  savePending(); updateTray();
}
function nextCard(markDiscussed) {
  if (!deck.length) return;
  if (focusMode) { saveMeetNote(); exitMeeting(); return; }
  saveMeetNote();
  const id = deck.shift();
  if (markDiscussed) { discussedIds.add(id); savePending(); }
  const p = byId(id);
  if (p && p.status !== "Completed") deck.push(id);   // completed cards drop out of the deck
  const allSeen = deck.length && deck.every(x => discussedIds.has(x));
  if (!deck.length || (markDiscussed && allSeen)) { showRecap(true); return; }
  showCard();
}
function showRecap(complete) {
  saveMeetNote();
  inRecap = true;
  progress();
  $("meetMain").innerHTML = `<div class="meet-card">
    <h3>${complete && !deck.length ? "Deck complete 🎉" : complete ? "Every card discussed 🎉" : "Meeting recap"}</h3>
    <p class="prev-notes">Copy this recap and paste it to Claude — it will apply the changes to Airtable and log the meeting.</p>
    <textarea class="recap-box" id="recapBox">${esc(changesText())}</textarea>
  </div>`;
  $("meetActs").innerHTML = `
    <button class="btn" id="copyRecap">Copy recap</button>
    ${deck.length ? `<button class="btn ghost" id="backToCards">Back to cards ▸</button>` : ""}
    <button class="btn ghost" id="endMeet">End meeting</button>`;
  $("copyRecap").addEventListener("click", () => {
    const box = $("recapBox"); box.select();
    (navigator.clipboard ? navigator.clipboard.writeText(box.value) : Promise.reject())
      .then(() => { $("copyRecap").textContent = "Copied ✓"; })
      .catch(() => { document.execCommand && document.execCommand("copy"); $("copyRecap").textContent = "Copied ✓"; });
  });
  if (deck.length) $("backToCards").addEventListener("click", showCard);
  $("endMeet").addEventListener("click", exitMeeting);
}
function exitMeeting() {
  saveMeetNote();
  focusMode = false;
  deck = [];
  $("meet").classList.remove("on");
  document.body.style.overflow = "";
  refresh();
}

// ---- wiring ----
function refresh() { kpis(); render(); updateTray(); }
loadPending();
filters();
refresh();
$("meetBtn").addEventListener("click", startMeeting);
$("addBtn").addEventListener("click", () => openEditor(null));
$("trayBtn").addEventListener("click", openTray);
$("meetExit").addEventListener("click", exitMeeting);
$("meetRecapBtn").addEventListener("click", () => showRecap(false));
document.querySelectorAll(".modal").forEach(m => m.addEventListener("click", e => { if (e.target === m) m.classList.remove("on"); }));
document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    $("editModal").classList.remove("on"); $("trayModal").classList.remove("on");
    if (focusMode && $("meet").classList.contains("on")) exitMeeting();
    return;
  }
  if (!$("meet").classList.contains("on") || inRecap) return;
  if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;
  if (e.key === " " || e.key === "ArrowRight") { e.preventDefault(); nextCard(true); }
  if (e.key === "s" || e.key === "S") { e.preventDefault(); nextCard(false); }
});
</script>
"""


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "dashboard.html")
    records = slim(fetch_all())
    team = sorted(set(TEAM_DEFAULTS) | {o for r in records for o in r["owners"]})
    html_page = (TEMPLATE
                 .replace("__DATA__", json.dumps(records, ensure_ascii=False))
                 .replace("__TEAM__", json.dumps(team, ensure_ascii=False))
                 .replace("__CATS__", json.dumps(CATEGORIES, ensure_ascii=False))
                 .replace("__ASOF__", date.today().strftime("%B %d, %Y"))
                 .replace("__BASE_URL__", BASE_URL))
    out.write_text(html_page, encoding="utf-8")
    print(f"wrote {out} ({len(records)} projects)")
