#!/usr/bin/env python3
"""
STAR Terminal — a Bloomberg-style research terminal backed by REAL data.

Data sources:
  - yfinance: quotes, historical charts, company profile, fundamentals, news
  - live_account.json: your real IBKR portfolio (written by ibkr_live_sync.py)

Serves terminal.html and a small JSON API on http://localhost:8080
Run:  ./venv/bin/python3 terminal_server.py
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

import yfinance as yf
import db

HERE = Path(__file__).parent
PORT = 8080
_cache = {}            # tiny TTL cache to avoid hammering yfinance
CACHE_TTL = 20         # seconds


def cached(key, fn):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


def num(x):
    try:
        f = float(x)
        return f if f == f else None  # nan -> None
    except (TypeError, ValueError):
        return None


def quote(sym):
    def build():
        t = yf.Ticker(sym)
        fi = t.fast_info
        last = num(fi.get("lastPrice"))
        prev = num(fi.get("previousClose"))
        chg = (last - prev) if (last is not None and prev) else None
        chg_pct = (chg / prev * 100) if (chg is not None and prev) else None
        return {
            "symbol": sym.upper(),
            "last": last,
            "prev_close": prev,
            "change": chg,
            "change_pct": chg_pct,
            "open": num(fi.get("open")),
            "day_high": num(fi.get("dayHigh")),
            "day_low": num(fi.get("dayLow")),
            "year_high": num(fi.get("yearHigh")),
            "year_low": num(fi.get("yearLow")),
            "volume": num(fi.get("lastVolume")),
            "market_cap": num(fi.get("marketCap")),
            "currency": fi.get("currency") or "USD",
        }
    return cached(f"q:{sym}", build)


def history(sym, rng):
    period_map = {"1mo": ("1mo", "1d"), "6mo": ("6mo", "1d"),
                  "1y": ("1y", "1d"), "5y": ("5y", "1wk"), "1d": ("1d", "5m")}
    period, interval = period_map.get(rng, ("6mo", "1d"))

    def build():
        df = yf.Ticker(sym).history(period=period, interval=interval)
        pts = [{"t": idx.strftime("%Y-%m-%d %H:%M"), "c": num(row["Close"])}
               for idx, row in df.iterrows() if num(row["Close"]) is not None]
        return {"symbol": sym.upper(), "range": rng, "points": pts}
    return cached(f"h:{sym}:{rng}", build)


def profile(sym):
    def build():
        info = {}
        try:
            info = yf.Ticker(sym).info or {}
        except Exception:
            pass
        return {
            "symbol": sym.upper(),
            "name": info.get("longName") or info.get("shortName") or sym.upper(),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "employees": info.get("fullTimeEmployees"),
            "country": info.get("country"),
            "website": info.get("website"),
            "summary": info.get("longBusinessSummary"),
            "pe": num(info.get("trailingPE")),
            "forward_pe": num(info.get("forwardPE")),
            "eps": num(info.get("trailingEps")),
            "dividend_yield": num(info.get("dividendYield")),
            "beta": num(info.get("beta")),
            "profit_margin": num(info.get("profitMargins")),
            "revenue": num(info.get("totalRevenue")),
            "gross_margin": num(info.get("grossMargins")),
            "52w_change": num(info.get("52WeekChange")),
            "target_mean": num(info.get("targetMeanPrice")),
            "recommendation": info.get("recommendationKey"),
        }
    return cached(f"p:{sym}", build)


def news(sym):
    def build():
        out = []
        try:
            for n in (yf.Ticker(sym).news or [])[:8]:
                content = n.get("content", n)
                title = content.get("title") or n.get("title")
                if not title:
                    continue
                pub = content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else n.get("publisher")
                url = (content.get("canonicalUrl", {}) or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else n.get("link")
                out.append({"title": title, "publisher": pub or "", "url": url or ""})
        except Exception:
            pass
        return {"symbol": sym.upper(), "items": out}
    return cached(f"n:{sym}", build)


def market_overview():
    syms = {"^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow",
            "^VIX": "VIX", "BTC-USD": "Bitcoin", "^TNX": "10Y Yield"}
    def build():
        rows = []
        for s, label in syms.items():
            try:
                q = quote(s)
                rows.append({"label": label, "symbol": s,
                             "last": q["last"], "change_pct": q["change_pct"]})
            except Exception:
                rows.append({"label": label, "symbol": s, "last": None, "change_pct": None})
        return {"indices": rows}
    return cached("mkt", build)


def portfolio():
    f = HERE / "live_account.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {"status": "no_data", "positions": []}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # quiet

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, name, ctype="text/html"):
        p = HERE / name
        if not p.exists():
            self.send_error(404)
            return
        body = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        sym = (q.get("sym", ["AAPL"])[0] or "AAPL").upper()
        try:
            if u.path in ("/", "/terminal.html"):
                return self._send_file("terminal.html")
            if u.path == "/api/quote":
                return self._send_json(quote(sym))
            if u.path == "/api/history":
                return self._send_json(history(sym, q.get("range", ["6mo"])[0]))
            if u.path == "/api/profile":
                return self._send_json(profile(sym))
            if u.path == "/api/news":
                return self._send_json(news(sym))
            if u.path == "/api/market":
                return self._send_json(market_overview())
            if u.path == "/api/portfolio":
                return self._send_json(portfolio())
            if u.path == "/api/trades":
                return self._send_json({"trades": db.trades(int(q.get("limit", ["200"])[0]))})
            if u.path == "/api/account_history":
                return self._send_json({"history": db.account_history(int(q.get("days", ["30"])[0]))})
            self.send_error(404)
        except Exception as e:
            self._send_json({"error": f"{type(e).__name__}: {e}"}, code=500)


if __name__ == "__main__":
    db.init_db()
    print(f"🖥️  STAR Terminal running → http://localhost:{PORT}")
    print("   Data: yfinance (real, ~15min delayed) + IBKR portfolio + SQLite history")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
