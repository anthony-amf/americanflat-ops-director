# Slack Post Template

A single message with three labeled sections, each framed by solid divider bars. No thread structure — one copy-pasteable message.

## Formatting style — Unicode bold + emoji + solid borders

The ops team pastes this into Slack's rich-text composer, where Markdown/mrkdwn `*asterisks*` do NOT convert to bold — they show as literal junk. So:

- 𝗕𝗼𝗹𝗱 = 𝗨𝗻𝗶𝗰𝗼𝗱𝗲 𝗯𝗼𝗹𝗱 𝗰𝗵𝗮𝗿𝗮𝗰𝘁𝗲𝗿𝘀, never asterisks. Convert header/label text to Mathematical Sans-Serif Bold (A→𝗔, a→𝗮, 0→𝟬). These display as real bold everywhere with zero markup. NEVER wrap anything in `*...*`.
- 𝗞𝗲𝗲𝗽 𝗢𝗿𝗱𝗲𝗿#𝘀 𝗮𝗻𝗱 𝗦𝗞𝗨𝘀 𝗶𝗻 𝗡𝗢𝗥𝗠𝗔𝗟 𝘁𝗲𝘅𝘁 (not Unicode bold) so they stay searchable and copy-pasteable. Bold only: the title, the 3 section headers, the Volume / Routing breakdown / Note / Full cancellation / Partial coverage labels, and each "Redirect to ..." sub-header.
- 𝗥𝗲𝗮𝗹 𝗲𝗺𝗼𝗷𝗶 𝗰𝗵𝗮𝗿𝗮𝗰𝘁𝗲𝗿𝘀 only (🚨 📊 📈 🔀 📝 🚫 📦 🚚 ☎️ ❌ 📭 🔒 ⚠️ ✅) — never `:shortcode:` names.
- 𝗦𝗼𝗹𝗶𝗱 𝗱𝗶𝘃𝗶𝗱𝗲𝗿 𝗯𝗮𝗿𝘀: a line of `━━━━━━━━━━━━━━━━` directly above AND below each of the 3 main section headers (SHORT ANALYSIS, WAREHOUSE RE-DIRECTS, CUSTOMER SERVICE ACTIONS). These render as clean unbroken borders. Do NOT put bars anywhere else; use blank lines.
- Bullets: `•` top-level, `◦` indented. No `-`, `#`, or backticks.
- @-mentions stay as-is — Slack resolves them to pings.

Fixed emoji-to-element mapping (use every run):

| Element | Emoji |
|---|---|
| Report title | 🚨 |
| SHORT ANALYSIS header | 📊 |
| Volume line | 📈 |
| Routing breakdown line | 🔀 |
| Note line | 📝 |
| Full cancellation line | 🚫 |
| Partial coverage line | ⚠️ |
| WAREHOUSE RE-DIRECTS header | 📦 |
| Each "Redirect to ..." sub-header | 🚚 (leading) |
| CUSTOMER SERVICE ACTIONS header | ☎️ |
| Notify-and-cancel line | ❌ |
| Notify-partial-fulfillment line | 📭 |
| SKU disable line | 🔒 |
| Fully-covered shorted line | ✅ (trailing) |

## Template (rendered example — copy this exact style)

