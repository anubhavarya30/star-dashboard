#!/usr/bin/env python3
"""
STAR — GEX desk. Ports Nick Ireland's (nickelninjatrades) 7-step SPY gamma system
into a STAR paper desk with a scorecard, exactly as his step 7 prescribes:

  1. Order flow moves price (not patterns)          -> context, not a gate here
  2. One ticker, commit to it                        -> SPY ONLY (SYMBOL below)
  3. Read the gamma map (dealer positioning)         -> engine/gex.py compute()
  4. Gamma environment: positive vs negative gamma   -> regime gate (governs the setup)
  5. EMA stack = direction                           -> _ema_stack() 8/21/50 on 5m
  6. ONE setup = gamma + EMA stack + volume confirm  -> maybe_enter()
  7. Paper-trade with a scorecard, review weekly     -> this desk (ENTRIES paper, stats())

THE ONE SETUP (step 6), regime-gated by step 4:
  POSITIVE gamma  -> price is PINNED between the put wall and call wall; vol suppressed.
                     FADE the walls toward the middle.
                       LONG  near the put wall  if EMA stack is UP   + volume confirm
                       SHORT near the call wall if EMA stack is DOWN + volume confirm
  NEGATIVE gamma  -> dealer hedging AMPLIFIES moves; trade WITH the trend.
                       SHORT below the gamma flip if EMA stack is DOWN + volume confirm
                       LONG  above the gamma flip if EMA stack is UP   + volume confirm
  Target = the opposite gamma level (wall/flip). Stop = just beyond the level we lean on.
  Require >= 1.5R or skip. One position at a time (one ticker, one setup).

DATA HONESTY: real dealer gamma needs live options open-interest (engine/gex.py pulls it
from yfinance). There is NO free options-OI HISTORY, so this setup CANNOT be historically
backtested the way FVG was. That is exactly why Nick's step 7 is "paper-trade with a
scorecard" — the desk forward-tests the edge live in SIM and stats() is the scorecard.
The non-gamma mechanics (EMA stack + volume + level fade/continuation) can be separately
sanity-checked in TradingView; the gamma source cannot. Entries stay OFF until the
scorecard shows a real edge.
"""
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
STATE = os.path.join(ROOT, "data", "gex_state.json")

SYMBOL = "SPY"          # step 2: one ticker, commit
NOTIONAL = 1000.0       # $ per trade (paper sizing; shares as a proxy for the options play)
MIN_RR = 1.5            # skip setups worse than 1.5R
NEAR_WALL_PCT = 0.0025  # "at" a wall = within 0.25% of it
STOP_BUF_PCT = 0.0025   # stop sits 0.25% beyond the level we lean on
VOL_MULT = 1.2          # volume confirmation: last 5m bar >= 1.2x its 20-bar average
ENTRIES_ENABLED = False # PAPER/scorecard only (step 7). Prove the edge before real money.


def _broker_ok():
    try:
        import paper_session as ps
        return bool(ps._broker().get("can_auto_trade"))
    except Exception:
        return False


def _load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"open": [], "realized": 0.0, "trades": 0, "wins": 0, "last_alert": 0}


def _save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2, default=str)


def _price(sym=SYMBOL):
    # live price first (webull realtime), yfinance fallback
    try:
        import realtime_data as rt
        p = rt.price(sym)
        if p:
            return round(float(p.get("last") if isinstance(p, dict) else p), 2)
    except Exception:
        pass
    try:
        import yfinance as yf
        return round(float(yf.Ticker(sym).fast_info.get("lastPrice")), 2)
    except Exception:
        return None


def _ema_stack(sym=SYMBOL):
    """Step 5: EMA stack on 5m bars. Returns ('up'|'down'|'none', last_vol, avg_vol)."""
    try:
        import yfinance as yf
        df = yf.Ticker(sym).history(period="5d", interval="5m")
        if df is None or len(df) < 55:
            return "none", None, None
        c = df["Close"]
        e8, e21, e50 = c.ewm(span=8).mean(), c.ewm(span=21).mean(), c.ewm(span=50).mean()
        last, a8, a21, a50 = c.iloc[-1], e8.iloc[-1], e21.iloc[-1], e50.iloc[-1]
        vols = df["Volume"]
        last_vol = float(vols.iloc[-1])
        avg_vol = float(vols.iloc[-21:-1].mean())
        if a8 > a21 > a50 and last >= a8:
            return "up", last_vol, avg_vol
        if a8 < a21 < a50 and last <= a8:
            return "down", last_vol, avg_vol
        return "none", last_vol, avg_vol
    except Exception:
        return "none", None, None


def _gamma():
    """Step 3+4: gamma map + regime for SPY."""
    try:
        import gex
        d = gex.compute(SYMBOL)
        if d.get("error"):
            return None
        return d
    except Exception:
        return None


