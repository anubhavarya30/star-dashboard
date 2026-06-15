#!/usr/bin/env python3
"""
STAR — Runner Grader. Applies the RUNNERS_PLAYBOOK discipline layer to LIVE data.

The scanner tells you a name is "in play". The grader tells you the thing that
actually matters: WHERE in the lifecycle it is right now, and whether the playbook
says it's a watch, a no-chase, or a landmine. Everything is computed from real
yfinance intraday stats (day open/high/low, prev close, volume). No fabrication.

Verdicts:
  AVOID-LANDMINE   sub-$1 / nano-cap — manipulation/ruin zone, skip
  DO-NOT-CHASE     parabolic & extended at highs — the classic retail trap
  PULLBACK-WATCH   pulled back from highs but holding above open — Setup B watch
  EARLY-WATCH      in play, not yet extended — Setup A watch
  NOT-IN-PLAY      volume/% too low to matter today
"""


def _f(x):
    try:
        v = float(x)
        return v if v == v else None  # drop NaN
    except (TypeError, ValueError):
        return None


def grade(symbol):
    import yfinance as yf
    tk = yf.Ticker(symbol)
    fi = {}
    try:
        fi = dict(tk.fast_info)
    except Exception:
        pass
    price = _f(fi.get("lastPrice")) or _f(fi.get("last_price"))
    day_open = _f(fi.get("open"))
    day_high = _f(fi.get("dayHigh")) or _f(fi.get("day_high"))
    day_low = _f(fi.get("dayLow")) or _f(fi.get("day_low"))
    prev = _f(fi.get("previousClose")) or _f(fi.get("previous_close"))
    vol = _f(fi.get("lastVolume")) or _f(fi.get("last_volume"))
    info = {}
    try:
        info = tk.get_info()
    except Exception:
        pass
    float_sh = _f(info.get("floatShares"))
    mcap = _f(info.get("marketCap"))
    avgvol = _f(info.get("averageVolume"))

    if price is None or prev is None or prev == 0:
        return {"symbol": symbol.upper(), "verdict": "NO-DATA",
                "reason": "no live price/prev close available"}

    chg = (price / prev - 1) * 100
    rel_vol = (vol / avgvol) if (vol and avgvol) else None
    # extension metrics
    off_high = ((day_high - price) / day_high * 100) if (day_high and day_high > 0) else None
    above_open = ((price / day_open - 1) * 100) if day_open else None
    rng_pos = ((price - day_low) / (day_high - day_low) * 100) if (day_high and day_low and day_high > day_low) else None

    # ---- landmine gate first ----
    if price < 1.0:
        return _out(symbol, "AVOID-LANDMINE", f"Sub-$1 (${price:.3f}) — delisting/manipulation zone.",
                    price, chg, rel_vol, off_high, rng_pos, float_sh, mcap)
    if mcap and mcap < 30e6:
        return _out(symbol, "AVOID-LANDMINE", f"Nano-cap (${mcap/1e6:.0f}M) — thin, easily manipulated.",
                    price, chg, rel_vol, off_high, rng_pos, float_sh, mcap)

    # ---- in play? ----
    big_move = chg >= 20
    in_play = big_move and (rel_vol is None or rel_vol >= 3)
    if not in_play:
        return _out(symbol, "NOT-IN-PLAY",
                    f"Up {chg:.0f}%{'' if rel_vol is None else f', rel vol {rel_vol:.1f}x'} — not enough to matter today.",
                    price, chg, rel_vol, off_high, rng_pos, float_sh, mcap)

    # ---- lifecycle classification ----
    # Extension is driven FIRST by how much it has already run today: a name up
    # 200% is late-stage by definition and can never be "early", no matter where
    # it sits in the range. Then we refine by position vs the high.
    near_high = off_high is not None and off_high <= 8
    held_above_open = above_open is None or above_open > 0
    pulled = off_high is not None and off_high >= 15

    if chg >= 80:                              # already parabolic for the day
        if near_high:
            v, why = "DO-NOT-CHASE", f"Up {chg:.0f}% and pinned at/near HOD — peak distribution trap. Chase = donate."
        elif pulled and held_above_open:
            v, why = "PULLBACK-WATCH", (f"Up {chg:.0f}%, faded {off_high:.0f}% off high but still above open — "
                                        "HIGH-RISK Setup B only on a clean VWAP reclaim with volume.")
        else:
            v, why = "DO-NOT-CHASE", (f"Up {chg:.0f}% and {off_high:.0f}% off high, fading/choppy — late and messy. "
                                      "Stand aside; no clean setup.")
    elif chg >= 40:                            # extended but not vertical
        if near_high:
            v, why = "DO-NOT-CHASE", f"Up {chg:.0f}% and near HOD — extended. Wait for a real pullback (Setup B)."
        elif pulled and held_above_open:
            v, why = "PULLBACK-WATCH", (f"Up {chg:.0f}%, pulled {off_high:.0f}% off high, holding above open — "
                                        "Setup B: watch for VWAP/MA reclaim, stop under pullback low.")
        else:
            v, why = "EARLY-WATCH", (f"Up {chg:.0f}%, mid-move and not pinned at highs — cautious Setup A: "
                                     "only on a clean opening-range/PM-high break with volume.")
    else:                                      # 20-40%: genuine early zone
        if pulled and held_above_open:
            v, why = "PULLBACK-WATCH", (f"Up {chg:.0f}%, pulled {off_high:.0f}% off high, above open — "
                                        "Setup B: reclaim entry, stop under pullback low.")
        else:
            v, why = "EARLY-WATCH", (f"Up {chg:.0f}%, early and in play — Setup A: break of PM/opening-range high "
                                     "on volume, stop under the break.")
    return _out(symbol, v, why, price, chg, rel_vol, off_high, rng_pos, float_sh, mcap)


def _out(sym, verdict, reason, price, chg, rel_vol, off_high, rng_pos, float_sh, mcap):
    return {
        "symbol": sym.upper(), "verdict": verdict, "reason": reason,
        "price": round(price, 4) if price else None, "change_pct": round(chg, 1),
        "rel_volume": round(rel_vol, 1) if rel_vol else None,
        "pct_off_high": round(off_high, 1) if off_high is not None else None,
        "range_position_pct": round(rng_pos, 0) if rng_pos is not None else None,
        "float_m": round(float_sh / 1e6, 1) if float_sh else None,
        "market_cap_m": round(mcap / 1e6, 0) if mcap else None,
        "actionable": verdict in ("EARLY-WATCH", "PULLBACK-WATCH"),
    }


def grade_movers(limit=8):
    """Pull today's live gainers (Webull) and grade each against the playbook."""
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # webull_movers lives at repo root
    import webull_movers
    try:
        m = webull_movers.movers()
        gainers = (m.get("gainers") or [])[:limit]
    except Exception as e:
        return {"error": f"movers unavailable: {e}", "graded": []}
    graded = [grade(g["symbol"]) for g in gainers if g.get("symbol")]
    # actionable first, then by change
    graded.sort(key=lambda r: (not r.get("actionable"), -(r.get("change_pct") or 0)))
    from datetime import datetime, timezone
    return {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(), "graded": graded}


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) > 1:
        print(json.dumps(grade(sys.argv[1]), indent=2, default=str))
    else:
        print(json.dumps(grade_movers(), indent=2, default=str))
