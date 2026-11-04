#!/usr/bin/env python3
"""
STAR watchdog — health monitor for the 24/7 desk.

Runs periodically (via launchd com.star.watchdog, every few minutes). Checks the
critical pieces of the running system and TELEGRAMS the user the moment any of
them breaks — then sends a follow-up when it recovers. Honest by design: it
reports the real state, never a fake "all good".

Checks:
  1. dashboard      — terminal_server answering on http://localhost:8080
  2. engine         — com.star.activewatch loaded AND its tick log is fresh
  3. ibkr           — broker connected to the PAPER account, can_auto_trade
  4. desk halted    — risk manager hit the daily loss limit (informational alert)

State (last status per check + last-alert time) lives in
/tmp/star_watchdog_state.json so we only alert on TRANSITIONS (ok->fail,
fail->ok) and re-nag at most once every RENAG_MIN minutes for a stuck failure.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import telegram_alert  # noqa: E402

STATE = "/tmp/star_watchdog_state.json"
TICK_LOG = "/tmp/star_paper.log"
DASH = "http://localhost:8080"
RENAG_MIN = 30          # re-nag at most every 30 min for an ongoing failure
ENGINE_STALE_MIN = 15   # engine tick log older than this => stale


def _now():
    return time.time()


def _load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def _save_state(s):
    try:
        json.dump(s, open(STATE, "w"))
    except Exception:
        pass


def _http_ok(path):
    try:
        with urllib.request.urlopen(DASH + path, timeout=8) as r:
            return r.status == 200, r.read()
    except Exception as e:
        return False, str(e).encode()


def check_dashboard():
    ok, _ = _http_ok("/api/risk_status")
    return ok, "dashboard not responding on :8080" if not ok else ""


def check_engine():
    # job must be loaded
    try:
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=8).stdout
    except Exception as e:
        return False, f"launchctl unavailable: {e}"
    if "com.star.activewatch" not in out:
        return False, "engine job com.star.activewatch is NOT loaded"
    # tick log must be fresh
    try:
        age_min = (_now() - os.path.getmtime(TICK_LOG)) / 60.0
    except Exception:
        return False, "engine tick log missing (/tmp/star_paper.log)"
    if age_min > ENGINE_STALE_MIN:
        return False, f"engine tick log stale ({age_min:.0f} min old) — engine may be stuck"
    return True, ""


def _fresh_broker_status():
    """Connect to IBKR in a brand-new process with a DEDICATED client id (77), so
    we measure the TRUE broker reachability — not terminal_server's possibly-wedged
    cached view, and without colliding with the engine's 88/89 connections."""
    try:
        env = dict(os.environ, STAR_IBKR_STATUS_CID="77")
        out = subprocess.run([sys.executable, os.path.join(HERE, "ibkr_broker.py")],
                             capture_output=True, text=True, timeout=25, env=env).stdout
        return json.loads(out)
    except Exception as e:
        return {"connected": False, "error": f"{type(e).__name__}: {e}"}


def check_ibkr():
    d = _fresh_broker_status()
    if not d.get("connected"):
        return False, f"IBKR DISCONNECTED — {d.get('error', 'no connection')} (relaunch TWS/Gateway, log into PAPER on 7497)"
    if not d.get("can_auto_trade"):
        return False, f"IBKR connected but auto-trade OFF (account {d.get('account')}, type {d.get('type')})"
    # Broker IS reachable. If terminal_server's own IBKR view is wedged, self-heal it.
    tok, body = _http_ok("/api/ibkr_broker")
    server_ok = False
    if tok:
        try:
            server_ok = bool(json.loads(body).get("connected"))
        except Exception:
            server_ok = False
    if not server_ok:
        _heal_terminal()
    return True, ""


def _heal_terminal():
    """terminal_server is up but its IBKR connection wedged (e.g. after a TWS daily
    restart). Kick the job so it rebuilds a clean connection. Telegram once."""
    try:
        subprocess.run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/com.star.terminal"],
                       capture_output=True, timeout=10)
        telegram_alert.send("🔧 self-heal: dashboard IBKR connection was wedged (likely TWS daily restart) — restarted terminal_server, broker is reachable.")
    except Exception:
        pass


def check_halted():
    ok, body = _http_ok("/api/risk_status")
    if not ok:
        return True, ""  # dashboard check already covers this
    try:
        d = json.loads(body)
    except Exception:
        return True, ""
    if d.get("halted"):
        return False, f"desk HALTED — daily loss limit hit (realized ${d.get('realized_pnl')})"
    return True, ""


CHECKS = {
    "dashboard": check_dashboard,
    "engine": check_engine,
    "ibkr": check_ibkr,
    "halted": check_halted,
}


def main():
    state = _load_state()
    now = _now()
    stamp = datetime.now(timezone.utc).astimezone().strftime("%H:%M")
    for name, fn in CHECKS.items():
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"watchdog check error: {type(e).__name__}: {e}"
        prev = state.get(name, {"ok": True, "last_alert": 0})
        was_ok = prev.get("ok", True)
        last_alert = prev.get("last_alert", 0)

        if not ok:
            # alert on ok->fail, or re-nag if stuck failing past RENAG_MIN
            if was_ok or (now - last_alert) > RENAG_MIN * 60:
                telegram_alert.send(f"⚠️ [{stamp}] {name.upper()} — {detail}")
                last_alert = now
        else:
            # recovery: fail->ok
            if not was_ok:
                telegram_alert.send(f"✅ [{stamp}] {name.upper()} recovered — back to normal")
                last_alert = 0
        state[name] = {"ok": ok, "last_alert": last_alert, "detail": detail}

    _save_state(state)
    # one-line stdout for the launchd log
    summary = " ".join(f"{k}={'ok' if v['ok'] else 'FAIL'}" for k, v in state.items())
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} watchdog: {summary}")


if __name__ == "__main__":
    main()
