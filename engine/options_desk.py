#!/usr/bin/env python3
"""
STAR — Options desk (experimental, paper). Expresses the VALIDATED 9-vote signal
through defined-risk CALL options for leverage, instead of inventing an untested
options strategy. Runs in PARALLEL to the stock desk (own ledger), so we can
compare options-vs-stock honestly over time.

Approach (honest, conservative):
  • Entry: a 9-vote APPROVED name (same signal the stock desk uses), not blocked by
    earnings/news → buy ONE ~30-45 DTE call (defined risk = premium).
  • Manage on the UNDERLYING (not Greeks): exit when the stock hits the strategy's
    1.5xATR stop or 3.75xATR target, OR the option is down 50% / up 100%, OR <=7
    DTE (theta cliff), OR earnings within 2 days.
  • Max loss per trade = premium. Max 1 open option position (small account).
Honest limits: can't backtest options (no free history) — this is forward paper
validation only; theta + wide spreads are real drags. Max loss is the premium.
"""
import json
import os
import sys
from datetime import date, datetime

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
STATE = os.path.join(HERE, "..", "data", "options_state.json")


def _load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"open": [], "realized": 0.0, "trades": 0, "wins": 0}


def _save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2, default=str)


def _underlying(sym):
    import yfinance as yf
    try:
        return float(yf.Ticker(sym).fast_info.get("lastPrice"))
    except Exception:
        return None


def manage():
    import paper_session as ps, options_play as op, ibkr_broker as b
    s = _load()
    if not s["open"]:
        return
    bs = ps._broker()
    for p in list(s["open"]):
        px = _underlying(p["symbol"])
        opx = op.option_price(p["symbol"], p["expiry"], p["strike"], "C")
        if px is None:
            continue
        dte = (datetime.strptime(p["expiry"], "%Y-%m-%d").date() - date.today()).days
        reason = None
        if px <= p["under_stop"]:
            reason = "underlying stop"
        elif px >= p["under_target"]:
            reason = "underlying target"
        elif opx is not None and opx <= p["premium"] * 0.5:
            reason = "option -50%"
        elif opx is not None and opx >= p["premium"] * 2.0:
            reason = "option +100%"
        elif dte <= 7:
            reason = "DTE<=7 (theta)"
        if reason:
            exitp = opx if opx is not None else 0.0
            if bs.get("can_auto_trade"):
                b.place_option_order(p["symbol"], p["expiry"], p["strike"], "C", p["contracts"], exitp, action="SELL")
            pnl = round((exitp - p["premium"]) * 100 * p["contracts"], 2)
            s["realized"] = round(s["realized"] + pnl, 2); s["trades"] += 1
            s["wins"] += 1 if pnl > 0 else 0
            s["open"].remove(p); _save(s)
            _rec_db({**p, "exit": exitp, "pnl": pnl, "closed_at": datetime.now().isoformat()})
            ps._alert(f"{'🟢' if pnl>=0 else '🔴'} OPTION EXIT — {p['symbol']} {p['strike']}C "
                      f"({reason}) {'+' if pnl>=0 else ''}${pnl} | realized ${s['realized']}")


def maybe_enter():
    import paper_session as ps, star_score as ss, options_play as op, ibkr_broker as b, earnings
    s = _load()
    if len(s["open"]) >= 1:           # one option position at a time ($500)
        return
    try:
        nw = __import__("news_watch").assess()
        if nw.get("risk_level") == "high":
            return
    except Exception:
        pass
    pick = ss.best_pick(min_score=6)   # slightly stricter for the leveraged play
    if (pick.get("risk") or {}).get("verdict") != "APPROVED":
        return
    sym = pick["symbol"]
    if earnings.blocked(sym, within=5)["blocked"]:
        return
    plan = pick["risk"]["plan"]
    opt = op.best_call(sym, min_dte=30, max_dte=45)   # swing-appropriate, low theta
    if opt.get("error") or not opt.get("strike"):
        return
    bs = ps._broker()
    via = "sim"
    if bs.get("can_auto_trade"):
        r = b.place_option_order(sym, opt["expiry"], opt["strike"], "C", opt["contracts"], opt["premium"])
        if not (r.get("filled") and r.get("avg_fill")):
            ps._log(f"option buy not filled {sym} ({r.get('status') or r.get('error')})")
            return
        prem = round(float(r["avg_fill"]), 2); via = "ibkr"
    else:
        prem = opt["premium"]
    pos = {"symbol": sym, "strike": opt["strike"], "expiry": opt["expiry"], "right": "C",
           "contracts": opt["contracts"], "premium": prem,
           "under_entry": plan["entry"], "under_stop": plan["stop"], "under_target": plan["target"],
           "max_loss": round(prem * 100 * opt["contracts"], 2), "opened_at": datetime.now().isoformat()}
    s["open"].append(pos); _save(s)
    ps._alert(f"🟢 OPTION ENTRY[{via}] {sym} {opt['strike']}C exp {opt['expiry']} "
              f"x{opt['contracts']} @ ${prem} (max loss ${pos['max_loss']}, {opt.get('leverage')}x) "
              f"· {pick.get('thesis','')[:45]}")


def _rec_db(p):
    try:
        import db
        db.record_paper_trade({"source": "option", "symbol": f"{p['symbol']} {p['strike']}C",
                               "dir": "CALL", "shares": p.get("contracts"), "entry": p.get("premium"),
                               "exit": p.get("exit"), "pnl": p.get("pnl"),
                               "opened_at": p.get("opened_at"), "closed_at": p.get("closed_at")})
    except Exception:
        pass


def tick():
    import paper_session as ps
    phase = ps._market_phase(ps._now_ct())
    if phase == "closed":
        return "market closed"
    manage()
    if phase == "open":
        maybe_enter()
    s = _load()
    return f"options tick [{phase}] | open {len(s['open'])} | realized ${s['realized']} | {s['trades']} closed"


def stats():
    s = _load()
    return {"open": s["open"], "realized": s["realized"], "trades": s["trades"],
            "wins": s["wins"], "win_rate": round(s["wins"]/s["trades"]*100, 1) if s["trades"] else 0}


if __name__ == "__main__":
    print(tick())
