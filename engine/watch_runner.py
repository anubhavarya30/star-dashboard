#!/usr/bin/env python3
"""
STAR — live runner monitor. Polls one symbol every ~60s and watches for a REAL
playbook setup (not a chase). Writes a status line + JSON snapshot so STAR can
report the moment a valid trigger appears. All live yfinance data.

Setup B (VWAP reclaim off the lows): price was below VWAP, reclaims it while
holding above the day low, on rising volume. That's a disciplined long trigger
with a tight, affordable stop (under the reclaim low). Anything pinned at HOD
after a parabola is reported as DO-NOT-CHASE, never a trigger.
"""
import json
import math
import sys
import time
from datetime import datetime

LOG = "/tmp/star_runner_watch.log"
STATUS = "/tmp/star_runner_status.json"


def snapshot(sym):
    import yfinance as yf
    tk = yf.Ticker(sym)
    h = tk.history(period="1d", interval="1m")
    if h is None or len(h) < 2:
        return None
    tp = (h["High"] + h["Low"] + h["Close"]) / 3.0
    vwap = float((tp * h["Volume"]).cumsum().iloc[-1] / h["Volume"].cumsum().iloc[-1])
    price = float(h["Close"].iloc[-1]); prev_close = float(h["Close"].iloc[-2])
    hod = float(h["High"].max()); lod = float(h["Low"].min())
    last_vol = float(h["Volume"].iloc[-1]); avg_vol = float(h["Volume"].tail(20).mean())
    above_vwap = price > vwap
    was_below = prev_close <= vwap
    off_low = (price / lod - 1) * 100 if lod else 0
    off_high = (hod - price) / hod * 100 if hod else 0
    # Setup B reclaim trigger
    trigger = (was_below and above_vwap and off_low > 1 and last_vol > avg_vol)
    note = "VWAP RECLAIM — Setup B trigger" if trigger else (
        "above VWAP, holding" if above_vwap else "below VWAP — no long, stand aside")
    plan = None
    if trigger:
        entry = round(price, 2); stop = round(min(vwap, lod) * 0.995, 2)
        rps = round(entry - stop, 2)
        sh = math.floor(25 / rps) if rps > 0 else 0
        plan = {"entry": entry, "stop": stop, "risk_per_share": rps, "shares": sh,
                "cost": round(sh * entry, 2), "target_2R": round(entry + 2 * rps, 2)}
    return {"symbol": sym.upper(), "ts": datetime.now().strftime("%H:%M:%S"),
            "price": round(price, 3), "vwap": round(vwap, 3), "hod": round(hod, 2),
            "lod": round(lod, 2), "off_high_pct": round(off_high, 1),
            "off_low_pct": round(off_low, 1), "rel_vol_1m": round(last_vol / avg_vol, 1) if avg_vol else None,
            "above_vwap": above_vwap, "trigger": trigger, "note": note, "plan": plan}


def main(sym="JRSH", minutes=120, interval=60):
    end = time.time() + minutes * 60
    with open(LOG, "a") as f:
        f.write(f"\n===== watch {sym} start {datetime.now()} =====\n")
    while time.time() < end:
        try:
            s = snapshot(sym)
            if s:
                json.dump(s, open(STATUS, "w"), default=str)
                line = (f"{s['ts']} {sym} ${s['price']} vwap ${s['vwap']} "
                        f"(off_high {s['off_high_pct']}% off_low {s['off_low_pct']}%) "
                        f"relvol {s['rel_vol_1m']}x :: {s['note']}")
                with open(LOG, "a") as f:
                    f.write(("*** TRIGGER *** " if s["trigger"] else "") + line + "\n")
        except Exception as e:
            with open(LOG, "a") as f:
                f.write(f"{datetime.now().strftime('%H:%M:%S')} err: {e}\n")
        time.sleep(interval)


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "JRSH"
    mins = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    main(sym, mins)
