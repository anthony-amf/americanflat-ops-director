---
name: "canada-inventory-report"
description: "Daily Canada inventory report for Americanflat. Downloads the Americanflat Inventory view from the Yusen Logistics Canada portal (via the Claude in Chrome browser), saves it as CSV, uploads to Google Drive as a Google Sheet, posts the link to #dp-and-inventory on Slack, and appends the day's snapshot to BigQuery (Demand_Planning.Warehouse_Inventory as 'Yusen CA'). Use when the user says \"run the Canada inventory report\", \"pull the Yusen inventory\", \"get the Canada inventory\", \"update Canada inventory in BigQuery\", or mentions Yusen Canada / Brampton inventory."
---

# Canada Inventory Daily Report

## Overview
Download the Americanflat Inventory report from Yusen Logistics Canada, save as CSV, upload to Google Drive as a Google Sheet, post the sheet link to the #dp-and-inventory Slack channel, and append the day's snapshot to BigQuery table `americanflat.Demand_Planning.Warehouse_Inventory`.

Requires the Claude in Chrome browser tools, a Slack connector, and a Google Drive connector. All Google API calls (token exchange + BigQuery) must run via `fetch` from a browser tab — the Linux sandbox cannot reach googleapis.com.

## Step 0 — Resolve the session outputs directory
In bash, the outputs directory is `/sessions/<SESSION>/mnt/outputs`. Resolve it once and use it everywhere below (substitute for `<OUTDIR>`):
```bash
OUTDIR=$(ls -d /sessions/*/mnt/outputs 2>/dev/null | head -1); echo "$OUTDIR"
```

## Step 1 — Get today's date
Use Bash to get today's date in two formats and keep both:
- Filename format: YYYY-MM-DD (e.g. 2026-04-01)
- Display format: Month D, YYYY (e.g. April 1, 2026)
```bash
echo "FILENAME=$(date +%Y-%m-%d)"; echo "DISPLAY=$(date '+%B %-d, %Y')"
```

## Step 2 — Download inventory data from Yusen
1. Get the browser tab context (create a tab if needed), then navigate to `https://canada.us.yusen-logistics.com/tpm/trans/tpmpersonalviews`.
2. Take a screenshot. If a token error shows, refresh (F5). If a Microsoft SSO prompt shows, the account Anthony.Armstrong@ca.yusen-logistics.com should already be signed in; wait for the Personal views page.
3. Select the "Americanflat Inventory" personal view (keyNum=118) and click Go:
   ```javascript
   try { $(document.querySelector('#comboTpmPersonalView')).igCombo('value', '118'); } catch(e){}
   document.getElementById('LoadctionStart').click();
   ```
   Wait ~8 seconds.
4. Fetch the inventory data directly using the ADAL token from localStorage (store in a window var; only read back a short status string, since JS output truncates at ~950 chars):
   ```javascript
   var token = localStorage.getItem('adal.access.token.keyab9eb15d-e84b-4288-8651-1901ccb5552a');
   window.__inv_status__ = 'pending';
   fetch('/general/scaleapi/TpmPersonalViewApi/GetPersonalViewsData?keyNum=118&_=' + Date.now(), {
     credentials: 'include',
     headers: { 'Authorization': 'Bearer ' + token }
   }).then(r => r.json()).then(d => { window.__inventoryData__ = d; window.__inv_status__ = 'OK rows=' + (d.PersonalViewData ? d.PersonalViewData.length : 'none'); }).catch(e => { window.__inv_status__ = 'ERR: ' + e.message; });
   'token present: ' + (token ? 'yes' : 'no')
   ```
   Wait ~5 seconds, then read `window.__inv_status__`. Row count varies (typically ~214–400). Anything in that range is a valid full pull.

## Step 3 — Build the CSV in the browser, then extract it
The JS tool truncates output at ~950 chars AND blocks any output it detects as contiguous base64. The reliable pattern is to build the whole CSV + a base64 copy inside the page, then pull the base64 out in fixed-size slices.

