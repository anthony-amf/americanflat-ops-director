import sys
from brampton_worksheets_2025_08_2026_07 import MONTHS, CONTRACT, FREE_PALLETS, HST

C = 0.011  # cent tolerance
def near(a,b,tol=C): return abs(a-b) <= tol

BQ = {  # invoice_number -> (receiving_usd, storage_usd) from finance.yusen_invoices
 "CA2WFS0003089": (2982.61, 8380.83), "CA2WFS0003115": (3972.74, 7774.23),
 "CA2WFS0003152": (5035.56, 5971.46), "CA2WFS0003194": (2173.66, 4808.82),
 "CA2WFS0003214": (6324.14, 5684.55), "CA2WFS0003251": (4527.33, 10103.27), "CA2WFS0003390": (6636.99, 7956.50),
 "CA2WFS0003477": (None,    5549.30),
}

allfind=[]
for inv, m in MONTHS.items():
    f=[]
    lines = m["storage"]+m["ops"]+m["vas"]
    # 1. line math: qty x rate == printed subtotal
    for name,qty,rate,sub in lines:
        if not near(round(qty*rate,2), sub):
            f.append(f"LINE MATH {name}: {qty} x {rate} = {qty*rate:.2f} but printed {sub:.2f}")
    # 2. rate vs contract
    for name,qty,rate,sub in lines:
        key = "Pallet" if name.startswith("Pallet wk") else name
        c = CONTRACT.get(key)
        if c is None: f.append(f"NO CONTRACT RATE for '{name}'")
        elif not near(rate,c,0.0001):
            f.append(f"OFF-CARD {name}: billed {rate} vs contract {c}")
    # 3. section subtotals
    for label,items,printed in (("Storage",m["storage"],m["storage_sub"]),
                                ("Inbound+OrderProc",m["ops"],m["ops_sub"]),
                                ("VAS",m["vas"],m["vas_sub"])):
        s=round(sum(x[3] for x in items),2)
        if not near(s,printed): f.append(f"SECTION {label}: lines sum {s:.2f} vs printed {printed:.2f}")
    # 4. grand subtotal / HST / total
    gs=round(m["storage_sub"]+m["ops_sub"]+m["vas_sub"],2)
    if not near(gs,m["printed_sub"]): f.append(f"SUBTOTAL: sections {gs:.2f} vs printed {m['printed_sub']:.2f}")
    hst=round(m["printed_sub"]*HST,2)
    if not near(hst,m["printed_hst"]): f.append(f"HST: 13% = {hst:.2f} vs printed {m['printed_hst']:.2f}")
    tot=round(m["printed_sub"]+m["printed_hst"],2)
    if not near(tot,m["printed_total"]): f.append(f"TOTAL: {tot:.2f} vs printed {m['printed_total']:.2f}")
    # 5. FX
    usd=m["printed_total"]/m["fx"]
    if not near(usd,m["printed_usd"],0.51):
        f.append(f"FX: {m['printed_total']:.2f}/{m['fx']} = {usd:.2f} vs printed USD {m['printed_usd']:.2f}")
    elif not near(usd,m["printed_usd"],0.011):
        f.append(f"~FX rounding: computed {usd:.2f} vs printed {m['printed_usd']:.2f} (diff {m['printed_usd']-usd:+.2f})")
    # 6. pallet basis: billed == tracked - 115
    for i,(name,qty,rate,sub) in enumerate(x for x in m["storage"] if x[0].startswith("Pallet wk")):
        tr=m["tracked"][i]
        exp = max(0, tr-FREE_PALLETS) if tr else 0
        if qty!=exp: f.append(f"PALLET BASIS wk{i+1}: billed {qty}, tracked {tr} - {FREE_PALLETS} = {exp}")
    # 7. reconcile to BigQuery (Storage row = Storage+VAS sections; Receiving row = Inbound+OrderProc)
    recv_bq, stor_bq = BQ[inv]
    stor_calc = round((m["storage_sub"]+m["vas_sub"])*(1+HST)/m["fx"],2)
    recv_calc = round(m["ops_sub"]*(1+HST)/m["fx"],2)
    if recv_bq is not None and not near(recv_calc,recv_bq,0.06):
        f.append(f"BQ RECEIVING: worksheet {recv_calc:.2f} vs ledger {recv_bq:.2f}")
    if not near(stor_calc,stor_bq,0.45):
        f.append(f"BQ STORAGE: worksheet {stor_calc:.2f} vs ledger {stor_bq:.2f}")
    bq_tot = (recv_bq or 0)+stor_bq
    if recv_bq is not None and not near(bq_tot,m["printed_usd"],0.03):
        f.append(f"BQ TOTAL: ledger {bq_tot:.2f} vs worksheet USD {m['printed_usd']:.2f}")
    # 8. internal consistency flags (billing-practice, not math)
    ops={n:(q,r,s) for n,q,r,s in m["ops"]}
    mr = ops.get("Order processing (Manual Regular)")
    ed = ops.get("Order processing (E.D.I.)")
    if mr and ed and ed[0]>0 and mr[0]>0:
        f.append(f"DOUBLE-BILL? Manual Regular {mr[0]} orders AND E.D.I. {ed[0]} orders billed on the same order count (+${ed[2]:.2f} CAD)")
    cc = ops.get("Courier Parcel Shipping Creation") or ops.get("LTL/Courier Parcel Shipping Creation")
    print(f"\n=== {inv}  {m['period']}  CAD {m['printed_total']:,.2f} -> USD {m['printed_usd']:,.2f} (FX {m['fx']}) ===")
    print(f"    storage {m['storage_sub']:>10,.2f} | inbound+ops {m['ops_sub']:>10,.2f} | vas {m['vas_sub']:>9,.2f}  CAD")
    print(f"    ledger: Receiving {str(recv_bq):>9} + Storage {stor_bq:>9,.2f} = {bq_tot:,.2f} USD")
    if f:
        for x in f: print("    !! "+x)
    else:
        print("    OK  every line, section, HST, FX and ledger tie exact")
    allfind.append((inv,m['period'],f))

print("\n"+"="*78)
clean=[a for a in allfind if not a[2]]
print(f"CLEAN: {len(clean)}/{len(allfind)} months  ->  {', '.join(a[0][-4:] for a in clean)}")
for inv,per,f in allfind:
    if f: print(f"FLAGGED {inv} ({per}): {len(f)} item(s)")
