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
LIVE = True            # REAL IBKR PAPER orders 2026-07-10 (user approved): places a DAY
                       # LIMIT at the v3 gap top; _reconcile_working() promotes it to an open
                       # position once IBKR fills it (tracks the resting order). Sim-records
                       # only if the broker is unreachable. This trades the PROVEN v3 edge
                       # (gap-top fill), not a market fill.
# V3 APPROVED + LIVE (paper scorecard) 2026-07-07: fvg.signal() synced to the
# TradingView-proven v3 params — 1h bars, gap must form on >1.2x-avg volume + stacked
# EMA (close>=EMA200 AND EMA50>EMA200), LIMIT entry at the gap top, stop below the gap,
# 3R target. Cross-symbol basket (no re-tuning): AAPL PF 1.21, MSFT 1.48, AMD 1.53,
# TSM 1.66 (4/5 clear PF>1.3), vs the dead daily/2R baseline (PF 0.13, -$207 live).
# User approved after reviewing the TV Strategy Tester results.
ENTRIES_ENABLED = True    # v3 proven in TV + approved. Paper scorecard forward-test is LIVE.


def _broker_ok():
    try:
        import paper_session as ps
        return bool(ps._broker().get("can_auto_trade"))
    except Exception:
        return False


def _load():
    try:
        s = json.load(open(STATE))
    except Exception:
        s = {"open": [], "realized": 0.0, "trades": 0, "wins": 0, "last_alert": {}}
    s.setdefault("working", [])   # resting gap-top limit orders awaiting fill (LIVE mode)
    return s


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
    if len(s["open"]) + len(s["working"]) >= MAX_OPEN:
        return
    busy = {p["symbol"] for p in s["open"]} | {w["symbol"] for w in s["working"]}
    now = time.time()
    can_trade = LIVE and _broker_ok()
    for sym in ss.UNIVERSE:
        if len(s["open"]) + len(s["working"]) >= MAX_OPEN:
            break
        if sym in busy or now - s["last_alert"].get(sym, 0) < COOLDOWN:
            continue
        try:
            sig = fvg.signal(sym)
        except Exception:
            continue
        if not sig.get("setup"):
            continue
        entry = round(float(sig["entry"]), 2)          # v3: gap-top LIMIT price
        shares = max(1, int(NOTIONAL / entry))
        if can_trade:
            # place a DAY LIMIT at the gap top — the v3 edge is the tight-risk fill AT the
            # gap, not a market fill above it. Rests on IBKR; _reconcile_working() promotes
            # it to an open position once IBKR reports the fill.
            placed = False
            try:
                import ibkr_broker as b
                r = b.place_order(sym, shares, "BUY", order_type="LMT", limit_price=entry)
                if r.get("filled") and r.get("avg_fill"):      # filled inside the poll window
                    s["open"].append({"symbol": sym, "entry": round(float(r["avg_fill"]), 2),
                                      "stop": sig["stop"], "target": sig["target"], "shares": shares,
                                      "via": "ibkr", "note": sig.get("note"),
                                      "opened_at": datetime.now().isoformat()})
                    _log(f"FVG FILL[ibkr] {sym} {shares}sh @ ${round(float(r['avg_fill']),2)} (immediate)")
                    placed = True
                elif r.get("ok"):                              # resting — track as working
                    s["working"].append({"symbol": sym, "shares": shares, "entry": entry,
                                         "stop": sig["stop"], "target": sig["target"],
                                         "note": sig.get("note"), "placed_at": datetime.now().isoformat()})
                    _log(f"FVG LIMIT[working] {sym} {shares}sh @ ${entry} (gap-top, resting) "
                         f"stop ${sig['stop']} tgt ${sig['target']}")
                    placed = True
            except Exception:
                pass
            if not placed:
                continue
        else:
            # SIM scorecard: record the fill at the gap top immediately
            s["open"].append({"symbol": sym, "entry": entry, "stop": sig["stop"],
                              "target": sig["target"], "shares": shares, "via": "sim",
                              "note": sig.get("note"), "opened_at": datetime.now().isoformat()})
            _log(f"FVG ENTRY[sim] {sym} {shares}sh @ ${entry} stop ${sig['stop']} tgt ${sig['target']}")
        s["last_alert"][sym] = now; busy.add(sym); _save(s)


def _reconcile_working():
    """Promote resting gap-top limits that IBKR has FILLED to open positions; drop DAY
    orders that expired unfilled. Fill = the symbol now held at the broker for >= our
    shares (paper; a rare cross-desk same-symbol hold could false-promote — acceptable)."""
    s = _load()
    if not s["working"]:
        return
    held = {}
    if LIVE:
        try:
            import ibkr_broker as b
            held = b.positions()
        except Exception:
            held = {}
    changed = False
    for w in list(s["working"]):
        if held.get(w["symbol"], 0) >= w["shares"]:
            s["open"].append({"symbol": w["symbol"], "entry": w["entry"], "stop": w["stop"],
                              "target": w["target"], "shares": w["shares"], "via": "ibkr",
                              "note": w.get("note"), "opened_at": datetime.now().isoformat()})
            s["working"].remove(w); changed = True
            _log(f"FVG FILL[ibkr] {w['symbol']} {w['shares']}sh @ ${w['entry']} (limit filled)")
        else:
            try:
                age = (datetime.now() - datetime.fromisoformat(w["placed_at"])).total_seconds()
            except Exception:
                age = 0
            if age > 86400:                    # DAY order — expired unfilled after a session
                s["working"].remove(w); changed = True
                _log(f"FVG CANCEL {w['symbol']} resting limit expired unfilled")
    if changed:
        _save(s)


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
    _reconcile_working()                       # promote filled gap-top limits / expire stale
    manage()
    if phase == "open" and ENTRIES_ENABLED:
        maybe_enter()
    s = _load()
    tag = "" if ENTRIES_ENABLED else " [BENCHED: manage-only]"
    return (f"fvg tick [{phase}]{tag} | open {len(s['open'])} working {len(s['working'])} "
            f"| realized ${s['realized']} | {s['trades']} closed")


def stats():
    s = _load()
    return {"open": s["open"], "working": s.get("working", []),
            "realized": s["realized"], "trades": s["trades"],
            "wins": s["wins"], "win_rate": round(s["wins"]/s["trades"]*100, 1) if s["trades"] else 0}


if __name__ == "__main__":
    print(tick())
