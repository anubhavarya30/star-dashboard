#!/usr/bin/env python3
"""
STAR — Breakdown (short/put) scanner. Catch DROPS, not just rips. Finds names
rolling over today (down on the day, trading in the lower part of their range,
below the open = sellers in control) and — crucially for a $500 account — only
surfaces ones where a PUT actually FITS the budget. AMD dropping 6% is useless to
us if one put costs $2,295; a $15 name breaking down with a $60 put is tradeable.

Real data (yfinance + Webull losers). Defined-risk bearish via puts.
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))


def scan(equity=500.0, max_put_cost=200.0, shortlist=6):
    import yfinance as yf
    import webull_movers
    import scout
    import options_play as op

    uni = set(scout.BASE)
    try:
        m = webull_movers.movers()
        for r in (m.get("losers") or []):
            if r.get("symbol"):
                uni.add(r["symbol"].upper())
    except Exception:
        pass

    cands = []
    for sym in uni:
        try:
            fi = dict(yf.Ticker(sym).fast_info)
        except Exception:
            continue
        last = fi.get("lastPrice") or fi.get("last_price")
        prev = fi.get("previousClose") or fi.get("previous_close")
        op_ = fi.get("open"); hi = fi.get("dayHigh") or fi.get("day_high")
        lo = fi.get("dayLow") or fi.get("day_low")
        if not last or not prev:
            continue
        chg = (last / prev - 1) * 100
        if chg > -2:                                  # must be DOWN >=2% (rolling over)
            continue
        rng_pos = ((last - lo) / (hi - lo) * 100) if (hi and lo and hi > lo) else 50
        below_open = op_ is not None and last < op_
        # breakdown = down day, lower third of range, below open = sellers control
        if rng_pos > 45 or not below_open:
            continue
        cands.append({"symbol": sym.upper(), "price": round(last, 2), "chg_pct": round(chg, 1),
                      "range_pos": round(rng_pos, 0)})

    # strongest breakdowns first (biggest drop, weakest in range)
    cands.sort(key=lambda c: (c["chg_pct"], c["range_pos"]))
    # attach an AFFORDABLE put for the top names
    out = []
    for c in cands[:shortlist + 4]:
        put = op.best_put(c["symbol"], equity=equity)
        c["put"] = put
        c["affordable"] = bool(put and not put.get("error") and put.get("cost_per_contract", 1e9) <= max_put_cost)
        out.append(c)
        if sum(1 for x in out if x["affordable"]) >= shortlist:
            break
    out.sort(key=lambda c: (not c["affordable"], c["chg_pct"]))
    from datetime import datetime
    return {"generated_at": datetime.now().astimezone().isoformat(),
            "breakdowns": out, "tradeable": [c for c in out if c["affordable"]]}


if __name__ == "__main__":
    import json
    print(json.dumps(scan(), indent=2, default=str))
