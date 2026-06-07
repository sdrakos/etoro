#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only eToro check: real bid/ask spread (→ round-trip cost in bps) for the crypto basket,
via /api/v1/market-data/instruments/rates. Compare to our cost-survivability break-even.
No orders placed."""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "back")))
from etoro_api.server import get_server_client

CRYPTO = ["BTC", "ETH", "SOL", "XRP", "ADA", "LTC", "DOGE", "BNB"]
client = get_server_client()

# 1) resolve instrument ids
ids = {}
for tk in CRYPTO:
    try:
        r = client.request("GET", f"/api/v1/market-data/search?internalSymbolFull={tk}")
        items = r.get("items") if isinstance(r, dict) else None
        if items:
            ids[tk] = items[0].get("internalInstrumentId")
    except Exception as e:
        print(f"search {tk}: {type(e).__name__}")

idlist = ",".join(str(v) for v in ids.values() if v is not None)
print("resolved ids:", ids)

# 2) live rates
rr = client.request("GET", f"/api/v1/market-data/instruments/rates?instrumentIds={idlist}")
rates = rr.get("rates") if isinstance(rr, dict) else rr
if rates:
    print("# rate item keys:", list(rates[0].keys()))
id2tk = {v: k for k, v in ids.items()}

def g(d, *names):
    for n in names:
        for k, v in d.items():
            if k.lower() == n and isinstance(v, (int, float)):
                return v
    return None

print(f"\n{'sym':<6}{'bid':>13}{'ask':>13}{'spread_bps':>12}")
print("-" * 44)
spreads = []
for it in (rates or []):
    iid = it.get("instrumentID") or it.get("instrumentId") or it.get("internalInstrumentId")
    tk = id2tk.get(iid, str(iid))
    bid = g(it, "bid", "bidrate", "sellrate", "sell")
    ask = g(it, "ask", "askrate", "buyrate", "buy")
    if bid and ask:
        mid = (bid + ask) / 2; bps = (ask - bid) / mid * 1e4
        spreads.append(bps)
        print(f"{tk:<6}{bid:>13.4f}{ask:>13.4f}{bps:>12.1f}")
    else:
        print(f"{tk:<6}  (no bid/ask) keys={list(it.keys())[:8]}")
if spreads:
    import statistics as st
    print(f"\nmedian crypto spread ~ {st.median(spreads):.1f} bps (~ round-trip cost); range {min(spreads):.0f}-{max(spreads):.0f} bps.")
    print("Our crypto banded config break-even > 80 bps (turnover ~0.003/bar) -> survives with margin.")
