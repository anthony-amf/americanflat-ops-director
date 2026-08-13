# v1.5.0 — warehouse-scoped hourly labor rates (apply on the Mac)

**Why:** the validator kept every MSA hourly rate in one flat list, so $63.00
passed at any warehouse. Per the MSA hourly table, $63.00 is **South Carolina
physical inventory / stock consolidation only** — SC general labor is $53.55,
New Jersey is $53.55, Fontana is $59.8278. The bundled rate snapshot also still
carried SC labor at the old $51.00 card rate.

Nothing has been mis-paid because of this: of every invoice line the sweep has
ever checked at an hourly rate, there are only three — NJ at $53.55 (755985,
756179) and Fontana at $59.8278 (756527) — all correct for their site.

## Files to change

Canonical source is `~/.claude/skills/yusen-invoice-validator/`. The finished
files are in this repo at `skill-updates/v1.5.0/` — copy them over:

| Copy from (repo) | Copy to (Mac) |
|---|---|
| `skill-updates/v1.5.0/validate_rate_card.py` | `~/.claude/skills/yusen-invoice-validator/scripts/validate_rate_card.py` |
| `skill-updates/v1.5.0/rate-card-snapshot.json` | `~/.claude/skills/yusen-invoice-validator/references/rate-card-snapshot.json` |
| `skill-updates/v1.5.0/SKILL.md` | `~/.claude/skills/yusen-invoice-validator/SKILL.md` |
| `skill-updates/v1.5.0/CHANGELOG.md` | `~/.claude/skills/yusen-invoice-validator/CHANGELOG.md` |
| `skill-updates/v1.5.0/skill.toml` | `~/.claude/skills/yusen-invoice-validator/skill.toml` |

```bash
cd ~/americanflat-ops-director && git pull origin claude/msa-labor-hourly-rate-38slhl && \
  mkdir -p ~/skill-backup/2026-08-13 && \
  cp ~/.claude/skills/yusen-invoice-validator/scripts/validate_rate_card.py ~/skill-backup/2026-08-13/ && \
  cp ~/.claude/skills/yusen-invoice-validator/references/rate-card-snapshot.json ~/skill-backup/2026-08-13/ && \
  cp ~/.claude/skills/yusen-invoice-validator/SKILL.md ~/skill-backup/2026-08-13/ && \
  cp ~/.claude/skills/yusen-invoice-validator/CHANGELOG.md ~/skill-backup/2026-08-13/ && \
  cp ~/.claude/skills/yusen-invoice-validator/skill.toml ~/skill-backup/2026-08-13/
```

(The backup copies into a fresh dated folder first, so the originals are always
recoverable. Then copy the five new files over the source.)

## Edit 1 — `scripts/validate_rate_card.py`: split hourly out of the flat table

Hourly rates leave `MSA_LINE_RATES` and become per-warehouse tables. The missing
SC dray admin fee ($51.45) is added alongside Fontana's $52.8831 and NJ's $47.334.

**Remove** these three lines from `MSA_LINE_RATES`:

```python
    35.0: "hourly", 42.0: "hourly", 53.55: "hourly", 59.8278: "hourly", 63.0: "hourly",
    77.70: "hourly", 82.1166: "hourly", 47.1232: "hourly", 32.0: "hourly", 40.0: "hourly",
    56.82: "hourly (returns)", 0.42: "label", 0.45: "label", 0.92: "pack carton",
```

**Replace** with (the label rates stay, the hourly ones move out):

```python
    51.45: "dray admin SC",
    0.42: "label", 0.45: "label", 0.92: "pack carton",
```

**Add** immediately after the closing `}` of `MSA_LINE_RATES`:

