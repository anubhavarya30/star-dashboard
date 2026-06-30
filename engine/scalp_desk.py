#!/usr/bin/env python3
"""
STAR — intraday SCALP desk (SIM until real-time data).

Keeps the team hunting all day: scans a universe of liquid + low-float names on 5m
bars for OVERSOLD-BOUNCE scalps (RSI flushed then turning back up + reclaiming the
5m EMA8), buys, takes a SMALL fast target (~1.2R), tight stop, and exits quick
(target / stop / 90-min time-stop / EOD flatten). One batched yfinance download per
scan keeps it fast.

HONEST: yfinance is ~15 min delayed, so this is SIM-ONLY — it validates the scalp
edge + grows the DB without trading bad fills. The day a real-time feed is added
(IBKR market data ~$3/mo), flip LIVE=True to route real orders. Records source='scalp'.
"""
import json
import os
import sys
import time
from datetime import datetime, date

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
STATE = os.path.join(ROOT, "data", "scalp_state.json")

LIVE = True             # IBKR PAPER (real fills); sim-fallback. NOTE: delayed data handicaps scalp timing until a real-time feed is added.
MAX_OPEN = 4
# Tuned 2026-06-27 via scalp_backtest sweep (60d/5m, 108 combos): best expectancy
# was oversold 30 / turn 45 / target 2.0R / hold 120m → 56% win, +0.14R/trade.
MAX_HOLD_MIN = 120      # give the bounce room to run
TARGET_R = 2.0          # let winners run (was 1.2)
RSI_OVERSOLD = 30       # demand a real flush (was 35)
RSI_TURN = 45           # confirm a stronger turn-up (was 42)
COOLDOWN = 1800         # per-name re-entry cooldown (s)
NOTIONAL = 500.0        # $ per scalp — scalp is the primary engine now (user-set 2026-06-27)

_uni = {"t": 0, "syms": []}


def _broker_ok():
    try:
        import paper_session as ps
        return bool(ps._broker().get("can_auto_trade"))
    except Exception:
        return False


def _universe():
    """LIQUID large/mid-caps only. We dropped the low-float runner junk (e.g. JEM) —
    it gave garbage fills + absurd levels. Scalp wants tight spreads + clean data."""
    if _uni["syms"] and time.time() - _uni["t"] < 1800:
        return _uni["syms"]
    syms = []
    try:
        import star_score as ss
        syms = list(ss.UNIVERSE)
    except Exception:
        pass
    out, seen = [], set()
    for s in syms:
        if s and s not in seen:
            seen.add(s); out.append(s)
    _uni.update(t=time.time(), syms=out)
    return _uni["syms"]


def _load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"open": [], "realized": 0.0, "trades": 0, "wins": 0, "last_alert": {}}


def _save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2, default=str)


def _ema(v, n):
    if len(v) < n:
        return v[-1]
    k = 2 / (n + 1); e = v[0]
    for x in v[1:]:
        e = x * k + e * (1 - k)
    return e


def scan():
    """Batch-download 5m bars for the universe; return oversold-bounce scalp triggers."""
    import yfinance as yf
    import star_score as ss
    uni = _universe()
    if not uni:
        return []
    try:
        data = yf.download(uni, period="3d", interval="5m", group_by="ticker",
                           progress=False, threads=True)
    except Exception:
        return []
    out = []
    for sym in uni:
        try:
            df = data[sym] if len(uni) > 1 else data
            closes = [float(x) for x in df["Close"].dropna().tolist()]
            lows = [float(x) for x in df["Low"].dropna().tolist()]
            if len(closes) < 40:
                continue
            c0 = round(closes[-1], 2)
            if c0 < 10:                      # no low-priced junk (wide spreads, bad fills)
                continue
            rsi_now = ss.rsi(closes, 14)
            rsi_15 = ss.rsi(closes[:-3], 14)
            rsi_30 = ss.rsi(closes[:-6], 14)
            ema8 = _ema(closes, 8)
            # cheap pre-filter on the (delayed) bars — only fetch real-time for candidates
            if not (min(rsi_15, rsi_30) <= RSI_OVERSOLD and rsi_now > rsi_15
                    and rsi_now >= RSI_TURN and c0 > ema8 and c0 > closes[-2]):
                continue
            # CANDIDATE -> confirm + price off the REAL-TIME current price (not 15-min delayed)
            import realtime_data as rt
            live = rt.price(sym)
            c = live if live else c0
            if not (c > ema8 and c > closes[-2]):     # re-confirm the bounce on the live price
                continue
            # stop just below the swing low, CAPPED to a 1–3% band (no JEM −78% bug)
            stop = round(min(c * 0.99, max(min(lows[-10:]) * 0.998, c * 0.97)), 2)
            risk = max(c - stop, 0.01)
            target = round(c + TARGET_R * risk, 2)
            out.append({"symbol": sym, "price": c, "stop": stop, "target": target,
                        "rsi": round(rsi_now, 1), "rt": bool(live),
                        "note": f"oversold bounce (RSI {round(rsi_15)}→{round(rsi_now)}, reclaim EMA8){' [RT]' if live else ''}"})
        except Exception:
            continue
    return out


