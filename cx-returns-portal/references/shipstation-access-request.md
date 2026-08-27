# Reaching ShipStation from a cloud session

Checked against the Claude Code docs on 2026-08-27
(`code.claude.com/docs/en/cloud-environments`). An earlier version of this file
recommended "allow + inject credentials" — that is **not** something you can
configure for ShipStation. Corrected below.

## What the environment can and cannot do

Anthony owns this environment, so no admin is involved. It is a **Claude Code
cloud environment** setting on claude.ai — nothing in Google Cloud, and unrelated
to BigQuery dataset permissions.

**Can:** set network access to `Custom` and allow `ssapi.shipstation.com`. That
fixes reachability — today the proxy denies it with a 403 on CONNECT.

**Cannot:** attach a ShipStation credential to the proxy. The `api.airtable.com`
and `bigquery.googleapis.com` injection this environment already has comes from
Anthropic-side connector plumbing, not a per-host setting anyone can add. There is
no ShipStation connector.

That matters because the docs are explicit about the alternative:

> Anyone who uses the environment can read the values, and cloud environments have
> no dedicated secrets store, so don't add API keys or other credentials.

So an allow-list alone does not give a cloud session a safe way to hold the
ShipStation key. `STEDI_API_KEY` is in this environment's variables against that
guidance, and it leaked into a session transcript on 2026-08-27 — the failure mode
is real, not hypothetical.

## Decision: run it from the cloud anyway

Anthony's call, 2026-08-27. The key goes in the environment's variables and the
domain gets allow-listed. See `cloud-reship-runbook.md` for the setup, the
verification, and the trade-offs that come with holding a credential there.

The table below still describes where each piece *can* run today; it stops being
accurate for the ShipStation rows once the environment is configured.

## What this means in practice

| Operation | Where it should run |
|---|---|
| `confirm_940.py` (Stedi, read-only) | Cloud — already works |
| `lookup_order.py` (BigQuery, read-only) | Cloud — already works |
| `shipstation_probe.py` (read-only) | **Mac** |
| `create_reship_order.py --send` (creates real warehouse work) | **Mac** |

The Mac is not behind this proxy and can hold credentials properly, so the
credentialed half of the workflow belongs there. Both scripts already support
either mode, so nothing needs rewriting if that changes later.

## If you still want the domain allowed

Reasonable — it lets a cloud session at least reach ShipStation, and pairs with the
env-var trade-off if you decide to accept it.

1. Go to **claude.ai/code**. In the row above the message box, click the **cloud
   icon** showing the current environment's name. There is no settings page or
   direct URL for this.
2. Hover the environment and click the **settings icon** on the right.
3. Set **Network access** to **Custom**.
4. In **Allowed domains**, one per line:

   ```
   ssapi.shipstation.com
   *.frame.claudeusercontent.com
   core.us.stedi.com
   bigquery.googleapis.com
   ```

5. Tick **"Also include default list of common package managers."**
6. Save, then start a **new** session — running sessions keep the config they
   started with.

### Two things that will break if you skip them

- **`*.frame.claudeusercontent.com`** — Claude Code fetches artifact content from
  that host. Leave it out and sessions in this environment can no longer read
  artifacts, which includes this project's returns portal.
- **The "include defaults" checkbox** — unticked, `Custom` allows *only* what you
  list, so package installs and GitHub tooling lose access.

Stedi and BigQuery are listed because this skill uses both; confirm anything else
you rely on before switching off `Trusted`.

## Verifying

```bash
python3 cx-returns-portal/scripts/shipstation_probe.py
```

- Still blocked → `Tunnel connection failed: 403 Forbidden`
- Reachable, no credential → `401`
- Working → prints the mode it used, then stores and warehouses

Distinguishable on purpose, so a half-finished change is obvious.