1. Build the CSV and its base64 in-page:
   ```javascript
   function esc(v){ v=(v===null||v===undefined)?'':String(v); return /[",\n]/.test(v) ? '"'+v.replace(/"/g,'""')+'"' : v; }
   var header='Warehouse,Item,Item Description,Inventory Status,Lot,On Hand Qty,Allocated Qty,In Transit Qty,Company,Aging Date';
   var lines=[header], d=window.__inventoryData__.PersonalViewData;
   for(var i=0;i<d.length;i++){ var r=d[i]; lines.push([r.warehouse||'',r.ITEM||'',r.ITEMDESC||'',r.INVENTORYSTS||'',r.LOT||'',r.ONHANDQTY||0,r.ALLOCATEDQTY||0,r.INTRANSITQTY||0,r.COMPANY||'',r.AGINGDATE||''].map(esc).join(',')); }
   var csv=lines.join('\n');
   window.__csvText__=csv;
   window.__csvB64__=btoa(unescape(encodeURIComponent(csv)));
   'csv chars='+csv.length+' b64len='+window.__csvB64__.length+' datarows='+d.length
   ```
2. Extract `window.__csvB64__` in slices no larger than ~700 chars using `window.__csvB64__.substr(START, 700)` (START = 0, 700, 1400, …). Because the base64 blob is large (~35 KB → ~50 slices), **spawn a sub-agent** to do this grind: it reads every slice in order, concatenates them (verify total length matches b64len), writes to `<OUTDIR>/inv_b64.txt`, then decodes:
   ```bash
   base64 -d <OUTDIR>/inv_b64.txt > <OUTDIR>/canada_inventory_YYYY-MM-DD.csv
   wc -l <OUTDIR>/canada_inventory_YYYY-MM-DD.csv   # expect datarows + 1 header
   ```
   Sub-agent robustness tip: capture the source SHA-256 in the browser (`await crypto.subtle.digest` or simpler per-slice length checks) and confirm the reconstructed file's hash/length matches, so transcription slips are caught. Retry any mismatched slice.
3. Confirm the file: header row + expected data rows, and note the SUM of the On Hand Qty column (column 6) for later verification:
   ```bash
   python3 -c "import csv; rows=list(csv.reader(open('<OUTDIR>/canada_inventory_YYYY-MM-DD.csv')))[1:]; print('datarows',len(rows),'sum_onhand',sum(int(float(r[5])) for r in rows))"
   ```

## Step 4 — Upload to Google Drive as a Google Sheet
Use the Google Drive connector's `create_file`. Passing the CSV as `textContent` with `contentMimeType: "text/csv"` auto-converts it to a Google Sheet.
- title: "Canada Inventory (Month D, YYYY)" (display date)
- contentMimeType: "text/csv"
- textContent: the full CSV text

Capture the returned file `id` and build the URL: `https://docs.google.com/spreadsheets/d/FILE_ID/edit`.

**If Drive upload fails:** proceed to Step 5 without a sheet link and log the error.

## Step 5 — Send Slack message
Send to channel #dp-and-inventory (channel ID: C03A2NFA8AD).

**Sheet created:**
```
Canada Inventory (Month D, YYYY)
:bar_chart: <GOOGLE_SHEETS_URL|View in Google Sheets>
```
**Sheet failed/skipped:**
```
Canada Inventory (Month D, YYYY)
```
**Entire download failed:**
```
Canada Inventory (Month D, YYYY) — :warning: Download failed. Please check the Yusen portal manually.
```

## Step 6 — Append snapshot to BigQuery
Run this AFTER the Slack post so a BigQuery failure never blocks the message. If it fails after 2 attempts, log the error and stop.

Table: `americanflat.Demand_Planning.Warehouse_Inventory` (Warehouse STRING, sku STRING, quantity INTEGER, date TIMESTAMP). Canada rows use Warehouse='Yusen CA', quantity = On Hand Qty only (per Anthony, 2026-06-12). US warehouses (NJ, SC, FON) are loaded by a separate pipeline — never modify their rows.

Constraints:
- All Google API calls run via `fetch` from a browser tab (CORS is open on Google APIs). Do NOT use curl/python for these.
- Browser JS output truncates at ~950 chars: store responses in `window` vars, read back short status strings.
- JWT signing happens offline in the sandbox with openssl — the private key never goes into the browser.

### 6a. Materialize the service account key (sandbox)
The run needs the `canada-and-eu-inventory-update@americanflat.iam.gserviceaccount.com`
key. It is **not** stored in this skill — supply it at run time as the
`CANADA_INVENTORY_SA_KEY` environment variable, holding the base64-encoded
service-account JSON.

SENSITIVE: never print the decoded JSON or the private key, never send it
anywhere except the offline JWT signing step below, and delete it at the end of
the run (step 9).

