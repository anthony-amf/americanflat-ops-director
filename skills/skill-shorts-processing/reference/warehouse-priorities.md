# Warehouse Routing Reference

Detailed reference for the warehouse routing logic, including edge cases and the substitution SKU rules.

## Warehouse global priority

SC → Fontana → NJ. This is the priority order regardless of origin warehouse. The origin is always skipped.

| Priority | Warehouse | Stock column |
|---|---|---|
| 1st | South Carolina (SC) | `SC Stock` |
| 2nd | Fontana, CA | `CA Stock` |
| 3rd | New Jersey (NJ) | `NJ Stock` |

Canada and EU stock columns are visible in the tool but **cannot** fulfill US orders. Ignore them for routing.

## Order prefix → origin warehouse

| Prefix | Origin | Effective priority after skipping origin |
|---|---|---|
| `AMF*` | Fontana | SC → NJ |
| `AME*` | NJ | SC → Fontana |
| `AMS*` | SC | Fontana → NJ |

## Decision tree (in order, take first match)

For each shorted line:

### Step 1 — Identify origin

Read the `Order#` prefix. Apply the mapping above.

### Step 2 — Original SKU routing

Check non-origin warehouses in priority order. Take the first one with stock > 0.

### Step 3 — Substitution SKU (only if original has zero stock at all non-origin warehouses)

Look up column M (`Alternative SKU / Potential Sub`):

- **`#N/A` or blank** → no sub. Go to Step 5.
- **Sub SKU listed** → look up the sub's stock row. Re-run Step 2 against the sub.
  - If sub has stock at a non-origin warehouse → route using the sub.
  - `AMF Note` format: `Send to [warehouse] (sub: [sub SKU])`
  - Qty stays the same (1 original = 1 sub, they're interchangeable).

### Step 4 — Split-ship (only if Step 2 found partial coverage AND a sub exists)

If the original covers some of the short but not all, AND a sub can cover the gap at any non-origin warehouse:

- Route as `Split: [N] x original to [warehouse], [M] x sub ([sub SKU]) to [warehouse]`
- Always flag for review.

### Step 5 — Fully OOS

If neither the original nor the sub has stock at any non-origin warehouse → `AMF Note = OOS`.

## Coverage flag logic

Applied to whichever SKU is chosen (original or sub):

| Stock vs. Short | Action | Flag |
|---|---|---|
| Stock > Short | Route normally | None |
| Stock = Short | Route at that warehouse | **Zero-buffer flag** |
| Stock < Short | Route partial + check sub | **Partial coverage flag** |

## Key principles

1. **Original SKU always wins when it can fully cover.** Even if the sub has way more stock, the original is the customer's expected SKU. Only fall back to sub when the original can't deliver.

2. **Pick by priority, not by quantity.** If SC has 1 unit and NJ has 1000, SC wins. The deterministic ordering matters more than maximizing on-hand stock.

3. **Consignee location does NOT factor in.** No proximity routing. The priority order is fixed.

4. **AME orders going to Fontana are normal redirects.** Don't treat them as "handoffs" or "external partner" — Fontana is a regular AMF warehouse, just one that holds AME inventory.

5. **Order-level TS POA, not line-level.** Group by `Order#` after assigning AMF Notes. If ANY line in an order is going somewhere (Send to SC/Fontana/NJ), the whole order is `Partial Ship`. Only when EVERY line is OOS does the order become `Cancel`.

## Common stock view verification mistakes

- **Cropped screenshots.** Multi-SKU stock views are often longer than what's visible in one image. Always scan top to bottom and ask for additional screenshots if a SKU appears missing.
- **Multiple images.** If the user uploads two stock screenshots, check both before declaring a SKU missing.
- **Substitution row not checked.** When following Step 3, the sub SKU has its own row in the stock view — find and read that row before deciding the sub is also OOS.
- **`#N/A` confusion.** `#N/A` in the stock columns is real "no data" (sub not configured). `#N/A` in the SKU column itself usually means an empty row — different meaning.