```
🚨 𝗦𝗵𝗼𝗿𝘁𝘀 𝗥𝗲𝗽𝗼𝗿𝘁 — 05/27/26
cc: @opsmarketplaces @Juan Portillo

━━━━━━━━━━━━━━━━
📊 𝗦𝗛𝗢𝗥𝗧 𝗔𝗡𝗔𝗟𝗬𝗦𝗜𝗦
━━━━━━━━━━━━━━━━

📈 𝗩𝗼𝗹𝘂𝗺𝗲: 18 shorted lines across 8 orders

🔀 𝗥𝗼𝘂𝘁𝗶𝗻𝗴 𝗯𝗿𝗲𝗮𝗸𝗱𝗼𝘄𝗻:
• SC — 3 lines
• Fontana — 0 lines
• NJ — 2 lines
• FBA short-ship, no redirect — 12 lines
• OOS — 1 line (1 full order cancel)

📝 𝗡𝗼𝘁𝗲: FBA exception today — AMF*R4B2DHUP2D5RU and AME*UBPS2FAYD2VKM ship origin allocation only, no redirects, no subs.

🚫 𝗙𝘂𝗹𝗹 𝗰𝗮𝗻𝗰𝗲𝗹𝗹𝗮𝘁𝗶𝗼𝗻:
• AMF*129114810395687 — Genie Hamilton — MP-SB-1620-WHITE (no US stock)

━━━━━━━━━━━━━━━━
📦 𝗪𝗔𝗥𝗘𝗛𝗢𝗨𝗦𝗘 𝗥𝗘-𝗗𝗜𝗥𝗘𝗖𝗧𝗦
━━━━━━━━━━━━━━━━

@Carolina del Rio please redirect…

🚚 𝗥𝗲𝗱𝗶𝗿𝗲𝗰𝘁 𝘁𝗼 𝗦𝗼𝘂𝘁𝗵 𝗖𝗮𝗿𝗼𝗹𝗶𝗻𝗮
• AME*P4WNyhWZJ — 1 x PS1620WH11142PK
• AME*CS658452820 — 1 x MP-ABS-SIF-1824-BLACK-3PK
• AME*CS658137677 — 1 x MP-ABS-SIF-1824-BLACK-3PK

🚚 𝗥𝗲𝗱𝗶𝗿𝗲𝗰𝘁 𝘁𝗼 𝗡𝗲𝘄 𝗝𝗲𝗿𝘀𝗲𝘆
• AMF*912003487171779 — 1 x MP-PVC-LX-1216-BLACK
• AMF*102003494345533 — 2 x MP-PVC-LX-1824-BLACK

━━━━━━━━━━━━━━━━
☎️ 𝗖𝗨𝗦𝗧𝗢𝗠𝗘𝗥 𝗦𝗘𝗥𝗩𝗜𝗖𝗘 𝗔𝗖𝗧𝗜𝗢𝗡𝗦
━━━━━━━━━━━━━━━━

@opsmarketplaces — 3 orders affected by overselling…

❌ @Muhammad Umer (Raja) @Carlos Dubon — please notify and cancel for OOS
• AMF*129114810395687 — full cancel (MP-SB-1620-WHITE, no US stock)

📭 @Muhammad Umer (Raja) @Carlos Dubon — please notify customer of partial fulfillment

AME*UBPS2FAYD2VKM — FBA partial ship, origin allocation only:
• MP-ABS-0507-BLACK-6PK — shipping 9 of 88, 79 short
• MP-ABS-1319-BLACK-1117-3PK — shipping 0 of 28, 28 short
• MP-ABS-1114-BLACK-810-3PK — shipping 50 of 132, 82 short
• MP-MDF-1216-WHITE-812 — shipping 68 of 72, 4 short

AMF*R4B2DHUP2D5RU — FBA partial ship, origin allocation only:
• MP-MDF-WBDIST-0912-DBLUE — shipping 4 of 100, 96 short
• MP-MDF-MW-1216-BLACK-7SET — shipping 108 of 156, 48 short
• MP-MDF-0507-BLACK-46 — shipping 256 of 336, 80 short
• MP-MDF-GSK-0406-WHITE-12PK — shipping 15 of 60, 45 short
• MP-ABS-1319-BLACK-1117-3PK — shipping 84 of 96, 12 short
• MP-ABS-0507-BLACK-6PK — shipping 13 of 48, 35 short
• MP-ABS-0507-BLACK-12PK — shipping 1 of 64, 63 short
• MP-PVC-PS-8511-GOLD-5PK — shipping 77 of 78, 1 short

🔒 @Juan Portillo — please ensure these items are unavailable for any MPs
• MP-SB-1620-WHITE
```

## Section 1 — Short Analysis

- 𝗔𝗹𝘄𝗮𝘆𝘀 𝘀𝗵𝗼𝘄 𝗮𝗹𝗹 𝘁𝗵𝗿𝗲𝗲 𝘄𝗮𝗿𝗲𝗵𝗼𝘂𝘀𝗲𝘀 in the routing breakdown (SC, Fontana, NJ) — even if a count is 0. Add extra rows (e.g. "FBA short-ship, no redirect") when a one-off rule produces them.
- 𝗙𝘂𝗹𝗹 𝗰𝗮𝗻𝗰𝗲𝗹𝗹𝗮𝘁𝗶𝗼𝗻 𝘀𝗲𝗰𝘁𝗶𝗼𝗻 only lists orders that are full cancels for the customer (every shorted line OOS, no redirect rescue, no allocated lines). Skip it if there are none.
- 𝗣𝗮𝗿𝘁𝗶𝗮𝗹 𝗰𝗼𝘃𝗲𝗿𝗮𝗴𝗲 𝘀𝗲𝗰𝘁𝗶𝗼𝗻 lists lines where chosen warehouse stock < short qty (true partial) and where stock = short qty (zero-buffer). Skip if neither is present.
- 𝗡𝗼𝘁𝗲 𝗹𝗶𝗻𝗲 (📝): include only when a one-off rule was applied today (e.g. an FBA no-redirect/no-sub exception). Omit the whole line otherwise.