def _price(sym):
    """Real-time current price (alpaca/webull) for exits; falls back to yfinance."""
    try:
        import realtime_data as rt
        p = rt.price(sym)
        if p:
            return p
    except Exception:
        pass
    import yfinance as yf
    try:
        return round(float(yf.Ticker(sym).fast_info.get("lastPrice")), 2)
    except Exception:
        return None


def maybe_enter():
    s = _load()
    if len(s["open"]) >= MAX_OPEN:
        return
    open_syms = {p["symbol"] for p in s["open"]}
    now = time.time()
    can_trade = LIVE and _broker_ok()
    for sig in scan():
        if len(s["open"]) >= MAX_OPEN:
            break
        sym = sig["symbol"]
        if sym in open_syms or now - s["last_alert"].get(sym, 0) < COOLDOWN:
            continue
        shares = max(1, int(NOTIONAL / sig["price"]))
        entry, via = sig["price"], "sim"
        if can_trade:
            try:
                import ibkr_broker as b
                r = b.place_order(sym, shares, "BUY")
                if r.get("filled") and r.get("avg_fill"):
                    entry, via = round(float(r["avg_fill"]), 2), "ibkr"
                else:
                    _log(f"scalp {sym} IBKR not filled ({r.get('status') or r.get('error')}) — sim")
            except Exception as e:
                _log(f"scalp {sym} IBKR error {e} — sim")
        pos = {"symbol": sym, "entry": entry, "stop": sig["stop"], "target": sig["target"],
               "shares": shares, "via": via, "note": sig["note"],
               "opened_at": datetime.now().isoformat()}
        s["open"].append(pos); s["last_alert"][sym] = now; open_syms.add(sym)
        _save(s)
        _log(f"SCALP ENTRY[{via}] {sym} {shares}sh @ ${entry} stop ${sig['stop']} target ${sig['target']} · {sig['note']}")


def manage(force_close=False):
    s = _load()
    if not s["open"]:
        return
    for p in list(s["open"]):
        px = _price(p["symbol"])
        if px is None:
            continue
        held = (datetime.now() - datetime.fromisoformat(p["opened_at"])).total_seconds() / 60
        reason = None
        if px >= p["target"]:
            reason = "target"
        elif px <= p["stop"]:
            reason = "stop"
        elif held >= MAX_HOLD_MIN:
            reason = "time-stop"
        elif force_close:
            reason = "EOD flat"
        if not reason:
            continue
        exit_px, via = px, p.get("via", "sim")
        if LIVE and p.get("via") == "ibkr":
            try:
                import ibkr_broker as b
                r = b.place_order(p["symbol"], p["shares"], "SELL")
                if r.get("filled") and r.get("avg_fill"):
                    exit_px = round(float(r["avg_fill"]), 2)
            except Exception:
                pass
        pnl = round((exit_px - p["entry"]) * p["shares"], 2)
        s["realized"] = round(s["realized"] + pnl, 2); s["trades"] += 1
        s["wins"] += 1 if pnl > 0 else 0
        s["open"].remove(p); _save(s)
        _rec_db({**p, "exit": exit_px, "pnl": pnl, "closed_at": datetime.now().isoformat()})
        _log(f"SCALP EXIT[{via}] {p['symbol']} @ ${exit_px} ({reason}) {'+' if pnl>=0 else ''}${pnl} | realized ${s['realized']}")


def _rec_db(p):
    try:
        import db
        db.record_paper_trade({"source": "scalp", "symbol": p["symbol"], "dir": "LONG",
                               "shares": p.get("shares"), "entry": p.get("entry"),
                               "exit": p.get("exit"), "stop": p.get("stop"),
                               "target": p.get("target"), "pnl": p.get("pnl"),
                               "notes": p.get("note"), "opened_at": p.get("opened_at"),
                               "closed_at": p.get("closed_at")})
    except Exception:
        pass


def _log(msg):
    try:
        import paper_session as ps
        ps._log(msg)
    except Exception:
        print(msg)


def tick():
    import paper_session as ps
    phase = ps._market_phase(ps._now_ct())
    if phase == "closed":
        return "market closed"
    manage(force_close=(phase == "eod"))
    if phase == "open":
        maybe_enter()
    s = _load()
    return f"scalp tick [{phase}] | open {len(s['open'])} | realized ${s['realized']} | {s['trades']} closed"


def stats():
    s = _load()
    return {"open": s["open"], "realized": s["realized"], "trades": s["trades"],
            "wins": s["wins"], "win_rate": round(s["wins"]/s["trades"]*100, 1) if s["trades"] else 0,
            "live": LIVE}


if __name__ == "__main__":
    print(tick())
