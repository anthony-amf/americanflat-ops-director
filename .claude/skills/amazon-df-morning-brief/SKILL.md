---
name: amazon-df-morning-brief
description: >
  This skill should be used when the user says "run amazon DF morning brief",
  "run the morning brief", "process the DF orders CSV", or "send the amazon morning
  brief". It pulls Amazon Vendor Central Direct Fulfillment order data (either live
  via the Claude in Chrome browser extension or from an uploaded CSV), calculates
  order metrics, formats the daily briefing message, and schedules it to Slack
  channel #ops-vendorcentral at 8:45 AM ET.
metadata:
  version: "0.3.1"
  author: "Americanflat"
---

# Amazon DF Morning Brief

When triggered, check whether the Claude in Chrome browser extension tools are
available (`mcp__Claude_in_Chrome__*`). If they are, use the **Browser Mode**
(Steps 1-5). If not, fall back to **CSV Mode** (Step 6).

---

## Browser Mode (primary)

### Step 1 -- Navigate to Amazon Vendor Central and Log In

Use `mcp__Claude_in_Chrome__tabs_context_mcp` to check whether the user already
has an Amazon Vendor Central tab open. If so, switch to it. If not, navigate to:

```
https://vendorcentral.amazon.com/hz/vendor/members/df/orders
```

Wait for the page to load. If the page redirects to a login screen:

1. Use `mcp__Claude_in_Chrome__find` to locate the email/username input field.
2. Use `mcp__Claude_in_Chrome__shortcuts_execute` or `mcp__Claude_in_Chrome__form_input`
   to trigger autofill of saved credentials for `vendorcentral.amazon.com` from the
   browser's password manager.
3. Submit the login form and wait for the DF orders page to finish loading.

If saved credentials are not available and auto-login fails, let the user know they
need to log in manually and wait for confirmation before continuing.

### Step 2 -- Compute Date Timestamps in Browser

CRITICAL: Do NOT use `await` at the top level in `javascript_tool` -- it causes a
SyntaxError. Use `.then()` promise chains instead, store results in
`window.__variable`, then read them back in a follow-up JS call.

Run the following JavaScript to compute all the timestamps you will need:

```javascript
function getMTMidnight(daysAgo) {
  const d = new Date(Date.now() - daysAgo * 86400000);
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Denver',
    hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: false
  }).formatToParts(d);
  const h = parseInt(parts.find(p => p.type === 'hour').value) % 24;
  const m = parseInt(parts.find(p => p.type === 'minute').value);
  const s = parseInt(parts.find(p => p.type === 'second').value);
  return d.getTime() - (h * 3600 + m * 60 + s) * 1000 - d.getMilliseconds();
}

// Determine recap day:
//   Monday -> recap Friday (DF orders don't ship on weekends, so go back 3 days)
//   Tue-Fri -> recap yesterday (1 day back)
const dow = new Date().getDay(); // 0=Sun, 1=Mon
const recapDaysAgo = (dow === 1) ? 3 : 1;

const recapStart = getMTMidnight(recapDaysAgo);
const recapEnd   = getMTMidnight(recapDaysAgo - 1);
const todayStart = getMTMidnight(0);
const todayEnd   = getMTMidnight(-1); // tomorrow MT midnight
const farBack    = getMTMidnight(30); // last 30 days only -- keeps API calls fast

window.__recapStart = recapStart;
window.__recapEnd   = recapEnd;
window.__todayStart = todayStart;
window.__todayEnd   = todayEnd;
window.__farBack    = farBack;

// Recap date string (MM/DD/YYYY)
const recapDate = new Date(recapStart);
const recapStr  = (recapDate.getMonth()+1).toString().padStart(2,'0') + '/' +
                  recapDate.getDate().toString().padStart(2,'0') + '/' +
                  recapDate.getFullYear();

// Schedule timestamp: 8:45 AM ET, fallback to 2 min from now if already past
const etParts = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  hour: 'numeric', minute: 'numeric', hour12: false
}).formatToParts(new Date());
const etH = parseInt(etParts.find(p => p.type === 'hour').value) % 24;
const etM = parseInt(etParts.find(p => p.type === 'minute').value);
const pastTarget = (etH * 60 + etM) >= (8 * 60 + 45);
const scheduleTs = pastTarget
  ? Math.floor((Date.now() + 2 * 60000) / 1000)
  : Math.floor((Date.now() + ((8*60+45) - (etH*60+etM)) * 60000) / 1000);

window.__scheduleTs = scheduleTs;
window.__recapStr   = recapStr;

recapStr + ' | scheduleTs=' + scheduleTs;
```

