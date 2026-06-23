#!/usr/bin/env python3
"""
STAR — Reversal watcher for a focused LONG watchlist (default TSM, AMD, ARM).

These names are SELLING; the play is to catch the TURN UP and buy a bullish CALL
debit spread, then alert you (Telegram + dashboard) the instant a reversal entry
triggers. Confirmation-based, NOT knife-catching: we require the down-move to be
oversold AND visibly turning back up AND reclaiming a short-term level before we
fire — so we buy the bounce, not the falling knife.

Honest limit: free yfinance intraday is ~15 min delayed + rate-limited, so an alert
can lag the live tape by up to ~15 min. Good for swing-style reversal entries off
5-minute bars, not for scalps.
"""
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
STATE = os.path.join(HERE, "..", "data", "reversal_watch.json")

WATCH = ["TSM", "AMD", "ARM"]
COOLDOWN = 3600          # don't re-alert the same name within an hour
RSI_OVERSOLD = 36        # the down-move must have pushed RSI at/under this
RSI_TURN = 40            # ...and RSI must now be recovering back above this


def _load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"armed": list(WATCH), "last_alert": {}, "reads": {}}


def _save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2, default=str)


def _ema(vals, n):
    if len(vals) < n:
        return vals[-1]
    k = 2 / (n + 1); e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def assess(sym):
    """Read 5m bars; return the reversal-entry verdict + the levels for a call spread."""
    import yfinance as yf
    import star_score as ss
    h = yf.Ticker(sym).history(period="5d", interval="5m")
    if h is None or len(h) < 40:
        return {"symbol": sym, "error": "no intraday data"}
    closes = list(h["Close"]); lows = list(h["Low"])
    c = round(closes[-1], 2)
    rsi_now = ss.rsi(closes, 14)
    rsi_15ago = ss.rsi(closes[:-3], 14)         # ~3 bars = 15 min back
    rsi_30ago = ss.rsi(closes[:-6], 14)         # ~30 min back
    ema8 = _ema(closes, 8)
    swing_low = round(min(lows[-12:]), 2)       # last ~hour low
    oversold_recently = min(rsi_15ago, rsi_30ago) <= RSI_OVERSOLD
    turning_up = rsi_now > rsi_15ago and rsi_now >= RSI_TURN
    reclaim = c > ema8
    momentum = c > closes[-2]
    trigger = bool(oversold_recently and turning_up and reclaim and momentum)
    stop = round(min(swing_low * 0.998, c * 0.985), 2)   # just under the swing low
    risk = max(c - stop, 0.01)
    target = round(c + 1.6 * risk, 2)            # ~1.6:1 reward on the bounce
    return {
        "symbol": sym, "price": c, "rsi": round(rsi_now, 1),
        "rsi_15ago": round(rsi_15ago, 1), "ema8": round(ema8, 2), "swing_low": swing_low,
        "oversold_recently": oversold_recently, "turning_up": turning_up,
        "reclaim_ema8": reclaim, "momentum_up": momentum, "trigger": trigger,
        "entry": c, "stop": stop, "target": target,
        "note": (f"oversold bounce confirmed (RSI {round(rsi_15ago)}→{round(rsi_now)}, reclaimed 5m EMA8)"
                 if trigger else "watching — no reversal yet"),
    }


PER_TRADE_BUDGET = 150.0     # $ allocated per option play (tunable — these are pricey names)


def _alert_entry(a):
    """Fire a Telegram reversal alert. If a defined-risk call spread fits the per-trade
    budget, attach a ready-to-place Webull ticket; otherwise send the reversal + levels
    in ONE message and flag that the name is too pricey to auto-size."""
    import options_play as op
    import telegram_alert
    try:
        spr = op.best_call_spread(a["symbol"], budget_pct=PER_TRADE_BUDGET / 500.0, target=a["target"])
    except Exception as e:
        spr = {"error": str(e)}
    if spr.get("long_strike"):
        telegram_alert.send(
            f"🎯 <b>REVERSAL ENTRY — {a['symbol']}</b>\n{a['note']}\n"
            f"Entry ~${a['entry']} · stop ${a['stop']} · target ${a['target']}\n→ Webull ticket 👇")
        import webull_ticket
        pos = {"symbol": a["symbol"], "right": "C", "expiry": spr["expiry"],
               "long_strike": spr["long_strike"], "short_strike": spr["short_strike"],
               "net_debit": spr["net_debit"], "contracts": spr["contracts"],
               "max_loss": spr["max_loss"], "max_gain": spr["max_gain"], "rr": spr["rr"]}
        webull_ticket.entry_ticket(pos, f"reversal long — {a['note']}")
        return [f"spread {spr['long_strike']}/{spr['short_strike']}C"]
    # too pricey for the budget — one honest combined message with the stock levels
    telegram_alert.send(
        f"🎯 <b>REVERSAL ENTRY — {a['symbol']}</b>\n{a['note']}\n"
        f"Entry ~${a['entry']} · stop ${a['stop']} · target ${a['target']}\n"
        f"⚠️ No call spread fits a ${int(PER_TRADE_BUDGET)} budget (it's a ${a['price']} stock). "
        f"Size your own call on Webull, or tell STAR a bigger per-trade $.")
    return ["no affordable spread — sent levels"]


def tick():
    """Called from the 60s always-on loop. Assess each armed name; alert on trigger."""
    import time
    s = _load()
    out = []
    for sym in s.get("armed", WATCH):
        try:
            a = assess(sym)
            s["reads"][sym] = {**a, "at": datetime.now().isoformat()}
            if a.get("trigger"):
                last = s["last_alert"].get(sym, 0)
                if time.time() - last >= COOLDOWN:
                    _alert_entry(a)
                    s["last_alert"][sym] = time.time()
                    out.append(f"{sym} ENTRY ALERTED")
                else:
                    out.append(f"{sym} trigger (cooldown)")
            else:
                out.append(f"{sym} watching rsi={a.get('rsi')}")
        except Exception as e:
            out.append(f"{sym} err {type(e).__name__}")
    _save(s)
    return out


def status():
    s = _load()
    return {"armed": s.get("armed", WATCH), "reads": s.get("reads", {}),
            "last_alert": s.get("last_alert", {})}


if __name__ == "__main__":
    import json as _j
    print(_j.dumps(status() if (len(sys.argv) > 1 and sys.argv[1] == "status") else tick(), indent=2, default=str))
