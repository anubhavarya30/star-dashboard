#!/usr/bin/env python3
"""
STAR — Alpaca real-time market data (free IEX feed). Decouples the SIGNAL data from
IBKR: trade on IBKR paper (real fills), get real-time prices/bars from Alpaca. This
sidesteps IBKR's entitlement maze entirely.

Free Alpaca data tier = real-time IEX quotes — plenty for a 5-min scalp signal on
liquid names. Keys live in data/alpaca_config.json (gitignored). Sign up free at
alpaca.markets, generate API keys, paste them there.
"""
import json
import os

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
CFG = os.path.join(ROOT, "data", "alpaca_config.json")
BASE = "https://data.alpaca.markets/v2/stocks"


def _cfg():
    k = os.environ.get("ALPACA_KEY"); s = os.environ.get("ALPACA_SECRET")
    if k and s:
        return {"key": k, "secret": s}
    try:
        return json.load(open(CFG))
    except Exception:
        return {}


def configured():
    c = _cfg()
    return bool(c.get("key") and c.get("secret") and "YOUR_" not in str(c.get("key")))


def _headers():
    c = _cfg()
    return {"APCA-API-KEY-ID": c.get("key", ""), "APCA-API-SECRET-KEY": c.get("secret", "")}


def _get(url):
    import requests
    r = requests.get(url, headers=_headers(), timeout=8)
    r.raise_for_status()
    return r.json()


def price(symbol):
    """Latest real-time trade price (IEX)."""
    try:
        d = _get(f"{BASE}/{symbol.upper()}/trades/latest?feed=iex")
        return round(float(d["trade"]["p"]), 2)
    except Exception:
        return None


def bars_5m(symbol, limit=80):
    """Recent 5-minute bars (real-time IEX). Returns dict of close/high/low lists."""
    try:
        d = _get(f"{BASE}/{symbol.upper()}/bars?timeframe=5Min&limit={int(limit)}&feed=iex&adjustment=raw")
        bars = d.get("bars") or []
        return {"c": [float(b["c"]) for b in bars],
                "h": [float(b["h"]) for b in bars],
                "l": [float(b["l"]) for b in bars]}
    except Exception:
        return None


def available():
    """True if configured AND the feed actually responds (real-time live)."""
    if not configured():
        return False
    return price("AAPL") is not None


if __name__ == "__main__":
    import sys
    print("configured:", configured())
    if configured():
        sym = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
        print(f"{sym} real-time price:", price(sym))
        b = bars_5m(sym, 5)
        print(f"{sym} last 5m closes:", b["c"][-5:] if b else None)
