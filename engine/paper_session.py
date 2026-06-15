#!/usr/bin/env python3
"""
STAR — autonomous paper-trading session. One "tick" of the desk: manage open
paper positions (stop/target/EOD), then take the scout's strongest APPROVED setup
if flat. Run on a schedule (launchd, every ~15 min); it gates itself to weekday
US market hours and no-ops otherwise. Fully local, deterministic, uses the risk
manager + ledger. Logs to /tmp/star_paper.log.

HONEST: fills use delayed yfinance prices, so paper P&L is indicative, not exact —
good enough to learn whether the edge is real before risking the $500.
"""
import os
import sys
from datetime import datetime, time as dtime

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
LOG = "/tmp/star_paper.log"


def _now_ct():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Chicago"))
    except Exception:
        return datetime.now()


def _market_phase(now):
    """'closed' | 'open' (RTH) | 'eod' (last 5 min) — US Central time."""
    if now.weekday() >= 5:
        return "closed"
    t = now.time()
    if dtime(8, 30) <= t < dtime(14, 55):
        return "open"
    if dtime(14, 55) <= t < dtime(15, 0):
        return "eod"
    return "closed"


def _price(sym):
    import yfinance as yf
    try:
        fi = yf.Ticker(sym).fast_info
        return float(fi.get("lastPrice") or fi.get("last_price"))
    except Exception:
        return None


def _log(msg):
    line = f"{_now_ct().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    with open(LOG, "a") as f:
        f.write(line + "\n")
    return line


def manage_open(force_close=False):
    import risk_manager as rm
    s = rm._load()
    for p in list(s["open"]):
        px = _price(p["symbol"])
        if px is None:
            continue
        exit_px = reason = None
        if force_close:
            exit_px, reason = px, "EOD close"
        elif px <= p["stop"]:
            exit_px, reason = p["stop"], "stop hit"
        elif p.get("target") and px >= p["target"]:
            exit_px, reason = p["target"], "target hit"
        if exit_px is not None:
            r = rm.record_exit(p["symbol"], exit_px)
            _log(f"EXIT {p['symbol']} @ ${exit_px} ({reason}) pnl ${r.get('pnl')} | realized today ${r.get('realized_today')}")


def maybe_enter():
    import risk_manager as rm, scout
    s = rm.status()
    if s["halted"]:
        _log("HALTED — daily loss limit hit, no new entries"); return
    if len(s["open_positions"]) >= rm.CFG["max_open"]:
        return
    open_syms = {p["symbol"] for p in s["open_positions"]}
    d = scout.scan()
    pick = d.get("pick") or {}
    plan = (pick.get("risk") or {}).get("plan") or {}
    if (pick.get("risk") or {}).get("verdict") != "APPROVED":
        _log(f"no APPROVED setup ({pick.get('symbol')}: {(pick.get('risk') or {}).get('verdict')})"); return
    sym = pick["symbol"]
    if sym in open_syms or plan.get("shares", 0) < 1:
        return
    rm.record_entry(sym, plan["entry"], plan["stop"], plan["shares"], plan["target"])
    _log(f"ENTER {sym} {plan['shares']}sh @ ${plan['entry']} stop ${plan['stop']} tgt ${plan['target']} "
         f"risk ${plan['dollar_risk']} | {pick.get('thesis','')[:60]}")


def tick():
    now = _now_ct()
    phase = _market_phase(now)
    if phase == "closed":
        return _log("market closed — no action")
    manage_open(force_close=(phase == "eod"))
    if phase == "open":
        maybe_enter()
    import risk_manager as rm
    st = rm.status()
    return _log(f"tick done [{phase}] | open {len(st['open_positions'])} | realized ${st['realized_pnl']} | halted {st['halted']}")


if __name__ == "__main__":
    print(tick())
