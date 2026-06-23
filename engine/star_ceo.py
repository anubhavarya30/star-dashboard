#!/usr/bin/env python3
"""
STAR — CEO orchestrator. STAR is the CEO; the engine/ modules are the workers.

Runs PRE-MARKET (launchd com.star.ceo, weekdays ~07:50 CT): STAR assigns each worker
agent a job, collects their reports, and fuses them into ONE decision artifact —
a ranked, tradeable STOCK watchlist + a market brief — so the desk walks into the
open with a plan instead of reacting. Writes:
  - data/premarket/ceo_YYYY-MM-DD.{json,md}   (the brief)
  - data/premarket/watchlist.json             (symbols the desk focuses on today)
and Telegrams the brief + a readiness check.

Honest scope: real IBKR execution is STOCKS, long-only (account is options Level 1).
The watchlist is therefore the day's strongest LONG setups; shorts/options are
context + sim/Webull. yfinance data is delayed ~15m — fine for swing entries.
"""
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
OUTDIR = os.path.join(ROOT, "data", "premarket")


def _agent(name, fn, default=None):
    """Run one worker agent; capture failure so one bad agent never sinks the report."""
    try:
        return fn()
    except Exception as e:
        return {"_agent_error": f"{name}: {type(e).__name__}: {e}"} if default is None else default


def research(max_watch=6):
    import star_score as ss
    import earnings

    # --- worker reports ---------------------------------------------------------
    regime = _agent("news", lambda: __import__("news_watch").assess(), default={})
    risk_level = regime.get("risk_level", "unknown")
    gex = _agent("gex", lambda: __import__("gex").compute("SPY"), default={})
    longs = _agent("score_long", lambda: ss.scan(min_score=5).get("ranked", []), default=[])
    shorts = _agent("score_short", lambda: ss.worst_candidates(min_score=6), default=[])
    gappers = _agent("premarket", lambda: __import__("premarket_research").build(), default={})

    reversal = {}
    try:
        import watch_reversal as wr
        for s in wr.WATCH:
            reversal[s] = _agent(f"rev:{s}", lambda s=s: wr.assess(s), default={})
    except Exception as e:
        reversal = {"_error": str(e)}

    # --- STAR's decision: rank LONG candidates, drop earnings landmines ----------
    # On a risk-off tape, demand relative strength (score>=7); else score>=5.
    min_score = 7 if risk_level == "high" else 5
    watch = []
    for c in (longs or []):
        if not isinstance(c, dict):
            continue
        if c.get("score", 0) < min_score:
            continue
        try:
            if earnings.blocked(c["symbol"], within=3)["blocked"]:
                continue
        except Exception:
            pass
        watch.append({"symbol": c["symbol"], "score": c["score"], "rr": c.get("rr"),
                      "price": c.get("price"), "stop": c.get("stop"), "target": c.get("target"),
                      "reasons": (c.get("reasons") or [])[:4]})
        if len(watch) >= max_watch:
            break

    bias = ("risk-off — demand relative strength (long score>=7); puts are context only"
            if risk_level == "high" else
            "constructive — trade the strongest 9-vote longs (score>=5)")

    out = {"date": datetime.now().strftime("%Y-%m-%d"),
           "generated_at": datetime.now().astimezone().isoformat(),
           "regime": risk_level, "bias": bias,
           "gex_flip": (gex or {}).get("gamma_flip"), "gex_regime": (gex or {}).get("regime"),
           "watchlist": watch,
           "shorts_context": [{"symbol": s.get("symbol"), "score": s.get("score"),
                               "thesis": s.get("thesis")} for s in (shorts or [])[:4] if isinstance(s, dict)],
           "reversal_armed": {k: {"price": v.get("price"), "rsi": v.get("rsi"),
                                  "trigger": v.get("trigger"), "note": v.get("note")}
                              for k, v in reversal.items() if isinstance(v, dict)},
           "gappers": [g.get("symbol") for g in (gappers.get("top_watches") or [])] if isinstance(gappers, dict) else [],
           "readiness": readiness()}
    _write(out)
    _telegram(out)
    return out


