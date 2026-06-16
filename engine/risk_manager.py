#!/usr/bin/env python3
"""
STAR — Risk Manager. The brain's risk layer. Every trade decision passes through
here BEFORE (size it / approve / reject) and AFTER (track R, daily P&L, exits).

This is how we take real risk responsibly: not by refusing to act, but by sizing
every position so a loss is survivable and the day can't blow up. The rules are
numbers, not vibes:

  - Risk per trade   = RISK_PCT of equity   (default 5% -> $25 on $500)
  - Daily max loss   = DAILY_PCT of equity  (default 10% -> $50, then flat)
  - Max open risk    = total $ at risk across open positions <= daily max loss
  - Position cost cap = MAX_POS_PCT of equity per name (default 60%)
  - Min reward:risk  = MIN_RR (default 1.5) if a target is given

State (today's realized P&L + open positions) persists in data/risk_state.json so
the daily loss limit and open-risk cap are enforced ACROSS trades, not per trade.
"""
import json
import math
import os
from datetime import date, datetime

HERE = os.path.dirname(__file__)
STATE = os.path.join(HERE, "..", "data", "risk_state.json")

CFG = {
    "equity": 500.0,        # Webull runner account
    "risk_pct": 0.15,       # 15% of equity at risk per trade -> $75 (user-set, aggressive)
    "daily_pct": 0.30,      # 30% daily max loss -> $150 (raised so a 15% trade fits)
    "max_pos_pct": 0.90,    # one position's cost <= 90% of equity (scalp needs room)
    "max_open": 2,          # max concurrent positions
    "min_rr": 1.2,          # require >= 1.2R (scalps run tighter targets)
}


def _today():
    return date.today().isoformat()


def _load():
    try:
        s = json.load(open(STATE))
    except Exception:
        s = {}
    if s.get("date") != _today():               # new day -> reset realized P&L,
        s = {"date": _today(), "realized_pnl": 0.0,  # but CARRY OVER open positions
             "open": s.get("open", []), "closed": []}
        _save(s)
    return s


def _save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2, default=str)


def pre_trade_check(symbol, entry, stop, target=None, equity=None, cfg=None):
    """Approve/reject + exact size. The gate the brain calls BEFORE any entry."""
    c = {**CFG, **(cfg or {})}
    eq = float(equity or c["equity"])
    entry = float(entry); stop = float(stop)
    s = _load()
    reasons, warnings = [], []

    # --- structural validity ---
    if entry <= 0 or stop <= 0:
        return _decision(False, symbol, ["invalid entry/stop"], [], None)
    if stop >= entry:
        return _decision(False, symbol, ["stop must be BELOW entry for a long"], [], None)

    risk_ps = entry - stop
    rr = (float(target) - entry) / risk_ps if target else None

    # --- daily loss limit (hard stop on the day) ---
    daily_max = eq * c["daily_pct"]
    realized = s["realized_pnl"]
    if realized <= -daily_max:
        reasons.append(f"daily loss limit hit (realized ${realized:.2f} <= -${daily_max:.2f}) — NO MORE TRADES today")

    # --- open positions / open-risk budget ---
    open_risk = sum(p["risk_dollars"] for p in s["open"])
    if len(s["open"]) >= c["max_open"]:
        reasons.append(f"max open positions ({c['max_open']}) reached")

    # --- size by risk ---
    risk_dollars = eq * c["risk_pct"]
    # cap so total open risk + this trade <= daily max loss
    remaining_budget = daily_max - open_risk - max(0.0, -realized)
    if remaining_budget <= 0:
        reasons.append(f"no risk budget left today (open risk ${open_risk:.2f}, realized ${realized:.2f})")
    risk_dollars = min(risk_dollars, max(0.0, remaining_budget))
    shares = math.floor(risk_dollars / risk_ps) if risk_ps > 0 else 0

    # --- position cost cap vs equity ---
    cost_cap = eq * c["max_pos_pct"]
    if shares * entry > cost_cap:
        shares = math.floor(cost_cap / entry)
        warnings.append(f"size capped by {int(c['max_pos_pct']*100)}% position limit (${cost_cap:.0f})")
    actual_risk = round(shares * risk_ps, 2)

    if shares < 1:
        reasons.append("computed size < 1 share after risk caps — trade too risky for this account")
    if target and rr is not None and rr < c["min_rr"]:
        reasons.append(f"reward:risk {rr:.2f} < min {c['min_rr']}")

    approved = not reasons
    plan = {
        "symbol": symbol.upper(), "entry": round(entry, 2), "stop": round(stop, 2),
        "target": round(float(target), 2) if target else None,
        "risk_per_share": round(risk_ps, 2), "shares": shares,
        "cost": round(shares * entry, 2), "dollar_risk": actual_risk,
        "rr": round(rr, 2) if rr is not None else None,
        "pct_of_equity_risked": round(actual_risk / eq * 100, 1),
    }
    return _decision(approved, symbol, reasons, warnings, plan,
                     daily={"realized_pnl": round(realized, 2), "daily_max_loss": round(daily_max, 2),
                            "open_positions": len(s["open"]), "open_risk": round(open_risk, 2),
                            "risk_budget_left": round(max(0.0, remaining_budget), 2)})


