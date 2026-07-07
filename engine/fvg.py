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


def backtest(symbol, target_R=3.0, max_wait=15, htf_filter=True, vol_mult=1.2):
    """Backtest FVG v3 (matches engine/fvg_strategy.pine + live signal()): 1h intraday
    bars, gap must form on above-avg volume, stacked-EMA uptrend (close>=EMA200 AND
    EMA50>EMA200), LIMIT entry at the gap top, stop below the gap, 3R target. No
    look-ahead: the outcome is scanned only on bars AFTER the entry fills."""
    import yfinance as yf
    h = yf.Ticker(symbol).history(period="730d", interval="1h")
    if h is None or len(h) < 250:
        return {"symbol": symbol, "error": "not enough data"}
    highs = list(h["High"]); lows = list(h["Low"]); closes = list(h["Close"]); vols = list(h["Volume"])
    fvgs = find_fvgs(highs, lows, "bull")
    trades = []
    used_entry_bars = set()
    for g in fvgs:
        gi, glo, ghi = g["i"], g["lo"], g["hi"]
        # quality: gap-forming bar must carry conviction volume
        if vol_mult and gi >= 20:
            vsma = statistics.mean(vols[gi - 20:gi]) or 0
            if vsma and vols[gi] < vol_mult * vsma:
                continue
        # look for a retest that fills a LIMIT at the gap top (ghi)
        for j in range(gi + 1, min(gi + 1 + max_wait, len(closes) - 1)):
            if j in used_entry_bars:
                continue
            # limit at ghi fills if the bar trades down to/through the gap top
            if lows[j] <= ghi and closes[j] > glo:
                # stacked-trend filter at the entry bar
                if htf_filter and (closes[j] < _ema(closes[:j + 1], 200)
                                   or _ema(closes[:j + 1], 50) <= _ema(closes[:j + 1], 200)):
                    break
                entry = ghi                       # LIMIT fill at the gap top
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


def signal(symbol, htf_filter=True, target_R=3.0, vol_mult=1.2, max_wait=15):
    """LIVE check (FVG v3 — TradingView-proven params, basket PF 1.2–1.66 across
    NVDA/AAPL/MSFT/AMD/TSM): is `symbol` setting up a bullish-FVG-support long NOW?

    v3 edge (synced from engine/fvg_strategy.pine, 2026-07-06):
      • 1h intraday bars (daily overnight gaps blew through the stop — no edge)
      • gap must form on ABOVE-AVG volume (>= vol_mult x 20-bar SMA) — quality filter
      • STACKED uptrend: close >= EMA200 AND EMA50 > EMA200 (not just price>EMA200)
      • entry = LIMIT at the GAP TOP (ghi) — tight risk, better fill than entering at close
      • stop = gap bottom - 0.3%; target = entry + 3R
    Returns a LIMIT order (order='limit', entry=gap top) for the desk to rest + cancel."""
    import yfinance as yf
    h = yf.Ticker(symbol).history(period="60d", interval="1h")
    if h is None or len(h) < 210:
        return {"symbol": symbol, "setup": False, "error": "no data"}
    highs = list(h["High"]); lows = list(h["Low"]); closes = list(h["Close"]); vols = list(h["Volume"])
    ema50 = _ema(closes, 50); ema200 = _ema(closes, 200)
    fvgs = find_fvgs(highs, lows, "bull")
    last = len(closes) - 1
    for g in reversed(fvgs):
        gi = g["i"]
        if gi < last - max_wait or gi >= last:
            continue
        glo, ghi = g["lo"], g["hi"]
        # quality: the gap-forming bar must carry conviction volume
        if vol_mult and gi >= 20:
            vsma = statistics.mean(vols[gi - 20:gi]) or 0
            if vsma and vols[gi] < vol_mult * vsma:
                continue
        # retest: current bar dips into the zone but holds above the gap bottom
        if lows[last] <= ghi and closes[last] > glo:
            # stacked-trend filter (HTF bias): price above EMA200 AND EMA50>EMA200
            if htf_filter and (closes[last] < ema200 or ema50 <= ema200):
                continue
            entry = round(ghi, 2)                 # LIMIT at the gap top
            stop = round(glo * 0.997, 2)
            risk = entry - stop
            if risk <= 0:
                continue
            return {"symbol": symbol, "setup": True, "order": "limit",
                    "entry": entry, "stop": stop,
                    "target": round(entry + target_R * risk, 2), "rr": target_R,
                    "fvg_zone": [round(glo, 2), round(ghi, 2)],
                    "note": "FVG v3: 1h gap + vol + stacked-EMA, limit @ gap top, 3R"}
    return {"symbol": symbol, "setup": False}


if __name__ == "__main__":
    import json
    if len(sys.argv) > 1 and sys.argv[1] == "signal":
        print(json.dumps(signal(sys.argv[2] if len(sys.argv) > 2 else "NVDA"), indent=2))
    else:
        print(json.dumps(basket_backtest(), indent=2, default=str))
