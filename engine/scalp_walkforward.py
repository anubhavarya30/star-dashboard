#!/usr/bin/env python3
"""
STAR — walk-forward, cost-aware validator for the scalp edge. The honest test.

WHY: a single in-sample param sweep overfits — 90%+ of such backtests fail live
(CFA). And scalping dies on transaction costs. So this:
  1) WALK-FORWARD: for each fold, optimize params on PAST (in-sample) data, then
     measure performance on the NEXT, UNSEEN (out-of-sample) data. Only OOS counts.
  2) COSTS: every trade is charged slippage + commission. We report NET edge.
A real edge is POSITIVE out-of-sample AFTER costs. Anything else = don't risk money.

Writes data/walkforward.json for the dashboard's Validation board.
"""
import itertools
import json
import os
import sys

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "data", "walkforward.json")


def _run_seg(d, start, end, oversold, turn, target_R, max_hold):
    """Run the scalp logic over bars[start:end]; return per-trade {R, entry, risk}."""
    c, h, lo, rsi, ema8 = d["c"], d["h"], d["l"], d["rsi"], d["ema8"]
    trades, i = [], max(start, 20)
    while i < end - 1:
        r0, r3, r6 = rsi[i], rsi[i - 3], rsi[i - 6]
        if (r0 and r3 and r6 and min(r3, r6) <= oversold and r0 > r3 and r0 >= turn
                and c[i] > ema8[i] and c[i] > c[i - 1]):
            entry = c[i]
            stop = min(min(lo[max(0, i - 10):i + 1]) * 0.998, entry * 0.99)
            risk = max(entry - stop, 0.01)
            target = entry + target_R * risk
            out, j = None, i
            for j in range(i + 1, min(i + 1 + max_hold, end)):
                if lo[j] <= stop:
                    out = -1.0; break
                if h[j] >= target:
                    out = target_R; break
            if out is None:
                out = (c[j] - entry) / risk
            trades.append({"R": out, "entry": entry, "risk": risk})
            i = j + 1
        else:
            i += 1
    return trades


def _net_R(tr, slippage_bps, commission, notional):
    """Gross R minus realistic costs (slippage both sides + commission), in R units."""
    entry, risk = tr["entry"], tr["risk"]
    shares = max(1, int(notional / entry))
    gross = tr["R"] * risk * shares
    cost = 2 * commission + 2 * (slippage_bps / 10000.0) * entry * shares
    denom = risk * shares
    return (gross - cost) / denom if denom else 0.0


def _agg(lst):
    n = len(lst)
    return {"trades": n, "expectancy_R": round(sum(lst) / n, 3) if n else 0,
            "total_R": round(sum(lst), 1) if n else 0,
            "win_rate": round(sum(1 for x in lst if x > 0) / n * 100, 1) if n else 0}


def validate(symbols=None, folds=3, slippage_bps=5.0, commission=0.0, notional=500.0):
    import scalp_backtest as sb
    import star_score as ss
    syms = symbols or list(ss.UNIVERSE)[:12]
    bars = sb._load_bars(syms)
    grid = list(itertools.product([30, 35], [42, 45], [1.2, 2.0], [12, 24]))  # 16 combos
    is_exps, oos_gross, oos_net = [], [], []
    for d in bars.values():
        N = len(d["c"]); seg = N // (folds + 1)
        if seg < 60:
            continue
        for f in range(folds):
            is_end = (f + 1) * seg
            oos_end = min((f + 2) * seg, N)
            best = None
            for (ov, tn, tr_, mh) in grid:
                t = _run_seg(d, 0, is_end, ov, tn, tr_, mh)
                if len(t) >= 12:
                    e = sum(x["R"] for x in t) / len(t)
                    if best is None or e > best[0]:
                        best = (e, (ov, tn, tr_, mh))
            if not best:
                continue
            is_exps.append(best[0])
            ov, tn, tr_, mh = best[1]
            for tr in _run_seg(d, is_end, oos_end, ov, tn, tr_, mh):
                oos_gross.append(tr["R"])
                oos_net.append(_net_R(tr, slippage_bps, commission, notional))
    is_e = round(sum(is_exps) / len(is_exps), 3) if is_exps else 0
    gross, net = _agg(oos_gross), _agg(oos_net)
    wfe = round(net["expectancy_R"] / is_e * 100, 1) if is_e > 0 else None
    if net["expectancy_R"] > 0.03:
        verdict, vcls = "REAL EDGE — positive out-of-sample AFTER costs. Safe to scale carefully.", "good"
    elif net["expectancy_R"] > 0:
        verdict, vcls = "MARGINAL — barely positive after costs. Not safe to scale yet.", "warn"
    else:
        verdict, vcls = "NO EDGE — negative out-of-sample after costs. Do NOT trade real money on it.", "bad"
    out = {"generated_at": __import__("datetime").datetime.now().astimezone().isoformat(),
           "symbols": len(bars), "folds": folds, "slippage_bps": slippage_bps,
           "in_sample_expectancy_R": is_e, "oos_gross": gross, "oos_net_after_costs": net,
           "walk_forward_efficiency_pct": wfe, "verdict": verdict, "verdict_class": vcls,
           "note": "OOS = data NOT used to pick params. Net = after slippage+commission. This is the honest edge."}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2, default=str)
    return out


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, default=str))