def _decision(approved, symbol, reasons, warnings, plan, daily=None):
    return {"symbol": symbol.upper(), "approved": bool(approved),
            "verdict": "APPROVED" if approved else "REJECTED",
            "reasons": reasons, "warnings": warnings, "plan": plan, "daily": daily,
            "checked_at": datetime.now().astimezone().isoformat()}


def record_entry(symbol, entry, stop, shares, target=None):
    s = _load()
    s["open"].append({"symbol": symbol.upper(), "entry": entry, "stop": stop, "shares": shares,
                      "target": target, "risk_dollars": round((entry - stop) * shares, 2),
                      "opened_at": datetime.now().isoformat()})
    _save(s); return s


TRADES_CSV = os.path.join(HERE, "..", "data", "paper_trades.csv")
TRADE_FIELDS = ["opened_at", "closed_at", "duration_min", "symbol", "shares",
                "entry", "exit", "stop", "target", "pnl", "pnl_pct"]


def _append_trade(rec):
    """Durably log every closed trade (survives the daily reset)."""
    import csv
    new = not os.path.exists(TRADES_CSV)
    os.makedirs(os.path.dirname(TRADES_CSV), exist_ok=True)
    with open(TRADES_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TRADE_FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: rec.get(k) for k in TRADE_FIELDS})


def record_exit(symbol, exit_price):
    s = _load(); hit = None
    for p in s["open"]:
        if p["symbol"] == symbol.upper():
            hit = p; break
    if not hit:
        return {"error": f"no open position in {symbol}"}
    pnl = round((exit_price - hit["entry"]) * hit["shares"], 2)
    s["open"].remove(hit)
    s["realized_pnl"] = round(s["realized_pnl"] + pnl, 2)
    closed_at = datetime.now().isoformat()
    try:
        dur = round((datetime.fromisoformat(closed_at)
                     - datetime.fromisoformat(hit["opened_at"])).total_seconds() / 60, 1)
    except Exception:
        dur = None
    rec = {**hit, "exit": exit_price, "pnl": pnl,
           "pnl_pct": round((exit_price / hit["entry"] - 1) * 100, 2),
           "closed_at": closed_at, "duration_min": dur}
    s["closed"].append(rec)
    _save(s)
    _append_trade(rec)                       # permanent trade history
    return {"symbol": symbol.upper(), "pnl": pnl, "realized_today": s["realized_pnl"]}


def post_trade_check(symbol, current_price):
    """AFTER-decision check on an open position: R, stop status, action."""
    s = _load(); p = next((x for x in s["open"] if x["symbol"] == symbol.upper()), None)
    if not p:
        return {"error": f"no open position in {symbol}"}
    risk_ps = p["entry"] - p["stop"]
    r_mult = round((current_price - p["entry"]) / risk_ps, 2) if risk_ps else 0
    if current_price <= p["stop"]:
        action = "EXIT NOW — stop hit"
    elif r_mult >= 2:
        action = "TRAIL / take final — at/above 2R"
    elif r_mult >= 1:
        action = "scale out half, trail stop to breakeven"
    else:
        action = "hold — thesis intact, stop in place"
    return {"symbol": symbol.upper(), "current": current_price, "entry": p["entry"], "stop": p["stop"],
            "r_multiple": r_mult, "action": action,
            "daily_realized": s["realized_pnl"]}


def status():
    s = _load(); c = CFG
    return {"date": s["date"], "equity": c["equity"], "realized_pnl": s["realized_pnl"],
            "daily_max_loss": round(c["equity"] * c["daily_pct"], 2),
            "open_positions": s["open"],
            "open_risk": round(sum(p["risk_dollars"] for p in s["open"]), 2),
            "halted": s["realized_pnl"] <= -c["equity"] * c["daily_pct"]}


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4 and sys.argv[1] == "check":
        # check SYM ENTRY STOP [TARGET]
        t = float(sys.argv[5]) if len(sys.argv) > 5 else None
        print(json.dumps(pre_trade_check(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), t), indent=2))
    else:
        print(json.dumps(status(), indent=2, default=str))
