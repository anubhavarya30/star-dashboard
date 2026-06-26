#!/usr/bin/env python3
"""
STAR — Overnight / world-market agent. Before the US open, read what happened
globally so STAR walks in with an informed bias: Asia (Nikkei, Hang Seng, Shanghai,
Kospi), Europe (FTSE, DAX, Euro Stoxx), and US futures (ES/NQ). Derives a global
risk-on/off read that the CEO folds into the morning brief + Market Read.

Honest: yfinance gives EOD/last-close for these (and live-ish futures) — good enough
for a directional overnight read, not tick precision.
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

MARKETS = {
    "Asia": [("Nikkei", "^N225"), ("Hang Seng", "^HSI"), ("Shanghai", "000001.SS"), ("Kospi", "^KS11")],
    "Europe": [("FTSE", "^FTSE"), ("DAX", "^GDAXI"), ("Euro Stoxx", "^STOXX50E")],
    "US Futures": [("S&P fut", "ES=F"), ("Nasdaq fut", "NQ=F")],
}


def read():
    import yfinance as yf
    out = {}; ups = downs = 0; fut = {}
    for region, items in MARKETS.items():
        rows = []
        for name, t in items:
            try:
                h = yf.Ticker(t).history(period="2d")
                c = float(h["Close"].iloc[-1]); p = float(h["Close"].iloc[-2])
                pct = round((c / p - 1) * 100, 2)
                if pct != pct or p <= 0:        # NaN / bad data guard
                    rows.append({"name": name, "chg_pct": None}); continue
                rows.append({"name": name, "chg_pct": pct})
                if region == "US Futures":
                    fut[name] = pct
                if pct > 0:
                    ups += 1
                elif pct < 0:
                    downs += 1
            except Exception:
                rows.append({"name": name, "chg_pct": None})
        out[region] = rows
    bias = "risk-on" if ups > downs + 1 else ("risk-off" if downs > ups + 1 else "mixed")
    return {"regions": out, "global_bias": bias, "ups": ups, "downs": downs, "futures": fut}


def narrative(r):
    """One-line overnight read for the brief."""
    f = r.get("futures", {})
    fut = ", ".join(f"{k} {v:+.1f}%" for k, v in f.items()) or "flat"
    asia = r["regions"].get("Asia", [])
    eu = r["regions"].get("Europe", [])
    def avg(rows):
        v = [x["chg_pct"] for x in rows if x.get("chg_pct") is not None and x["chg_pct"] == x["chg_pct"]]
        return round(sum(v) / len(v), 2) if v else None
    a, e = avg(asia), avg(eu)
    bits = [f"Overnight: global tape is <b>{r['global_bias']}</b>."]
    if a is not None:
        bits.append(f"Asia avg {a:+.1f}%")
    if e is not None:
        bits.append(f"Europe avg {e:+.1f}%")
    bits.append(f"US futures {fut}.")
    return " ".join(bits)


if __name__ == "__main__":
    import json
    r = read()
    print(json.dumps(r, indent=2))
    print(narrative(r))