def readiness():
    """Pre-open self-check: is IBKR order-ready? Returns a small status dict."""
    try:
        import ibkr_broker as b
        st = b.status(client_id=75)
        return {"ibkr_connected": st.get("connected"), "account": st.get("account"),
                "can_auto_trade": st.get("can_auto_trade"),
                "ready": bool(st.get("can_auto_trade"))}
    except Exception as e:
        return {"ready": False, "error": f"{type(e).__name__}: {e}"}


def _write(out):
    os.makedirs(OUTDIR, exist_ok=True)
    json.dump(out, open(os.path.join(OUTDIR, f"ceo_{out['date']}.json"), "w"), indent=2, default=str)
    # the desk reads this to focus the day's universe
    json.dump({"date": out["date"], "symbols": [w["symbol"] for w in out["watchlist"]],
               "detail": out["watchlist"]},
              open(os.path.join(OUTDIR, "watchlist.json"), "w"), indent=2, default=str)
    # human brief
    md = [f"# STAR Pre-Market Brief — {out['date']}", "",
          f"_Generated {out['generated_at'][:19]} CT. Regime: **{out['regime']}**._", "",
          f"**Bias:** {out['bias']}", "",
          f"**Readiness:** IBKR {'✅ ready' if out['readiness'].get('ready') else '⚠️ NOT ready'} "
          f"({out['readiness'].get('account')})", "",
          "## 🎯 Tradeable watchlist (real IBKR longs)", ""]
    if out["watchlist"]:
        for w in out["watchlist"]:
            md.append(f"- **{w['symbol']}** score {w['score']}/9 · ${w['price']} · "
                      f"stop ${w['stop']} → target ${w['target']} ({w['rr']}:1) — {', '.join(w['reasons'])}")
    else:
        md.append("_No long cleared the bar — patience, not forcing._")
    md += ["", "## 🔻 Shorts (context / sim only)",
           "  " + (", ".join(f"{s['symbol']}({s['score']})" for s in out["shorts_context"]) or "—"),
           "", "## ⚡ Reversal armed (TSM/AMD/ARM)"]
    for k, v in out["reversal_armed"].items():
        md.append(f"- {k}: ${v.get('price')} rsi {v.get('rsi')} {'🔥TRIGGER' if v.get('trigger') else 'watching'}")
    open(os.path.join(OUTDIR, f"{out['date']}.md"), "w").write("\n".join(md))


def _telegram(out):
    try:
        import telegram_alert
    except Exception:
        return
    wl = out["watchlist"]
    names = ", ".join(f"{w['symbol']}({w['score']})" for w in wl) or "none cleared the bar"
    rdy = "✅ IBKR ready" if out["readiness"].get("ready") else "⚠️ IBKR NOT ready"
    rev_hot = [k for k, v in out["reversal_armed"].items() if v.get("trigger")]
    msg = (f"🌅 <b>STAR Pre-Market Brief — {out['date']}</b>\n"
           f"Regime: <b>{out['regime']}</b> · {rdy}\n"
           f"<b>{len(wl)} long(s) armed:</b> {names}\n"
           + (f"⚡ reversal TRIGGER: {', '.join(rev_hot)}\n" if rev_hot else
              "⚡ TSM/AMD/ARM: watching\n")
           + f"<i>{out['bias']}</i>\n"
           f"Desk will take the entry at the open + manage to exit.")
    telegram_alert.send(msg)


def current_watchlist():
    """Today's CEO watchlist symbols (for the desk). Empty if not generated today."""
    try:
        d = json.load(open(os.path.join(OUTDIR, "watchlist.json")))
        if d.get("date") == datetime.now().strftime("%Y-%m-%d"):
            return d.get("symbols", [])
    except Exception:
        pass
    return []


if __name__ == "__main__":
    o = research()
    print(f"STAR CEO brief {o['date']} — regime {o['regime']}, {len(o['watchlist'])} longs armed: "
          f"{[w['symbol'] for w in o['watchlist']]}, IBKR ready={o['readiness'].get('ready')}")
