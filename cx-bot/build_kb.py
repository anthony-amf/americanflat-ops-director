#!/usr/bin/env python3
"""
Build the Americanflat CX product knowledge base from BigQuery.

Source: americanflat.merchant_center.Products_136085689 (the Google Merchant
Center feed) -- the only customer-facing product catalogue we hold. Reads the
most recent snapshot, applies the correctness rules documented below, and
writes cx-bot/product_kb.json.

WHY THESE RULES EXIST (all measured against the 2026-08-25 snapshot, 6,022 rows):

1. PRICE. `sale_price` matches what customers actually paid on Shopify 86% of
   the time; `price` matches 1.4%. `price` is the compare-at / list price.
   So current_price = sale_price or price, and list_price is kept separately.

2. SIZE COMES FROM THE TITLE, NEVER THE DESCRIPTION. 639 products (11%) have a
   description quoting a different size than their own title -- recycled
   marketing copy. One description is shared by 288 products.

3. TWO US FEEDS OVERLAP. feed_label 'US' (3,768 rows) and 'US2' (2,252) share
   1,773 offer_ids and disagree: 1,772 titles, 152 prices, 165 stock states.
   Where they disagree on price, 'US' matched real Shopify sales 11 times and
   'US2' zero, so 'US' wins. Disagreements are recorded, not hidden -- the bot
   must refuse to state a firm price/stock when a conflict is flagged.

4. product_type is free text ('Picture Frame' / 'Picture Frames' /
   'PictureFrames' / 'Frames'), so it is normalised through CATEGORY_MAP.

Usage:
    python3 cx-bot/build_kb.py                  # writes cx-bot/product_kb.json
    python3 cx-bot/build_kb.py --out other.json
    python3 cx-bot/build_kb.py --report         # also print a data-quality report
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT = "americanflat"
TABLE = "americanflat.merchant_center.Products_136085689"
HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "product_kb.json"

# Feed preference: earlier entries win when the same offer_id appears twice.
FEED_PRIORITY = ["US", "US2"]

QUERY = f"""
SELECT offer_id, feed_label, title, description, link, image_link,
       price.value AS list_price, sale_price.value AS sale_price,
       availability, gtin, mpn, product_type, brand
