#!/usr/bin/env python3
"""
STAR — Gold strategy tester (24/7). Gold futures (GC=F) trade ~23h/day, so this
runs around the clock, paper-testing a two-directional VWAP strategy and logging
every trade to build real win-rate/expectancy. Pure strategy test in R-multiples
(no $ sizing) — the goal is to PROVE and STRENGTHEN the gold edge over time.

Signal (15m bars):
  LONG  — price above VWAP, pulls back to it and reclaims on volume (trend dip-buy)
  SHORT — price below VWAP, breaks the recent low on volume (breakdown)
Exit  — fixed stop (VWAP-based) and 2R target; one position at a time.
Results -> data/gold_results.csv (closed trades, R-multiple + %). Self-contained
ledger in data/gold_state.json (does not touch the stock desk).
"""
import csv
import json
import os
from datetime import datetime

HERE = os.path.dirname(__file__)
STATE = os.path.join(HERE, "..", "data", "gold_state.json")
RESULTS = os.path.join(HERE, "..", "data", "gold_results.csv")
SYM = "GC=F"
RES_FIELDS = ["opened_at", "closed_at", "duration_min", "dir", "entry", "exit",
              "stop", "target", "r_mult", "pnl_pct", "reason"]


def _load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"open": None, "trades": 0, "wins": 0, "sum_r": 0.0}


def _save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2, default=str)


def _bars():
    import yfinance as yf
    return yf.Ticker(SYM).history(period="2d", interval="15m")


def signal(h):
    import pandas as pd
    if h is None or len(h) < 25:
        return None
    tp = (h["High"] + h["Low"] + h["Close"]) / 3.0
    vwap = float((tp * h["Volume"]).cumsum().iloc[-1] / max(h["Volume"].cumsum().iloc[-1], 1))
    price = float(h["Close"].iloc[-1]); prev = float(h["Close"].iloc[-2])
    last_vol = float(h["Volume"].iloc[-1]); avg_vol = float(h["Volume"].tail(20).mean() or 0)
    vol_ok = (avg_vol == 0 or last_vol > avg_vol)
    prior_low = float(h["Low"].iloc[-16:-1].min())
    prior_high = float(h["High"].iloc[-16:-1].max())
    atr = float((h["High"] - h["Low"]).tail(14).mean())
    above = price > vwap
    # LONG: reclaim of VWAP from below, in an up context, on volume
    if above and prev <= vwap and vol_ok:
        stop = round(min(vwap, price - 1.2 * atr), 1)
        return {"dir": "LONG", "entry": round(price, 1), "stop": stop,
                "target": round(price + 2 * (price - stop), 1), "reason": "VWAP reclaim"}
    # SHORT: breakdown of recent low below VWAP on volume
    if not above and price <= prior_low and vol_ok:
        stop = round(max(vwap, price + 1.2 * atr), 1)
        return {"dir": "SHORT", "entry": round(price, 1), "stop": stop,
                "target": round(price - 2 * (stop - price), 1), "reason": "breakdown"}
    return None


def tick():
    s = _load()
    h = _bars()
    if h is None or len(h) < 2:
        return "no gold data"
    price = float(h["Close"].iloc[-1])
    now = datetime.now().astimezone().isoformat()
    # manage open
    if s["open"]:
        p = s["open"]; risk = abs(p["entry"] - p["stop"]); exit_px = reason = None
        if p["dir"] == "LONG":
            if price <= p["stop"]: exit_px, reason = p["stop"], "stop"
            elif price >= p["target"]: exit_px, reason = p["target"], "target"
        else:
            if price >= p["stop"]: exit_px, reason = p["stop"], "stop"
            elif price <= p["target"]: exit_px, reason = p["target"], "target"
        if exit_px is not None:
            sign = 1 if p["dir"] == "LONG" else -1
            r = round(sign * (exit_px - p["entry"]) / risk, 2) if risk else 0
            pnl_pct = round(sign * (exit_px / p["entry"] - 1) * 100, 2)
            try:
                dur = round((datetime.fromisoformat(now) - datetime.fromisoformat(p["opened_at"])).total_seconds() / 60, 1)
            except Exception:
                dur = None
            _append({"opened_at": p["opened_at"], "closed_at": now, "duration_min": dur,
                     "dir": p["dir"], "entry": p["entry"], "exit": exit_px, "stop": p["stop"],
                     "target": p["target"], "r_mult": r, "pnl_pct": pnl_pct, "reason": reason})
            s["trades"] += 1; s["wins"] += 1 if r > 0 else 0; s["sum_r"] = round(s["sum_r"] + r, 2)
            s["open"] = None; _save(s)
            return f"GOLD EXIT {p['dir']} @ {exit_px} ({reason}) {r:+.2f}R | total {s['trades']} trades, {s['sum_r']:+.2f}R"
    # enter
    if not s["open"]:
        sig = signal(h)
        if sig:
            s["open"] = {**sig, "opened_at": now}; _save(s)
            return f"GOLD ENTER {sig['dir']} @ {sig['entry']} stop {sig['stop']} tgt {sig['target']} ({sig['reason']})"
    exp = round(s["sum_r"] / s["trades"], 2) if s["trades"] else 0
    return f"gold tick: price {price} | open {bool(s['open'])} | {s['trades']} trades, {s['wins']}W, {s['sum_r']:+.2f}R, exp {exp}R/trade"


def _append(rec):
    new = not os.path.exists(RESULTS)
    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    with open(RESULTS, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RES_FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: rec.get(k) for k in RES_FIELDS})
    try:                                      # + durable DB for analysis
        import sys
        sys.path.insert(0, os.path.join(HERE, ".."))
        import db
        db.record_paper_trade({**rec, "source": "gold", "symbol": SYM})
    except Exception:
        pass


def stats():
    s = _load()
    trips = list(csv.DictReader(open(RESULTS))) if os.path.exists(RESULTS) else []
    return {"open": s.get("open"), "trades": s.get("trades", 0), "wins": s.get("wins", 0),
            "total_r": s.get("sum_r", 0.0),
            "expectancy_r": round(s["sum_r"] / s["trades"], 2) if s.get("trades") else 0,
            "win_rate": round(s["wins"] / s["trades"] * 100, 1) if s.get("trades") else 0,
            "closed": trips[-50:]}


if __name__ == "__main__":
    import sys
    print(json.dumps(stats(), indent=2, default=str) if len(sys.argv) > 1 and sys.argv[1] == "stats" else tick())
