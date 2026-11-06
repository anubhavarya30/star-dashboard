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
IBKR_LIVE = True      # 2026-11-04: route entries/exits to IBKR PAPER as 1 MGC (micro gold) contract
CONTRACTS = 1
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
    """15m MGC bars from IBKR (fresher than Yahoo's ~10-min-delayed free feed); Yahoo GC=F fallback."""
    try:
        import signal as _sig
        import pandas as pd
        from ib_async import IB, ContFuture
        _sig.alarm(40)
        ib = IB(); ib.connect("127.0.0.1", 7497, clientId=96, timeout=10)
        try:
            cf = ContFuture("MGC", "COMEX"); ib.qualifyContracts(cf)
            b = ib.reqHistoricalData(cf, "", "2 D", "15 mins", "TRADES", useRTH=False)
        finally:
            ib.disconnect(); _sig.alarm(0)
        if b and len(b) >= 25:
            return pd.DataFrame({"Open": [x.open for x in b], "High": [x.high for x in b], "Low": [x.low for x in b],
                                 "Close": [x.close for x in b], "Volume": [x.volume for x in b]},
                                index=[x.date for x in b])
    except Exception:
        pass
    import yfinance as yf
    return yf.Ticker(SYM).history(period="2d", interval="15m")


def night_window(now=None):
    """User plan 2026-11-04: gold = evening->morning; stocks own the cash session.
    No NEW gold entries Mon-Fri 08:30-15:00 Central (open positions still managed)."""
    from zoneinfo import ZoneInfo
    t = (now or datetime.now(ZoneInfo("America/Chicago")))
    day = t.weekday() < 5 and (8, 30) <= (t.hour, t.minute) < (15, 0)
    return not day


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


def _breakeven(p, s, price, risk):
    """At +1R move the stop to entry (desk + IBKR-held stop) so a winner can't become a loser."""
    if p.get("init_stop") or not risk:
        return
    up = (price - p["entry"]) if p["dir"] == "LONG" else (p["entry"] - price)
    if up < risk:
        return
    p["init_stop"] = p["stop"]; p["stop"] = p["entry"]
    if p.get("via") == "ibkr" and p.get("broker_stop_id"):
        try:
            import ibkr_broker as b
            b.cancel_future_stop(p.pop("broker_stop_id"))   # _broker_stop() re-places it at entry
        except Exception:
            pass
    _save(s)
    try:
        import telegram_alert
        telegram_alert.send(f"🟢 GOLD {p['dir']} +1R — stop moved to breakeven {p['entry']} (can't lose now)")
    except Exception:
        pass


def _broker_stop(p, s):
    """Keep a protective stop resting AT IBKR for an open ibkr trade. Returns 'filled' when the
    broker shows us flat (stop fired), else None. Places the stop if missing (self-heal)."""
    try:
        import sys
        sys.path.insert(0, HERE)
        import ibkr_broker as b
        pos = b.positions(client_id=91)
        if not pos:            # shortcut: {} == couldn't connect (account always holds stocks); skip
            return None
        if pos.get("MGC", 0) == 0:
            return "filled"
        if not p.get("broker_stop_id"):
            r = b.place_future_stop("MGC", "COMEX", p.get("contracts", CONTRACTS),
                                    "SELL" if p["dir"] == "LONG" else "BUY", p["stop"])
            if r.get("ok"):
                p["broker_stop_id"] = r["order_id"]; _save(s)
                try:
                    import telegram_alert
                    telegram_alert.send(f"🛡 GOLD broker stop placed at IBKR @ {r['stop']} ({p['dir']})")
                except Exception:
                    pass
    except Exception:
        pass
    return None


