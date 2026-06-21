#!/usr/bin/env python3
"""
STAR — earnings-date guard. Now that the desk holds SWINGS (overnight), entering
right before an earnings report = uncontrolled gap risk. This blocks new entries
when a name reports within `within` trading days. Uses yfinance earnings dates
(free, reliable) — no scraping needed for the date itself.
"""
from datetime import date


def next_earnings(sym):
    """Next upcoming earnings date (or None)."""
    import yfinance as yf
    t = yf.Ticker(sym)
    today = date.today()
    # primary: full earnings-date table
    try:
        df = t.get_earnings_dates(limit=12)
        if df is not None and len(df):
            fut = [ix.date() for ix in df.index if ix.date() >= today]
            if fut:
                return min(fut)
    except Exception:
        pass
    # fallback: calendar
    try:
        cal = t.calendar
        ed = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if ed:
            d = ed[0] if isinstance(ed, (list, tuple)) else ed
            d = d.date() if hasattr(d, "date") else d
            if d and d >= today:
                return d
    except Exception:
        pass
    return None


def days_to_earnings(sym):
    d = next_earnings(sym)
    return (d - date.today()).days if d else None


def blocked(sym, within=3):
    """True if `sym` reports within `within` days (skip new entries)."""
    d = days_to_earnings(sym)
    return {"blocked": d is not None and 0 <= d <= within,
            "days_to_earnings": d, "earnings_date": str(next_earnings(sym)) if d is not None else None}


if __name__ == "__main__":
    import sys, json
    print(json.dumps(blocked(sys.argv[1] if len(sys.argv) > 1 else "AAPL"), indent=2, default=str))