## Section 2 — Warehouse Re-directs

- Default @-mention is @Carolina del Rio. Change only if the user specifies otherwise.
- Sub-sections in fixed order: SC → Fontana → NJ. Skip any with zero lines.
- Group multiple shorted lines from the same Order# under one bullet with stacked `◦` sub-bullets.
- Inline ⚠️ callouts on flagged lines (partial coverage / zero buffer / sub available).
- Do NOT include OOS / cancelled lines — they belong in Section 3.
- AME orders going to Fontana count as a Fontana redirect.
- If zero redirects today, replace the body with: `No redirects — all shorts were either fully covered at origin or fully OOS.` Keep the framed header.

## Section 3 — Customer Service Actions

Three sub-blocks; any can be skipped if empty.

### Sub-block A: Full cancellations (❌ notify and cancel for OOS)
- Orders where the customer receives nothing. Bullet: `[Order#]` (+ optional short reason). Skip if none.

### Sub-block B: Partial fulfillments (📭 notify customer of partial fulfillment)
- Orders where the customer receives some but not all units.
- 𝗔𝗹𝘄𝗮𝘆𝘀 𝗴𝗶𝘃𝗲 𝗮 𝗽𝗲𝗿-𝘀𝗵𝗼𝗿𝘁𝗲𝗱-𝗹𝗶𝗻𝗲 𝘀𝗵𝗶𝗽 𝗯𝗿𝗲𝗮𝗸𝗱𝗼𝘄𝗻 — never a single rolled-up figure.
- Header line (normal text, no bullet): `[Order#] — partial fulfillment, per shorted line:` then one `•` bullet per shorted line.
- Per-line bullet: `[SKU] — shipping [X] of [Ord Qty] ([alloc] origin + [redirect qty] [warehouse]), [N] short`
  - [X] = Alloc Qty + redirected qty. OOS lines: [X] = Alloc Qty. If no redirect, show only `([alloc] origin)`.
  - [N] = Ord Qty − X. Append ` ✅` and `0 short` when fully covered.
- Only shorted lines are listed (not full-shipping lines).

### Sub-block C: SKU disable list (🔒 ensure unavailable for any MPs)
- **Default: include every distinct vendor part that had any OOS line today.** List each SKU once. Skip the sub-block only if there were zero OOS lines.
- **Do NOT filter the list based on whether the SKU has stock somewhere in the network.** If a SKU shorted, the listing risks overselling — Juan disables it, restocks, and re-enables. The cost of an extra disable is small; the cost of letting more orders come in for a SKU we can't fulfill is real (more failed orders, more CS work, more bounce-backs).
- One narrow exception: large bulk B2B/3PL lines (e.g. AWD AWD-prefixed consignees) where the origin has plenty of stock at the SKU level and the short is clearly a multi-line allocation edge case for that specific bulk order, NOT a marketplace overselling risk. In that case, omit from the disable list and flag in needs-review with the reason. Default is always to INCLUDE.

### Section 3 rules
- `@opsmarketplaces — [N] order[s] affected by overselling` — N = distinct orders in sub-blocks A + B.
- If all three sub-blocks are empty, replace the body with: `No CS actions needed today — no OOS lines.` Keep the framed header.

## General rules

- One single Slack message — no threads.
- Never delete the three framed section headers, even on quiet days.
- Use the date from the report filename or today's date.
- 𝗔𝗹𝘄𝗮𝘆𝘀 𝗶𝗻𝗰𝗹𝘂𝗱𝗲 𝘁𝗵𝗲 𝘁𝗼𝗽-𝗹𝗶𝗻𝗲 𝗰𝗰 (`cc: @opsmarketplaces @Juan Portillo`) directly under the title — every run.