```python
# Hourly labor is priced PER SITE, so it can't live in the flat table above: the
# MSA charges the same role differently by warehouse, and a rate that is on
# schedule at one DC is off-card at another. $63.00 is the clearest case — it is
# only South Carolina physical inventory / stock consolidation; billed at NJ or
# Fontana it is not an MSA rate at all. Keyed by the WAREHOUSE_MAP canonical key.
# Source: MSA "Hourly labor rates" table, mirrored on the Notion rate card.
MSA_HOURLY_RATES = {
    "fontana": {
        35.0: "material handler", 42.0: "clerical", 47.1232: "QA",
        59.8278: "general labor / physical inventory / stock consolidation",
        82.1166: "salaried supervisor",
    },
    "new_jersey": {
        35.0: "material handler", 42.0: "clerical",
        53.55: "general labor / physical inventory / stock consolidation",
        77.70: "salaried supervisor",
    },
    "south_carolina": {
        32.0: "material handler", 40.0: "clerical", 53.55: "general labor",
        63.0: "physical inventory / stock consolidation",
        77.70: "salaried supervisor",
    },
}
# Hourly lines valid at every US site: national MSA lines plus rates verified
# against real invoices before the per-site table existed (kept so the 1.4.0
# verdicts don't regress).
MSA_HOURLY_RATES_ALL = {185.0: "IT", 56.82: "returns (legacy verified rate)"}
SITE_LABEL = {"fontana": "Fontana", "new_jersey": "New Jersey",
              "south_carolina": "South Carolina"}
```

## Edit 2 — `_rate_candidates` learns the warehouse

The 2dp-truncation matching is pulled into its own helper so both the on-schedule
and the off-card hourly tables reuse it. `_rate_candidates` now takes `wh` and
returns a `flag` (`None` / `"disputed"` / `"off_card"`) instead of a boolean.
Two new helpers build the per-site tables. See
`skill-updates/v1.5.0/validate_rate_card.py` lines 132–206 (`_fmt_rate`,
`_rate_match_priority`, `_hourly_table`, `_off_site_hourly_table`,
`_rate_candidates`) — that block replaces the old `_rate_candidates` in full.

Ordering matters and is deliberate: disputed rates are checked first, then the
flat MSA table, then this site's hourly schedule, then other sites' — so a
legitimate line always wins over an off-card interpretation of the same number.

## Edit 3 — `_parse_charge_lines` takes and uses `wh`

Signature gains `wh: Optional[str] = None`; every `_rate_candidates(rate)` call
becomes `_rate_candidates(rate, wh)`; the `disp` boolean becomes `flag`; each
parsed line now carries both `disputed` and `off_card`. The VAS ad-hoc job-rate
escape hatch is unchanged in behaviour but can no longer swallow an off-card
rate, because the off-card table matches earlier in the same pass.

## Edit 4 — `apply_line_pass` reports off-card labor

- `wh = result.get("warehouse")` is read once and passed to `_parse_charge_lines`.
- The scanned/OCR fallback runs the same off-card check, so a mis-keyed rate on
  a scanned SC-style work order is caught too.
- New `off_card` list, and a new branch after the `disputed` branch that stamps
  `needs_detail` and prints the site's own hourly schedule in the report card.

Deliberate: an off-card rate is **not** `disputed`. `disputed` is reserved for the
enumerated MSA conflicts (AF-7 pack-out, AF-9 wrap, every-pick billing) that we
short-pay. A wrong-site labor rate is a rebill request — hold it at
`needs_detail`, ask Yusen what the work was, pay it if the answer fits the site.

## Edit 5 — `references/rate-card-snapshot.json`

- `admin_vas.south_carolina.vas_hourly`: **51.0 → 53.55** (51.00 was the pre-June
  card rate), with a `_vas_hourly_note` recording the correction.
- New top-level `hourly_labor` block mirroring the MSA's per-site role table, so
  the fallback snapshot carries the same rates as the code.

## Edit 6 — version, changelog, SKILL.md

- `skill.toml`: `version = "1.4.0"` → `"1.5.0"`.
- `CHANGELOG.md`: new 1.5.0 entry at the top.
- `SKILL.md`: new "Hourly labor is checked per warehouse (v1.5.0)" paragraph in
  the line-level pass section.

## Verify after applying

Run this from the skill directory — it needs no BigQuery, no network, no PDFs.
It should print 18 PASS and `failures: 0`:

