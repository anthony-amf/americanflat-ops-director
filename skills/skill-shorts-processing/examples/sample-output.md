# Sample Output — A Worked Example

This is what a complete daily delivery looks like, using a realistic day with cancels, redirects, partial ships, and a sub-available case.

---

## Input (what the user gave Claude)

A Client Short Report CSV with 8 shorted lines across 6 orders. Stock is pulled from BigQuery (`americanflat.Demand_Planning.Warehouse_Inventory`) for all 8 SKUs and any sub candidates; substitution mappings are looked up in `reference/sku-alternates.csv`.

All orders today are `AMF*` prefix → origin Fontana → redirect priority SC → NJ.

---

## Deliverable 1 — AMF Short Report

| Order# | Vendor Part | Consignee | Ord Qty | Alloc Qty | Short | On Order | Total Order Units | TS POA | AMF Note |
|---|---|---|---|---|---|---|---|---|---|
| AMF*129114068484675 | MP-SB-8511-BLACK | Anthony Maddaloni | 1 |  | 1 | 0 | 1 | Partial Ship | Send to NJ ⚑ |
| AMF*129114169581011 | MP-SB-1114-PBRASS | Natalie White Bledman | 1 |  | 1 | 0 | 1 | Partial Ship | Send to NJ |
| AMF*20336 | KAF8511WH2PK | Melissa Anderson | 5 | 4 | 1 | 0 | 5 | Cancel | OOS |
| AMF*20344 | A5WALNUT | Katie French | 4 |  | 4 | 0 | 11 | Cancel | OOS |
| AMF*20344 | A4WALNUT | Katie French | 7 |  | 7 | 0 | 11 | Cancel | OOS |
| AMF*CS656733218 | MP-MDF-KAF-10125-CTCPK-8511 | Emma Best | 4 |  | 4 | 0 | 8 | Partial Ship | Send to SC |
| AMF*CS656749541 | MP-PVC-LX-2030-BLACK-1218 | Julia Pike | 1 |  | 1 | 0 | 3 | Partial Ship | Send to SC |
| AMF*CS656749541 | MP-PVC-LX-1624-BLACK-812 | Julia Pike | 1 |  | 1 | 0 | 3 | Partial Ship | Send to SC |

### Needs review (1 line)

- **AMF*129114068484675 · MP-SB-8511-BLACK · Anthony Maddaloni** — short 1, NJ has exactly 1 (zero buffer). Sub `SB8511BK` has 647 units available if swap preferred.

---

## Deliverable 2 — Slack Post

