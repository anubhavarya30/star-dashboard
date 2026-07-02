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
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

import sys
import yfinance as yf
import db

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "engine"))  # let us import the engine/ trading brain
PORT = 8080
_cache = {}            # tiny TTL cache to avoid hammering yfinance
CACHE_TTL = 20         # seconds


def cached(key, fn, ttl=CACHE_TTL):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


def agents():
    def build():
        import star_agents
        return star_agents.run()
    return cached("agents", build, ttl=180)  # agent run is heavy; refresh every 3 min


def pnl_calendar():
    return cached("pnl", lambda: {"days": db.pnl_calendar(35)}, ttl=15)


def forensic(sym):
    def build():
        import forensic as fz
        return fz.analyze(sym)
    return cached(f"fz:{sym}", build, ttl=600)  # forensic pull is heavy; 10-min cache


def runners():
    def build():
        import runner_scanner
        acct = 100.0
        try:
            d = json.loads((HERE / "live_account.json").read_text())
            if d.get("status") == "connected" and d.get("net_liquidation"):
                acct = d["net_liquidation"]
        except Exception:
            pass
        return runner_scanner.scan(account_size=acct, max_names=10)
    return cached("runners", build, ttl=600)  # heavy (yfinance per name); 10-min cache


def run_backtest(sym, period):
    def build():
        import backtest as bt
        return bt.backtest(sym, period=period)
    return cached(f"backtest:{sym}:{period}", build, ttl=600)  # heavy; 10-min cache


def gex(sym):
    def build():
        import gex as gx
        return gx.compute(sym)
    return cached(f"gex:{sym}", build, ttl=120)  # options pull is heavy; 2-min cache