```bash
if [ -z "$CANADA_INVENTORY_SA_KEY" ]; then
  echo "CANADA_INVENTORY_SA_KEY is not set - cannot authenticate to Google APIs" >&2
  exit 1
fi
printf '%s' "$CANADA_INVENTORY_SA_KEY" | base64 -d > /tmp/sa.json
chmod 600 /tmp/sa.json
python3 -c "import json;d=json.load(open('/tmp/sa.json'));print('key loaded for',d['client_email'])"
```

If the variable is missing, stop and ask the operator to provide it rather than
attempting any other credential path.

### 6b. Sign a JWT offline (sandbox)
```bash
python3 << 'EOF'
import json, base64, time, subprocess
sa = json.load(open('/tmp/sa.json'))
open('/tmp/sa_key.pem','w').write(sa['private_key'])
def b64url(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
now = int(time.time())
header = b64url(json.dumps({'alg':'RS256','typ':'JWT'}))
payload = b64url(json.dumps({'iss': sa['client_email'], 'scope': 'https://www.googleapis.com/auth/bigquery', 'aud': 'https://oauth2.googleapis.com/token', 'iat': now, 'exp': now + 3600}))
si = header + '.' + payload
open('/tmp/jwt_input.txt','wb').write(si.encode())
sig = subprocess.run(['openssl','dgst','-sha256','-sign','/tmp/sa_key.pem'], stdin=open('/tmp/jwt_input.txt','rb'), capture_output=True).stdout
open('/tmp/jwt.txt','w').write(si + '.' + b64url(sig))
print('JWT_LEN', len(si + '.' + b64url(sig)))
EOF
cat /tmp/jwt.txt   # ~670 chars, safe to read and paste into the browser
```

### 6c. Exchange JWT for access token (browser)
Paste the JWT string in place of `<JWT>`:
```javascript
window.__bqres__ = 'pending';
fetch('https://oauth2.googleapis.com/token', {
  method: 'POST',
  headers: {'Content-Type': 'application/x-www-form-urlencoded'},
  body: 'grant_type=' + encodeURIComponent('urn:ietf:params:oauth:grant-type:jwt-bearer') + '&assertion=<JWT>'
}).then(r => r.json()).then(d => { window.__bqtok__ = d.access_token || null; window.__bqres__ = d.access_token ? 'TOKEN_OK' : 'ERR: ' + JSON.stringify(d).slice(0,300); }).catch(e => { window.__bqres__ = 'FETCH_ERR: ' + e.message; });
'started'
```
Poll `window.__bqres__` until TOKEN_OK.

### 6d. Build the 4-column load payload (sandbox)
One row per CSV data row: `Yusen CA,<Item>,<On Hand Qty as int>,<uniform UTC timestamp>`. Keep duplicate SKUs/lots as separate rows; include 0-on-hand rows. Note the row count and SUM of On Hand Qty for verification.
```bash
python3 -c "
import csv, base64, io
from datetime import datetime, timezone
ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S+00')
rows = list(csv.reader(open('<OUTDIR>/canada_inventory_YYYY-MM-DD.csv')))[1:]
out = io.StringIO(); w = csv.writer(out, lineterminator='\n'); total = 0
for r in rows:
    q = int(float(r[5])); total += q
    w.writerow(['Yusen CA', r[1], q, ts])
open('/tmp/payload_b64.txt','w').write(base64.b64encode(out.getvalue().encode()).decode())
print('ROWS', len(rows), 'TOTAL_QTY', total)
"
cat /tmp/payload_b64.txt   # paste this into 6e as <BASE64_PAYLOAD>
```

