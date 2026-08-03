---
name: luminous-inventory-report
description: >
  Automates the weekly Yusen Netherlands (NL) inventory report for Americanflat.
  Use this skill when the user says "run the Luminous inventory report",
  "pull the Yusen NL inventory", "get the Netherlands inventory",
  "run the Luminous report", "Yusen NL report", or "weekly inventory report".
  Also triggers automatically every Tuesday and Thursday at 12:00 PM ET via scheduled task.
  The skill logs into the Luminous dashboard, navigates to the Warehouse Location
  Summary report, filters to Yusen NL only, downloads the inventory CSV, and posts
  it to the #dp-and-inventory Slack channel with the message
  "Yusen NL Inventory (Month Day, Year)". Use this skill any time there's a mention of
  Luminous, Yusen NL, Netherlands inventory, or the weekly inventory report.
---

# Luminous Inventory Report — Yusen Netherlands

This skill automates a weekly workflow: log into the Luminous dashboard, pull the
Warehouse Location Summary filtered to the Yusen NL warehouse, download the CSV,
and post it to Slack in #dp-and-inventory.

## Overview of steps

1. Navigate to the Luminous reports library and open the Warehouse Location Summary
2. Filter the report to show only the Yusen NL warehouse
3. Download the report as CSV
4. Post to Slack in #dp-and-inventory with the CSV attached

---

## Step 1: Navigate to the Warehouse Location Summary

Use the Claude in Chrome tools:

1. Navigate to: `https://americanflat.joinluminous.com/reports/library`
2. The browser should auto-fill login credentials associated with `anthony@americanflat.com`.
   If a login form appears and credentials aren't auto-filled, stop and notify the user.
3. Once on the Reports Library page, look for **"Warehouse Location Summary"** and click on it.
4. Wait for the report to fully load (you may see an "Initializing..." spinner — wait
   until the table appears with columns like Warehouse Name, Location Name, Sku, etc.).

### Important: Switch to the Cumul.io iframe URL

The Warehouse Location Summary report is rendered inside an embedded **Cumul.io iframe**.
Clicks on the warehouse filter checkboxes will NOT register when interacting with the
parent Luminous page. To make the checkboxes clickable, you must navigate to the
iframe's URL directly:

1. After the report loads on the Luminous page, use `javascript_tool` to extract the
   iframe src:
   ```js
   document.querySelector('iframe').src;
   ```
2. Open a **new tab** using `tabs_create_mcp`.
3. Navigate the new tab to the iframe URL you extracted.
4. Wait for the Cumul.io dashboard to load fully in the new tab (you should see the
   "Warehouse Location Summary" title, the warehouse checkboxes, and the data table).
5. **All remaining steps (filtering, downloading) should be done in this new tab.**

---

## Step 2: Filter to Yusen NL only

Now working in the **direct Cumul.io tab** (not the parent Luminous page):

The report page displays warehouse filter checkboxes near the middle-top of the page.
There are four warehouses, all checked by default:

- **FON** — Fontana
- **NJ** — New Jersey
- **SC** — South Carolina
- **Yusen NL** — Yusen Netherlands

You need to uncheck three of them so that only **Yusen NL** remains selected:

1. Click the **FON** checkbox to uncheck it. Wait ~2 seconds for the table to reload.
2. Click the **NJ** checkbox to uncheck it. Wait ~2 seconds for the table to reload.
3. Click the **SC** checkbox to uncheck it. Wait ~3 seconds for the table to reload.

After all three are unchecked, verify with a zoomed screenshot of the checkbox area
that only Yusen NL remains checked. The table should now show only rows where
Warehouse Name is "Yusen NL" and Location Name is "General - NL".

---

## Step 3: Download the CSV

1. Hover over the **right side of the table header area** to reveal a download icon/button
   on the furthest right-hand side of the top of the table. It may only appear on hover,
   so move the mouse to that area to uncover it.
2. Click the download button. A format selection will appear.
3. Select **CSV** from the format options.
4. Wait for the file to download. Note the filename — you'll reference it in the Slack post.

If the download button is hard to find via hover, try using `read_page` to look for
download-related elements (icons, buttons, or links) near the top-right of the table.
You can also try using `javascript_tool` to inspect elements in that area.

---

## Step 4: Post to Slack

Use the Slack MCP tools:

1. The channel ID for `#dp-and-inventory` is `C03A2NFA8AD`.
   (Use `slack_search_channels` with query `dp-and-inventory` if you need to confirm.)
2. Send a message to the channel using `slack_send_message` with this text:
   ```
   Yusen NL Inventory (Month Day, Year)
   ```
   Replace `Month Day, Year` with today's date in long form — full month name, day,
   four-digit year. For example: `Yusen NL Inventory (April 14, 2026)`.
3. After the message is posted, upload or attach the downloaded CSV file to the same
   thread. If direct file upload isn't available via the Slack tools, DM Anthony Armstrong
   (Slack user ID: `U06MW1DCG9Y`) with the filename and location so he can upload it
   manually. The DM should read:

   ```
   The Yusen NL inventory CSV has been downloaded and is ready to upload.

   📎 File: [filename].csv (in your Downloads folder)
   🧵 Thread: [message_link from the Slack post above]

   Please upload the CSV file to that thread when you get a chance.
   ```

---

## Handling errors

- **Can't log in to Luminous**: DM Anthony Armstrong (user ID: `U06MW1DCG9Y`) explaining
  that the scheduled Luminous inventory report failed due to a login issue, so he can
  run it manually.
- **Warehouse Location Summary not found**: The reports library layout may have changed.
  Use `read_page` or `get_page_text` to search for the report name. If still not found,
  notify Anthony via DM.
- **Warehouse filter checkboxes not responding to clicks**: This almost certainly means
  you are clicking inside the parent Luminous page rather than the direct Cumul.io tab.
  Go back to Step 1 and extract the iframe URL, open it in a new tab, and retry.
- **Warehouse filter checkboxes not visible**: Try scrolling up or using `read_page` to
  locate them. They should be near the middle-top of the report page.
- **Download button not appearing on hover**: Try moving the mouse to different positions
  along the top-right of the table. Also try using `find` or `javascript_tool` to locate
  download-related UI elements.
- **Slack post fails**: Retry once with the same message content.

In any error case, DM Anthony Armstrong to let him know what went wrong.

---

## Notes

- This workflow runs automatically every Tuesday and Thursday at 12:00 PM ET via scheduled task.
- The download produces a **CSV** file.
- The date in the Slack message uses long form: `Month Day, Year` (e.g., `April 14, 2026`).
- Channel ID for #dp-and-inventory: `C03A2NFA8AD`
- Anthony Armstrong's Slack user ID: `U06MW1DCG9Y`
- The four warehouse identifiers are: FON (Fontana), NJ (New Jersey), SC (South Carolina),
  Yusen NL (Yusen Netherlands). Only Yusen NL data is needed for this report.
