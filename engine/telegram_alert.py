#!/usr/bin/env python3
"""
STAR — Telegram alerts. Sends push messages to your phone for real trade events
(entries, scale-outs, exits, daily summary, halts). Credentials come from
data/telegram_config.json (gitignored) or env vars — NEVER hardcoded/committed.

Setup:
  1. Telegram -> @BotFather -> /newbot -> copy the bot TOKEN.
  2. Message your new bot once (say "hi"), then get your CHAT ID:
     open https://api.telegram.org/bot<TOKEN>/getUpdates -> find "chat":{"id":...}
  3. Put them in data/telegram_config.json: {"token":"...","chat_id":"..."}
"""
import json
import os
import urllib.parse
import urllib.request

HERE = os.path.dirname(__file__)
CFG = os.path.join(HERE, "..", "data", "telegram_config.json")


def _cfg():
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    cid = os.environ.get("TELEGRAM_CHAT_ID")
    if tok and cid:
        return tok, cid
    try:
        d = json.load(open(CFG))
        return d.get("token"), d.get("chat_id")
    except Exception:
        return None, None


def configured():
    tok, cid = _cfg()
    return bool(tok and cid)


def send(msg):
    tok, cid = _cfg()
    if not tok or not cid:
        return {"ok": False, "error": "telegram not configured"}
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": cid, "text": "🤖 STAR: " + msg,
                                   "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=10) as r:
            return {"ok": r.status == 200}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    import sys
    print(send(sys.argv[1] if len(sys.argv) > 1 else "test alert — STAR connected ✅"))