```bash
cd ~/.claude/skills/yusen-invoice-validator && python3 - <<'EOF'
import importlib.util, sys, types
g=types.ModuleType("google"); c=types.ModuleType("google.cloud"); b=types.ModuleType("google.cloud.bigquery")
b.Client=object; c.bigquery=b; g.cloud=c
sys.modules.update({"google":g,"google.cloud":c,"google.cloud.bigquery":b})
spec=importlib.util.spec_from_file_location("v","scripts/validate_rate_card.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
cases=[("SC $63 phys inv","PHYSICAL INVENTORY 8 @ 63.00 $ 504.00",504.00,"vas","south_carolina","ok"),
("NJ $63","PHYSICAL INVENTORY 8 @ 63.00 $ 504.00",504.00,"vas","new_jersey","OFF-CARD"),
("Fontana $63","STOCK CONSOL 8 @ 63.00 $ 504.00",504.00,"vas","fontana","OFF-CARD"),
("NJ 53.55","VAS LABOR 10 @ 53.55 $ 535.50",535.50,"vas","new_jersey","ok"),
("SC 53.55","VAS LABOR 10 @ 53.55 $ 535.50",535.50,"vas","south_carolina","ok"),
("Fontana 59.82 trunc","BACK OFFICE 40 @ 59.82 $ 2,393.11",2393.11,"vas","fontana","ok"),
("Fontana 53.55","VAS LABOR 10 @ 53.55 $ 535.50",535.50,"vas","fontana","OFF-CARD"),
("SC 32 mat handler","MATERIAL HANDLER 6 @ 32.00 $ 192.00",192.00,"vas","south_carolina","ok"),
("NJ 32 (SC rate)","MATERIAL HANDLER 6 @ 32.00 $ 192.00",192.00,"vas","new_jersey","OFF-CARD"),
("SC 51.45 dray","DRAY ADMIN 3 @ 51.45 $ 154.35",154.35,"vas","south_carolina","ok"),
("all-site IT 185","IT SUPPORT 2 @ 185.00 $ 370.00",370.00,"vas","new_jersey","ok"),
("legacy returns 56.82","RETURNS 5 @ 56.82 $ 284.10",284.10,"vas","fontana","ok"),
("unknown wh $63","PHYS INV 8 @ 63.00 $ 504.00",504.00,"vas",None,"ok"),
("NJ storage 4.34","2346 PALLETS ON HAND @ 4.34/PALLET $ 10,181.64",10181.64,"storage","new_jersey","ok"),
("NJ wrap 4.347","121 STRETCHWRAP STD @ 4.34 $ 525.99",525.99,"sml parcel/ltl","new_jersey","DISPUTED"),
("Fontana pack-out .966","4000 PACK OUT @ 0.966 $ 3,864.00",3864.00,"sml parcel/ltl","fontana","DISPUTED"),
("ecom order 2.2264","5437 E-COMMERCE @ 2.2264 $ 12,104.94",12104.94,"sml parcel/ltl","new_jersey","ok"),
("SC ad-hoc 47.50","SPECIAL PROJECT 4 @ 47.50 $ 190.00",190.00,"vas","south_carolina","ok")]
fails=0
for name,text,amt,t,wh,want in cases:
    ls=m._parse_charge_lines(text,amt,t,wh)
    got="none" if not ls else ("DISPUTED" if ls[0]["disputed"] else ("OFF-CARD" if ls[0]["off_card"] else "ok"))
    fails += got!=want
    print(f"{'PASS' if got==want else 'FAIL':4} {name:24} want={want:9} got={got:9} {ls[0]['label'] if ls else ''}")
print("\nfailures:", fails)
EOF
```

Then re-run the known invoices per the house rule and confirm no status moves:

```bash
export STEDI_API_KEY=<key> && cd ~/.claude/skills/yusen-invoice-validator && \
  python3 scripts/validate_rate_card.py 752857 && \
  python3 scripts/validate_rate_card.py 752738 && \
  python3 scripts/validate_rate_card.py --list-all --limit 400
```

(No `--write` on that sweep — it reports without touching the table. Add
`--write` only once the statuses look right.)

## Then repackage and commit

1. `cd "<skill-creator dir>" && python3 -m scripts.package_skill ~/.claude/skills/yusen-invoice-validator`
2. Copy the produced `.skill` to `~/Downloads/` and to this repo, commit both the
   package and `skill-updates/v1.5.0/` to `main`.
3. Publishing to `americanflat/skill-yusen-invoice-validator` is a separate job —
   the org repo is on v1.1.0 (per OPEN-ITEMS.md) while local source is now 1.5.0.
   Use the `skill-pr-helper` skill when you want to catch it up; it has to run
   from the Mac (cloud sessions can't reach `americanflat/*`).

## Worth knowing

Settled rows are skipped before the PDF is even fetched, so this check does not
re-examine invoices already stamped `valid` or `disputed`. That's the 1.3.0
stickiness rule and it stays. The audit above (three hourly lines, all correct)
is what covers the back catalogue; this change is about what gets billed next.
