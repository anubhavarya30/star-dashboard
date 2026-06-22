#!/usr/bin/env python3
"""
STAR — Options layer. For a strong directional name, surface a concrete CALL play
so a $500 account gets real leverage instead of a ~16-share stock trade that makes
$9 on a win. Defined risk: the most you can lose is the premium you pay.

All real data (yfinance options chain). Picks a near-dated, liquid, ~ATM/slightly
-OTM call, computes cost/contract, contracts that fit a budget, breakeven, max
loss (= premium), and leverage vs buying shares. Honest about the tradeoff:
options decay (theta) and can go to ZERO — that's the price of the leverage.
"""
import os
import sys
from datetime import date, datetime

HERE = os.path.dirname(__file__)


def _mid(bid, ask, last):
    try:
        bid = float(bid or 0); ask = float(ask or 0); last = float(last or 0)
    except (TypeError, ValueError):
        return None
    if bid > 0 and ask > 0:
        return round((bid + ask) / 2, 2)
    return round(ask or last or 0, 2) or None


def best_call(symbol, equity=500.0, budget_pct=0.30, min_dte=5, max_dte=21):
    import yfinance as yf
    tk = yf.Ticker(symbol)
    try:
        spot = float(tk.fast_info.get("lastPrice") or tk.fast_info.get("last_price"))
    except Exception:
        spot = None
    if not spot:
        return {"symbol": symbol.upper(), "error": "no spot price"}
    exps = list(getattr(tk, "options", []) or [])
    if not exps:
        return {"symbol": symbol.upper(), "error": "no options listed for this name"}

    today = date.today()
    # choose the nearest expiry within [min_dte, max_dte]; else nearest available
    def dte(e):
        return (datetime.strptime(e, "%Y-%m-%d").date() - today).days
    in_range = [e for e in exps if min_dte <= dte(e) <= max_dte]
    exp = (in_range or sorted(exps, key=dte))[0]
    days = dte(exp)

    try:
        calls = tk.option_chain(exp).calls
    except Exception as e:
        return {"symbol": symbol.upper(), "error": f"chain fetch failed: {e}"}

    # candidate strikes: ATM to ~12% OTM, liquid (OI>0, has a price)
    cands = []
    for strike, bid, ask, last, oi, vol in zip(
            calls["strike"], calls["bid"], calls["ask"], calls["lastPrice"],
            calls["openInterest"], calls["volume"]):
        try:
            strike = float(strike); oi = float(oi or 0)
        except (TypeError, ValueError):
            continue
        if strike < spot * 0.98 or strike > spot * 1.12 or oi < 1:
            continue
        prem = _mid(bid, ask, last)
        if not prem or prem <= 0:
            continue
        cands.append({"strike": strike, "premium": prem, "oi": oi})
    if not cands:
        return {"symbol": symbol.upper(), "spot": round(spot, 2), "expiry": exp,
                "error": "no liquid near-ATM calls (wide/empty chain)"}

    # prefer the most liquid strike nearest to ATM (slightly OTM ok)
    cands.sort(key=lambda c: (abs(c["strike"] - spot), -c["oi"]))
    best = cands[0]
    cost_pc = round(best["premium"] * 100, 2)               # one contract
    budget = equity * budget_pct
    contracts = max(1, int(budget // cost_pc)) if cost_pc <= budget else 1
    max_loss = round(cost_pc * contracts, 2)                # defined risk = total premium
    breakeven = round(best["strike"] + best["premium"], 2)
    notional = round(spot * 100 * contracts, 2)             # shares-equivalent controlled
    leverage = round(notional / max_loss, 1) if max_loss else None
    shares_for_same = int(max_loss / spot) if spot else 0   # shares you'd get for the same $

    return {
        "symbol": symbol.upper(), "spot": round(spot, 2), "expiry": exp, "dte": days,
        "type": "CALL", "strike": best["strike"], "premium": best["premium"],
        "cost_per_contract": cost_pc, "contracts": contracts, "max_loss": max_loss,
        "pct_of_equity": round(max_loss / equity * 100, 1), "breakeven": breakeven,
        "open_interest": int(best["oi"]), "notional_controlled": notional, "leverage": leverage,
        "vs_shares": f"${max_loss:.0f} buys {contracts} call(s) controlling {contracts*100} sh "
                     f"vs only {shares_for_same} shares outright",
        "warning": "Defined risk = you can lose 100% of premium. Theta decays it daily; "
                   "needs the move to happen reasonably fast.",
        "generated_at": datetime.now().astimezone().isoformat(),
    }


def option_price(symbol, expiry, strike, right="C"):
    """Current mid price of a specific option contract (yfinance chain). For exits."""
    import yfinance as yf
    try:
        ch = yf.Ticker(symbol).option_chain(expiry)
        df = ch.calls if right.upper().startswith("C") else ch.puts
        row = df[df["strike"] == float(strike)]
        if len(row) == 0:
            return None
        bid = float(row["bid"].iloc[0] or 0); ask = float(row["ask"].iloc[0] or 0)
        last = float(row["lastPrice"].iloc[0] or 0)
        return round((bid + ask) / 2, 2) if (bid > 0 and ask > 0) else (round(ask or last, 2) or None)
    except Exception:
        return None


def best_put(symbol, equity=500.0, budget_pct=0.30, min_dte=5, max_dte=21):
    """Bearish play — catch a DROP with defined risk. Picks a liquid near-ATM put.
    Same engine as best_call, mirrored to the downside."""
    import yfinance as yf
    tk = yf.Ticker(symbol)
    try:
        spot = float(tk.fast_info.get("lastPrice") or tk.fast_info.get("last_price"))
    except Exception:
        spot = None
    if not spot:
        return {"symbol": symbol.upper(), "error": "no spot price"}
    exps = list(getattr(tk, "options", []) or [])
    if not exps:
        return {"symbol": symbol.upper(), "error": "no options listed"}
    from datetime import date, datetime
    today = date.today()
    def dte(e):
        return (datetime.strptime(e, "%Y-%m-%d").date() - today).days
    in_range = [e for e in exps if min_dte <= dte(e) <= max_dte]
    exp = (in_range or sorted(exps, key=dte))[0]
    days = dte(exp)
    try:
        puts = tk.option_chain(exp).puts
    except Exception as e:
        return {"symbol": symbol.upper(), "error": f"chain fetch failed: {e}"}
    cands = []
    for strike, bid, ask, last, oi in zip(puts["strike"], puts["bid"], puts["ask"],
                                          puts["lastPrice"], puts["openInterest"]):
        try:
            strike = float(strike); oi = float(oi or 0)
        except (TypeError, ValueError):
            continue
        if strike > spot * 1.02 or strike < spot * 0.88 or oi < 1:  # ATM to ~12% OTM (below spot)
            continue
        prem = _mid(bid, ask, last)
        if not prem or prem <= 0:
            continue
        cands.append({"strike": strike, "premium": prem, "oi": oi})
    if not cands:
        return {"symbol": symbol.upper(), "spot": round(spot, 2), "expiry": exp,
                "error": "no liquid near-ATM puts"}
    cands.sort(key=lambda c: (abs(c["strike"] - spot), -c["oi"]))
    best = cands[0]
    cost_pc = round(best["premium"] * 100, 2)
    budget = equity * budget_pct
    contracts = max(1, int(budget // cost_pc)) if cost_pc <= budget else 1
    max_loss = round(cost_pc * contracts, 2)
    breakeven = round(best["strike"] - best["premium"], 2)
    notional = round(spot * 100 * contracts, 2)
    return {
        "symbol": symbol.upper(), "spot": round(spot, 2), "expiry": exp, "dte": days,
        "type": "PUT", "strike": best["strike"], "premium": best["premium"],
        "cost_per_contract": cost_pc, "contracts": contracts, "max_loss": max_loss,
        "pct_of_equity": round(max_loss / equity * 100, 1), "breakeven": breakeven,
        "open_interest": int(best["oi"]), "notional_controlled": notional,
        "leverage": round(notional / max_loss, 1) if max_loss else None,
        "warning": "Defined risk = lose 100% of premium if wrong. Profits as the stock FALLS "
                   "below breakeven. Theta decays it daily.",
        "generated_at": datetime.now().astimezone().isoformat(),
    }


if __name__ == "__main__":
    import json
    sym = sys.argv[1] if len(sys.argv) > 1 else "QBTS"
    side = sys.argv[2] if len(sys.argv) > 2 else "call"
    print(json.dumps(best_put(sym) if side == "put" else best_call(sym), indent=2, default=str))
