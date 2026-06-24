#!/usr/bin/env python3
"""
STAR — Webull PAPER auto-trader (unofficial `webull` package).

Practices STAR's scalp/reversal trades on Webull's PAPER account (no real money) so
we validate the auto-execution pipe before ever touching the real $500. Credentials
live in data/webull_config.json (GITIGNORED — never committed, never in chat).

HONEST LIMITS: the unofficial Webull API is reverse-engineered and fragile — it can
break on Webull app updates, and the first login usually needs an MFA code. This is
PAPER-ONLY practice; real money waits until the pipe is proven + real-time data is on.
"""
import json
import os
import sys

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
CFG = os.path.join(ROOT, "data", "webull_config.json")
SESS = os.path.join(ROOT, "data", "webull_session.json")

_client = None


def _cfg():
    try:
        return json.load(open(CFG))
    except Exception:
        return {}


def configured():
    c = _cfg()
    return bool(c.get("email") and c.get("password") and c.get("trade_pin"))


def _save_session(wb):
    try:
        json.dump(wb.build_req_headers() and {
            "access_token": wb._access_token, "refresh_token": wb._refresh_token,
            "token_expire": wb._token_expire, "uuid": wb._uuid, "did": wb._did},
            open(SESS, "w"))
    except Exception:
        pass


def _new_client():
    """Login to Webull PAPER and arm the trade token. Reuses a saved device id (did)
    so MFA is only needed once."""
    from webull import paper_webull
    c = _cfg()
    wb = paper_webull()
    # reuse device id to avoid re-MFA
    try:
        s = json.load(open(SESS))
        if s.get("did"):
            wb._did = s["did"]
    except Exception:
        pass
    mfa = str(c.get("mfa") or "")
    if mfa:
        login = wb.login(c["email"], c["password"], mfa=mfa,
                         question_id=c.get("question_id"), question_answer=c.get("question_answer"))
    else:
        login = wb.login(c["email"], c["password"])
    if not (isinstance(login, dict) and login.get("accessToken")):
        raise RuntimeError(f"login failed: {login}")
    if not wb.get_trade_token(str(c["trade_pin"])):
        raise RuntimeError("trade-token (PIN) failed")
    _save_session(wb)
    return wb


def _wb():
    global _client
    if _client is None:
        _client = _new_client()
    return _client


def request_mfa():
    """Trigger Webull to send an MFA code to your email/phone (run once, then put the
    code in data/webull_config.json -> 'mfa' and run login_test)."""
    from webull import paper_webull
    c = _cfg()
    wb = paper_webull()
    return wb.get_mfa(c["email"])


def account():
    try:
        return _wb().get_account()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def positions():
    try:
        return _wb().get_positions()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def place_stock(symbol, qty, action="BUY", limit=None):
    """Place a PAPER stock order. Marketable limit if a price is given, else market."""
    if not configured():
        return {"ok": False, "error": "webull not configured"}
    try:
        wb = _wb()
        if limit:
            r = wb.place_order(stock=symbol.upper(), action=action.upper(), orderType="LMT",
                               enforce="DAY", quant=int(qty), price=round(float(limit), 2))
        else:
            r = wb.place_order(stock=symbol.upper(), action=action.upper(), orderType="MKT",
                               enforce="DAY", quant=int(qty))
        ok = bool(isinstance(r, dict) and (r.get("success") or r.get("orderId")))
        return {"ok": ok, "raw": r, "symbol": symbol.upper(), "action": action, "qty": int(qty)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "mfa":
        print("MFA requested:", request_mfa())
    elif cmd == "login":
        print("configured:", configured())
        print("account:", json.dumps(account(), default=str)[:600])
    else:
        print("configured:", configured(), "| cfg present:", os.path.exists(CFG))
