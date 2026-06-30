#!/usr/bin/env python3
"""
STAR — real-time data auto-detector. IBKR market-data sharing changes propagate on a
delay (usually next trading day). Rather than test by hand, this checks whether the
paper account is actually entitled to real-time data, remembers the state, and the
moment it flips ON it Telegrams "real-time LIVE" + writes a flag the scalp desk reads.
Runs on a schedule (com.star.rtcheck). Safe: pure read, never touches trading.
"""
import json
import os
import sys

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
STATE = os.path.join(ROOT, "data", "realtime_status.json")
PORT = int(os.environ.get("STAR_IBKR_PORT", "7497"))


def probe():
    """Is the paper account entitled to real-time data? (10089/10168 = not entitled.)"""
    from ib_async import IB, Stock
    errs = []
    ib = IB()
    ib.errorEvent += lambda i, c, m, x=None: errs.append(c)
    try:
        ib.connect("127.0.0.1", PORT, clientId=58, timeout=10)
    except Exception as e:
        return {"available": False, "reason": f"ibkr down: {type(e).__name__}"}
    try:
        ib.reqMarketDataType(1)
        k = Stock("AAPL", "SMART", "USD"); ib.qualifyContracts(k)
        t = ib.reqMktData(k, "", False, False); ib.sleep(4)
        blocked = any(e in (10089, 10168, 10197, 354) for e in errs)
        last = t.last if (t.last == t.last) else None      # nan-safe
        # entitled = no subscription error. (When market is closed, last may still be
        # None even if entitled — the ABSENCE of the block error is the real signal.)
        return {"available": (not blocked), "blocked": blocked, "last": last}
    finally:
        ib.disconnect()


def _load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"available": False}


def tick():
    import datetime
    prev = _load().get("available", False)
    r = probe()
    now = {"available": r.get("available", False), "last": r.get("last"),
           "checked_at": datetime.datetime.now().astimezone().isoformat()}
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(now, open(STATE, "w"), indent=2, default=str)
    # alert only on a real OFF->ON flip
    if now["available"] and not prev:
        try:
            import telegram_alert
            telegram_alert.send("✅ STAR: IBKR REAL-TIME data is now LIVE on the paper account. "
                                "Tell Claude 'wire real-time' to switch the scalp engine to on-bar execution.")
        except Exception:
            pass
    return now


def available():
    """For the scalp desk to read (cheap, from the cached flag)."""
    return bool(_load().get("available"))


if __name__ == "__main__":
    print(json.dumps(tick(), indent=2, default=str))
