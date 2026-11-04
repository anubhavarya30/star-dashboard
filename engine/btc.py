#!/usr/bin/env python3
"""
STAR — BTC desk (24/7), IBKR PAPER. Reuses the gold desk's VWAP signal (gold.signal)
on BTC-USD 15m bars, LONG ONLY (IBKR crypto can't be shorted). ~$1,000 notional per
trade, stop/target from the signal (2R). UNPROVEN forward test — not TV-validated yet.
State: data/btc_state.json · closed trades also go to the paper_trades DB (source=btc).
"""
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
STATE = os.path.join(HERE, "..", "data", "btc_state.json")
SYM = "BTC-USD"
NOTIONAL = 1000.0


def _load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"open": None, "trades": 0, "wins": 0, "sum_r": 0.0, "pnl": 0.0}


def _save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2, default=str)


def _bars():
    import yfinance as yf
    return yf.Ticker(SYM).history(period="2d", interval="15m")


def _order(action, qty, px):
    import ibkr_broker as b
    try:
        return b.place_crypto_order("BTC", qty, action, px)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _alert(msg):
    try:
        import telegram_alert
        telegram_alert.send(msg)
    except Exception:
        pass


def tick():
    import gold
    s = _load()
    h = _bars()
    if h is None or len(h) < 25:
        return "btc: no data"
    price = float(h["Close"].iloc[-1])
    now = datetime.now().astimezone().isoformat()
    p = s["open"]
    if p:
        reason = "stop" if price <= p["stop"] else "target" if price >= p["target"] else None
        if not reason:
            return f"btc tick: {price:.0f} | open LONG {p['qty']} @ {p['entry']} stop {p['stop']} tgt {p['target']}"
        r_ = _order("SELL", p["qty"], price)
        if not r_.get("ok"):
            return f"BTC EXIT FAILED ({reason}) — {r_} — retry next tick"
        exit_px = float(r_["avg_fill"])
        risk = p["entry"] - p["stop"]
        r = round((exit_px - p["entry"]) / risk, 2) if risk else 0
        pnl = round((exit_px - p["entry"]) * p["qty"], 2)
        s["trades"] += 1; s["wins"] += 1 if pnl > 0 else 0
        s["sum_r"] = round(s["sum_r"] + r, 2); s["pnl"] = round(s["pnl"] + pnl, 2); s["open"] = None
        _save(s)
        try:
            import db
            db.record_paper_trade({"source": "btc", "symbol": "BTC", "dir": "LONG", "entry": p["entry"],
                                   "exit": exit_px, "shares": p["qty"], "pnl": pnl, "r_mult": r,
                                   "opened_at": p["opened_at"], "closed_at": now, "reason": reason})
        except Exception:
            pass
        _alert(f"🔶 BTC EXIT ({reason}) @ {exit_px:.2f} {r:+.2f}R ${pnl:+.2f}")
        return f"BTC EXIT ({reason}) @ {exit_px:.2f} {r:+.2f}R ${pnl:+.2f} | total {s['trades']} tr ${s['pnl']:+.2f}"
    sig = gold.signal(h)
    if not sig or sig["dir"] != "LONG":
        return f"btc tick: {price:.0f} | flat, no long signal | {s['trades']} tr, {s['wins']}W, ${s['pnl']:+.2f}"
    qty = round(NOTIONAL / price, 4)
    r_ = _order("BUY", qty, price)
    if not r_.get("ok"):
        return f"BTC ENTRY SKIPPED — {r_}"
    entry = float(r_["avg_fill"])
    s["open"] = {"entry": entry, "stop": sig["stop"], "target": sig["target"], "qty": float(r_["filled"]),
                 "opened_at": now, "reason": sig["reason"]}
    _save(s)
    _alert(f"🔶 BTC LONG [ibkr paper] {s['open']['qty']} @ {entry:.2f} stop {sig['stop']} tgt {sig['target']}")
    return f"BTC ENTER LONG {s['open']['qty']} @ {entry:.2f} stop {sig['stop']} tgt {sig['target']} ({sig['reason']})"


def stats():
    s = _load()
    return {"open": s.get("open"), "trades": s.get("trades", 0), "wins": s.get("wins", 0),
            "total_r": s.get("sum_r", 0.0), "pnl": s.get("pnl", 0.0),
            "win_rate": round(s["wins"] / s["trades"] * 100, 1) if s.get("trades") else 0}


if __name__ == "__main__":
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tick())
