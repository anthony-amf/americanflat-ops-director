# Request: allow ShipStation through the agent proxy, with credential injection

Hand this to whoever administers the Claude Code environment for this repo. It is
an environment/egress-policy change — it cannot be made from inside a session, and
sessions are required to report policy denials rather than route around them.

## The change

| Field | Value |
|---|---|
| **Host** | `ssapi.shipstation.com` |
| **Mode** | **Allow + inject credentials** (not allow-only) |
| **Credential** | ShipStation API v1 key + secret, sent as HTTP Basic (`base64(key:secret)`) |
| **Protocol** | HTTPS, REST |

Optional and **not** needed today: `api.shipstation.com` (their v2 API). Everything
here uses v1. Leave it blocked unless something later needs it.

## Why credential injection rather than allow-only

This environment already does exactly this for two hosts:

```
api.airtable.com          — Allow + inject Airtable
bigquery.googleapis.com   — Allow + inject Data Warehouse
```

which is why BigQuery queries work here with no key anywhere in the repo. Same
mechanism, same benefit: the ShipStation key lives in the proxy, so it never
appears in the repository, an environment variable, a shell history, or a session
transcript. Allow-only would work but would put the key back in the session — and
an environment secret was leaked into a transcript in this project on 2026-08-27,
so the weaker option has a demonstrated failure mode here.

## What the sessions will call

Read-only (`scripts/shipstation_probe.py`):

- `GET /stores` — store IDs; reships live in **Manual Shopify Orders** (`438065`)
- `GET /warehouses` — the `warehouseId` → site mapping, which decides **which 3PL
  receives the EDI 940**. This is the field we cannot safely guess.
- `GET /orders?pageSize=1` — field shapes only; no customer data is written out

Write (`scripts/create_reship_order.py`):

- `POST /orders/createorder` — creates one replacement order

**The write has physical consequences.** A created order is transmitted to the 3PL
as an EDI 940 and a picker acts on it: real product, real freight, billed. The
script is dry-run by default, requires `--send`, and makes the operator type the
order number back before it posts. Rate limit is 40 requests/minute.

## Verifying it landed

One command, read-only, from a cloud session:

```bash
python3 cx-returns-portal/scripts/shipstation_probe.py
```

- **Working:** prints `using proxy-injected credentials (no key in session)` and
  lists stores and warehouses.
- **Still blocked:** `Tunnel connection failed: 403 Forbidden`.
- **Allowed but not injecting:** reaches ShipStation and returns `401`.

Those three are distinguishable on purpose, so a half-finished change is obvious.

## After it lands

1. Run the probe; commit the `warehouseId` → site mapping into
   `references/shipstation-discovered.json`.
2. Reconcile the create payload's field names against a real order and clear the
   "unverified" warnings in `shipstation-csv.md` and the scripts.
3. Reships can then be created and confirmed end to end from a cloud session:
   create → 940 to the 3PL → `confirm_940.py` verifies it arrived.

Until then reships run from the Mac, where the proxy does not apply.
