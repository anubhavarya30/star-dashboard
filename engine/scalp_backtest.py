#!/usr/bin/env python3
"""
STAR — scalp engine tuner. Backtests the oversold-bounce scalp on ~60 days of 5-minute
bars and SWEEPS the parameters (RSI oversold/turn thresholds, target-R, hold time) to
find the settings that maximize expectancy. This is how we sharpen the proven edge.

No look-ahead: entry decided on bar i from data up to i; outcome scanned on bars > i.
"""
import os
import sys
import itertools

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)


def _rsi_series(c, n=14):
    r = [None] * len(c)
    if len(c) < n + 1:
        return r
    g = l = 0.0
    for i in range(1, n + 1):
        d = c[i] - c[i - 1]; g += max(d, 0); l += max(-d, 0)
    ag, al = g / n, l / n
    r[n] = 100 - 100 / (1 + ag / al) if al else 100.0
    for i in range(n + 1, len(c)):
        d = c[i] - c[i - 1]
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
        r[i] = 100 - 100 / (1 + ag / al) if al else 100.0
    return r


def _ema_series(c, n):
    k = 2 / (n + 1); e = [c[0]] * len(c)
    for i in range(1, len(c)):
        e[i] = c[i] * k + e[i - 1] * (1 - k)
    return e


def _load_bars(symbols):
    """Batch 60d/5m bars; precompute rsi + ema8 per symbol once (reused across sweep)."""
    import yfinance as yf
    data = yf.download(symbols, period="60d", interval="5m", group_by="ticker",
                       progress=False, threads=True)
    out = {}
    for s in symbols:
        try:
            df = data[s] if len(symbols) > 1 else data
            c = [float(x) for x in df["Close"].dropna().tolist()]
            h = [float(x) for x in df["High"].dropna().tolist()]
            lo = [float(x) for x in df["Low"].dropna().tolist()]
            if len(c) < 100:
                continue
            n = min(len(c), len(h), len(lo))
            out[s] = {"c": c[:n], "h": h[:n], "l": lo[:n],
                      "rsi": _rsi_series(c[:n], 14), "ema8": _ema_series(c[:n], 8)}
        except Exception:
            continue
    return out


def _run(bars, oversold, turn, target_R, max_hold):
    """Simulate the scalp on precomputed bars; return list of R-outcomes."""
    trades = []
    for d in bars.values():
        c, h, lo, rsi, ema8 = d["c"], d["h"], d["l"], d["rsi"], d["ema8"]
        i, N = 20, len(c)
        while i < N - 1:
            r0, r3, r6 = rsi[i], rsi[i - 3], rsi[i - 6]
            if (r0 and r3 and r6 and min(r3, r6) <= oversold and r0 > r3 and r0 >= turn
                    and c[i] > ema8[i] and c[i] > c[i - 1]):
                entry = c[i]
                stop = min(min(lo[max(0, i - 10):i + 1]) * 0.998, entry * 0.99)
                risk = max(entry - stop, 0.01)
                target = entry + target_R * risk
                out, j = None, i
                for j in range(i + 1, min(i + 1 + max_hold, N)):
                    if lo[j] <= stop:
                        out = -1.0; break
                    if h[j] >= target:
                        out = target_R; break
                if out is None:
                    out = (c[j] - entry) / risk
                trades.append(out)
                i = j + 1
            else:
                i += 1
    return trades


def sweep(symbols=None):
    import star_score as ss
    syms = symbols or list(ss.UNIVERSE)[:20]
    bars = _load_bars(syms)
    grid = {
        "oversold": [30, 35, 40], "turn": [40, 45, 50],
        "target_R": [1.0, 1.2, 1.5, 2.0], "max_hold": [12, 18, 24],
    }
    results = []
    for ov, tn, tr, mh in itertools.product(grid["oversold"], grid["turn"], grid["target_R"], grid["max_hold"]):
        t = _run(bars, ov, tn, tr, mh)
        if len(t) < 30:
            continue
        n = len(t); wins = sum(1 for x in t if x > 0); totR = sum(t)
        results.append({"oversold": ov, "turn": tn, "target_R": tr, "max_hold_min": mh * 5,
                        "trades": n, "win_rate": round(wins / n * 100, 1),
                        "expectancy_R": round(totR / n, 3), "total_R": round(totR, 1)})
    results.sort(key=lambda r: r["expectancy_R"], reverse=True)
    return {"symbols": len(bars), "tested_combos": len(results), "top": results[:8],
            "current_settings_rank": next((i + 1 for i, r in enumerate(results)
                                           if r["oversold"] == 35 and r["turn"] == 42 and r["target_R"] == 1.2), None)}


if __name__ == "__main__":
    import json
    print(json.dumps(sweep(), indent=2, default=str))