Read back the result to confirm timestamps look correct before proceeding.

### Step 3 -- Fetch Order Counts via AJAX

Amazon Vendor Central exposes internal AJAX endpoints. The `getSingleShipmentCount`
action returns a plain integer -- safe to return because the extension blocks
responses containing cookies, query strings, or base64 data. Always return only
pipe-delimited integers from JavaScript.

```javascript
const base = '/hz/vendor/members/df/orders/ajax?action=getSingleShipmentCount'
  + '&zoneId=America%2FBoise'
  + '&creationDateStart=' + window.__farBack
  + '&creationDateEnd='   + window.__todayEnd;

Promise.all([
  // (a) Shipped on recap day
  fetch(base + '&statuses=SHIPPED&rsdStart=' + window.__recapStart + '&rsdEnd=' + window.__recapEnd),
  // (b) Late: pending (ACCEPTED+NEW) with RSD before today
  fetch(base + '&statuses=UNSHIPPED&rsdEnd=' + window.__todayStart),
  // (c) Pending today: ACCEPTED+NEW with RSD = today
  fetch(base + '&statuses=UNSHIPPED&rsdStart=' + window.__todayStart + '&rsdEnd=' + window.__todayEnd),
]).then(rs => Promise.all(rs.map(r => r.text())))
  .then(texts => { window.__counts = texts.join('||'); });
```

Wait approximately 2 seconds, then read `window.__counts`.
Parse as `shippedCount || lateCount || pendingCount` (plain integers).

Note: UNSHIPPED maps to ACCEPTED + NEW statuses in Vendor Central.

### Step 4 -- Fetch Per-Warehouse Breakdown

Use `getOrders` for both shipped (recap day) and late (per-warehouse) stats.
Page through up to 3 pages of 100 orders each; fetch more pages if all three are full.

Shipped per warehouse:

```javascript
const ordersBase = '/hz/vendor/members/df/orders/ajax?action=getOrders'
  + '&pageSize=100&zoneId=America%2FBoise'
  + '&creationDateStart=' + window.__farBack
  + '&creationDateEnd='   + window.__todayEnd
  + '&statuses=SHIPPED'
  + '&rsdStart=' + window.__recapStart
  + '&rsdEnd='   + window.__recapEnd;

// Warehouse codes: ETCY=Fontana, FJFP=New Jersey, FZJE=South Carolina
const WH = { ETCY: 'F', FJFP: 'NJ', FZJE: 'SC' };
const stats = { F:{o:0,u:0}, NJ:{o:0,u:0}, SC:{o:0,u:0} };

Promise.all([1, 2, 3].map(p =>
  fetch(ordersBase + '&page=' + p).then(r => r.json())
)).then(pages => {
  for (const data of pages) {
    for (const order of (data.entities || [])) {
      const wh = order.warehouseCode || '';
      let qty = 0;
      for (const item of (order.items || [])) {
        qty += parseInt(item.quantity || item.orderedQuantity || item.itemQuantity || 1);
      }
      if (qty === 0) qty = 1;
      const key = WH[wh];
      if (key) { stats[key].o++; stats[key].u += qty; }
    }
  }
  window.__result = stats.F.o+'/'+stats.F.u+'|'+stats.NJ.o+'/'+stats.NJ.u+'|'+stats.SC.o+'/'+stats.SC.u;
});
```

Wait approximately 3 seconds, then read `window.__result`.
Parse as: `fontanaOrders/fontanaUnits | njOrders/njUnits | scOrders/scUnits`

Late orders per warehouse:

```javascript
const lateBase = '/hz/vendor/members/df/orders/ajax?action=getOrders'
  + '&pageSize=100&zoneId=America%2FBoise'
  + '&creationDateStart=' + window.__farBack
  + '&creationDateEnd='   + window.__todayEnd
  + '&statuses=UNSHIPPED'
  + '&rsdEnd=' + window.__todayStart;

const WH2 = { ETCY: 'F', FJFP: 'NJ', FZJE: 'SC' };
const late = { F:0, NJ:0, SC:0 };

Promise.all([1, 2, 3].map(p =>
  fetch(lateBase + '&page=' + p).then(r => r.json())
)).then(pages => {
  for (const data of pages) {
    for (const order of (data.entities || [])) {
      const key = WH2[order.warehouseCode || ''];
      if (key) late[key]++;
    }
  }
  window.__lateResult = late.F+'|'+late.NJ+'|'+late.SC;
});
```

