#!/usr/bin/env python3
"""
STAR — Daily Trade Picker. "Take a trade every day, no matter the day."

Each call it scans the live board, grades it, and returns ONE concrete, risk-sized
trade card so there's always something actionable — buy the best setup available.
It never refuses; on a flat day it surfaces the least-bad candidate and labels its
quality honestly (A = clean setup, C = forced/low-quality) so you know what you're
taking. Sizing always goes through the risk manager (15%/trade gate).

Honest limits: yfinance data is delayed and there is no broker API here, so this
is a PLAN you execute on Webull — not an auto-scalp. Entry/stop are intraday
levels (price / VWAP / day low); treat them as the 1-min trigger reference.
"""
import os
import sys
from datetime import datetime

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))


def _levels(sym):
    import watch_runner as w
    return w.snapshot(sym)


def pick(account_equity=None):
    import runner_grader as rg
    import risk_manager as rm
    import webull_movers

    rows = (webull_movers.movers().get("gainers") or [])[:10]
    graded = []
    for r in rows:
        if not r.get("symbol"):
            continue
        try:
            graded.append(rg.grade(r["symbol"]))
        except Exception:
            pass

    # rank: actionable setups first, then 'in play' names, landmines last
    order = {"EARLY-WATCH": 0, "PULLBACK-WATCH": 0, "DO-NOT-CHASE": 1,
             "NOT-IN-PLAY": 2, "AVOID-LANDMINE": 3, "NO-DATA": 4}
    graded.sort(key=lambda g: (order.get(g.get("verdict"), 9), -(g.get("change_pct") or 0)))
    if not graded:
        return {"error": "no movers available", "generated_at": datetime.now().astimezone().isoformat()}

    best = graded[0]
    # quality grade: clean setup = A, forced (no real setup today) = C
    if best["verdict"] in ("EARLY-WATCH", "PULLBACK-WATCH"):
        quality, qnote = "A", "Clean playbook setup."
    elif best["verdict"] == "DO-NOT-CHASE":
        quality, qnote = "C", "FORCED PICK — best name is extended; only a tight scalp, not a position. -EV if chased."
    else:
        quality, qnote = "C", "FORCED PICK — no real setup on the board today. Lowest-conviction; consider sitting out."

    sym = best["symbol"]
    snap = _levels(sym) or {}
    price = snap.get("price") or best.get("price")
    vwap = snap.get("vwap")
    lod = snap.get("lod")
    if not price:
        return {"error": f"no live price for {sym}", "candidate": best}

    # intraday long levels: entry = current, stop under VWAP/LOD, quick 1.5R target
    entry = round(price, 2)
    base = min([x for x in (vwap, lod) if x] or [price * 0.97])
    stop = round(min(base, price * 0.985) * 0.997, 2)   # just under support / ~1.5% min
    if stop >= entry:
        stop = round(entry * 0.97, 2)
    target = round(entry + 1.5 * (entry - stop), 2)      # quick 1.5R scalp target

    risk = rm.pre_trade_check(sym, entry, stop, target, equity=account_equity)
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "symbol": sym, "name": best.get("name"), "quality": quality, "quality_note": qnote,
        "grader_verdict": best["verdict"], "grader_reason": best.get("reason"),
        "change_pct": best.get("change_pct"), "float_m": best.get("float_m"),
        "above_vwap": snap.get("above_vwap"), "vwap": vwap,
        "risk": risk,
        "execution_note": "Delayed data + no broker API: execute on Webull. Use these as 1-min "
                          "reference levels — enter on the trigger, hard stop in, exit into the target.",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(pick(), indent=2, default=str))