### 6e. Dedupe same-day rows, then load (browser)
First, delete any existing same-day Yusen CA rows (normally 0):
```javascript
window.__bqres__ = 'pending';
fetch('https://bigquery.googleapis.com/bigquery/v2/projects/americanflat/queries', {
  method: 'POST',
  headers: {'Authorization': 'Bearer ' + window.__bqtok__, 'Content-Type': 'application/json'},
  body: JSON.stringify({query: "DELETE FROM `americanflat.Demand_Planning.Warehouse_Inventory` WHERE Warehouse='Yusen CA' AND DATE(date)=CURRENT_DATE()", useLegacySql: false})
}).then(r => r.json()).then(d => { window.__bqres__ = d.error ? 'ERR: ' + JSON.stringify(d.error).slice(0,300) : 'DELETE_DONE'; }).catch(e => { window.__bqres__ = 'FETCH_ERR: ' + e.message; });
'started'
```
Then submit the multipart load job:
```javascript
var b64 = '<BASE64_PAYLOAD>';
var csv = atob(b64);
var meta = JSON.stringify({configuration:{load:{destinationTable:{projectId:'americanflat',datasetId:'Demand_Planning',tableId:'Warehouse_Inventory'},sourceFormat:'CSV',writeDisposition:'WRITE_APPEND',skipLeadingRows:0,fieldDelimiter:','}}});
var B = 'bq_boundary_7391';
var body = '--' + B + '\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n' + meta + '\r\n--' + B + '\r\nContent-Type: text/csv\r\n\r\n' + csv + '\r\n--' + B + '--';
window.__bqres__ = 'pending';
fetch('https://bigquery.googleapis.com/upload/bigquery/v2/projects/americanflat/jobs?uploadType=multipart', {
  method: 'POST',
  headers: {'Authorization': 'Bearer ' + window.__bqtok__, 'Content-Type': 'multipart/related; boundary=' + B},
  body: body
}).then(r => r.json()).then(d => { if (d.error) { window.__bqres__ = 'ERR: ' + JSON.stringify(d.error).slice(0,400); return; } window.__bqjob__ = d.jobReference.jobId; window.__bqres__ = 'JOB: ' + d.jobReference.jobId + ' state=' + d.status.state; }).catch(e => { window.__bqres__ = 'FETCH_ERR: ' + e.message; });
'submitted'
```
Poll the job until DONE; confirm no errors and outputRows == row count from 6d:
```javascript
window.__bqres__ = 'pending';
fetch('https://bigquery.googleapis.com/bigquery/v2/projects/americanflat/jobs/' + window.__bqjob__, { headers: {'Authorization': 'Bearer ' + window.__bqtok__} })
.then(r => r.json()).then(d => { var s = d.status || {}; var st = d.statistics && d.statistics.load ? ' outRows=' + d.statistics.load.outputRows + ' badRecords=' + d.statistics.load.badRecords : ''; window.__bqres__ = 'state=' + s.state + st + (s.errorResult ? ' ERR=' + JSON.stringify(s.errors || s.errorResult).slice(0,400) : ' no errors'); }).catch(e => { window.__bqres__ = 'FETCH_ERR: ' + e.message; });
'checking'
```

### 6f. Verify (browser)
```javascript
window.__bqres__ = 'pending';
fetch('https://bigquery.googleapis.com/bigquery/v2/projects/americanflat/queries', {
  method: 'POST',
  headers: {'Authorization': 'Bearer ' + window.__bqtok__, 'Content-Type': 'application/json'},
  body: JSON.stringify({query: "SELECT COUNT(*) c, SUM(quantity) q FROM `americanflat.Demand_Planning.Warehouse_Inventory` WHERE Warehouse='Yusen CA' AND DATE(date)=CURRENT_DATE()", useLegacySql: false})
}).then(r => r.json()).then(d => { window.__bqres__ = d.error ? 'ERR: ' + JSON.stringify(d.error).slice(0,300) : d.rows[0].f.map(c => c.v).join(' | '); }).catch(e => { window.__bqres__ = 'FETCH_ERR: ' + e.message; });
'verifying'
```
COUNT must equal the row count and SUM must equal TOTAL_QTY from 6d. Include "BigQuery: N rows appended (total on-hand M)" — or the failure reason — in the run output.

### 6g. Clean up (sandbox)
```bash
rm -f /tmp/sa.json /tmp/sa_key.pem /tmp/sa_b64.txt /tmp/jwt.txt /tmp/jwt_input.txt /tmp/payload_b64.txt
```
Also clear browser vars: set `window.__bqtok__`, `window.__csvB64__`, `window.__csvText__`, `window.__simpleData__`, `window.__inventoryData__` to null.

## Notes
- The Yusen portal uses Microsoft Azure AD / ADAL (SSO); Anthony Armstrong's account should be pre-signed in.
- Personal view "Americanflat Inventory" = keyNum=118. Expected ~214–400 data rows + 1 header (varies).
- JS output truncates at ~950 chars and blocks contiguous base64 output — store large data in window vars, extract via ~700-char slices, and lean on a sub-agent for the CSV extraction grind.
- The embedded service account key is sensitive: never print the decoded JSON or private key, never send it anywhere except the offline JWT signing step, and delete the temp files at the end.
- If browser tools are not connected at the start, retry a few times; if still unavailable, post the "Download failed" Slack message so the team checks the portal manually.
