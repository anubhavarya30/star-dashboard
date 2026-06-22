#!/usr/bin/env python3
"""
STAR — Webull options TICKET (semi-manual real execution).

Webull has no usable public API, so STAR is the BRAIN and you are the TRIGGER:
when the options desk picks a spread, this Telegrams you a ready-to-place order
ticket. You tap it into the Webull app — real money, you approve every trade,
no credentials stored anywhere. Entry tickets when STAR opens a spread; close
tickets when STAR's exit rules fire. The sim desk's lifecycle drives the tickets;
its tracked P&L approximates your Webull P&L (modulo your actual fills).
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)


def _send(msg):
    try:
        import telegram_alert
        return telegram_alert.send(msg)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def entry_ticket(pos, thesis=""):
    """Telegram a BUY-TO-OPEN ticket for a vertical debit spread."""
    r = pos.get("right", "C").upper()[0]
    is_put = r == "P"
    name = "BEAR PUT" if is_put else "BULL CALL"
    glyph = "🔻" if is_put else "🟢"
    word = "PUT" if is_put else "CALL"
    lk, sk = pos["long_strike"], pos["short_strike"]
    debit, qty = pos["net_debit"], pos["contracts"]
    msg = (
        f"🎟️ <b>WEBULL TICKET — BUY TO OPEN</b>\n"
        f"{glyph} <b>{name} DEBIT SPREAD</b>\n"
        f"<b>{pos['symbol']}</b> · exp {pos['expiry']}\n"
        f"  • BUY  {lk} {word}  ×{qty}\n"
        f"  • SELL {sk} {word}  ×{qty}\n"
        f"Limit (net debit): <b>${debit}</b>  → cost ${pos['max_loss']}\n"
        f"Max loss ${pos['max_loss']} · Max gain ${pos['max_gain']} · {pos['rr']}:1\n"
        + (f"<i>{thesis[:60]}</i>\n" if thesis else "")
        + f"\n<b>Place on Webull:</b>\n"
        f"1. {pos['symbol']} → Options → {pos['expiry']}\n"
        f"2. Strategy → Vertical → {word.title()} Debit Spread\n"
        f"3. Buy {lk}{r} / Sell {sk}{r} · Qty {qty}\n"
        f"4. Limit ${debit} · DAY → Review → Send\n"
        f"\n⏳ STAR will ping you when to CLOSE."
    )
    return _send(msg)


def exit_ticket(pos, reason, value, pnl):
    """Telegram a SELL-TO-CLOSE ticket when STAR's exit rules fire."""
    r = pos.get("right", "C").upper()[0]
    emo = "🟢" if pnl >= 0 else "🔴"
    msg = (
        f"🎟️ <b>WEBULL TICKET — CLOSE (SELL TO CLOSE)</b>\n"
        f"{emo} <b>{pos['symbol']} {pos['long_strike']}/{pos['short_strike']}{r}</b> ×{pos['contracts']}\n"
        f"Reason: {reason}\n"
        f"Close ~<b>${value}</b> (spread value) → est P&amp;L {'+' if pnl >= 0 else ''}${pnl}\n"
        f"\n<b>Webull:</b> Positions → {pos['symbol']} spread → Close → "
        f"limit ~${value} · DAY → Send"
    )
    return _send(msg)


if __name__ == "__main__":
    demo = {"symbol": "WMT", "right": "P", "expiry": "2026-07-24",
            "long_strike": 117.0, "short_strike": 113.0, "net_debit": 1.49,
            "contracts": 1, "max_loss": 149.0, "max_gain": 251.0, "rr": 1.68}
    print(entry_ticket(demo, "DOWNSIDE 7/9 (ema stack down, macd bearish)"))
