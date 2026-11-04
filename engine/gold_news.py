#!/usr/bin/env python3
"""
STAR — gold news bias from IBKR's free Dow Jones / Briefing headlines (GLD as the gold
news anchor; MGC futures carry no news). Keyword score over the last few hours ->
"bullish" / "bearish" / "neutral". Used by gold.py as a GATE only: it blocks a trade
that fights the news, never creates one. UNPROVEN — every trade logs the bias so we
can measure whether the gate helps.
"""
import re
from datetime import datetime, timedelta, timezone

PROVIDERS = "BRFG+BRFUPDN+DJ-N+DJ-RTG+DJ-RTPRO"
RELEVANT = re.compile(r"\b(gold|bullion|precious|fed|fomc|powell|dollar|yield|treasur|inflation|cpi|"
                      r"rate cut|rate hike|safe.haven|geopolit|war|tariff)", re.I)
BULL = [r"rate cut", r"dovish", r"dollar (falls|slips|weak|drops|slides)", r"weak(er)? dollar",
        r"safe.haven", r"gold (rises|gains|jumps|climbs|rall|hits record|record)", r"yields? (fall|drop|slip|ease)",
        r"inflation (rises|jumps|hot|accelerat)", r"geopolit", r"\bwar\b", r"escalat"]
BEAR = [r"hawkish", r"rate hike", r"dollar (rises|gains|jumps|strong|climbs|rall)", r"strong(er)? dollar",
        r"gold (falls|slips|drops|slides|tumbles|declines)", r"yields? (rise|jump|climb|surge)",
        r"inflation (cools|eases|slows)", r"ceasefire", r"risk.on"]


def score(headlines):
    """headlines: list of str -> (bias, score, n_relevant)."""
    s = n = 0
    for h in headlines:
        h = re.sub(r"^\{[^}]*\}", "", h)          # strip IBKR's {A:...:L:en} prefix
        if not RELEVANT.search(h):
            continue
        n += 1
        s += sum(bool(re.search(p, h, re.I)) for p in BULL) - sum(bool(re.search(p, h, re.I)) for p in BEAR)
    return ("bullish" if s >= 2 else "bearish" if s <= -2 else "neutral"), s, n


def bias(hours=6):
    """Fetch recent headlines from IBKR (clientId 95). Neutral on any failure — never blocks on an outage."""
    try:
        import signal as _sig
        _sig.alarm(40)
        from ib_async import IB, Stock
        ib = IB(); ib.connect("127.0.0.1", 7497, clientId=95, timeout=10)
        try:
            g = Stock("GLD", "SMART", "USD"); ib.qualifyContracts(g)
            items = ib.reqHistoricalNews(g.conId, PROVIDERS, "", "", 50) or []
        finally:
            ib.disconnect(); _sig.alarm(0)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        heads = []
        for x in items:
            t = x.time if isinstance(x.time, datetime) else datetime.fromisoformat(str(x.time))
            if (t if t.tzinfo else t.replace(tzinfo=timezone.utc)) >= cutoff:
                heads.append(x.headline)
        b, s, n = score(heads)
        return {"bias": b, "score": s, "relevant": n, "headlines": len(heads)}
    except Exception as e:
        return {"bias": "neutral", "score": 0, "relevant": 0, "headlines": 0, "error": str(e)[:120]}


if __name__ == "__main__":
    assert score(["Gold rises as dollar slips on rate cut bets"])[0] == "bullish"
    assert score(["{A:800015:L:en}Dollar rises, yields jump after hawkish Fed"])[0] == "bearish"
    assert score(["Allied Gold 3Q EPS 20c"])[0] == "neutral"
    print(bias())
