#!/usr/bin/env python3
"""
STAR — US market (NYSE) calendar awareness. The desk must NOT trade on holidays,
and research should account for pre-holiday drift (low volume / accumulation) and
the gap risk of a long weekend.
"""
from datetime import date, timedelta

# NYSE full closures
HOLIDAYS_2026 = {
    "2026-01-01": "New Year's Day", "2026-01-19": "MLK Day",
    "2026-02-16": "Presidents' Day", "2026-04-03": "Good Friday",
    "2026-05-25": "Memorial Day", "2026-06-19": "Juneteenth",
    "2026-07-03": "Independence Day (obs)", "2026-09-07": "Labor Day",
    "2026-11-26": "Thanksgiving", "2026-12-25": "Christmas",
}
# Early closes (1pm ET / 12pm CT)
HALF_DAYS_2026 = {"2026-11-27": "Day after Thanksgiving", "2026-12-24": "Christmas Eve"}


def _d(dt=None):
    return (dt or date.today())


def is_holiday(dt=None):
    return _d(dt).isoformat() in HOLIDAYS_2026


def is_half_day(dt=None):
    return _d(dt).isoformat() in HALF_DAYS_2026


def is_trading_day(dt=None):
    d = _d(dt)
    return d.weekday() < 5 and not is_holiday(d)


def next_trading_day(dt=None):
    d = _d(dt) + timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


def long_weekend_ahead(dt=None):
    """True if today is a trading day but the NEXT trading day is >1 calendar day
    out (a holiday-extended break) — i.e., we'd be gapping over a long weekend."""
    d = _d(dt)
    if not is_trading_day(d):
        return False
    return (next_trading_day(d) - d).days > 1


def status(dt=None):
    d = _d(dt)
    nxt = next_trading_day(d)
    gap = (nxt - d).days
    return {
        "date": d.isoformat(), "weekday": d.strftime("%A"),
        "trading_day": is_trading_day(d),
        "holiday": HOLIDAYS_2026.get(d.isoformat()),
        "half_day": HALF_DAYS_2026.get(d.isoformat()),
        "pre_holiday": long_weekend_ahead(d) and gap > 1,
        "next_trading_day": nxt.isoformat(), "gap_days": gap,
        "note": (f"CLOSED — {HOLIDAYS_2026[d.isoformat()]}" if is_holiday(d)
                 else "weekend" if d.weekday() >= 5
                 else f"pre-holiday: {gap}-day gap to {nxt.strftime('%A')} — expect low volume + gap risk"
                 if long_weekend_ahead(d) else "normal trading day"),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(status(), indent=2))