FROM `{TABLE}`
WHERE product_data_timestamp = (SELECT MAX(product_data_timestamp) FROM `{TABLE}`)
"""

# --- normalisation tables -------------------------------------------------

CATEGORY_MAP = {
    "picture frame": "Picture Frame", "picture frames": "Picture Frame",
    "pictureframes": "Picture Frame", "frames": "Picture Frame",
    "frame": "Picture Frame", "molding picture frame": "Picture Frame",
    "hinged picture frame": "Picture Frame",
    "floating aluminum & plexiglass picture frame": "Picture Frame",
    "magneticpictureframes": "Picture Frame",
    "instant photo frame": "Picture Frame",
    "poster frame": "Poster Frame", "poster frames": "Poster Frame",
    "collage picture frame": "Collage Frame", "collage frame": "Collage Frame",
    "gallery wall frames": "Gallery Wall Set",
    "shadow box frame": "Shadow Box", "shadow box": "Shadow Box",
    "jersey display case": "Shadow Box", "display case": "Shadow Box",
    "coin display case": "Shadow Box", "baseball card display": "Shadow Box",
    "kids art frame": "Kids Art Frame",
    "diploma frame": "Diploma Frame", "graduation frame": "Diploma Frame",
    "album frame": "Album Frame",
    "framed prints": "Framed Print",
    "shower curtains": "Shower Curtain", "shower curtain": "Shower Curtain",
    "blanket": "Blanket", "blankets": "Blanket",
    "mirrors": "Mirror", "mirror": "Mirror",
    "displayeasels": "Easel / Stand", "stand": "Easel / Stand",
    "wall shelves & ledges": "Wall Shelf",
    "hanging photo display": "Photo Display",
    "art set": "Art Set",
}

COLORS = [
    "charcoal black", "rose gold", "matte black", "distressed white",
    "black", "white", "gold", "silver", "natural", "walnut", "oak",
    "driftwood", "gray", "grey", "brown", "cherry", "maple", "gunmetal",
    "espresso", "bronze", "copper", "ivory", "beige", "sage", "navy",
    "turquoise blue", "clear",
]

SIZE_RE = re.compile(r"(\d{1,3}(?:\.\d)?)\s*[xX×]\s*(\d{1,3}(?:\.\d)?)")
PACK_RE = re.compile(r"\b(\d{1,2})\s*[- ]?\s*pack\b", re.I)
SET_RE = re.compile(r"\b(\d{1,2})\s*(?:frames|piece|pc)\b", re.I)


def _norm_size(a, b):
    def f(v):
        v = float(v)
        return str(int(v)) if v == int(v) else str(v)
    return f"{f(a)}x{f(b)}"


def title_size(title):
    """Size of the variant the customer bought, preferring the variant segment."""
    vt = variant_text(title)
    if vt:
        m = SIZE_RE.search(vt)
        if m:
            return _norm_size(m.group(1), m.group(2))
    m = SIZE_RE.search(title or "")
    return _norm_size(m.group(1), m.group(2)) if m else None


def parent_size(title):
    """Size named in the product-name part, which can disagree with the variant."""
    vt = variant_text(title)
    if not vt:
        return None
    head = (title or "")[: len(title) - len(vt)]
    m = SIZE_RE.search(head)
    return _norm_size(m.group(1), m.group(2)) if m else None


def sizes_in(text):
    return {_norm_size(a, b) for a, b in SIZE_RE.findall(text or "")}


def variant_text(title):
    """Isolate the Shopify variant options at the end of a feed title.

    Feed titles are "<product name> <opt> / <opt> / <opt>", and the product
    name often carries the PARENT's size/colour, not the one the customer
    bought -- e.g. "8.5x11 | Walnut | Picture Frame | Streamline 24x24 / Black
    / 1 Pack" is a 24x24 Black frame. Everything from the last "|" of the first
    slash-segment onward is the variant, so that is what we read.
    Returns None when the title carries no " / " variant segment.
    """
    if " / " not in (title or ""):
        return None
    parts = title.split(" / ")
    head = parts[0].split("|")[-1]
    return " / ".join([head] + parts[1:]).strip()


def _color_in(text):
    t = (text or "").lower()
    for c in COLORS:                      # longest-first via ordering above
        if re.search(rf"\b{re.escape(c)}\b", t):
            return c.title()
    return None


def extract_color(title):
    """Variant colour wins over the parent colour in the product name."""
    return _color_in(variant_text(title)) or _color_in(title)


def extract_pack(title):
    for text in (variant_text(title), title):
        if not text:
            continue
        m = PACK_RE.search(text) or SET_RE.search(text)
        if m:
            return int(m.group(1))
    return 1


def extract_features(title):
    """Only ever read the TITLE -- descriptions are recycled (rule 2)."""
    t = (title or "").lower()
    f = {}
    if re.search(r"\bmats?\b|matted|with mat", t):
        f["mat"] = "Mat included (per title)"
    if "tempered" in t:
        f["glazing"] = "Tempered shatter-resistant glass"
    elif "plexiglass" in t or "plexi" in t:
        f["glazing"] = "Plexiglass"
    elif "acrylic" in t:
        f["glazing"] = "Acrylic"
    elif "shatter-resistant" in t or "shatter resistant" in t:
        f["glazing"] = "Shatter-resistant"
    if re.search(r"horizontal or vertical|vertical or horizontal", t):
        f["orientation"] = "Hangs horizontally or vertically"
    elif "vertical format" in t:
        f["orientation"] = "Vertical format"
    elif "horizontal format" in t:
        f["orientation"] = "Horizontal format"
    if "hanging hardware" in t:
        f["hardware"] = "Hanging hardware included"
    if "tabletop" in t and "wall" in t:
        f["display"] = "Tabletop or wall"
    elif "tabletop" in t:
        f["display"] = "Tabletop"
    if "lockable" in t or "with lock" in t:
        f["lock"] = "Lockable"
    return f


# --- BigQuery access (works on the Mac via ADC, in cloud via the proxy) ---

def run_query_client():
    from google.cloud import bigquery       # noqa: local import, Mac path
    client = bigquery.Client(project=PROJECT)
    return [dict(r) for r in client.query(QUERY).result()]


def _curl(url, method="GET", body=None):
    cmd = ["curl", "-sS", "-X", method, url, "-H", "Content-Type: application/json"]
    if body:
        cmd += ["-d", json.dumps(body)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"curl failed: {res.stderr[:300]}")
    return json.loads(res.stdout)


def run_query_rest():
    """Cloud-session path: the agent proxy injects BigQuery credentials."""
    base = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}"
    d = _curl(f"{base}/queries", "POST",
              {"query": QUERY, "useLegacySql": False,
               "maxResults": 2000, "timeoutMs": 180000})
    if "error" in d:
        raise RuntimeError(json.dumps(d["error"])[:400])
    fields = [f["name"] for f in d["schema"]["fields"]]
    rows = list(d.get("rows", []))
    total = int(d.get("totalRows", 0))
    job, loc = d["jobReference"]["jobId"], d["jobReference"].get("location", "US")
    token = d.get("pageToken")
    while len(rows) < total:
        url = f"{base}/queries/{job}?maxResults=2000&location={loc}"
        if token:
            url += f"&pageToken={token}"
        p = _curl(url)
        if "error" in p or not p.get("rows"):
            break
        rows += p["rows"]
        token = p.get("pageToken")
        if not token:
            break
    return [dict(zip(fields, (c["v"] for c in r["f"]))) for r in rows]


def fetch_rows():
    try:
        return run_query_client()
    except Exception:
        return run_query_rest()


# --- build ----------------------------------------------------------------

def num(v):
    if v in (None, ""):
        return None
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def build(rows, desc_chars=300):
    by_feed = {}
    for r in rows:
        by_feed.setdefault(r["offer_id"], {})[r.get("feed_label")] = r

    # descriptions reused across many products are marketing boilerplate
    desc_counts = Counter((r.get("description") or "")[:200] for r in rows
                          if r.get("description"))

    products, stats = [], Counter()
    for offer_id, feeds in by_feed.items():
        primary = next((feeds[f] for f in FEED_PRIORITY if f in feeds),
                       next(iter(feeds.values())))
        others = [v for k, v in feeds.items() if v is not primary]

        title = (primary.get("title") or "").strip()
        desc = (primary.get("description") or "").strip()
        size = title_size(title)
        d_sizes = sizes_in(desc)

        conflicts = []
        psize = parent_size(title)
        if psize and size and psize != size:
            conflicts.append({"level": "block", "message":
                f"the title also names {psize} (the parent listing's size); the "
                f"variant actually sold here is {size}"})
            stats["variant_size_mismatch"] += 1
        if size and d_sizes and size not in d_sizes:
            conflicts.append({"level": "block", "message":
                f"description quotes {', '.join(sorted(d_sizes))} but the title "
                f"says {size} -- trust {size}"})
            stats["desc_size_conflict"] += 1

        cur = num(primary.get("sale_price")) or num(primary.get("list_price"))
        lst = num(primary.get("list_price"))
        avail = primary.get("availability")

        for o in others:
            o_cur = num(o.get("sale_price")) or num(o.get("list_price"))
            if o_cur is not None and cur is not None and abs(o_cur - cur) >= 0.01:
                conflicts.append({"level": "block", "message":
                    f"feed {o.get('feed_label')} prices this at ${o_cur:.2f} "
                    f"vs ${cur:.2f} -- verify before quoting a price"})
                stats["price_conflict"] += 1
            if o.get("availability") != avail:
                conflicts.append({"level": "block", "message":
                    f"feed {o.get('feed_label')} says '{o.get('availability')}' "
                    f"but feed {primary.get('feed_label')} says '{avail}' "
                    f"-- verify stock before promising it"})
                stats["stock_conflict"] += 1

        boiler = desc_counts.get(desc[:200], 0)
        raw_type = (primary.get("product_type") or "").strip()
        category = CATEGORY_MAP.get(raw_type.lower(), raw_type or "Uncategorised")

        p = {
            "id": offer_id,
            "title": title,
            "category": category,
            "size": size,
            "color": extract_color(title),
            "pack": extract_pack(title),
            "features": extract_features(title),
            "current_price": cur,
            "list_price": lst if lst and cur and lst > cur else None,
            "in_stock": avail == "in stock",
            "availability": avail,
            "gtin": primary.get("gtin"),
            "sku": primary.get("mpn"),
            "url": (primary.get("link") or "").split("?")[0] or None,
            "image": primary.get("image_link"),
            "feeds": sorted(feeds.keys()),
            "conflicts": conflicts,
            "description": desc[:desc_chars],
            "description_is_boilerplate": boiler > 5,
        }
        products.append(p)
        stats["total"] += 1
        if not p["in_stock"]:
            stats["out_of_stock"] += 1
        if boiler > 5:
            stats["boilerplate_desc"] += 1
        if any(c["level"] == "block" for c in conflicts):
            stats["products_with_blocking_defect"] += 1
        if not size:
            stats["no_size"] += 1

    # A UPC is NOT a unique key in this feed: 1,036 UPCs are reused across
    # 2,665 products (one appears on 7). Flag it so no one resolves a customer's
    # UPC to a single product without confirming.
    gtin_counts = Counter(p["gtin"] for p in products if p.get("gtin"))
    for p in products:
        n = gtin_counts.get(p.get("gtin"), 0)
        p["upc_shared_with"] = n - 1 if n > 1 else 0
        if p["upc_shared_with"]:
            p["conflicts"].append({"level": "note", "message":
                f"UPC {p['gtin']} is also on {p['upc_shared_with']} other "
                f"product(s) -- confirm which one the customer has"})
    stats["shared_upc_products"] = sum(1 for p in products if p["upc_shared_with"])

    products.sort(key=lambda p: (p["category"], p["title"]))
    kb = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": TABLE,
        "feed_priority": FEED_PRIORITY,
        "product_count": len(products),
        "stats": dict(stats),
        "products": products,
    }
    return kb


def report(kb):
    s = kb["stats"]
    print("\n=== Americanflat CX knowledge base ===")
    print(f"products (deduped)        : {s.get('total', 0)}")
    print(f"out of stock              : {s.get('out_of_stock', 0)}")
    print(f"no size in title          : {s.get('no_size', 0)}")
    print(f"recycled/boilerplate desc : {s.get('boilerplate_desc', 0)}")
    print("\n--- listing defects worth fixing ---")
    print(f"description contradicts title size : {s.get('desc_size_conflict', 0)}")
    print(f"US vs US2 price disagreement       : {s.get('price_conflict', 0)}")
    print(f"US vs US2 stock disagreement       : {s.get('stock_conflict', 0)}")
    print(f"variant size != parent title size  : {s.get('variant_size_mismatch', 0)}")
    print(f"products sharing a UPC with another: {s.get('shared_upc_products', 0)}  (advisory)")
    print(f"PRODUCTS WITH A BLOCKING DEFECT    : {s.get('products_with_blocking_defect', 0)}")
    cats = Counter(p["category"] for p in kb["products"])
    print("\n--- categories ---")
    for c, n in cats.most_common(12):
        print(f"  {n:>5}  {c}")


def write_defects(kb, path):
    """Export the blocking listing defects as a CSV for merchandising to fix.

    These are the errors that make the catalogue unsafe to quote from, so
    fixing them at the source is what actually improves CX answers.
    """
    import csv
    rows = []
    for p in kb["products"]:
        blocking = [c["message"] for c in p.get("conflicts") or []
                    if c.get("level") == "block"]
        for m in blocking:
            if "parent listing's size" in m:
                kind = "variant size vs title size"
            elif "description quotes" in m:
                kind = "description contradicts title size"
            elif "prices this at" in m:
                kind = "feed price disagreement"
            elif "verify stock" in m:
                kind = "feed stock disagreement"
            else:
                kind = "other"
            rows.append({
                "defect": kind, "detail": m, "title": p["title"],
                "size": p.get("size") or "", "category": p["category"],
                "upc": p.get("gtin") or "", "sku": p.get("sku") or "",
                "price": p.get("current_price") or "",
                "in_stock": "yes" if p.get("in_stock") else "no",
                "url": p.get("url") or "", "offer_id": p["id"],
            })
    rows.sort(key=lambda r: (r["defect"], r["title"]))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    counts = Counter(r["defect"] for r in rows)
    print(f"wrote {path} ({len(rows)} defects across "
          f"{len({r['offer_id'] for r in rows})} products)")
    for k, n in counts.most_common():
        print(f"    {n:>5}  {k}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--desc-chars", type=int, default=300)
    ap.add_argument("--defects", nargs="?", const=str(HERE / "listing-defects.csv"),
                    help="also export blocking listing defects as CSV")
    args = ap.parse_args()

    print("querying BigQuery for the latest Merchant Center snapshot ...")
    rows = fetch_rows()
    print(f"  {len(rows)} feed rows")
    kb = build(rows, desc_chars=args.desc_chars)
    out = Path(args.out)
    out.write_text(json.dumps(kb, indent=1))
    size_mb = out.stat().st_size / 1_048_576
    print(f"wrote {out} ({kb['product_count']} products, {size_mb:.1f} MB)")
    if args.report:
        report(kb)
    if args.defects:
        write_defects(kb, args.defects)


if __name__ == "__main__":
    sys.exit(main())