Wait approximately 3 seconds, then read `window.__lateResult`.
Parse as: `fontanaLate | njLate | scLate`

Troubleshooting:
- If `window.__result` or `window.__lateResult` is undefined, wait another 2 seconds and retry.
- If `data.entities` is always empty, run `Object.keys(data)` to find the actual array field.
- If warehouse totals do not add up to the count from Step 3, fetch additional pages.

### Step 5 -- Assemble Message, Preview, and Schedule

Build totals:
- `totalShippedOrders` = fontanaOrders + njOrders + scOrders
- `totalShippedUnits`  = fontanaUnits + njUnits + scUnits

Format the message exactly as follows:

```
Hello Team! @ops-amazon @amazon-na

We have {lateCount} late DF orders reports on Amazon this morning.

And so far today, Amazon is expecting us to ship a total of {pendingCount} DF orders.

Recap of {recapStr} Ship Date:
Total DF Orders Shipped: {totalShippedOrders} orders for {totalShippedUnits} units.
Fontana - {fontanaOrders} orders for {fontanaUnits} units ({fontanaLate} Late orders from Fontana WH)
New Jersey - {njOrders} orders for {njUnits} units ({njLate} Late orders from NJ WH)
South Carolina - {scOrders} orders for {scUnits} units ({scLate} Late orders from SC WH)
```

Present the message for review before scheduling:

```
Here's the morning brief I'll schedule for [schedule time]:

---
[message]
---

Shall I go ahead and schedule this to #ops-vendorcentral?
```

Wait for the user to confirm (e.g., "yes", "looks good", "send it") before scheduling.