```
🚨 𝗦𝗵𝗼𝗿𝘁𝘀 𝗥𝗲𝗽𝗼𝗿𝘁 — 05/20/26
cc: @opsmarketplaces @Juan Portillo

━━━━━━━━━━━━━━━━
📊 𝗦𝗛𝗢𝗥𝗧 𝗔𝗡𝗔𝗟𝗬𝗦𝗜𝗦
━━━━━━━━━━━━━━━━

📈 𝗩𝗼𝗹𝘂𝗺𝗲: 8 shorted lines across 6 orders

🔀 𝗥𝗼𝘂𝘁𝗶𝗻𝗴 𝗯𝗿𝗲𝗮𝗸𝗱𝗼𝘄𝗻:
• SC — 3 lines
• Fontana — 0 lines
• NJ — 2 lines
• OOS — 3 lines (2 full order cancels)

🚫 𝗙𝘂𝗹𝗹 𝗰𝗮𝗻𝗰𝗲𝗹𝗹𝗮𝘁𝗶𝗼𝗻𝘀:
• AMF*20336 — Melissa Anderson — KAF8511WH2PK (no US stock, no sub available)
• AMF*20344 — Katie French — A5WALNUT + A4WALNUT (no US stock, no sub available)

⚠️ 𝗣𝗮𝗿𝘁𝗶𝗮𝗹 𝗰𝗼𝘃𝗲𝗿𝗮𝗴𝗲:
• AMF*129114068484675 MP-SB-8511-BLACK — short 1, NJ has exactly 1 (zero buffer). Sub SB8511BK has 647 units available if swap preferred.

━━━━━━━━━━━━━━━━
📦 𝗪𝗔𝗥𝗘𝗛𝗢𝗨𝗦𝗘 𝗥𝗘-𝗗𝗜𝗥𝗘𝗖𝗧𝗦
━━━━━━━━━━━━━━━━

@Carolina del Rio please redirect…

🚚 𝗥𝗲𝗱𝗶𝗿𝗲𝗰𝘁 𝘁𝗼 𝗦𝗼𝘂𝘁𝗵 𝗖𝗮𝗿𝗼𝗹𝗶𝗻𝗮
• AMF*CS656733218 - partial ship, send only:
    ◦ 4 x MP-MDF-KAF-10125-CTCPK-8511
• AMF*CS656749541 - partial ship, send only:
    ◦ 1 x MP-PVC-LX-2030-BLACK-1218
    ◦ 1 x MP-PVC-LX-1624-BLACK-812

🚚 𝗥𝗲𝗱𝗶𝗿𝗲𝗰𝘁 𝘁𝗼 𝗡𝗲𝘄 𝗝𝗲𝗿𝘀𝗲𝘆
• AMF*129114068484675 - partial ship, send only:
    ◦ 1 x MP-SB-8511-BLACK  ⚠️ NJ has exactly 1 — zero buffer (sub SB8511BK available with 647 units if swap preferred)
• AMF*129114169581011 - partial ship, send only:
    ◦ 1 x MP-SB-1114-PBRASS

━━━━━━━━━━━━━━━━
☎️ 𝗖𝗨𝗦𝗧𝗢𝗠𝗘𝗥 𝗦𝗘𝗥𝗩𝗜𝗖𝗘 𝗔𝗖𝗧𝗜𝗢𝗡𝗦
━━━━━━━━━━━━━━━━

@opsmarketplaces — 2 orders affected by overselling…

❌ @Muhammad Umer (Raja) @Carlos Dubon — please notify and cancel for OOS
• AMF*20336
• AMF*20344

🔒 @Juan Portillo — please ensure these items are unavailable for any MPs
• KAF8511WH2PK
• A5WALNUT
• A4WALNUT
```

---

## Deliverable 3 — Warehouse Action Email

Only one email needed — all action items are `AMF*` → Fontana.

**Email to Fontana:**

> **Subject:** AMF x TS Fontana Shorted Orders 05/20/26 - 6 orders
>
> Hi Fontana Team,
>
> Please action the following orders from today's short report:
>
> CANCEL — do not ship:
> • AMF*20336 — Melissa Anderson
> • AMF*20344 — Katie French
>
> PARTIAL SHIP — ship only the allocated portion, do not ship the shorted units:
> • AMF*129114068484675 — Anthony Maddaloni
> • AMF*129114169581011 — Natalie White Bledman
> • AMF*CS656733218 — Emma Best
> • AMF*CS656749541 — Julia Pike
>
> Full short report attached for SKU and quantity detail.
>
> Thanks,
> [Sender]

---

## Numbers check (always include at the bottom)

8 lines = 3 SC + 0 Fontana + 2 NJ + 3 OOS ✓ across 6 orders, 2 full cancels.

---

## What this example demonstrates

- **Origin = Fontana** for all `AMF*` orders → priority SC → NJ.
- **Sub-available case** (line 1) — original has stock at NJ but it's a zero buffer. Sub has plenty. Per the rules: original wins when it can cover, but the sub is surfaced inline as an option.
- **Multi-line order cancel** (AMF*20344) — two lines both OOS → whole order is `Cancel`.
- **Multi-line order partial ship** (AMF*CS656749541) — two lines both routing to SC → both flagged `Partial Ship`, grouped under one bullet in the redirect post.
- **All three Slack section headers present** even though Fontana routing count is 0.
- **Email subject reflects total Fontana actions** (6 = 2 cancels + 4 partial ships), not just cancels.
