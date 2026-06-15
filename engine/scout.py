#!/usr/bin/env python3
"""
STAR — Market Scout. The CEO funnel: look 360°, shortlist a few SOLID candidates,
research them, then hit the single strongest with a risk-sized plan.

  1. SCAN (360°)  : whole-market movers (Webull gainers + actives) + the core
                    liquid watchlist (quantum, semis/AI, momentum names).
  2. SHORTLIST    : keep only SOLID names (liquid $-volume, real momentum, not a
                    sub-$1/parabolic landmine); rank by a momentum x liquidity score.
  3. RESEARCH     : deep-dive the few — VWAP/trend, day range position, grader
                    verdict, sector confirmation (a whole theme moving = real edge).
  4. HIT STRONGEST: pick #1 actionable, size it through the risk manager -> a plan.

All real data (yfinance + Webull). Nothing fabricated.
"""
import os
import sys
from datetime import datetime

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

# core liquid watchlist by theme (for sector-confirmation + a stable 360 base)
SECTORS = {
    "QUANTUM": ["QBTS", "QUBT", "IONQ", "RGTI"],
    "AI/SEMI": ["NVDA", "AMD", "AVGO", "SMCI", "MU", "ARM"],
    "SOFTWARE": ["ORCL", "PLTR", "CRM", "NOW"],
    "CRYPTO": ["COIN", "MARA", "MSTR", "BMNR"],
    "MEGA/FIN": ["AAPL", "MSFT", "META", "TSLA", "AXP", "JPM"],
    "MOMENTUM": ["OPEN", "LCID", "SOFI", "HOOD"],
}
SECTOR_OF = {s: name for name, syms in SECTORS.items() for s in syms}
BASE = [s for syms in SECTORS.values() for s in syms]


def _quick(sym):
    import yfinance as yf
    try:
        fi = dict(yf.Ticker(sym).fast_info)
    except Exception:
        return None
    last = fi.get("lastPrice") or fi.get("last_price")
    prev = fi.get("previousClose") or fi.get("previous_close")
    vol = fi.get("lastVolume") or fi.get("last_volume")
    hi = fi.get("dayHigh") or fi.get("day_high")
    lo = fi.get("dayLow") or fi.get("day_low")
    op = fi.get("open")
    mcap = fi.get("marketCap") or fi.get("market_cap")
    shares = fi.get("shares") or fi.get("shares_outstanding")
    if not mcap and shares and last:
        mcap = shares * last
    if not last or not prev:
        return None
    chg = (last / prev - 1) * 100
    dvol = (last * vol) if vol else 0
    rng_pos = ((last - lo) / (hi - lo) * 100) if (hi and lo and hi > lo) else None
    return {"symbol": sym.upper(), "price": round(last, 2), "chg_pct": round(chg, 1),
            "dollar_vol": dvol, "market_cap": mcap or 0,
            "range_pos": round(rng_pos, 0) if rng_pos is not None else None,
            "above_open": (op is not None and last >= op), "sector": SECTOR_OF.get(sym.upper())}


def scan(account_equity=None, shortlist_n=5):
    import webull_movers
    uni = set(BASE)
    try:
        m = webull_movers.movers()
        for k in ("gainers", "active"):
            for r in (m.get(k) or []):
                if r.get("symbol"):
                    uni.add(r["symbol"].upper())
    except Exception:
        pass

    scanned = [q for q in (_quick(s) for s in uni) if q]
    # SOLID filter: liquid, real momentum, NOT a sub-$2 / parabolic micro-cap pump.
    # chg capped at 80% — anything above that is a late-stage pump, not a solid name.
    # market cap >= $500M is the SOLID gate — cleanly drops nano-cap pumps
    # (VSME/QTEX/RGNT etc.) while keeping real names (QBTS, AMD, ORCL...).
    solid = [r for r in scanned if r["price"] >= 2 and r["dollar_vol"] >= 1e7
             and r["market_cap"] >= 5e8 and 2 <= r["chg_pct"] <= 80]
    # score: SUSTAINED momentum x liquidity. Momentum is rewarded in the 3-30% zone
    # and PENALIZED when parabolic (>40%) — solid > spectacular-but-late.
    for r in solid:
        c = r["chg_pct"]
        mom = c if c <= 30 else (30 if c <= 40 else max(5.0, 30 - (c - 40) * 0.5))
        liq = min(r["dollar_vol"] / 5e7, 3.0)              # up to 3x for very liquid
        trend = 1.0 if r["above_open"] else 0.6
        pos = (r["range_pos"] / 100) if r["range_pos"] is not None else 0.6
        r["score"] = round(mom * liq * trend * (0.5 + pos), 1)
    shortlist = sorted(solid, key=lambda r: -r["score"])[:shortlist_n]

    # sector confirmation: a theme with 2+ strong names = real momentum, boost
    from collections import Counter
    sec_count = Counter(r["sector"] for r in solid if r["sector"])
    hot_sectors = [s for s, c in sec_count.items() if c >= 2]
    for r in shortlist:
        r["sector_confirmed"] = r["sector"] in hot_sectors

    # RESEARCH the few: real VWAP/trend + grader verdict
    researched = [_research(r) for r in shortlist]

    # HIT STRONGEST: best actionable (above VWAP, not extended), sized by risk mgr
    pick = _pick(researched, account_equity)
    return {"generated_at": datetime.now().astimezone().isoformat(),
            "scanned": len(scanned), "solid": len(solid), "hot_sectors": hot_sectors,
            "shortlist": researched, "pick": pick}


def _research(r):
    import watch_runner as w
    snap = {}
    try:
        snap = w.snapshot(r["symbol"]) or {}
    except Exception:
        pass
    r["vwap"] = snap.get("vwap")
    r["above_vwap"] = snap.get("above_vwap")
    r["off_high_pct"] = snap.get("off_high_pct")
    r["lod"] = snap.get("lod")
    # simple actionable read: trending (above vwap & open) and not blown off (room from high)
    r["actionable"] = bool(r.get("above_vwap") and r["above_open"]
                           and (r.get("off_high_pct") is None or r["off_high_pct"] <= 12))
    return r


def _pick(researched, equity):
    import risk_manager as rm
    cands = [r for r in researched if r.get("actionable")] or researched
    if not cands:
        return None
    best = max(cands, key=lambda r: r["score"])
    price = best["price"]
    stop = round(min(best.get("vwap") or price * 0.97, best.get("lod") or price * 0.97, price * 0.985) * 0.997, 2)
    if stop >= price:
        stop = round(price * 0.97, 2)
    target = round(price + 2 * (price - stop), 2)
    risk = rm.pre_trade_check(best["symbol"], price, stop, target, equity=equity)
    sec = f" · {best['sector']}{' (CONFIRMED)' if best.get('sector_confirmed') else ''}" if best.get("sector") else ""
    # leverage layer: surface the call play (real $500 upside vs a few shares)
    try:
        import options_play as op
        opt = op.best_call(best["symbol"], equity=equity or 500.0)
    except Exception as e:
        opt = {"error": f"options lookup failed: {e}"}
    return {"symbol": best["symbol"], "thesis": f"Strongest of {len(researched)} researched: "
            f"+{best['chg_pct']}% on liquid volume, holding above VWAP{sec}.",
            "score": best["score"], "sector": best.get("sector"),
            "sector_confirmed": best.get("sector_confirmed"), "risk": risk, "options": opt}


if __name__ == "__main__":
    import json
    print(json.dumps(scan(), indent=2, default=str))
