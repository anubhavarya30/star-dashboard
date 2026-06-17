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
    """'closed' | 'open' (RTH) | 'eod' (last 5 min) — US Central time.
    Holiday-aware: returns 'closed' on NYSE holidays (e.g., Juneteenth)."""
    if now.weekday() >= 5:
        return "closed"
    try:
        import market_calendar as mc
        if mc.is_holiday(now.date()):
            return "closed"
    except Exception:
        pass
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


def _alert(msg):
    """Log locally AND push to Telegram (for real trade events)."""
    _log(msg)
    try:
        import telegram_alert
        telegram_alert.send(msg)
    except Exception:
        pass
    return msg


def _broker():
    """IBKR paper status — only auto-trades a verified DU (paper) account."""
    try:
        import ibkr_broker as b
        return b.status()
    except Exception as e:
        return {"can_auto_trade": False, "error": str(e)}


def _place(sym, qty, action):
    try:
        import ibkr_broker as b
        return b.place_order(sym, abs(int(qty)), action)
    except Exception as e:
        return {"ok": False, "filled": 0, "error": str(e)}


def manage_open(force_close=False):
    import risk_manager as rm
    s = rm._load()
    if not s["open"]:
        return
    # ---- PASS 0: SCALE OUT half at +1R (bank profit, ride the rest) ----
    if not force_close:
        bs0 = None
        for p in list(s["open"]):
            px = _price(p["symbol"])
            if px is None or p.get("scaled") or p["shares"] < 2:
                continue
            risk = p.get("init_risk") or round(p["entry"] - p["stop"], 4)
            if risk > 0 and (px - p["entry"]) / risk >= 1.0:
                half = p["shares"] // 2
                exit_px, via = px, "sim"
                if bs0 is None:
                    bs0 = _broker()
                if bs0.get("can_auto_trade"):
                    r = _place(p["symbol"], half, "SELL")
                    if r.get("filled") and r.get("avg_fill"):
                        exit_px, via = round(float(r["avg_fill"]), 2), "ibkr"
                res = rm.record_partial_exit(p["symbol"], half, exit_px)
                _alert(f"SCALE[{via}] {p['symbol']} sold {half}/{p['shares']} @ ${exit_px} (+1R) "
                     f"banked ${res.get('pnl')}, {res.get('remaining')} riding, stop->breakeven")
        s = rm._load()   # reload after any scale-outs
    # ---- PASS 1: ACTIVE MANAGEMENT — raise stops to lock gains ----
    # At +1R move stop to breakeven (can't lose). Above +2R trail 0.5R behind
    # price (bank profit). A winner never round-trips into a loss.
    if not force_close:
        changed = False
        for p in s["open"]:
            px = _price(p["symbol"])
            if px is None:
                continue
            risk = p.get("init_risk") or round(p["entry"] - p["stop"], 4)
            if not p.get("init_risk"):
                p["init_risk"] = risk; changed = True
            if risk <= 0:
                continue
            R = (px - p["entry"]) / risk
            ns = p["stop"]
            if R >= 2.0:
                ns = max(ns, round(px - 0.5 * risk, 2))      # trail 0.5R behind
            elif R >= 1.0:
                ns = max(ns, round(p["entry"], 2))           # breakeven
            if ns > p["stop"]:
                _log(f"RAISE STOP {p['symbol']} ${p['stop']}->${ns} "
                     f"({'trail' if R >= 2 else 'breakeven'} @ {R:.2f}R, locks "
                     f"${round((ns - p['entry']) * p['shares'], 2)})")
                p["stop"] = ns; changed = True
        if changed:
            rm._save(s)
    # ---- PASS 2: EXITS (uses the updated stops) ----
    s = rm._load()
    bs = None  # lazy-connect to IBKR only when an exit actually fires (cheap 60s loop)
    for p in list(s["open"]):
        px = _price(p["symbol"])
        if px is None:
            continue
        exit_px = reason = None
        if force_close:
            exit_px, reason = px, "EOD close"
        elif px <= p["stop"]:
            exit_px, reason = p["stop"], ("locked gain" if p["stop"] >= p["entry"] else "stop hit")
        elif p.get("target") and px >= p["target"]:
            exit_px, reason = p["target"], "target hit"
        if exit_px is not None:
            via = "sim"
            if bs is None:
                bs = _broker()                                 # connect only now, on a real exit
            if bs.get("can_auto_trade"):                       # close via real IBKR paper
                r = _place(p["symbol"], p["shares"], "SELL")
                if r.get("filled") and r.get("avg_fill"):
                    exit_px, via = round(float(r["avg_fill"]), 2), "ibkr"
                else:
                    _log(f"IBKR sell not filled {p['symbol']} ({r.get('status') or r.get('error')}) — marking exit {exit_px} (sim)")
            r2 = rm.record_exit(p["symbol"], exit_px)
            _alert(f"EXIT[{via}] {p['symbol']} @ ${exit_px} ({reason}) pnl ${r2.get('pnl')} | realized today ${r2.get('realized_today')}")


