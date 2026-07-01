#!/usr/bin/env python3
"""
STAR — FVG sim desk. Forward-tests the backtested Fair-Value-Gap edge (+0.27R over
1,719 trades) live, in SIM, before it ever risks real money. Takes bullish-FVG-support
longs from fvg.signal() across the universe, holds as a SWING (no intraday flatten),
exits at the 2R target or the gap-low stop. Logs source='fvg' to the DB.
"""
import json
import os
import sys
import time
from datetime import datetime

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
STATE = os.path.join(ROOT, "data", "fvg_state.json")

MAX_OPEN = 3
NOTIONAL = 1000.0      # $ per FVG swing (sizing)
COOLDOWN = 86400       # one entry per name per day
LIVE = True            # route through IBKR PAPER (real fills); sim-fallback if a fill fails
# BENCHED 2026-07-01: FVG is the only losing desk (-$177.75 all-time, 18% win, -$16/trade).
# It single-handedly turns STAR from +$131 to -$46. New entries OFF until its edge is
# proven fixable; manage() still runs so the open positions exit cleanly (no orphans).
ENTRIES_ENABLED = False


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
        return {"open": [], "realized": 0.0, "trades": 0, "wins": 0, "last_alert": {}}


def _save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2, default=str)


def _price(sym):
    import yfinance as yf
    try:
        return round(float(yf.Ticker(sym).fast_info.get("lastPrice")), 2)
    except Exception:
        return None


def maybe_enter():
    import star_score as ss, fvg
    s = _load()
    if len(s["open"]) >= MAX_OPEN:
        return
    open_syms = {p["symbol"] for p in s["open"]}
    now = time.time()
    can_trade = LIVE and _broker_ok()
    for sym in ss.UNIVERSE:
        if len(s["open"]) >= MAX_OPEN:
            break
        if sym in open_syms or now - s["last_alert"].get(sym, 0) < COOLDOWN:
            continue
        try:
            sig = fvg.signal(sym)
        except Exception:
            continue
        if not sig.get("setup"):
            continue
        shares = max(1, int(NOTIONAL / sig["entry"]))
        entry, via = sig["entry"], "sim"
        if can_trade:
            try:
                import ibkr_broker as b
                r = b.place_order(sym, shares, "BUY")
                if r.get("filled") and r.get("avg_fill"):
                    entry, via = round(float(r["avg_fill"]), 2), "ibkr"
            except Exception:
                pass
        pos = {"symbol": sym, "entry": entry, "stop": sig["stop"], "target": sig["target"],
               "shares": shares, "via": via, "note": sig.get("note", "FVG support long"),
               "opened_at": datetime.now().isoformat()}
        s["open"].append(pos); s["last_alert"][sym] = now; open_syms.add(sym); _save(s)
        _log(f"FVG ENTRY[{via}] {sym} {shares}sh @ ${entry} stop ${sig['stop']} target ${sig['target']}")


def manage():
    s = _load()
    if not s["open"]:
        return
    for p in list(s["open"]):
        px = _price(p["symbol"])
        if px is None:
            continue
        reason = None
        if px >= p["target"]:
            reason = "target"
        elif px <= p["stop"]:
            reason = "stop"
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
        _log(f"FVG EXIT[{via}] {p['symbol']} @ ${exit_px} ({reason}) {'+' if pnl>=0 else ''}${pnl} | realized ${s['realized']}")


def _rec_db(p):
    try:
        import db
        db.record_paper_trade({"source": "fvg", "symbol": p["symbol"], "dir": "LONG",
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
    tag = "" if ENTRIES_ENABLED else " [BENCHED: manage-only]"
    return f"fvg tick [{phase}]{tag} | open {len(s['open'])} | realized ${s['realized']} | {s['trades']} closed"


def stats():
    s = _load()
    return {"open": s["open"], "realized": s["realized"], "trades": s["trades"],
            "wins": s["wins"], "win_rate": round(s["wins"]/s["trades"]*100, 1) if s["trades"] else 0}


if __name__ == "__main__":
    print(tick())
