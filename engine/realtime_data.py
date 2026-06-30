#!/usr/bin/env python3
"""
STAR — unified REAL-TIME data provider. Decouples the scalp signal from IBKR's
entitlement maze. Source priority:
  1) Alpaca (free IEX) if a key is configured  — official, batchable, best
  2) Webull PUBLIC quote API (no key, no login) — real-time, what their site uses
  3) yfinance (~15-min delayed)                  — last-resort fallback

Webull is unofficial (can break on their changes) but works today with zero setup,
so we get real-time NOW and upgrade to Alpaca the moment a key's added.
"""
import os
import sys
import time

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
_WB = "https://quotes-gw.webullfintech.com/api"
_HDR = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
_tid = {}      # symbol -> webull tickerId (cached)


def _req(url):
    import requests
    r = requests.get(url, headers=_HDR, timeout=8)
    r.raise_for_status()
    return r.json()


def _wb_id(sym):
    if sym in _tid:
        return _tid[sym]
    try:
        d = _req(f"{_WB}/search/pc/tickers?keyword={sym}&pageIndex=1&pageSize=10")
        for x in d.get("data", []):
            if str(x.get("disSymbol", "")).upper() == sym.upper() or str(x.get("symbol", "")).upper() == sym.upper():
                _tid[sym] = x["tickerId"]; return _tid[sym]
    except Exception:
        return None
    return None


def _wb_price(sym):
    tid = _wb_id(sym)
    if not tid:
        return None
    try:
        q = _req(f"{_WB}/stock/tickerRealTime/getQuote?tickerId={tid}&includeSecu=1&includeQuote=1")
        for k in ("close", "pPrice", "price"):
            if q.get(k):
                return round(float(q[k]), 2)
    except Exception:
        return None
    return None


def _wb_bars(sym, count=120):
    tid = _wb_id(sym)
    if not tid:
        return None
    try:
        d = _req(f"{_WB}/quote/charts/query?tickerIds={tid}&type=m5&count={int(count)}&extendTrading=0")
        rows = d[0].get("data", []) if d else []
        c, h, l = [], [], []
        for row in reversed(rows):                 # webull returns newest-first
            p = row.split(",")                     # ts,open,close,high,low,prevClose,vol,vwap
            if len(p) >= 5 and p[2] not in ("", "null"):
                try:
                    c.append(float(p[2])); h.append(float(p[3])); l.append(float(p[4]))
                except (ValueError, IndexError):
                    pass
        return {"c": c, "h": h, "l": l} if len(c) >= 30 else None
    except Exception:
        return None


def price(sym):
    try:
        import alpaca_data as a
        if a.configured():
            p = a.price(sym)
            if p:
                return p
    except Exception:
        pass
    p = _wb_price(sym)
    if p:
        return p
    try:
        import yfinance as yf
        return round(float(yf.Ticker(sym).fast_info.get("lastPrice")), 2)
    except Exception:
        return None


def bars_5m(sym, count=120):
    try:
        import alpaca_data as a
        if a.configured():
            b = a.bars_5m(sym, count)
            if b and len(b["c"]) >= 30:
                return b
    except Exception:
        pass
    return _wb_bars(sym, count)   # yfinance bars handled by caller's batch fallback


def source():
    try:
        import alpaca_data as a
        if a.configured():
            return "alpaca-realtime"
    except Exception:
        pass
    return "webull-realtime" if _wb_price("AAPL") else "yfinance-delayed"


if __name__ == "__main__":
    print("active source:", source())
    for s in (sys.argv[1:] or ["AAPL", "NVDA"]):
        b = bars_5m(s)
        print(f"  {s}: price={price(s)} | 5m bars={len(b['c']) if b else 0}")
