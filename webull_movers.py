#!/usr/bin/env python3
"""
Webull market movers — top gainers / losers / most active.

Uses the `webull` package's PUBLIC ranking endpoint (no login required), which
is confirmed reachable. Returns clean rows: symbol, name, price, change_pct.

Note: this is Webull's public quote/ranking data, independent of the
APP_KEY/APP_SECRET (those are for the official OpenAPI, not used here).
"""
from webull import webull

_wb = webull()


def _rows(direction, rank_type, count):
    r = _wb.active_gainer_loser(direction=direction, rank_type=rank_type, count=count)
    out = []
    if not isinstance(r, dict):
        return out
    for rec in r.get("data", []):
        t = rec.get("ticker", {})
        v = rec.get("values", {}) or {}
        try:
            price = float(v.get("price") or t.get("close") or 0)
        except (TypeError, ValueError):
            price = None
        try:
            # changeRatio is a fraction (0.0429 = 4.29%); ×100 for percent
            cr = v.get("changeRatio") or t.get("changeRatio")
            change_pct = float(cr) * 100 if cr is not None else None
        except (TypeError, ValueError):
            change_pct = None
        sym = t.get("symbol") or t.get("disSymbol")
        if not sym:
            continue
        out.append({
            "symbol": sym,
            "name": t.get("name") or "",
            "price": price,
            "change_pct": change_pct,
        })
    return out


def movers(count=8):
    """Return gainers, losers, most-active. Failures degrade to [] per list."""
    result = {"gainers": [], "losers": [], "active": [], "source": "Webull (public)"}
    try:
        result["gainers"] = _rows("gainer", "1d", count)
    except Exception as e:
        result["gainers_error"] = f"{type(e).__name__}: {e}"
    try:
        result["losers"] = _rows("loser", "1d", count)
    except Exception as e:
        result["losers_error"] = f"{type(e).__name__}: {e}"
    try:
        result["active"] = _rows("active", "volume", count)
    except Exception as e:
        result["active_error"] = f"{type(e).__name__}: {e}"
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(movers(3), indent=2))
