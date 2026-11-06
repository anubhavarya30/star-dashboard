#!/usr/bin/env python3
"""
STAR — daily scorecard to Telegram (user's 3-week challenge from 2026-11-06: results every
day, aim >70% green). Sent once a day after the stock close by scripts/gold.sh (runs every 5
min). Counts STAR's own closed trades (all desks, from the DB) per calendar day, keeps the
day-by-day record in data/scorecard.json. Old untracked IBKR positions are NOT counted.
"""
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
CARD = os.path.join(HERE, "..", "data", "scorecard.json")
START = "2026-11-06"


def _load():
    try:
        return json.load(open(CARD))
    except Exception:
        return {"start": START, "days": {}, "sent": ""}


def build(today=None):
    import db
    today = today or date.today().isoformat()
    by, n, wins, pnl = {}, 0, 0, 0.0
    for r in db.paper_trades_all(5000):
        if str(r.get("closed_at", ""))[:10] != today or str(r.get("source", "")).endswith("_retired"):
            continue
        v = float(r.get("pnl") or 0); src = r.get("source") or "stock"
        b = by.setdefault(src, [0, 0.0]); b[0] += 1; b[1] += v
        n += 1; wins += v > 0; pnl += v
    c = _load()
    c["days"][today] = {"pnl": round(pnl, 2), "trades": n, "wins": int(wins)}
    days = [d for k, d in sorted(c["days"].items()) if k >= c["start"] and d["trades"]]
    green = sum(d["pnl"] > 0 for d in days)
    total = round(sum(d["pnl"] for d in days), 2)
    lines = [f"📊 STAR daily — {today}",
             f"Today: {'+' if pnl >= 0 else ''}${pnl:.2f} on {n} trades ({int(wins)} wins)"]
    lines += [f"  {s}: {k} tr, ${v:+.2f}" for s, (k, v) in sorted(by.items())]
    try:
        import gold, btc
        g = gold._load().get("open"); bo = btc._load().get("open")
        lines.append(f"Open: gold {g['dir'] + ' @ ' + str(g['entry']) if g else 'flat'} · btc {'LONG @ ' + str(bo['entry']) if bo else 'flat'}")
    except Exception:
        pass
    lines.append(f"Challenge since {c['start']}: {green}/{len(days)} green days"
                 f"{f' ({green / len(days) * 100:.0f}%)' if days else ''} · total ${total:+.2f} · target 70% green")
    return c, "\n".join(lines)


def send_once():
    """Send today's card once (idempotent); returns the text."""
    c, msg = build()
    today = date.today().isoformat()
    if c.get("sent") != today:
        import telegram_alert
        telegram_alert.send(msg)
        c["sent"] = today
    os.makedirs(os.path.dirname(CARD), exist_ok=True)
    json.dump(c, open(CARD, "w"), indent=2)
    return msg


if __name__ == "__main__":
    print(send_once() if "--send" in sys.argv else build()[1])
