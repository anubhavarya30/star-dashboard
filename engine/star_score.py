#!/usr/bin/env python3
"""
STAR — 9-vote tech scoring + 2.5:1 ATR risk, ported faithfully from the proven
gold-bot morning_screener (the algo that's been alerting you). The desk uses this
as its entry brain: a name needs score >= 5 of 9 trend/momentum votes, then we
size it with ATR-based stop (1.5x) and target (3.75x = 2.5:1 R:R).

Cached 10 min so the 60s desk loop doesn't hammer yfinance.
"""
import os
import statistics
import sys
import time

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

# Focused liquid universe (top names per sector from the gold-bot watchlist)
UNIVERSE = [
    "NVDA", "MSFT", "AAPL", "META", "GOOGL", "AMD", "AVGO", "ORCL",
    "TSM", "QCOM", "MU", "ARM", "SMCI", "MRVL",
    "JPM", "GS", "V", "MA", "AXP",
    "UNH", "LLY", "ABBV", "JNJ", "MRK",
    "CAT", "GE", "RTX",
    "WMT", "HD", "AMZN", "TSLA", "COST",
    "COIN", "MSTR", "PLTR", "HOOD",
]


def ema(p, n):
    if len(p) < n:
        return p[-1]
    k = 2 / (n + 1); e = p[0]
    for x in p[1:]:
        e = x * k + e * (1 - k)
    return e


def rsi(p, n=14):
    if len(p) < n + 1:
        return 50.0
    g = []; l = []
    for i in range(1, len(p)):
        d = p[i] - p[i - 1]; g.append(max(d, 0)); l.append(abs(min(d, 0)))
    ag = statistics.mean(g[-n:]); al = statistics.mean(l[-n:])
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def atr_v(p, n=14):
    if len(p) < 2:
        return p[-1] * 0.01
    return statistics.mean([abs(p[i] - p[i - 1]) for i in range(1, len(p))][-n:])


def adx_p(p, n=14):
    if len(p) < n * 2:
        return 25.0
    r = p[-n:]
    return min(60, max(10, (max(r) - min(r)) / statistics.mean(r) * 1000))


def macd_h(p, fast=12, slow=26):
    if len(p) < slow:
        return 0.0
    return ema(p, fast) - ema(p, slow)


def momentum_pct(p, n=20):
    if len(p) <= n:
        return 0.0
    return (p[-1] - p[-n]) / p[-n] * 100


def vol_ratio(vols, n=20):
    if not vols or len(vols) < n + 1:
        return 1.0
    avg = statistics.mean(vols[-n - 1:-1])
    return vols[-1] / avg if avg > 0 else 1.0


def tech_score(prices, volumes=None):
    """9-strategy vote (0-9). Faithful port of the gold-bot screener."""
    if len(prices) < 60:
        return 0, {}
    c = prices[-1]
    e8 = ema(prices, 8); e21 = ema(prices, 21); e50 = ema(prices, 50); e200 = ema(prices, 200)
    r14 = rsi(prices, 14); _atr = atr_v(prices, 14); adx = adx_p(prices, 14)
    mh = macd_h(prices); mom = momentum_pct(prices, 20)
    vsurge = vol_ratio(volumes) if volumes else 1.0
    votes = {
        "above_200ema": c > e200,
        "ema_stack": e8 > e21 > e50,
        "ema8_21_cross": e8 > e21,
        "macd_bullish": mh > 0,
        "rsi_healthy": 50 < r14 < 72,
        "adx_trending": adx > 22,
        "momentum_pos": mom > 1.5,
        "vol_surge": vsurge > 1.25,
        "near_ema21": c > e21 and c < e21 * 1.04,    # tight pullback = good entry
    }
    score = sum(1 for v in votes.values() if v)
    return score, {"price": round(c, 2), "rsi": round(r14, 1), "adx": round(adx, 1),
                   "mom": round(mom, 2), "atr": round(_atr, 2), "vol_surge": round(vsurge, 2),
                   "votes": votes}


def risk_levels(price, atr):
    return round(price - atr * 1.5, 2), round(price + atr * 3.75, 2)   # 2.5:1 R:R


def _series(sym):
    import yfinance as yf
    h = yf.Ticker(sym).history(period="1y")
    if h is None or len(h) < 60:
        return None, None
    return list(h["Close"]), list(h["Volume"])


def score_symbol(sym):
    closes, vols = _series(sym)
    if not closes:
        return {"symbol": sym.upper(), "score": 0, "error": "no data"}
    score, ind = tech_score(closes, vols)
    stop, target = risk_levels(ind["price"], ind["atr"])
    rr = round((target - ind["price"]) / (ind["price"] - stop), 1) if stop < ind["price"] else 0
    reasons = [k.replace("_", " ") for k, v in ind["votes"].items() if v]
    return {"symbol": sym.upper(), "score": score, "price": ind["price"], "rsi": ind["rsi"],
            "adx": ind["adx"], "atr": ind["atr"], "stop": stop, "target": target, "rr": rr,
            "reasons": reasons}


_cache = {"t": 0, "data": None}


def scan(min_score=5):
    """Score the whole universe; cache 10 min; return candidates with score>=min_score."""
    if _cache["data"] and time.time() - _cache["t"] < 600:
        rows = _cache["data"]
    else:
        rows = []
        for sym in UNIVERSE:
            try:
                r = score_symbol(sym)
                if r.get("score", 0) >= 1 and r.get("rr", 0) >= 1:
                    rows.append(r)
            except Exception:
                pass
        rows.sort(key=lambda r: (r["score"], r["rr"]), reverse=True)
        _cache.update(t=time.time(), data=rows)
    ranked = [r for r in rows if r["score"] >= min_score]
    return {"ranked": ranked, "scanned": len(UNIVERSE)}


def best_pick(equity=None, min_score=5):
    """Top 9-vote candidate (>=min_score), risk-sized via the risk manager."""
    import risk_manager as rm
    cands = scan(min_score).get("ranked", [])
    for c in cands:
        rk = rm.pre_trade_check(c["symbol"], c["price"], c["stop"], c["target"], equity=equity)
        if rk.get("approved"):
            return {"symbol": c["symbol"], "score": c["score"], "rr": c["rr"],
                    "thesis": f"9-vote score {c['score']}/9 ({', '.join(c['reasons'][:4])})",
                    "risk": rk}
    return {"symbol": None, "risk": {"verdict": "NONE", "plan": {}},
            "thesis": "no name scored >=5 with an approved risk plan"}


if __name__ == "__main__":
    import json
    print(json.dumps(scan(), indent=2, default=str)[:2500])
