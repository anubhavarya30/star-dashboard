#!/usr/bin/env python3
"""
STAR — live runner BASKET monitor. Watches up to ~6 names concurrently and flags
the moment any of them forms a REAL playbook setup. A runner desk never watches
one name; you watch the board so the 1-2 that set up cleanly pay for the rest.

Each cycle (~60s) it snapshots every symbol, computes VWAP, and looks for:
  Setup B (VWAP reclaim off the lows): was below VWAP, now above it, holding above
  the day low, on rising volume -> disciplined long trigger w/ a tight stop.
Anything pinned at HOD after a parabola is reported DO-NOT-CHASE, never a trigger.

Writes /tmp/star_runner_status.json (whole basket) + /tmp/star_runner_watch.log.
Auto-picks the watchlist from live movers if none given (price>=$1, drops the
sub-$1 landmines; nano-caps kept but flagged by the grader elsewhere).
"""
import json
import math
import os
import sys
import time
from datetime import datetime

LOG = "/tmp/star_runner_watch.log"
STATUS = "/tmp/star_runner_status.json"


def snapshot(sym):
    import yfinance as yf
    h = yf.Ticker(sym).history(period="1d", interval="1m")
    if h is None or len(h) < 2:
        return {"symbol": sym.upper(), "note": "no intraday data", "trigger": False}
    tp = (h["High"] + h["Low"] + h["Close"]) / 3.0
    vwap = float((tp * h["Volume"]).cumsum().iloc[-1] / max(h["Volume"].cumsum().iloc[-1], 1))
    price = float(h["Close"].iloc[-1]); prev = float(h["Close"].iloc[-2])
    hod = float(h["High"].max()); lod = float(h["Low"].min())
    last_vol = float(h["Volume"].iloc[-1]); avg_vol = float(h["Volume"].tail(20).mean() or 0)
    above_vwap = price > vwap
    was_below = prev <= vwap
    off_low = (price / lod - 1) * 100 if lod else 0
    off_high = (hod - price) / hod * 100 if hod else 0
    trigger = bool(was_below and above_vwap and off_low > 1 and (avg_vol == 0 or last_vol > avg_vol))
    if trigger:
        note = "VWAP RECLAIM — Setup B trigger"
    elif above_vwap:
        note = "above VWAP, holding"
    else:
        note = "below VWAP — stand aside"
    plan = None
    if trigger:
        entry = round(price, 2); stop = round(min(vwap, lod) * 0.995, 2)
        target = round(entry + 2 * (entry - stop), 2)   # 2R
        try:
            import risk_manager as rm
            plan = rm.pre_trade_check(sym, entry, stop, target)   # brain's risk gate sizes/approves it
        except Exception as e:
            plan = {"error": f"risk check failed: {e}"}
    return {"symbol": sym.upper(), "ts": datetime.now().strftime("%H:%M:%S"),
            "price": round(price, 3), "vwap": round(vwap, 3), "hod": round(hod, 2), "lod": round(lod, 2),
            "off_high_pct": round(off_high, 1), "off_low_pct": round(off_low, 1),
            "rel_vol_1m": round(last_vol / avg_vol, 1) if avg_vol else None,
            "above_vwap": above_vwap, "trigger": trigger, "note": note, "plan": plan}


def auto_watchlist(n=5):
    """Pick the watchlist from live movers: price>=$1, top by % change."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import webull_movers
    rows = (webull_movers.movers().get("gainers") or [])
    picks = [r["symbol"] for r in rows if (r.get("price") or 0) >= 1.0][:n]
    return picks or [r["symbol"] for r in rows][:n]


def scout_watchlist(n=5):
    """Pick the watchlist from the Scout's SOLID shortlist (liquid, sector-confirmed
    real names) instead of raw micro-cap movers — watch quality, not pumps."""
    sys.path.insert(0, os.path.dirname(__file__))
    import scout
    sl = (scout.scan().get("shortlist") or [])[:n]
    return [r["symbol"] for r in sl] or auto_watchlist(n)


def main(symbols, minutes=120, interval=60):
    end = time.time() + minutes * 60
    with open(LOG, "a") as f:
        f.write(f"\n===== watch {','.join(symbols)} start {datetime.now()} =====\n")
    while time.time() < end:
        basket = []
        for sym in symbols:
            try:
                basket.append(snapshot(sym))
            except Exception as e:
                basket.append({"symbol": sym, "note": f"err: {e}", "trigger": False})
        json.dump({"generated_at": datetime.now().isoformat(), "basket": basket}, open(STATUS, "w"), default=str)
        with open(LOG, "a") as f:
            for s in basket:
                if "price" not in s:
                    f.write(f"{datetime.now().strftime('%H:%M:%S')} {s['symbol']} {s.get('note','')}\n"); continue
                f.write(("*** TRIGGER *** " if s["trigger"] else "") +
                        f"{s['ts']} {s['symbol']:6} ${s['price']} vwap ${s['vwap']} "
                        f"(off_high {s['off_high_pct']}% off_low {s['off_low_pct']}%) :: {s['note']}\n")
        time.sleep(interval)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.isdigit()]
    mins = next((int(a) for a in sys.argv[1:] if a.isdigit()), 120)
    if args and args[0].lower() == "scout":           # source watchlist from the Scout
        syms = scout_watchlist(5)
    elif args:
        syms = args
    else:
        syms = auto_watchlist(5)
    print("watching:", syms)
    main(syms, mins)