def _signal():
    """Step 6: the ONE setup. Returns a position dict or None."""
    g = _gamma()
    if not g:
        return None
    spot = _price() or g.get("spot")
    if not spot:
        return None
    stack, last_vol, avg_vol = _ema_stack()
    if stack == "none":
        return None
    vol_ok = (last_vol is not None and avg_vol) and last_vol >= VOL_MULT * avg_vol
    if not vol_ok:
        return None

    regime = g["regime"]
    pw, cw, flip = g.get("put_wall"), g.get("call_wall"), g.get("gamma_flip")
    d = None

    if regime == "positive" and pw and cw:
        # pinned: fade the walls toward the middle
        if stack == "up" and abs(spot - pw) / spot <= NEAR_WALL_PCT:
            stop = pw * (1 - STOP_BUF_PCT)
            d = {"dir": "LONG", "entry": spot, "stop": round(stop, 2), "target": round(cw, 2),
                 "note": f"pos-gamma fade off put wall {pw} -> call wall {cw}, EMA stack up + vol"}
        elif stack == "down" and abs(spot - cw) / spot <= NEAR_WALL_PCT:
            stop = cw * (1 + STOP_BUF_PCT)
            d = {"dir": "SHORT", "entry": spot, "stop": round(stop, 2), "target": round(pw, 2),
                 "note": f"pos-gamma fade off call wall {cw} -> put wall {pw}, EMA stack down + vol"}

    elif regime == "negative" and flip:
        # amplified: trade with the trend relative to the flip
        if stack == "down" and spot < flip and pw:
            stop = spot * (1 + STOP_BUF_PCT * 1.6)
            d = {"dir": "SHORT", "entry": spot, "stop": round(stop, 2), "target": round(pw, 2),
                 "note": f"neg-gamma below flip {flip}: downside accelerates -> put wall {pw}, stack down + vol"}
        elif stack == "up" and spot > flip and cw:
            stop = spot * (1 - STOP_BUF_PCT * 1.6)
            d = {"dir": "LONG", "entry": spot, "stop": round(stop, 2), "target": round(cw, 2),
                 "note": f"neg-gamma above flip {flip}: upside runs -> call wall {cw}, stack up + vol"}

    if not d:
        return None
    risk = abs(d["entry"] - d["stop"])
    reward = abs(d["target"] - d["entry"])
    if risk <= 0 or reward / risk < MIN_RR:
        return None
    d["rr"] = round(reward / risk, 2)
    d["regime"] = regime
    return d


def maybe_enter():
    s = _load()
    if s["open"]:                       # one ticker, one setup at a time
        return
    sig = _signal()
    if not sig:
        return
    shares = max(1, int(NOTIONAL / sig["entry"]))
    entry, via = sig["entry"], "sim"
    if ENTRIES_ENABLED and _broker_ok():
        try:
            import ibkr_broker as b
            side = "BUY" if sig["dir"] == "LONG" else "SELL"
            r = b.place_order(SYMBOL, shares, side)
            if r.get("filled") and r.get("avg_fill"):
                entry, via = round(float(r["avg_fill"]), 2), "ibkr"
        except Exception:
            pass
    pos = {"symbol": SYMBOL, "dir": sig["dir"], "entry": entry, "stop": sig["stop"],
           "target": sig["target"], "shares": shares, "via": via, "rr": sig["rr"],
           "regime": sig["regime"], "note": sig["note"], "opened_at": datetime.now().isoformat()}
    s["open"].append(pos); _save(s)
    _log(f"GEX ENTRY[{via}] {sig['dir']} {SYMBOL} {shares}sh @ ${entry} stop ${sig['stop']} "
         f"target ${sig['target']} ({sig['rr']}R, {sig['regime']} gamma)")


def manage():
    s = _load()
    if not s["open"]:
        return
    px = _price()
    if px is None:
        return
    for p in list(s["open"]):
        long_ = p["dir"] == "LONG"
        hit_t = px >= p["target"] if long_ else px <= p["target"]
        hit_s = px <= p["stop"] if long_ else px >= p["stop"]
        reason = "target" if hit_t else ("stop" if hit_s else None)
        if not reason:
            continue
        exit_px, via = px, p.get("via", "sim")
        if ENTRIES_ENABLED and p.get("via") == "ibkr":
            try:
                import ibkr_broker as b
                side = "SELL" if long_ else "BUY"
                r = b.place_order(SYMBOL, p["shares"], side)
                if r.get("filled") and r.get("avg_fill"):
                    exit_px = round(float(r["avg_fill"]), 2)
            except Exception:
                pass
        gross = (exit_px - p["entry"]) if long_ else (p["entry"] - exit_px)
        pnl = round(gross * p["shares"], 2)
        s["realized"] = round(s["realized"] + pnl, 2); s["trades"] += 1
        s["wins"] += 1 if pnl > 0 else 0
        s["open"].remove(p); _save(s)
        _rec_db({**p, "exit": exit_px, "pnl": pnl, "closed_at": datetime.now().isoformat()})
        _log(f"GEX EXIT[{via}] {p['dir']} {SYMBOL} @ ${exit_px} ({reason}) "
             f"{'+' if pnl>=0 else ''}${pnl} | realized ${s['realized']}")


def _rec_db(p):
    try:
        import db
        db.record_paper_trade({"source": "gex", "symbol": p["symbol"], "dir": p.get("dir"),
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
    manage()
    if phase == "open" and ENTRIES_ENABLED:
        maybe_enter()
    s = _load()
    tag = "" if ENTRIES_ENABLED else " [PAPER/scorecard: entries off]"
    return (f"gex tick [{phase}]{tag} | open {len(s['open'])} | "
            f"realized ${s['realized']} | {s['trades']} closed")


def stats():
    """Step 7: the scorecard."""
    s = _load()
    return {"symbol": SYMBOL, "open": s["open"], "realized": s["realized"],
            "trades": s["trades"], "wins": s["wins"],
            "win_rate": round(s["wins"] / s["trades"] * 100, 1) if s["trades"] else 0}


if __name__ == "__main__":
    import json as _j
    cmd = sys.argv[1] if len(sys.argv) > 1 else "signal"
    if cmd == "signal":
        print(_j.dumps({"gamma": _gamma() and {k: _gamma().get(k) for k in
                        ("regime", "spot", "gamma_flip", "call_wall", "put_wall")},
                        "stack": _ema_stack()[0], "signal": _signal()}, indent=2, default=str))
    elif cmd == "tick":
        print(tick())
    elif cmd == "stats":
        print(_j.dumps(stats(), indent=2, default=str))
