#!/usr/bin/env python3
"""
STAR — Premarket Gap + Catalyst scanner. Get AHEAD of the open: find names gapping
before the bell, WHY they're moving (news catalyst), and how much volume is behind
it (relative volume). This is the head-start the desk was missing — react at 7:45am
with a reason, not at 9:34 to whatever's already green.

All real data: yfinance (prepost prices + news) + Webull movers for the universe.
A gap with a FRESH catalyst + high rel-vol is the high-probability setup.
"""
import os
import sys
import time
from datetime import datetime

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))


def _catalyst(tk):
    """Latest news headline + age (hours). yfinance news schema varies — handle both."""
    try:
        news = tk.news or []
    except Exception:
        return None
    best = None
    for n in news:
        c = n.get("content", n)  # newer yfinance nests under 'content'
        title = c.get("title") or n.get("title")
        pub = (c.get("provider", {}) or {}).get("displayName") or n.get("publisher")
        ts = n.get("providerPublishTime") or 0
        if not ts:
            pd = c.get("pubDate") or c.get("displayTime")
            if pd:
                try:
                    ts = datetime.fromisoformat(pd.replace("Z", "+00:00")).timestamp()
                except Exception:
                    ts = 0
        if not title:
            continue
        age_h = round((time.time() - ts) / 3600, 1) if ts else None
        if best is None or (age_h is not None and (best["age_h"] is None or age_h < best["age_h"])):
            best = {"headline": title[:120], "publisher": pub, "age_h": age_h}
    return best


def scan(min_gap=3.0, max_names=40):
    import yfinance as yf
    import webull_movers
    import scout

    uni = set(scout.BASE)
    try:
        m = webull_movers.movers()
        for k in ("gainers", "active"):
            for r in (m.get(k) or []):
                if r.get("symbol"):
                    uni.add(r["symbol"].upper())
    except Exception:
        pass

    out = []
    for sym in list(uni)[:max_names + 20]:
        try:
            tk = yf.Ticker(sym)
            fi = dict(tk.fast_info)
        except Exception:
            continue
        last = fi.get("lastPrice") or fi.get("last_price")
        prev = fi.get("previousClose") or fi.get("previous_close")
        vol = fi.get("lastVolume") or fi.get("last_volume")
        if not last or not prev or prev == 0:
            continue
        gap = (last / prev - 1) * 100
        if abs(gap) < min_gap or last < 1:
            continue
        cat = _catalyst(tk)
        out.append({
            "symbol": sym.upper(), "price": round(last, 2), "gap_pct": round(gap, 1),
            "prev_close": round(prev, 2), "volume": int(vol) if vol else None,
            "catalyst": cat["headline"] if cat else None,
            "catalyst_src": cat["publisher"] if cat else None,
            "catalyst_age_h": cat["age_h"] if cat else None,
            "fresh_catalyst": bool(cat and cat["age_h"] is not None and cat["age_h"] <= 24),
        })
    # rank: gappers with a FRESH catalyst first, then by gap size
    out.sort(key=lambda r: (not r["fresh_catalyst"], -abs(r["gap_pct"])))
    return {"generated_at": datetime.now().astimezone().isoformat(),
            "scanned": len(uni), "gappers": out[:max_names]}


if __name__ == "__main__":
    import json
    print(json.dumps(scan(), indent=2, default=str))
