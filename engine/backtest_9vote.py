#!/usr/bin/env python3
"""
STAR — backtest of the LIVE strategy (9-vote tech score + ATR risk), modeled the
way the desk actually trades: signal on day i (data through i's close, NO look-
ahead) -> enter at day i+1 OPEN -> exit same day (desk flattens EOD) at the
1.5xATR stop if the day's low hits it, the 3.75xATR target if the high hits it
(rare in 1 day), else the day's CLOSE. Reports real expectancy per name + overall.

Honest limits: daily bars (not intraday), ignores the desk's +1R partial scale &
trailing (which would modestly help), assumes mid-ish fills. Good enough to answer:
does the 9-vote signal actually have an edge?
"""
import os
import sys
import statistics

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import star_score as ss   # reuse the EXACT live scoring functions


def backtest_symbol(sym, period="3y", min_score=5, warmup=205):
    import yfinance as yf
    h = yf.Ticker(sym).history(period=period)
    if h is None or len(h) < warmup + 20:
        return None
    O, Hi, Lo, C, V = list(h["Open"]), list(h["High"]), list(h["Low"]), list(h["Close"]), list(h["Volume"])
    n = len(C)
    trades = []
    i = warmup
    while i < n - 1:
        score, ind = ss.tech_score(C[:i + 1], V[:i + 1])
        if score >= min_score:
            entry = O[i + 1]
            atr = ind["atr"]
            stop = entry - 1.5 * atr
            target = entry + 3.75 * atr
            risk = entry - stop
            if risk <= 0:
                i += 1; continue
            # 1-day hold (EOD flatten): stop, then target, else close
            if Lo[i + 1] <= stop:
                exit_px, why = stop, "stop"
            elif Hi[i + 1] >= target:
                exit_px, why = target, "target"
            else:
                exit_px, why = C[i + 1], "eod"
            r = (exit_px - entry) / risk
            trades.append({"r": r, "pct": (exit_px / entry - 1) * 100, "why": why, "score": score})
            i += 2   # skip the trade day (one position at a time, flatten EOD)
        else:
            i += 1
    if not trades:
        return {"symbol": sym, "trades": 0}
    rs = [t["r"] for t in trades]
    wins = [t for t in trades if t["r"] > 0]
    gross_w = sum(t["r"] for t in wins)
    gross_l = -sum(t["r"] for t in trades if t["r"] <= 0)
    eq = 1.0
    peak = 1.0; mdd = 0.0
    for t in trades:
        eq *= (1 + t["pct"] / 100)
        peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak)
    return {"symbol": sym, "trades": len(trades), "win_rate": round(len(wins) / len(trades) * 100, 1),
            "expectancy_r": round(statistics.mean(rs), 3), "total_r": round(sum(rs), 1),
            "profit_factor": round(gross_w / gross_l, 2) if gross_l > 0 else None,
            "ret_pct": round((eq - 1) * 100, 1), "max_dd_pct": round(mdd * 100, 1)}


def run(universe=None, period="3y"):
    uni = universe or ss.UNIVERSE
    rows = []
    for s in uni:
        try:
            r = backtest_symbol(s, period=period)
            if r and r.get("trades"):
                rows.append(r)
        except Exception as e:
            print(f"  {s}: {type(e).__name__}", file=sys.stderr)
    return rows


if __name__ == "__main__":
    import json
    rows = run()
    print(json.dumps(rows, indent=2))