def gex_agent(sym):
    def build():
        import gex as gx
        return gx.agent(sym)
    return cached(f"gexagent:{sym}", build, ttl=120)


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
        src = "delayed"
        # REAL-TIME override: use the live feed (Alpaca/Webull) for the current price so
        # the dashboard stops showing ~15-min-delayed yfinance numbers. prev_close/open/
        # hi-lo stay from yfinance (static-enough); only `last` needs to be live.
        try:
            import realtime_data as rt
            rp = rt.price(sym)
            if rp:
                last = rp
                src = rt.source()
        except Exception:
            pass
        chg = (last - prev) if (last is not None and prev) else None
        chg_pct = (chg / prev * 100) if (chg is not None and prev) else None
        return {
            "symbol": sym.upper(),
            "source": src,
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


def ohlc(sym, rng):
    """OHLC bars for candlestick charts (Lightweight Charts format).
    Intraday ranges return unix-second timestamps; daily/weekly return dates."""
    # rng -> (period, interval, resample_rule)
    cfg = {
        "5m":  ("5d",  "5m",  None),
        "1h":  ("1mo", "60m", None),
        "4h":  ("3mo", "60m", "4h"),   # yfinance has no native 4h; resample 1h
        "1mo": ("1mo", "1d",  None),
        "6mo": ("6mo", "1d",  None),
        "1y":  ("1y",  "1d",  None),
        "5y":  ("5y",  "1wk", None),
    }
    period, interval, resample = cfg.get(rng, ("6mo", "1d", None))
    intraday = interval.endswith("m") or interval.endswith("h")

    def build():
        df = yf.Ticker(sym).history(period=period, interval=interval)
        if resample and not df.empty:
            df = df.resample(resample).agg(
                {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
            ).dropna()
        bars = []
        for idx, row in df.iterrows():
            o, h, l, c = num(row["Open"]), num(row["High"]), num(row["Low"]), num(row["Close"])
            if None in (o, h, l, c):
                continue
            if intraday:
                t = int(idx.tz_convert("UTC").timestamp()) if idx.tzinfo else int(idx.timestamp())
            else:
                t = idx.strftime("%Y-%m-%d")
            bars.append({"time": t, "open": round(o, 2), "high": round(h, 2),
                         "low": round(l, 2), "close": round(c, 2)})
        return {"symbol": sym.upper(), "range": rng, "bars": bars, "intraday": intraday}
    return cached(f"o:{sym}:{rng}", build)


MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]


def mag7():
    def build():
        rows = []
        for s in MAG7:
            try:
                q = quote(s)
                rows.append({"symbol": s, "last": q["last"], "change_pct": q["change_pct"]})
            except Exception:
                rows.append({"symbol": s, "last": None, "change_pct": None})
        return {"stocks": rows}
    return cached("mag7", build)


def movers():
    def build():
        import webull_movers
        return webull_movers.movers(8)
    return cached("movers", build)


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


def _news_epoch(content, n):
    """Best-effort publish time (unix secs) across yfinance's old + new news shapes."""
    import datetime as _dt
    # new shape: ISO string in content.pubDate / displayTime
    for k in ("pubDate", "displayTime"):
        v = content.get(k)
        if v:
            try:
                return _dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
            except Exception:
                pass
    # old shape: unix seconds
    v = n.get("providerPublishTime") or content.get("providerPublishTime")
    try:
        return float(v) if v else None
    except Exception:
        return None


def news(sym):
    def build():
        import time as _t
        now = _t.time()
        MAX_AGE = 7 * 86400          # drop anything older than 7 days — no stale headlines
        out = []
        try:
            for n in (yf.Ticker(sym).news or []):
                content = n.get("content", n)
                title = content.get("title") or n.get("title")
                if not title:
                    continue
                ep = _news_epoch(content, n)
                if ep and (now - ep) > MAX_AGE:
                    continue                     # too old -> skip (staleness guard)
                pub = content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else n.get("publisher")
                url = (content.get("canonicalUrl", {}) or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else n.get("link")
                out.append({"title": title, "publisher": pub or "", "url": url or "",
                            "published": (__import__("datetime").datetime.fromtimestamp(ep).isoformat() if ep else None),
                            "age_min": (int((now - ep) / 60) if ep else None)})
        except Exception:
            pass
        out.sort(key=lambda x: x.get("age_min") if x.get("age_min") is not None else 10**9)  # freshest first
        return {"symbol": sym.upper(), "items": out[:8]}
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


_AUTH = {"loaded": False, "pw": None}


def _dash_pw():
    """Dashboard password from data/dashboard_auth.json (gitignored) or env DASH_PASS.
    None = not configured = open (so we never lock ourselves out before it's set)."""
    if not _AUTH["loaded"]:
        _AUTH["loaded"] = True
        try:
            _AUTH["pw"] = json.load(open(HERE / "data" / "dashboard_auth.json")).get("password")
        except Exception:
            _AUTH["pw"] = os.environ.get("DASH_PASS")
    return _AUTH["pw"]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # quiet

    def _authed(self):
        """HTTP Basic auth for REMOTE clients. Localhost is exempt (internal health
        checks/curls), so only LAN/Tailscale access needs the password."""
        pw = _dash_pw()
        if not pw:
            return True
        ip = self.client_address[0] if self.client_address else ""
        if ip in ("127.0.0.1", "::1", "localhost"):
            return True
        import base64
        h = self.headers.get("Authorization", "")
        if h.startswith("Basic "):
            try:
                if base64.b64decode(h[6:]).decode().partition(":")[2] == pw:
                    return True
            except Exception:
                pass
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="STAR"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        # never let the browser cache live API data (was showing stale P&L)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
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
        # never cache the dashboard — always serve the latest after a deploy
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not self._authed():
            return
        u = urlparse(self.path)
        if u.path == "/api/sync_calendar":
            # Write today's P&L as a calendar-event payload that the Google sync
            # picks up. Real push happens via the Google Calendar integration.
            try:
                days = db.pnl_calendar(35)
                from datetime import datetime as _dt
                today = _dt.now().astimezone().date().isoformat()
                row = next((d for d in days if d["date"] == today), None)
                total = row["total"] if row else 0.0
                payload = {
                    "date": today,
                    "title": f"P&L {('+' if total>=0 else '')}{total:.2f}",
                    "total": total,
                    "realized": row["realized"] if row else 0.0,
                    "unrealized": row["unrealized"] if row else 0.0,
                    "queued_at": _dt.now().astimezone().isoformat(),
                }
                (HERE / "pnl_calendar_sync.json").write_text(json.dumps(payload, indent=2))
                return self._send_json({"ok": True,
                    "message": f"Queued {payload['title']} for {today}. "
                               f"Run the Google Calendar sync to push it to your phone."})
            except Exception as e:
                return self._send_json({"ok": False, "message": f"{type(e).__name__}: {e}"}, code=500)
        self.send_error(404)

    def do_GET(self):
        if not self._authed():
            return
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
            if u.path == "/api/ohlc":
                return self._send_json(ohlc(sym, q.get("range", ["6mo"])[0]))
            if u.path == "/api/mag7":
                return self._send_json(mag7())
            if u.path == "/api/movers":
                return self._send_json(movers())
            if u.path == "/api/profile":
                return self._send_json(profile(sym))
            if u.path == "/api/news":
                return self._send_json(news(sym))
            if u.path == "/api/market":
                return self._send_json(market_overview())
            if u.path == "/api/portfolio":
                return self._send_json(portfolio())
            if u.path == "/api/agents":
                return self._send_json(agents())
            if u.path == "/api/pnl_calendar":
                return self._send_json(pnl_calendar())
            if u.path == "/api/forensic":
                return self._send_json(forensic(sym))
            if u.path == "/api/runners":
                return self._send_json(runners())
            if u.path == "/api/backtest":
                return self._send_json(run_backtest(sym, q.get("period", ["2y"])[0]))
            if u.path == "/api/gex":
                return self._send_json(gex(q.get("sym", ["SPY"])[0].upper()))
            if u.path == "/api/gex_agent":
                return self._send_json(gex_agent(q.get("sym", ["SPY"])[0].upper()))
            if u.path == "/api/premarket":
                if q.get("rebuild"):
                    def _pm():
                        import premarket_research as pr
                        return pr.build()
                    return self._send_json(cached("premarket_build", _pm, ttl=60))
                p = HERE / "data" / "premarket" / "latest.json"
                return self._send_json(json.loads(p.read_text()) if p.exists()
                                       else {"error": "no morning brief yet — runs premarket weekdays"})
            if u.path == "/api/risk_check":
                import risk_manager as rm
                t = q.get("target", [None])[0]
                return self._send_json(rm.pre_trade_check(
                    sym, float(q.get("entry", ["0"])[0]), float(q.get("stop", ["0"])[0]),
                    float(t) if t else None))
            if u.path == "/api/risk_status":
                import risk_manager as rm
                return self._send_json(rm.status())
            if u.path == "/api/premarket_gap":
                def _pg():
                    import premarket_gap as pg
                    return pg.scan()
                return self._send_json(cached("premarket_gap", _pg, ttl=120))
            if u.path == "/api/paper_results":
                import csv as _csv
                p = HERE / "data" / "paper_results.csv"
                rows = list(_csv.DictReader(p.open())) if p.exists() else []
                return self._send_json({"results": rows})
            if u.path == "/api/paper_trades":
                import csv as _csv, risk_manager as rm
                p = HERE / "data" / "paper_trades.csv"
                closed = list(_csv.DictReader(p.open())) if p.exists() else []
                st = rm.status()
                openp = []
                import realtime_data as _rt
                for pos in st["open_positions"]:
                    cur = _rt.price(pos["symbol"]) or num(yf.Ticker(pos["symbol"]).fast_info.get("lastPrice"))
                    risk = pos.get("init_risk") or (pos["entry"] - pos["stop"])
                    if cur is not None:
                        pos = {**pos, "current": round(cur, 2),
                               "unrealized": round((cur - pos["entry"]) * pos["shares"], 2),
                               "r_mult": round((cur - pos["entry"]) / risk, 2) if risk else 0,
                               "winning": cur >= pos["entry"]}
                    openp.append(pos)
                # realized_today must be the UNIFIED STAR number (all desks: scalp+stock+
                # fvg+gold), NOT risk_manager's stock-only figure — otherwise this tile
                # disagrees with the STAR Total P&L + calendar (same paper_trades ledger).
                return self._send_json({"closed": closed, "open": openp,
                                        "realized_today": db.star_pnl()["today_pnl"],
                                        "realized_stock_only": st["realized_pnl"]})
            if u.path == "/api/all_trades":
                return self._send_json({"trades": db.paper_trades_all(int(q.get("limit",["500"])[0])),
                                        "stats": db.paper_stats()})
            if u.path == "/api/strategy_detail":
                src = (q.get("source", ["scalp"])[0] or "scalp").lower()
                def _sd():
                    closed = [r for r in db.paper_trades_all(800) if (r.get("source") or "stock") == src][:60]
                    opens = []
                    try:
                        if src == "scalp":
                            import scalp_desk; opens = scalp_desk.stats().get("open", [])
                        elif src == "fvg":
                            import fvg_desk; opens = fvg_desk.stats().get("open", [])
                        elif src == "option":
                            import options_desk; opens = options_desk.stats().get("open", [])
                        elif src == "stock":
                            import risk_manager as rm; opens = rm.status().get("open_positions", [])
                    except Exception:
                        pass
                    return {"source": src, "closed": closed, "open": opens}
                return self._send_json(_sd())
            if u.path == "/api/star_pnl":
                return self._send_json(db.star_pnl())
            if u.path == "/api/walkforward":
                import json as _j, os as _os
                p = _os.path.join("data", "walkforward.json")
                if _os.path.exists(p):
                    return self._send_json(_j.load(open(p)))
                return self._send_json({"error": "not run yet — runs via scalp_walkforward.py"})
            if u.path == "/api/fvg":
                def _fvg():
                    import fvg
                    return fvg.signal(sym)
                return self._send_json(cached("fvg:" + sym, _fvg, ttl=120))
            if u.path == "/api/scalp":
                def _sc():
                    import scalp_desk
                    return scalp_desk.stats()
                return self._send_json(cached("scalp", _sc, ttl=20))
            if u.path == "/api/fvg_desk":
                def _fd():
                    import fvg_desk
                    return fvg_desk.stats()
                return self._send_json(cached("fvg_desk", _fd, ttl=20))
            if u.path == "/api/review":
                def _rv():
                    import daily_review
                    return daily_review.review()
                return self._send_json(cached("review", _rv, ttl=120))
            if u.path == "/api/ceo":
                def _ceo():
                    import glob, json as _j, os as _os
                    files = sorted(glob.glob(_os.path.join("data", "premarket", "ceo_*.json")))
                    if not files:
                        return {"error": "no CEO brief yet — runs pre-market (com.star.ceo) or via star_ceo.research()"}
                    return _j.load(open(files[-1]))
                return self._send_json(cached("ceo", _ceo, ttl=60))
            if u.path == "/api/gold":
                def _g():
                    import gold
                    return gold.stats()
                return self._send_json(cached("gold", _g, ttl=60))
            if u.path == "/api/breakdown":
                def _bd():
                    import breakdown_scan as bd
                    return bd.scan()
                return self._send_json(cached("breakdown", _bd, ttl=120))
            if u.path == "/api/options_play":
                def _op():
                    import options_play as op
                    return op.best_put(sym) if q.get("side",["call"])[0]=="put" else op.best_call(sym)
                return self._send_json(cached("opt:" + sym, _op, ttl=120))
            if u.path == "/api/earnings":
                def _e():
                    import earnings
                    return earnings.blocked(sym)
                return self._send_json(cached("earn:"+sym, _e, ttl=3600))
            if u.path == "/api/news_watch":
                def _nw():
                    import news_watch
                    return news_watch.assess()
                return self._send_json(cached("news_watch", _nw, ttl=1200))
            if u.path == "/api/options_desk":
                def _od():
                    import options_desk
                    return options_desk.stats()
                return self._send_json(cached("options_desk", _od, ttl=30))
            if u.path == "/api/calendar":
                import market_calendar as mcal
                return self._send_json(mcal.status())
            if u.path == "/api/star_score":
                def _ss():
                    import star_score
                    return star_score.scan()
                return self._send_json(cached("star_score", _ss, ttl=300))
            if u.path == "/api/scout":
                def _sc():
                    import scout
                    return scout.scan()
                return self._send_json(cached("scout", _sc, ttl=120))
            if u.path == "/api/daily_trade":
                def _dt():
                    import daily_trade as dt
                    return dt.pick()
                return self._send_json(cached("daily_trade", _dt, ttl=120))
            if u.path == "/api/runner_grade":
                def _rg():
                    import runner_grader as rg
                    s = q.get("sym", [None])[0]
                    return rg.grade(s.upper()) if s else rg.grade_movers()
                return self._send_json(cached("runner_grade:" + (q.get("sym", [""])[0] or "movers"), _rg, ttl=60))
            if u.path == "/api/trades":
                return self._send_json({"trades": db.trades(int(q.get("limit", ["200"])[0]))})
            if u.path == "/api/ibkr_fills":
                def _ibf():
                    import ibkr_broker as b
                    return b.fills()
                return self._send_json(cached("ibkr_fills", _ibf, ttl=30))
            if u.path == "/api/ibkr_broker":
                def _ib():
                    import ibkr_broker as b
                    return b.status()
                return self._send_json(cached("ibkr_broker", _ib, ttl=30))
            if u.path == "/api/round_trips":
                return self._send_json({"round_trips": db.round_trips(int(q.get("limit", ["200"])[0]))})
            if u.path == "/api/account_history":
                return self._send_json({"history": db.account_history(int(q.get("days", ["30"])[0]))})
            self.send_error(404)
        except Exception as e:
            self._send_json({"error": f"{type(e).__name__}: {e}"}, code=500)


if __name__ == "__main__":
    db.init_db()
    # Bind all interfaces by default so the dashboard is reachable over Tailscale/LAN
    # (was 127.0.0.1 = localhost-only). Override with STAR_BIND=127.0.0.1 to lock down.
    bind = os.environ.get("STAR_BIND", "0.0.0.0")
    print(f"🖥️  STAR Terminal on {bind}:{PORT} → http://localhost:{PORT} (or http://<tailscale-ip>:{PORT})")
    print("   Data: yfinance (real, ~15min delayed) + IBKR portfolio + SQLite history")
    ThreadingHTTPServer((bind, PORT), Handler).serve_forever()
