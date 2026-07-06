#!/usr/bin/env python3
"""
STAR — always-on active engine. Runs CONTINUOUSLY (KeepAlive), checking every 60s.
While the market is open it manages every open position (breakeven + trailing stop,
exit on stop/target) AND looks for new entries. The moment a trade is on, this is
watching it minute-by-minute until it's closed — losing a winner to a static stop
is not on the table.

Honest floor: free yfinance is ~1-min granularity and slightly delayed; true
tick-by-tick needs a paid real-time feed (we have none — IBKR Error 10089). 60s is
as tight as we can go without paying for data.
"""
import sys
import time
import os

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

INTERVAL = 60  # seconds


def main():
    import paper_session as ps
    ps._log("active_watch started — 60s loop, managing open trades until closed")
    while True:
        try:
            now = ps._now_ct()
            phase = ps._market_phase(now)
            if phase in ("open", "eod"):
                ps.manage_open(force_close=(phase == "eod"))     # breakeven/trail/exit every minute
                if phase == "open":
                    ps.maybe_enter()
                    # DISABLED 2026-07-06 (focus): watch_reversal (TSM/AMD/ARM reversal) is a
                    # diversion from the two chosen strategies (GEX->options, FVG->stocks) and
                    # was the source of the Webull-ticket + reversal Telegram spam. Off until
                    # explicitly re-enabled.
                    # import watch_reversal
                    # watch_reversal.tick()
                if phase == "eod":
                    ps.log_daily_summary()
        except Exception as e:
            try:
                ps._log(f"active_watch error: {type(e).__name__}: {e}")
            except Exception:
                pass
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
