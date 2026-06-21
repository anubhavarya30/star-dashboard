#!/usr/bin/env python3
"""
STAR — macro news watch (Crawl4AI). Scrapes market headlines and flags BIG,
market-moving events (Fed/CPI/jobs, war/tariffs/sanctions, presidential or policy
announcements, crashes/selloffs). 20-min cache.

HONEST design: news is a RISK/CONTEXT signal, not an auto buy/sell trigger.
Interpreting headlines for direction in real time is error-prone and dangerous, so:
  • a major RISK-OFF event -> the desk pauses new entries + Telegrams you,
  • the directional call stays with YOU (we surface the headlines, you decide).
"""
import asyncio
import os
import sys
import time

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

SOURCES = ["https://finviz.com/news.ashx", "https://www.cnbc.com/economy/"]

BIG_EVENT = ["fed", "fomc", "powell", "rate cut", "rate hike", "cpi", "inflation",
             "jobs report", "nonfarm", "gdp", "tariff", "sanction", "president",
             "trump", "white house", "election", "war", "invasion", "shutdown",
             "default", "downgrade", "stimulus"]
RISK_OFF = ["selloff", "sell-off", "plunge", "plunges", "crash", "tumble", "slump",
            "recession", "hawkish", "rate hike", "war", "invasion", "sanction",
            "tariff", "downgrade", "default", "shutdown", "spikes", "surges to"]

_cache = {"t": 0, "data": None}


async def _scrape(url):
    from crawl4ai import AsyncWebCrawler
    try:
        async with AsyncWebCrawler() as c:
            r = await c.arun(url=url)
            return r.markdown or ""
    except Exception:
        return ""


def assess(ttl=1200):
    if _cache["data"] and time.time() - _cache["t"] < ttl:
        return _cache["data"]
    md = ""
    try:
        for u in SOURCES:
            md += "\n" + asyncio.run(_scrape(u))
    except Exception:
        pass
    lines = [ln.strip() for ln in md.splitlines() if 25 < len(ln.strip()) < 180]
    big = []
    for ln in lines:
        low = ln.lower()
        if any(k in low for k in BIG_EVENT):
            risk = any(k in low for k in RISK_OFF)
            big.append({"headline": ln[:160], "risk_off": risk})
    risk_hits = [h for h in big if h["risk_off"]]
    level = "high" if len(risk_hits) >= 3 else "med" if risk_hits else "low"
    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M"), "scanned_lines": len(lines),
           "big_events": big[:12], "risk_off_count": len(risk_hits), "risk_level": level,
           "risk_off": level in ("high", "med"),
           "note": "RISK-OFF macro headlines — desk pauses new entries" if level != "low"
                   else "no major risk-off macro events detected"}
    _cache.update(t=time.time(), data=out)
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(assess(), indent=2, default=str))
