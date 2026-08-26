#!/usr/bin/env python3
"""
Look up Americanflat products to answer customer-experience questions.

Reads cx-bot/product_kb.json (built by build_kb.py) and answers by exact
identifier or by free-text search, printing only facts the catalogue actually
supports -- with any data conflicts shown up front so an agent never quotes a
number the feed disagrees with.

Search weights titles far above descriptions on purpose: 56% of descriptions in
the feed are recycled boilerplate shared across hundreds of products, and 553
of them contradict their own title's size.

Usage:
    python3 cx-bot/cx_lookup.py "black 11x14 frame with a mat"
    python3 cx-bot/cx_lookup.py --upc 810131993696
    python3 cx-bot/cx_lookup.py --id shopify_US_7274302898246_41006041464902
    python3 cx-bot/cx_lookup.py "shower curtain" --in-stock --limit 5
    python3 cx-bot/cx_lookup.py --size 11x14 --color black --category "Picture Frame"
    python3 cx-bot/cx_lookup.py "gallery wall set" --json
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

KB_PATH = Path(__file__).resolve().parent / "product_kb.json"

STOP = {
    "a", "an", "the", "is", "are", "do", "does", "did", "i", "my", "me", "you",
    "it", "this", "that", "for", "of", "in", "on", "with", "and", "or", "to",
    "can", "what", "which", "how", "much", "have", "has", "was", "were", "be",
    "customer", "asking", "asked", "wants", "want", "need", "needs", "please",
    "size", "sized", "come", "comes", "coming", "get", "got", "any", "there",
    "about", "would", "will", "if", "at", "from", "one", "does",
}

SIZE_RE = re.compile(r"\b(\d{1,3}(?:\.\d)?)\s*[xX×]\s*(\d{1,3}(?:\.\d)?)\b")
PACK_RE = re.compile(r"\b(\d{1,2})\s*[- ]?\s?pack\b", re.I)
SET_RE = re.compile(r"\b(\d{1,2})\s*(?:frames|piece|pc)\b", re.I)
DIGITS_RE = re.compile(r"^\d{8,14}$")

COLOR_WORDS = {
    "black", "white", "gold", "silver", "natural", "walnut", "oak", "driftwood",
    "gray", "grey", "brown", "cherry", "maple", "gunmetal", "espresso",
    "bronze", "copper", "ivory", "beige", "sage", "navy", "charcoal", "clear",
    "turquoise",
}


def load_kb(path=KB_PATH):
    if not Path(path).exists():
        sys.exit(f"knowledge base not found at {path}\n"
                 f"build it first:  python3 cx-bot/build_kb.py")
    return json.loads(Path(path).read_text())


def norm_size(a, b):
    def f(v):
        v = float(v)
        return str(int(v)) if v == int(v) else str(v)
    return f"{f(a)}x{f(b)}"


def tokens(text):
    return [t for t in re.split(r"[^a-z0-9.]+", (text or "").lower())
            if t and t not in STOP and len(t) > 1]


def find_exact(kb, needle):
    """Match a UPC/GTIN, SKU, offer id, Shopify variant id or product URL."""
    n = needle.strip().lower()
    bare = n.lstrip("0")
    out = []
    for p in kb["products"]:
        gtin = (p.get("gtin") or "").lower()
        if gtin and (gtin == n or gtin.lstrip("0") == bare):
            out.append(p); continue
        if (p.get("sku") or "").lower() == n:
            out.append(p); continue
        if p["id"].lower() == n or n in p["id"].lower().split("_")[-1:]:
            out.append(p); continue
        if n.startswith("http") and (p.get("url") or "").lower() == n.split("?")[0]:
            out.append(p)
    return out


def generic_tokens(products, threshold=0.15):
    """Words so common in the catalogue that matching them proves nothing.

    'frame', 'glass', 'wall' and friends appear in most titles, so a query that
    only brushes those has not actually identified a product. Derived from the
    data rather than hard-coded so it keeps up as the catalogue changes.
    """
    n = len(products) or 1
    df = Counter()
    for p in products:
        df.update(set(tokens(p["title"])))
    return {t for t, c in df.items() if c / n >= threshold}


def score(p, qt, want_size, want_pack, want_colors, generic=frozenset()):
    """Return (score, strength) where strength counts real evidence hits.

    strength drives the confidence warning: a keyword brushing a description,
    or hitting a catalogue-wide word like 'frame', is not evidence that this is
    the product the customer means.
    """
    title_set = set(tokens(p["title"]))
    desc_set = set(tokens(p.get("description"))) if not p.get(
        "description_is_boilerplate") else set()
    cat_set = set(tokens(p.get("category")))

    s, strength = 0.0, 0
    for t in qt:
        weight = 0 if t in generic else 1     # generic words score, never prove
        if t in title_set:
            s += 2.0 if t in generic else 6.0; strength += weight
        elif any(w.startswith(t) for w in title_set) and len(t) > 3:
            s += 3.0; strength += weight
        elif t in cat_set:
            s += 4.0; strength += weight
        elif t in desc_set:
            s += 0.6                      # descriptions are weak evidence
    if want_size:
        if p.get("size") == want_size:
            s += 14.0; strength += 2      # an exact size match is strong
        else:
            s -= 3.0
    if want_pack:
        if p.get("pack") == want_pack:
            s += 8.0; strength += 1
        else:
            s -= 2.0
    if want_colors:
        pc = (p.get("color") or "").lower()
        if pc and any(c in pc for c in want_colors):
            s += 7.0; strength += 1
    if s > 0 and p.get("in_stock"):
        s += 0.4        # tie-break among things that already matched, never
                        # a match on its own -- otherwise every in-stock
                        # product scores above zero and counts as a hit
    return s, strength


def search(kb, query, limit=5, size=None, color=None, category=None,
           in_stock=False, pack=None):
    qt = tokens(query)
    want_size = size
    if not want_size:
        m = SIZE_RE.search(query or "")
        if m:
            want_size = norm_size(m.group(1), m.group(2))
    want_pack = pack
    if not want_pack:
        m = PACK_RE.search(query or "") or SET_RE.search(query or "")
        if m:
            want_pack = int(m.group(1))
    want_colors = ([color.lower()] if color
                   else [t for t in qt if t in COLOR_WORDS])

    # drop size/pack tokens from keyword scoring; they are handled as boosts
    qt = [t for t in qt if not SIZE_RE.fullmatch(t) and not t.isdigit()]

    pool = kb["products"]
    if category:
        pool = [p for p in pool if category.lower() in (p.get("category") or "").lower()]
    if in_stock:
        pool = [p for p in pool if p.get("in_stock")]
    if size:
        pool = [p for p in pool if p.get("size") == size]

    generic = generic_tokens(kb["products"])

    # Browse mode: filters but no search words (e.g. --category alone). Every
    # product that passed the filters is a legitimate result, so list them
    # rather than scoring them all to zero and reporting nothing.
    if not qt and not want_size and not want_pack and not want_colors:
        return pool[:limit], True

    scored = []
    for p in pool:
        sc, strength = score(p, qt, want_size, want_pack, want_colors, generic)
        if sc > 0:
            scored.append((sc, strength, p))
    scored.sort(key=lambda t: (-t[0], t[2]["title"]))
    top = scored[:limit]

    # Confidence: at least two distinctive signals should land on the winner,
    # and a size the customer named must actually match, or we are guessing.
    specific = [t for t in qt if t not in generic]
    needed = 2 if len(specific) > 1 else 1
    confident = bool(top) and top[0][1] >= needed
    if want_size and top and top[0][2].get("size") != want_size:
        confident = False
    return [p for _, _, p in top], confident


def fmt(p, verbose=False):
    L = []
    stock = "IN STOCK" if p.get("in_stock") else f"OUT OF STOCK ({p.get('availability')})"
    L.append(f"{p['title']}")
    L.append(f"  {p.get('category') or '?'} | {stock}")

    price = p.get("current_price")
    if price is not None:
        line = f"  price: ${price:.2f}"
        if p.get("list_price"):
            line += f"  (list ${p['list_price']:.2f})"
        L.append(line)
    else:
        L.append("  price: not in the feed -- check Shopify")

    facts = []
    if p.get("size"):
        facts.append(f"size {p['size']} in")
    if p.get("color"):
        facts.append(p["color"])
    if p.get("pack", 1) > 1:
        facts.append(f"{p['pack']}-pack")
    for v in (p.get("features") or {}).values():
        facts.append(v)
    if facts:
        L.append("  " + " | ".join(facts))

    ids = []
    if p.get("gtin"):
        ids.append(f"UPC {p['gtin']}")
    if p.get("sku"):
        ids.append(f"SKU {p['sku']}")
    if ids:
        L.append("  " + " | ".join(ids))
    if p.get("url"):
        L.append(f"  {p['url']}")

    for c in p.get("conflicts") or []:
        marker = "[!]" if c.get("level") == "block" else "[i]"
        L.append(f"  {marker} {c.get('message', c)}")
    if p.get("description_is_boilerplate"):
        L.append("  [!] description is shared boilerplate -- do not quote it as a spec")
    if verbose and p.get("description"):
        L.append(f"  desc: {p['description'][:300]}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="*", help="free-text question or product words")
    ap.add_argument("--upc", help="exact UPC/GTIN lookup")
    ap.add_argument("--sku", help="exact SKU lookup")
    ap.add_argument("--id", dest="ident", help="offer id / Shopify variant id / URL")
    ap.add_argument("--size", help='exact size filter, e.g. 11x14')
    ap.add_argument("--color")
    ap.add_argument("--category")
    ap.add_argument("--pack", type=int)
    ap.add_argument("--in-stock", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verbose", action="store_true", help="include description text")
    ap.add_argument("--kb", default=str(KB_PATH))
    args = ap.parse_args()

    kb = load_kb(args.kb)
    query = " ".join(args.query)

    hits, how = [], ""
    for needle, label in ((args.upc, "UPC"), (args.sku, "SKU"), (args.ident, "id")):
        if needle:
            hits, how = find_exact(kb, needle), f"exact {label} match"
            break

    if not hits and not (args.upc or args.sku or args.ident):
        if query and DIGITS_RE.match(query.strip()):
            hits, how = find_exact(kb, query.strip()), "exact UPC match"
        if not hits and (query or args.size or args.color or args.category
                         or args.in_stock or args.pack is not None):
            hits, confident = search(kb, query, limit=args.limit, size=args.size,
                                     color=args.color, category=args.category,
                                     in_stock=args.in_stock, pack=args.pack)
            how = ("best keyword matches" if confident else
                   "WEAK MATCH -- nothing in the catalogue clearly matches this")
        elif not hits and not query and not args.in_stock and args.pack is None:
            ap.error("give a query or one of "
                     "--upc/--sku/--id/--size/--color/--category/--in-stock")

    if args.json:
        print(json.dumps({"how": how, "count": len(hits), "results": hits}, indent=1))
        return

    print(f"catalogue built {kb['generated_at']} | {kb['product_count']} products")
    if not hits:
        print(f"\nNo match for {query or args.upc or args.sku or args.ident!r}.")
        print("Not in the Google feed does not mean discontinued -- check Shopify "
              "admin before telling a customer it does not exist.")
        return
    print(f"{how} -- {len(hits)} result(s)\n")
    if how.startswith("WEAK"):
        print("Treat these as guesses. Confirm the product with the customer "
              "(order number, UPC or a photo) before quoting anything, and say "
              "you are checking rather than naming one of these.\n")
    for i, p in enumerate(hits, 1):
        print(f"{i}. {fmt(p, verbose=args.verbose)}\n")


if __name__ == "__main__":
    sys.exit(main())
