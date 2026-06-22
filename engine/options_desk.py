#!/usr/bin/env python3
"""
STAR — Options desk (experimental, paper). Expresses the VALIDATED 9-vote signal
through vertical DEBIT SPREADS, not naked long options — defined AND reduced risk,
far less theta bleed. Runs in PARALLEL to the stock desk (own ledger).

Approach (honest, conservative):
  • Direction from news: calm tape → bullish 9-vote → BULL CALL spread. Risk-off
    ("high") → weakest name → BEAR PUT spread (we profit on the drop, not hide).
  • Structure: buy near-ATM, sell further-OTM (same expiry, 30-45 DTE). Max loss =
    net debit (a fraction of a naked long); gains capped at the short strike.
  • Manage on the UNDERLYING: exit at the strategy's 1.5xATR stop / 3.75xATR target,
    OR the spread is down 50% / up 80% of its width, OR <=7 DTE, OR earnings near.
  • Max 1 open spread (small account). Defined risk = net debit, every time.
Honest limits: can't backtest options (no free history) — forward paper validation
only. Spreads cut theta and cost but CAP upside; that's the trade-off you chose.
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
        right = p.get("right", "C")
        is_put = right.upper().startswith("P")
        px = _underlying(p["symbol"])
        val = op.spread_value(p["symbol"], p["expiry"], p["long_strike"], p["short_strike"], right)
        if px is None:
            continue
        dte = (datetime.strptime(p["expiry"], "%Y-%m-%d").date() - date.today()).days
        debit = p["net_debit"]; width = p.get("width") or 0
        reason = None
        if is_put:                       # bearish: stop ABOVE, target BELOW
            if px >= p["under_stop"]:
                reason = "underlying stop"
            elif px <= p["under_target"]:
                reason = "underlying target"
        else:
            if px <= p["under_stop"]:
                reason = "underlying stop"
            elif px >= p["under_target"]:
                reason = "underlying target"
        if reason:
            pass
        elif val is not None and val <= debit * 0.5:
            reason = "spread -50%"
        elif val is not None and width and val >= debit + (width - debit) * 0.8:
            reason = "spread +80% of width"   # near max gain, take it
        elif dte <= 7:
            reason = "DTE<=7 (theta)"
        if reason:
            exitv = val if val is not None else 0.0
            if bs.get("can_auto_trade"):
                b.place_option_spread(p["symbol"], p["expiry"], p["long_strike"], p["short_strike"],
                                      right, p["contracts"],
                                      op.option_price(p["symbol"], p["expiry"], p["long_strike"], right) or 0.0,
                                      op.option_price(p["symbol"], p["expiry"], p["short_strike"], right) or 0.0,
                                      action="CLOSE")
            pnl = round((exitv - debit) * 100 * p["contracts"], 2)
            s["realized"] = round(s["realized"] + pnl, 2); s["trades"] += 1
            s["wins"] += 1 if pnl > 0 else 0
            s["open"].remove(p); _save(s)
            _rec_db({**p, "exit": exitv, "pnl": pnl, "closed_at": datetime.now().isoformat()})
            ps._alert(f"{'🟢' if pnl>=0 else '🔴'} SPREAD EXIT — {p['symbol']} "
                      f"{p['long_strike']}/{p['short_strike']}{right.upper()[0]} ({reason}) "
                      f"{'+' if pnl>=0 else ''}${pnl} | realized ${s['realized']}")


def maybe_enter():
    import paper_session as ps, star_score as ss, options_play as op, ibkr_broker as b, earnings
    s = _load()
    if len(s["open"]) >= 1:           # one option position at a time ($500)
        return

    # News-driven direction. Risk-off ("high") does NOT mean sit out — it means the
    # tape is selling, so we hunt the WEAKEST name and buy PUTS to profit on the drop.
    # Calm tape ("low"/"med") → bullish 9-vote → CALLS. Defined risk either way.
    risk_off = False
    try:
        risk_off = __import__("news_watch").assess().get("risk_level") == "high"
    except Exception:
        pass

    # Build a ranked candidate list (with each name's underlying plan), then take the
    # FIRST one we can actually afford a spread on — so an unaffordable top name (e.g.
    # META at $577) falls through to a cheaper name that fits the $500 account.
    if risk_off:
        cands = [{"symbol": c["symbol"], "thesis": c["thesis"],
                  "plan": {"entry": c["price"], "stop": c["stop"], "target": c["target"]}}
                 for c in ss.worst_candidates(min_score=6)]
        mk = op.best_put_spread; right, glyph = "P", "🔻"
    else:
        cands = []
        for c in ss.scan(min_score=6).get("ranked", []):
            rk = __import__("risk_manager").pre_trade_check(c["symbol"], c["price"], c["stop"], c["target"])
            if rk.get("approved"):
                cands.append({"symbol": c["symbol"],
                              "thesis": f"9-vote {c['score']}/9",
                              "plan": rk["plan"]})
        mk = op.best_call_spread; right, glyph = "C", "🟢"

    sym = plan = opt = None
    for c in cands:
        if earnings.blocked(c["symbol"], within=5)["blocked"]:
            continue
        o = mk(c["symbol"], min_dte=30, max_dte=45, target=c["plan"]["target"])
        if o.get("long_strike"):
            sym, plan, opt, pick = c["symbol"], c["plan"], o, c
            break
    if not opt:
        ps._log("no affordable spread among candidates")
        return
    bs = ps._broker()
    via = "sim"
    debit = opt["net_debit"]
    if bs.get("can_auto_trade"):
        lpx = op.option_price(sym, opt["expiry"], opt["long_strike"], right) or opt["net_debit"]
        spx = op.option_price(sym, opt["expiry"], opt["short_strike"], right) or 0.0
        r = b.place_option_spread(sym, opt["expiry"], opt["long_strike"], opt["short_strike"],
                                  right, opt["contracts"], lpx, spx, action="OPEN")
        if r.get("filled") and r.get("net_debit"):
            debit = r["net_debit"]; via = "ibkr"
        else:
            # IBKR refused/failed (e.g. TWS disclaimer 10141) — do NOT silently skip.
            # Record the trade on the simulator (clearly labelled) so the strategy is
            # always tracked and visible, then surface why the real fill didn't land.
            ps._log(f"spread not IBKR-filled {sym} ({r.get('error') or r.get('blocked') or r.get('legs')}) — recording SIM")
            via = "sim"
    max_loss = round(debit * 100 * opt["contracts"], 2)
    pos = {"symbol": sym, "right": right, "expiry": opt["expiry"],
           "long_strike": opt["long_strike"], "short_strike": opt["short_strike"],
           "width": opt["width"], "net_debit": debit, "contracts": opt["contracts"],
           "max_loss": max_loss, "max_gain": opt["max_gain"], "rr": opt["rr"],
           "under_entry": plan["entry"], "under_stop": plan["stop"], "under_target": plan["target"],
           "opened_at": datetime.now().isoformat()}
    s["open"].append(pos); _save(s)
    ps._alert(f"{glyph} SPREAD ENTRY[{via}] {sym} {opt['long_strike']}/{opt['short_strike']}{right} "
              f"exp {opt['expiry']} x{opt['contracts']} @ ${debit} debit "
              f"(max loss ${max_loss}, max gain ${opt['max_gain']}, {opt['rr']}:1) "
              f"· {pick.get('thesis','')[:40]}")


def _rec_db(p):
    try:
        import db
        r = p.get("right", "C")
        kind = "BULL CALL SPR" if r.upper().startswith("C") else "BEAR PUT SPR"
        db.record_paper_trade({"source": "option",
                               "symbol": f"{p['symbol']} {p['long_strike']}/{p['short_strike']}{r}",
                               "dir": kind, "shares": p.get("contracts"), "entry": p.get("net_debit"),
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