Then use the Slack `schedule_message` tool:
- channel: C015ST25QBW (#ops-vendorcentral)
- text: the formatted message
- post_at: `window.__scheduleTs` (Unix timestamp from Step 2)

Confirm: Scheduled for [time] in #ops-vendorcentral.

---

## CSV Mode (fallback)

Use this path when the Claude in Chrome extension is unavailable or the user has
already uploaded a CSV export from Amazon Vendor Central.

### Step 6a -- Locate the Uploaded CSV

Check `/sessions/inspiring-brave-archimedes/mnt/uploads/` for `.csv` files sorted
by modification time (most recent first). If no CSV is found, ask the user to
upload the Vendor Central DF orders CSV before continuing.

### Step 6b -- Run the Data Processing Script

The CSV uses `utf-8-sig` encoding (Vendor Central exports include a UTF-8 BOM)
and has 25 standard columns plus 2 extra columns that are safely ignored.

Install dependencies and run:

```bash
pip install pandas pytz --break-system-packages -q
python3 /tmp/df_brief.py "<path_to_csv>"
```

Write `/tmp/df_brief.py`:

```python
import pandas as pd
from datetime import datetime, timedelta
import pytz
import sys
import json

def find_column(columns, *keywords):
    cols_lower = [c.lower() for c in columns]
    for combo in keywords:
        terms = combo.lower().split()
        for i, col_lower in enumerate(cols_lower):
            if all(t in col_lower for t in terms):
                return columns[i]
    return None

def run_morning_brief(csv_path):
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    df.columns = df.columns.str.strip()

    ship_date_col = find_column(df.columns, "required ship date", "ship date", "required shipdate")
    status_col    = find_column(df.columns, "order status", "status")
    wh_col        = find_column(df.columns, "warehouse code", "fulfillment center", "fc code",
                                "ship from location", "vendor warehouse")
    qty_col       = find_column(df.columns, "ordered quantity", "order quantity", "quantity ordered",
                                "qty ordered", "units ordered", "item quantity", "quantity", "units")

    missing = [name for name, col in [
        ("Required Ship Date", ship_date_col), ("Order Status", status_col),
        ("Warehouse Code", wh_col), ("Quantity", qty_col),
    ] if col is None]

    if missing:
        print(json.dumps({"error": f"Could not identify columns: {', '.join(missing)}",
                          "available_columns": list(df.columns)}))
        sys.exit(1)

    et_tz    = pytz.timezone('America/New_York')
    now_et   = datetime.now(et_tz)
    today_et = now_et.date()
    # Monday -> recap Friday (no DF shipments on weekends); otherwise yesterday
    yesterday = today_et - timedelta(days=3 if today_et.weekday() == 0 else 1)

    df[ship_date_col] = pd.to_datetime(df[ship_date_col], errors='coerce').dt.date

    # Warehouse codes: ETCY=Fontana, FJFP=New Jersey, FZJE=South Carolina
    WH_MAP = {
        'ETCY': {'name': 'Fontana',        'late_label': 'Fontana WH'},
        'FJFP': {'name': 'New Jersey',     'late_label': 'NJ WH'},
        'FZJE': {'name': 'South Carolina', 'late_label': 'SC WH'},
    }

    # (a) Shipped: Required Ship Date = previous business day
    shipped_df = df[df[ship_date_col] == yesterday]

    # (b) Pending: ACCEPTED + NEW statuses with RSD = today
    all_pending_df = df[df[status_col].isin(['ACCEPTED', 'NEW'])]
    pending_df = all_pending_df[all_pending_df[ship_date_col] == today_et]

    # (c) Late: ACCEPTED/NEW where Required Ship Date < today
    late_df = all_pending_df[all_pending_df[ship_date_col] < today_et]

    wh_stats = {}
    for code, meta in WH_MAP.items():
        wh_name    = meta['name']
        wh_shipped = shipped_df[shipped_df[wh_col] == code]
        wh_late    = late_df[late_df[wh_col] == code]
        wh_stats[wh_name] = {
            'orders': len(wh_shipped),
            'units':  int(wh_shipped[qty_col].sum()) if not wh_shipped.empty else 0,
            'late':   len(wh_late),
        }

    recap_date  = yesterday.strftime('%m/%d/%Y')
    schedule_dt = now_et.replace(hour=8, minute=45, second=0, microsecond=0)
    if schedule_dt <= now_et:
        schedule_dt = now_et + timedelta(minutes=2)

    total_shipped_units = int(shipped_df[qty_col].sum()) if not shipped_df.empty else 0
    s = wh_stats
    message = (
        f"Hello Team! @ops-amazon @amazon-na\n\n"
        f"We have {len(late_df)} late DF orders reports on Amazon this morning.\n\n"
        f"And so far today, Amazon is expecting us to ship a total of {len(pending_df)} DF orders.\n\n"
        f"Recap of {recap_date} Ship Date:\n"
        f"Total DF Orders Shipped: {len(shipped_df)} orders for {total_shipped_units} units.\n"
        f"Fontana - {s['Fontana']['orders']} orders for {s['Fontana']['units']} units "
        f"({s['Fontana']['late']} Late orders from Fontana WH)\n"
        f"New Jersey - {s['New Jersey']['orders']} orders for {s['New Jersey']['units']} units "
        f"({s['New Jersey']['late']} Late orders from NJ WH)\n"
        f"South Carolina - {s['South Carolina']['orders']} orders for {s['South Carolina']['units']} units "
        f"({s['South Carolina']['late']} Late orders from SC WH)"
    )

    print(json.dumps({
        "message": message,
        "schedule_ts": int(schedule_dt.timestamp()),
        "schedule_time_display": schedule_dt.strftime('%I:%M %p ET on %m/%d/%Y'),
    }, indent=2))

if __name__ == '__main__':
    run_morning_brief(sys.argv[1])
```

### Step 6c -- Handle Output and Schedule

- Column error: Show available columns, ask user to identify them, re-run.
- Other error: Show the user and ask for guidance.
- Success: Preview message (same format as Step 5), get confirmation, then schedule to Slack.

---

## Quick Reference

| Item | Value |
|------|-------|
| Slack channel | C015ST25QBW (#ops-vendorcentral) |
| Scheduled time | 8:45 AM ET (fallback: +2 min if past 8:45) |
| Amazon timezone | Mountain Time (America/Denver) |
| Recap logic | Monday -> Friday (3 days back); Tue-Fri -> yesterday |
| Shipped filter | Required Ship Date = previous business day (no status filter) |
| Pending | ACCEPTED + NEW statuses with RSD = today |
| Late | ACCEPTED/NEW with RSD < today |
| Warehouse codes | ETCY=Fontana, FJFP=New Jersey, FZJE=South Carolina |
| CSV encoding | utf-8-sig (Vendor Central exports include UTF-8 BOM) |
| CSV columns | 25 standard + 2 extra (ignored safely) |
| getOrders array key | entities (not orders, shipments, or items) |
| Item qty field | quantity then orderedQuantity then itemQuantity then fallback 1 |
| Extension blocking | Return only pipe-delimited integers from JS |
| await in JS tool | SyntaxError -- use .then() chains + window.__var storage |
| Auto-login | Use browser saved credentials for vendorcentral.amazon.com; prompt user if unavailable |