def _ibkr(action, ref_price):
    """Send 1 MGC order to IBKR paper. Returns fill dict, or None if not routed."""
    if not IBKR_LIVE:
        return None
    try:
        import sys
        sys.path.insert(0, HERE)
        import ibkr_broker as b
        return b.place_future_order("MGC", "COMEX", CONTRACTS, action, ref_price)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def tick():
    s = _load()
    h = _bars()
    if h is None or len(h) < 2:
        return "no gold data"
    price = float(h["Close"].iloc[-1])
    now = datetime.now().astimezone().isoformat()
    # manage open
    if s["open"]:
        p = s["open"]; risk = abs(p["entry"] - p.get("init_stop", p["stop"])); exit_px = reason = None
        _breakeven(p, s, price, risk)
        if p.get("via") == "ibkr":
            bs = _broker_stop(p, s)
            if bs == "filled":   # IBKR's own stop closed it (e.g. while STAR/API was down)
                exit_px, reason = p["stop"], "stop (broker)"   # shortcut: logs stop px, not the exact fill
        if exit_px is None and p["dir"] == "LONG":
            if price <= p["stop"]: exit_px, reason = p["stop"], "stop"
            elif price >= p["target"]: exit_px, reason = p["target"], "target"
        elif exit_px is None:
            if price >= p["stop"]: exit_px, reason = p["stop"], "stop"
            elif price <= p["target"]: exit_px, reason = p["target"], "target"
        if exit_px is not None:
            if p.get("via") == "ibkr" and reason != "stop (broker)":
                if p.get("broker_stop_id"):
                    import ibkr_broker as b
                    b.cancel_future_stop(p.pop("broker_stop_id"))   # else the stop would flip us after we exit
                    _save(s)                                        # (re-placed next tick if the exit fails)
                r_ = _ibkr("SELL" if p["dir"] == "LONG" else "BUY", price)
                if not (r_ and r_.get("ok")):   # exit not filled: keep position, retry next tick
                    return f"GOLD EXIT FAILED [ibkr] {p['dir']} ({reason}) — {r_} — will retry"
                exit_px = round(float(r_["avg_fill"]), 1)
            sign = 1 if p["dir"] == "LONG" else -1
            r = round(sign * (exit_px - p["entry"]) / risk, 2) if risk else 0
            pnl_pct = round(sign * (exit_px / p["entry"] - 1) * 100, 2)
            try:
                dur = round((datetime.fromisoformat(now) - datetime.fromisoformat(p["opened_at"])).total_seconds() / 60, 1)
            except Exception:
                dur = None
            usd = round(sign * (exit_px - p["entry"]) * 10 * p.get("contracts", CONTRACTS), 2) if p.get("via") == "ibkr" else 0.0  # MGC = $10/pt
            _append({"opened_at": p["opened_at"], "closed_at": now, "duration_min": dur, "pnl": usd,
                     "dir": p["dir"], "entry": p["entry"], "exit": exit_px, "stop": p["stop"],
                     "target": p["target"], "r_mult": r, "pnl_pct": pnl_pct, "reason": reason})
            s["trades"] += 1; s["wins"] += 1 if r > 0 else 0; s["sum_r"] = round(s["sum_r"] + r, 2)
            s["open"] = None; _save(s)
            return f"GOLD EXIT {p['dir']} @ {exit_px} ({reason}) {r:+.2f}R | total {s['trades']} trades, {s['sum_r']:+.2f}R"
    # enter
    if not s["open"]:
        sig = signal(h.iloc[:-1]) if night_window() else None  # completed bars only; day = stocks' turn
        if sig:
            import gold_news
            nb = gold_news.bias()
            if (sig["dir"] == "LONG" and nb["bias"] == "bearish") or (sig["dir"] == "SHORT" and nb["bias"] == "bullish"):
                return f"GOLD {sig['dir']} BLOCKED by news ({nb['bias']} score {nb['score']}, {nb['relevant']} relevant headlines)"
            sig = {**sig, "news": nb["bias"]}
            via = "sim"
            r_ = _ibkr("BUY" if sig["dir"] == "LONG" else "SELL", sig["entry"])
            if r_ is not None:
                if not r_.get("ok"):           # IBKR didn't fill -> skip, don't fake a fill
                    return f"GOLD ENTRY SKIPPED [ibkr] {sig['dir']} — {r_}"
                via = "ibkr"; sig = {**sig, "entry": round(float(r_["avg_fill"]), 1)}
            s["open"] = {**sig, "opened_at": now, "via": via, "contracts": CONTRACTS}; _save(s)
            try:
                import telegram_alert
                telegram_alert.send(f"🟡 GOLD {sig['dir']} [{via}] {CONTRACTS} MGC @ {sig['entry']} stop {sig['stop']} tgt {sig['target']} | news {sig['news']}")
            except Exception:
                pass
            return f"GOLD ENTER [{via}] {sig['dir']} @ {sig['entry']} stop {sig['stop']} tgt {sig['target']} ({sig['reason']})"
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
