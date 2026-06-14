#!/usr/bin/env python3
"""
STAR — GEX history logger + edge tester.

We cannot backtest "negative gamma -> next-day downside" today: free historical
GEX is gone (SqueezeMetrics is paywalled) and yfinance has no options history.
So instead we BUILD the dataset honestly, one real day at a time:

  - `log_today(sym)` appends a real daily GEX snapshot to data/gex_history.csv
    (run it once per day, after the close — e.g. from cron or run_sync_loop).
  - `test_edge(sym)` joins the logged GEX regime against the ACTUAL next-day
    return (pulled from yfinance) and reports whether negative gamma actually
    preceded down days. It only reports once enough real days exist — no
    pretending a 3-row sample means anything.

This is the only intellectually honest way to validate the edge for free: forward
test on out-of-sample days we actually recorded.
"""
import csv
import os
from datetime import date, datetime

HERE = os.path.dirname(__file__)
CSV_PATH = os.path.join(HERE, "..", "data", "gex_history.csv")
FIELDS = ["date", "symbol", "spot", "net_gex", "regime", "gamma_flip", "above_flip"]


def log_today(sym="SPY"):
    import gex as gx
    d = gx.compute(sym)
    if d.get("error"):
        return {"ok": False, "error": d["error"]}
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    row = {
        "date": date.today().isoformat(), "symbol": d["symbol"], "spot": d["spot"],
        "net_gex": round(d["net_gex"], 0), "regime": d["regime"],
        "gamma_flip": d["gamma_flip"], "above_flip": d["above_flip"],
    }
    # de-dupe: one row per (date, symbol)
    existing = _read()
    existing = [r for r in existing if not (r["date"] == row["date"] and r["symbol"] == row["symbol"])]
    existing.append({k: str(row[k]) for k in FIELDS})
    _write(existing)
    return {"ok": True, "row": row, "total_rows": len(existing)}


def _read():
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH) as f:
        return list(csv.DictReader(f))


def _write(rows):
    rows = sorted(rows, key=lambda r: (r["date"], r["symbol"]))
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def test_edge(sym="SPY", min_days=20):
    """Join logged GEX regime vs actual next-day return. Honest about sample size."""
    import yfinance as yf
    rows = [r for r in _read() if r["symbol"] == sym.upper()]
    if len(rows) < min_days:
        return {"symbol": sym.upper(), "logged_days": len(rows), "min_days": min_days,
                "verdict": f"Not enough data yet — {len(rows)}/{min_days} days logged. "
                           "The logger must run daily; come back after the sample fills."}
    dates = sorted(r["date"] for r in rows)
    hist = yf.Ticker(sym).history(start=dates[0], end=None)
    closes = {d.strftime("%Y-%m-%d"): c for d, c in zip(hist.index, hist["Close"])}
    days = sorted(closes)
    nxt = {days[i]: (closes[days[i + 1]] / closes[days[i]] - 1) for i in range(len(days) - 1)}

    neg = [r for r in rows if r["regime"] == "negative" and r["date"] in nxt]
    pos = [r for r in rows if r["regime"] == "positive" and r["date"] in nxt]
    def stats(g):
        if not g:
            return {"n": 0}
        rets = [nxt[r["date"]] for r in g]
        down = sum(1 for x in rets if x < 0)
        return {"n": len(g), "avg_next_ret_pct": round(sum(rets) / len(rets) * 100, 3),
                "pct_down_next": round(down / len(rets) * 100, 1)}
    return {"symbol": sym.upper(), "logged_days": len(rows),
            "negative_gamma_days": stats(neg), "positive_gamma_days": stats(pos),
            "note": "Edge confirmed only if negative-gamma days show a LOWER avg next-day "
                    "return and a HIGHER % of down days than positive-gamma days."}


if __name__ == "__main__":
    import sys, json
    cmd = sys.argv[1] if len(sys.argv) > 1 else "log"
    sym = sys.argv[2] if len(sys.argv) > 2 else "SPY"
    print(json.dumps(test_edge(sym) if cmd == "test" else log_today(sym), indent=2, default=str))