def maybe_enter():
    import risk_manager as rm, star_score
    s = rm.status()
    if s["halted"]:
        _alert("HALTED — daily loss limit hit, no new entries"); return
    if len(s["open_positions"]) >= rm.CFG["max_open"]:
        return
    open_syms = {p["symbol"] for p in s["open_positions"]}
    # pre-holiday criteria: before a long weekend, low volume + gap risk -> be pickier
    min_score = 5
    try:
        import market_calendar as mc
        if mc.long_weekend_ahead():
            min_score = 7
            _log("pre-holiday session — raising entry bar to score>=7 (low volume/gap risk)")
    except Exception:
        pass
    pick = star_score.best_pick(equity=rm.CFG["equity"], min_score=min_score)  # gold-bot 9-vote + 2.5:1 ATR
    plan = (pick.get("risk") or {}).get("plan") or {}
    if (pick.get("risk") or {}).get("verdict") != "APPROVED":
        _log(f"no 9-vote setup ({pick.get('symbol')}: {(pick.get('risk') or {}).get('verdict')})"); return
    sym = pick["symbol"]
    if sym in open_syms or plan.get("shares", 0) < 1:
        return
    entry_px, via = plan["entry"], "sim"
    bs = _broker()
    if bs.get("can_auto_trade"):                               # enter via real IBKR paper
        r = _place(sym, plan["shares"], "BUY")
        if r.get("filled") and r.get("avg_fill"):
            entry_px, via = round(float(r["avg_fill"]), 2), "ibkr"
        else:                                                  # IBKR mode on but no fill -> don't fake a sim entry
            _log(f"IBKR buy not filled {sym} ({r.get('status') or r.get('error')}) — no entry this tick")
            return
    rm.record_entry(sym, entry_px, plan["stop"], plan["shares"], plan["target"])
    _alert(f"ENTER[{via}] {sym} {plan['shares']}sh @ ${entry_px} stop ${plan['stop']} tgt ${plan['target']} "
         f"risk ${plan['dollar_risk']} | {pick.get('thesis','')[:55]}")


RESULTS = os.path.join(HERE, "..", "data", "paper_results.csv")
RES_FIELDS = ["date", "trades", "wins", "losses", "win_rate", "net_pnl", "equity_end"]


def log_daily_summary():
    """Append today's result to data/paper_results.csv (idempotent per date).
    Builds the equity curve: equity_end = prior equity_end + today's net."""
    import csv
    import risk_manager as rm
    s = rm._load()
    today = s["date"]
    rows = []
    if os.path.exists(RESULTS):
        with open(RESULTS) as f:
            rows = list(csv.DictReader(f))
    if any(r["date"] == today for r in rows):
        return None                                  # already logged
    closed = s.get("closed", [])
    wins = sum(1 for t in closed if t.get("pnl", 0) > 0)
    losses = sum(1 for t in closed if t.get("pnl", 0) <= 0)
    net = round(s.get("realized_pnl", 0.0), 2)
    prev_eq = float(rows[-1]["equity_end"]) if rows else rm.CFG["equity"]
    row = {"date": today, "trades": len(closed), "wins": wins, "losses": losses,
           "win_rate": round(wins / len(closed) * 100, 1) if closed else 0,
           "net_pnl": net, "equity_end": round(prev_eq + net, 2)}
    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    with open(RESULTS, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RES_FIELDS)
        if not rows:
            w.writeheader()
        w.writerow(row)
    return _alert(f"DAILY SUMMARY {today}: {row['trades']} trades, {wins}W/{losses}L, "
                f"net ${net}, equity ${row['equity_end']}")


def eod_pnl_statement():
    """Telegram a full P&L statement at EOD: every closed trade today + totals."""
    import csv
    import risk_manager as rm
    s = rm._load()
    today = s["date"]
    closed = [t for t in s.get("closed", []) if str(t.get("closed_at", "")).startswith(today)]
    eq = rm.CFG["equity"]
    try:
        rows = list(csv.DictReader(open(RESULTS))) if os.path.exists(RESULTS) else []
        eq = float(rows[-1]["equity_end"]) if rows else eq
    except Exception:
        pass
    wins = sum(1 for t in closed if (t.get("pnl") or 0) > 0)
    net = round(sum(t.get("pnl") or 0 for t in closed), 2)
    lines = [f"📊 STAR EOD P&L STATEMENT — {today}", "─────────────────────"]
    if closed:
        for t in closed:
            pnl = t.get("pnl") or 0
            tag = "(partial)" if t.get("partial") else ""
            lines.append(f"{'🟢' if pnl >= 0 else '🔴'} {t['symbol']} {t.get('shares')}sh "
                         f"{t.get('entry')}→{t.get('exit')} {'+' if pnl >= 0 else ''}${pnl} "
                         f"({t.get('pnl_pct')}%) {tag}".rstrip())
    else:
        lines.append("No trades closed today.")
    lines += ["─────────────────────",
              f"Realized P&L: {'+' if net >= 0 else ''}${net}",
              f"Record: {wins}W / {len(closed) - wins}L"
              + (f" ({round(wins/len(closed)*100)}%)" if closed else ""),
              f"Equity: ${round(eq, 2)}"]
    return _alert("\n".join(lines))


def tick():
    now = _now_ct()
    phase = _market_phase(now)
    if phase == "closed":
        return _log("market closed — no action")
    manage_open(force_close=(phase == "eod"))
    if phase == "open":
        maybe_enter()
    if phase == "eod":
        log_daily_summary()                          # write the day's result + equity curve
        eod_pnl_statement()                          # Telegram the full P&L statement
    import risk_manager as rm
    st = rm.status()
    return _log(f"tick done [{phase}] | open {len(st['open_positions'])} | realized ${st['realized_pnl']} | halted {st['halted']}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        print(log_daily_summary() or "summary already logged for today")
    else:
        print(tick())
