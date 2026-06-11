#!/usr/bin/env python3
"""
STAR — Runner Scanner. Finds the daily low-float small-cap "runners" and, for
each, surfaces the things that actually matter for momentum trading:

  • why it's moving (gap %, relative volume, news/catalyst count)
  • is it the explosive kind (low float, small cap)
  • the LANDMINES (penny price, nano-cap, heavy short %, dilution risk)
  • a templated setup (entry trigger / stop / target / R:R) and account-sized qty

HONESTY: data is yfinance (~15-min delayed). This is a RESEARCH watchlist, not a
live intraday signal — relative volume and gaps are end-of-interval, not tick.
Float/short data is missing for some micro-caps. Trading these requires a
real-time feed; this surfaces candidates + risk so you do disciplined DD.
"""
import os
import sys
from datetime import datetime, timezone

import yfinance as yf

# webull_movers lives at repo root; make this importable standalone and via server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import webull_movers


def _num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _enrich(sym):
    """One yfinance .info pull per symbol → the fields a runner trader needs."""
    try:
        info = yf.Ticker(sym).info or {}
    except Exception:
        info = {}
    price = _num(info.get("currentPrice") or info.get("regularMarketPrice"))
    chg = _num(info.get("regularMarketChangePercent"))
    vol = _num(info.get("regularMarketVolume") or info.get("volume"))
    avgvol = _num(info.get("averageVolume") or info.get("averageDailyVolume10Day"))
    float_sh = _num(info.get("floatShares"))
    so = _num(info.get("sharesOutstanding"))
    mcap = _num(info.get("marketCap"))
    short_pct = _num(info.get("shortPercentOfFloat"))
    rel_vol = (vol / avgvol) if (vol and avgvol) else None
    try:
        news_n = len(yf.Ticker(sym).news or [])
    except Exception:
        news_n = None
    return {
        "symbol": sym, "name": info.get("longName") or info.get("shortName") or sym,
        "price": price, "change_pct": chg, "volume": vol, "avg_volume": avgvol,
        "rel_volume": round(rel_vol, 1) if rel_vol else None,
        "float": float_sh, "shares_out": so, "market_cap": mcap,
        "short_pct_float": round(short_pct * 100, 1) if short_pct else None,
        "news_count": news_n,
    }


def _score_and_flags(c, chg_from_mover):
    """Runner potential (0-100) + risk flags. Higher score = more runner-like;
    risk flags are surfaced SEPARATELY (they don't inflate the score)."""
    flags = []
    score = 0.0
    chg = c.get("change_pct") if c.get("change_pct") is not None else chg_from_mover

    # momentum: % change today
    if chg is not None:
        score += min(abs(chg), 100) * 0.4  # up to 40 pts

    # relative volume — the single best "in play" signal
    rv = c.get("rel_volume")
    if rv:
        score += min(rv, 10) * 4  # up to 40 pts at 10x+
        if rv >= 5:
            flags.append(("info", f"Relative volume {rv}x — clearly in play"))

    # low float = explosive
    fl = c.get("float")
    if fl:
        if fl < 10e6:
            score += 20; flags.append(("info", f"Very low float {fl/1e6:.1f}M — explosive/illiquid"))
        elif fl < 50e6:
            score += 10; flags.append(("info", f"Low float {fl/1e6:.1f}M"))

    # ---- LANDMINES (risk, not score) ----
    p = c.get("price")
    if p is not None and p < 1:
        flags.append(("high", f"Sub-$1 ({p:.2f}) — penny stock / delisting & manipulation risk"))
    elif p is not None and p < 5:
        flags.append(("med", f"${p:.2f} — low-priced, wide spreads"))
    mc = c.get("market_cap")
    if mc is not None and mc < 50e6:
        flags.append(("high", f"Nano-cap ${mc/1e6:.0f}M — thin, easily manipulated"))
    elif mc is not None and mc < 300e6:
        flags.append(("med", f"Micro-cap ${mc/1e6:.0f}M"))
    sp = c.get("short_pct_float")
    if sp and sp > 20:
        flags.append(("med", f"Short interest {sp}% of float — squeeze fuel but two-sided"))
    # dilution proxy: shares_out >> float can mean big share creep / offerings
    if c.get("float") and c.get("shares_out") and c["shares_out"] > 3 * c["float"]:
        flags.append(("med", "Shares outstanding ≫ float — possible dilution/lockups"))

    risk = "HIGH" if any(f[0] == "high" for f in flags) else "MED" if any(f[0] == "med" for f in flags) else "LOW"
    return round(min(score, 100), 1), flags, risk


def _setup(c):
    """Templated momentum setup (delayed-data template, not a live trigger)."""
    p = c.get("price")
    if not p:
        return None
    stop = round(p * 0.92, 2)          # ~8% risk
    target = round(p + 2 * (p - stop), 2)  # 2R
    return {"entry": f"break/hold above intraday high (≈${p:.2f})",
            "stop": stop, "target": target, "rr": "2:1",
            "note": "template on delayed data — confirm trigger on a real-time chart"}


def scan(account_size=100.0, max_names=10):
    m = webull_movers.movers(12)
    # candidate pool: gainers + most-active, deduped
    pool = {}
    for r in (m.get("gainers", []) + m.get("active", [])):
        if r["symbol"] not in pool:
            pool[r["symbol"]] = r
    candidates = []
    for sym, mv in list(pool.items())[:max_names]:
        c = _enrich(sym)
        score, flags, risk = _score_and_flags(c, mv.get("change_pct"))
        c.update({"runner_score": score, "flags": flags, "risk": risk,
                  "setup": _setup(c)})
        # account-sized qty at ~8% stop, risking 2% of tiny account
        if c.get("price"):
            risk_dollars = account_size * 0.02
            per_share_risk = c["price"] * 0.08
            c["suggested_qty"] = max(int(risk_dollars / per_share_risk), 0) if per_share_risk else 0
        candidates.append(c)
    candidates.sort(key=lambda x: x["runner_score"], reverse=True)
    return {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "source": "Webull movers + yfinance (delayed)",
            "account_size": account_size, "candidates": candidates}


if __name__ == "__main__":
    out = scan()
    for c in out["candidates"]:
        print(f"\n{c['symbol']:6} score {c['runner_score']:5}  [{c['risk']}]  ${c.get('price')}  "
              f"{c.get('change_pct')}%  relVol {c.get('rel_volume')}  float "
              f"{(c['float']/1e6 if c.get('float') else None)}M")
        for lvl, msg in c["flags"]:
            print(f"   {'⚠️' if lvl!='info' else '•'} [{lvl}] {msg}")
