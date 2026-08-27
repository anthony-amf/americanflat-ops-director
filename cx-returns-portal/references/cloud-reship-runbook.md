# Running a reship from a cloud session

The decision (Anthony, 2026-08-27) is that reships run from the cloud, not the Mac.
This is the setup and the handoff.

## One-time environment setup

Both steps are on the environment at **claude.ai/code** → the **cloud icon**
showing the environment name, in the row above the message box → hover the
environment → **settings icon**. There is no settings page or direct URL.

### 1. Network access → Custom

In **Allowed domains**, one per line:

```
ssapi.shipstation.com
*.frame.claudeusercontent.com
core.us.stedi.com
bigquery.googleapis.com
```

Tick **"Also include default list of common package managers."**

Two things break if you skip them: without `*.frame.claudeusercontent.com`
sessions can no longer read artifacts (including this project's portal), and
without the defaults checkbox `Custom` allows *only* the list, cutting off package
managers and tooling.

### 2. Environment variables

```
SHIPSTATION_API_KEY=<key>
SHIPSTATION_API_SECRET=<secret>
```

Set these in the environment dialog. **Do not paste them into a chat message** —
that puts them in a transcript.

Known trade-off, accepted deliberately: the docs say cloud environments have no
secrets store and advise against putting API keys in variables. Anyone with access
to the environment can read them. Two things reduce the blast radius:

- **Use a ShipStation API key created for this purpose**, not one shared with other
  systems, so it can be rotated without breaking anything else.
- **Never echo the variable.** To check it exists, use
  `[ -n "${SHIPSTATION_API_KEY:-}" ] && echo set || echo missing`.
  Do **not** use `${SHIPSTATION_API_KEY:-no}` — that prints the value when set, and
  is exactly how `STEDI_API_KEY` leaked into a transcript on 2026-08-27.

### 3. Start a new session

Running sessions copy environment values once at startup and never re-read them.
Neither change reaches a session that was already open, so start a fresh one.

## Verify the setup landed

```bash
python3 cx-returns-portal/scripts/shipstation_probe.py
```

| Output | Meaning |
|---|---|
| `Tunnel connection failed: 403 Forbidden` | Domain not allowed yet, or session predates the change |
| `401 unauthorized` | Domain allowed, credentials missing or wrong |
| Mode line, then stores and warehouses | Working |

On success, commit the `warehouseId` → site mapping into
`references/shipstation-discovered.json`. That mapping decides which 3PL receives
the 940 and is the last unverified input.

## Running a reship

1. **Look up the order** — `python3 scripts/lookup_order.py <order>` for SKUs and
   quantities as ordered. The shortfall comes from the customer, not the order.
2. **Check no RS already exists**, so the API create is not a second shipment.
3. **Check stock** in `Demand_Planning.Warehouse_Inventory` before choosing a
   warehouse — routing to a site with zero on hand just stalls.
4. **Dry run** `create_reship_order.py` and read the payload.
5. **Send** with `--send --warehouse-id <id>`, typing the order number to confirm.
6. **Confirm the 940** a few minutes later with `confirm_940.py <order>RS`. No 940
   means the warehouse never received it, whatever ShipStation shows.

## Live case waiting to run: 24235RS

Verified 2026-08-27, ready once the environment is configured.

| | |
|---|---|
| Original order | 24235 — `PAID / FULFILLED`, 2026-08-15 |
| Item | `WB2436PBRASSPC` × 1 — Epic Poster Frame |
| Customer | Sarah Imler |
| Ship to | 6126 Three Cedars Lane, Fredericksburg, VA 22407, US |
| Phone | +15408483483 |
| Warehouse | Fontana (Taylored West) — 920 on hand; SC has 0, NJ does not stock it |
| Pick | Loose unit |
| New order | 24235RS — confirmed not already in ShipStation |

```bash
python3 scripts/create_reship_order.py 24235 \
  --sku "WB2436PBRASSPC:1" \
  --name "Sarah Imler" \
  --address1 "6126 Three Cedars Lane" \
  --city "Fredericksburg" --state VA --postal 22407 --country US \
  --phone "+15408483483" \
  --pick units --reason "reship" \
  --warehouse-id <Fontana, from the probe> \
  --send
```

Then `python3 scripts/confirm_940.py 24235RS`.

Note: the payload's field names have not been checked against a real ShipStation
request. Run the probe first and reconcile them; a rejection is harmless, but a
create that succeeds with the wrong warehouse is not.
