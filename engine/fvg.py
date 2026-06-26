#!/usr/bin/env python3
"""
STAR — Fair Value Gap (FVG) / Inversion FVG strategy (ICT-style), built to be TESTED.

Honest framing: the viral "millionaire in 25 days / ₹8.5cr" claim is unverified
marketing. FVG is a legitimate price-imbalance concept, so this module DETECTS it and
BACKTESTS it on real data — we only let STAR trade it if the numbers show a real edge.

FVG = a 3-bar imbalance (price moved so fast it left an unfilled gap):
  bullish FVG at i:  high[i-2] < low[i]   -> gap zone [high[i-2], low[i]]
  bearish FVG at i:  low[i-2]  > high[i]  -> gap zone [high[i], low[i-2]]

Core tradeable idea (what we test): price pulls back INTO a bullish FVG and HOLDS it
as support -> go long; stop below the gap; target a multiple of risk. (Plus an
optional higher-timeframe uptrend filter, the ICT 'monthly bias'.)
"""
import os
import sys
import statistics

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))


def find_fvgs(highs, lows, kind="bull"):
    """Return list of {i, lo, hi} FVG zones. i = index of the 3rd bar of the gap."""
    out = []
    for i in range(2, len(highs)):
        if kind == "bull" and highs[i - 2] < lows[i]:
            out.append({"i": i, "lo": highs[i - 2], "hi": lows[i]})
        elif kind == "bear" and lows[i - 2] > highs[i]:
            out.append({"i": i, "lo": highs[i], "hi": lows[i - 2]})
    return out


def _ema(v, n):
    if len(v) < n:
        return v[-1]
    k = 2 / (n + 1); e = v[0]
    for x in v[1:]:
        e = x * k + e * (1 - k)
    return e


def backtest(symbol, target_R=2.0, max_wait=15, htf_filter=True):
    """Backtest the bullish-FVG-support long on 5y daily bars. Entry when a later bar
    dips into a bullish FVG and closes back above its bottom (holds support); stop
    below the gap; target = target_R * risk. Optional 200-EMA uptrend filter (HTF bias).
    No look-ahead: outcome is scanned only on bars AFTER entry."""
    import yfinance as yf
    h = yf.Ticker(symbol).history(period="5y")
    if h is None or len(h) < 250:
        return {"symbol": symbol, "error": "not enough data"}
    highs = list(h["High"]); lows = list(h["Low"]); closes = list(h["Close"])
    fvgs = find_fvgs(highs, lows, "bull")
    trades = []
    used_entry_bars = set()
    for g in fvgs:
        gi, glo, ghi = g["i"], g["lo"], g["hi"]
        # look for a retest in the bars right after the gap forms
        for j in range(gi + 1, min(gi + 1 + max_wait, len(closes) - 1)):
            if j in used_entry_bars:
                continue
            # retest: bar dips into the gap zone but closes back above the gap bottom
            if lows[j] <= ghi and closes[j] > glo:
                if htf_filter and closes[j] < _ema(closes[:j + 1], 200):
                    break  # only longs in an uptrend (HTF bias)
                entry = closes[j]
                stop = round(glo * 0.997, 4)
                risk = entry - stop
                if risk <= 0:
                    break
                target = entry + target_R * risk
                used_entry_bars.add(j)
                # scan forward for stop/target (next bar onward)
                outcome = None
                for k in range(j + 1, len(closes)):
                    if lows[k] <= stop:
                        outcome = -1; break
                    if highs[k] >= target:
                        outcome = +1; break
                if outcome is not None:
                    trades.append({"entry_i": j, "R": target_R if outcome > 0 else -1.0,
                                   "win": outcome > 0})
                break
    if not trades:
        return {"symbol": symbol, "trades": 0, "note": "no FVG setups triggered"}
    wins = sum(1 for t in trades if t["win"])
    total_R = sum(t["R"] for t in trades)
    n = len(trades)
    return {"symbol": symbol, "trades": n, "wins": wins,
            "win_rate": round(wins / n * 100, 1),
            "expectancy_R": round(total_R / n, 3), "total_R": round(total_R, 1),
            "target_R": target_R}


def basket_backtest(symbols=None, target_R=2.0):
    syms = symbols or ["NVDA", "AAPL", "MSFT", "AMD", "TSM", "META", "GOOGL", "AMZN",
                       "SPY", "QQQ", "TSLA", "AVGO"]
    rows, tot_tr, tot_R, tot_w = [], 0, 0.0, 0
    for s in syms:
        try:
            r = backtest(s, target_R=target_R)
            if r.get("trades"):
                rows.append(r); tot_tr += r["trades"]; tot_R += r["total_R"]; tot_w += r["wins"]
        except Exception:
            pass
    agg = {"names": len(rows), "trades": tot_tr,
           "win_rate": round(tot_w / tot_tr * 100, 1) if tot_tr else 0,
           "expectancy_R": round(tot_R / tot_tr, 3) if tot_tr else 0,
           "total_R": round(tot_R, 1), "target_R": target_R}
    return {"per_name": rows, "aggregate": agg}


def signal(symbol, htf_filter=True):
    """LIVE check: is `symbol` setting up a bullish-FVG-support long right now?
    Returns entry/stop/target if the latest bar is holding a fresh bullish FVG."""
    import yfinance as yf
    h = yf.Ticker(symbol).history(period="1y")
    if h is None or len(h) < 210:
        return {"symbol": symbol, "setup": False, "error": "no data"}
    highs = list(h["High"]); lows = list(h["Low"]); closes = list(h["Close"])
    fvgs = find_fvgs(highs, lows, "bull")
    last = len(closes) - 1
    for g in reversed(fvgs):
        if g["i"] < last - 15 or g["i"] >= last:
            continue
        glo, ghi = g["lo"], g["hi"]
        if lows[last] <= ghi and closes[last] > glo:      # current bar retesting + holding
            if htf_filter and closes[last] < _ema(closes, 200):
                continue
            entry = round(closes[last], 2); stop = round(glo * 0.997, 2)
            risk = entry - stop
            if risk <= 0:
                continue
            return {"symbol": symbol, "setup": True, "entry": entry, "stop": stop,
                    "target": round(entry + 2 * risk, 2), "rr": 2.0,
                    "fvg_zone": [round(glo, 2), round(ghi, 2)],
                    "note": "bullish FVG holding as support (uptrend)"}
    return {"symbol": symbol, "setup": False}


if __name__ == "__main__":
    import json
    if len(sys.argv) > 1 and sys.argv[1] == "signal":
        print(json.dumps(signal(sys.argv[2] if len(sys.argv) > 2 else "NVDA"), indent=2))
    else:
        print(json.dumps(basket_backtest(), indent=2, default=str))
