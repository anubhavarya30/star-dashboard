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

    idx = _agent("indices", _indices, default=[])
    world = _agent("world", lambda: __import__("world_market").read(), default={})
    review = _agent("review", lambda: __import__("daily_review").review(), default={})
    rev_state = {k: {"price": v.get("price"), "rsi": v.get("rsi"),
                     "trigger": v.get("trigger"), "note": v.get("note")}
                 for k, v in reversal.items() if isinstance(v, dict)}
    try:
        world_narr = __import__("world_market").narrative(world) if world.get("regions") else ""
    except Exception:
        world_narr = ""

    # --- FOCUS (2026-07-06): the two live strategies only --------------------------
    # FVG for STOCKS, GEX for OPTIONS. Overnight research assigns each desk its plan.
    fvg_stocks = []
    try:
        import fvg
        for sym in ss.UNIVERSE:
            try:
                sig = fvg.signal(sym)
                if isinstance(sig, dict) and sig.get("setup"):
                    fvg_stocks.append({"symbol": sym, "entry": sig.get("entry"),
                                       "stop": sig.get("stop"), "target": sig.get("target"),
                                       "note": sig.get("note", "FVG support long")})
            except Exception:
                pass
    except Exception:
        pass
    gex_options = {}
    try:
        import gex_desk
        gsig = _agent("gex_setup", gex_desk._signal, default=None)
        gex_options = {"symbol": "SPY", "regime": (gex or {}).get("regime"),
                       "flip": (gex or {}).get("gamma_flip"), "spot": (gex or {}).get("spot"),
                       "call_wall": (gex or {}).get("call_wall"), "put_wall": (gex or {}).get("put_wall"),
                       "setup": gsig}
    except Exception:
        pass

    out = {"date": datetime.now().strftime("%Y-%m-%d"),
           "generated_at": datetime.now().astimezone().isoformat(),
           "regime": risk_level, "bias": bias,
           "indices": idx,
           "world": world, "world_narrative": world_narr,
           "review": {k: review.get(k) for k in ("net", "cumulative", "by_source", "scoreboard", "lessons", "best", "worst")} if review else {},
           "narrative": _narrative(idx, risk_level, watch, rev_state, world),
           "gex_flip": (gex or {}).get("gamma_flip"), "gex_regime": (gex or {}).get("regime"),
           "watchlist": watch,
           "shorts_context": [{"symbol": s.get("symbol"), "score": s.get("score"),
                               "thesis": s.get("thesis")} for s in (shorts or [])[:4] if isinstance(s, dict)],
           "reversal_armed": {k: {"price": v.get("price"), "rsi": v.get("rsi"),
                                  "trigger": v.get("trigger"), "note": v.get("note")}
                              for k, v in reversal.items() if isinstance(v, dict)},
           "gappers": [g.get("symbol") for g in (gappers.get("top_watches") or [])] if isinstance(gappers, dict) else [],
           "fvg_stocks": fvg_stocks, "gex_options": gex_options,
           "readiness": readiness()}
    _write(out)
    _telegram(out)
    return out


def _indices():
    """Snapshot the headline indices for the market read."""
    import yfinance as yf
    out = []
    for name, t in (("Nasdaq", "^IXIC"), ("S&P 500", "^GSPC"), ("Dow", "^DJI"), ("VIX", "^VIX")):
        try:
            h = yf.Ticker(t).history(period="2d")
            c = float(h["Close"].iloc[-1]); p = float(h["Close"].iloc[-2])
            out.append({"name": name, "price": round(c, 2), "chg_pct": round((c / p - 1) * 100, 2)})
        except Exception:
            out.append({"name": name, "price": None, "chg_pct": None})
    return out


def _narrative(idx, regime, watch, reversal, world=None):
    """Auto-compose the prose market read from the agents' data.

    CONSISTENCY: the tape call is anchored to the LIVE overnight read (world futures)
    and the news regime — one source of truth — so it can never say 'risk-off' and
    'risk appetite is on' in the same breath (the old bug: the label came from news
    while the rotation line came from yfinance, and the two were never reconciled).

    NO STALE CLAIMS: pre-open, yfinance daily bars are YESTERDAY's close, so index
    %-moves are prior-session, not today. They're labelled 'Prior close' — never
    presented as the live tape (that's what made the brief forward stale info)."""
    world = world or {}
    off = (regime == "high") or str(world.get("global_bias", "")).lower().startswith("risk-off")
    fut = world.get("futures") or {}
    d = {i["name"]: i for i in idx}
    nas = d.get("Nasdaq", {}).get("chg_pct")
    dow = d.get("Dow", {}).get("chg_pct")
    vix = d.get("VIX", {})
    parts = []
    # 1) TAPE — from live overnight futures, consistent with the regime label
    tone = "risk-off" if off else "constructive"
    if fut:
        fbits = ", ".join(f"{k} {v:+.1f}%" for k, v in fut.items() if v is not None)
        parts.append(f"Tape is <b>{tone}</b> into the open — overnight futures {fbits}." if fbits
                     else f"Tape is <b>{tone}</b> into the open.")
    else:
        parts.append(f"Tape is <b>{tone}</b> into the open.")
    # 2) PRIOR-SESSION close context (explicitly labelled — not today's move)
    if nas is not None and dow is not None:
        spread = nas - dow
        rot = ("tech led — money into growth" if spread >= 1.0 else
               "value/defensives led — money out of tech" if spread <= -1.0 else
               "broad, no strong rotation")
        parts.append(f"Prior close: Nasdaq {nas:+.1f}% / Dow {dow:+.1f}% ({rot}).")
    if vix.get("chg_pct") is not None:
        v = vix.get("price")
        parts.append(f"VIX {v} — {'fear building' if (vix['chg_pct'] or 0) > 8 else 'orderly, not panic'}.")
    if watch:
        names = ", ".join(w["symbol"] for w in watch[:6])
        parts.append(f"STAR armed the relative-strength leaders that are holding up: <b>{names}</b> — "
                     f"{'leaders on a weak tape' if off else 'the strongest 9-vote setups'}, not falling knives.")
    else:
        parts.append("Nothing cleared the bar — patience over forcing a bad trade.")
    hot = [k for k, v in reversal.items() if v.get("trigger")]
    if hot:
        parts.append(f"Reversal TRIGGER firing on <b>{', '.join(hot)}</b>.")
    return " ".join(parts)


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
    rdy = "✅ IBKR ready" if out["readiness"].get("ready") else "⚠️ IBKR NOT ready"
    fvg = out.get("fvg_stocks", [])
    gx = out.get("gex_options", {})
    # FVG stock assignments
    if fvg:
        fvg_line = "\n".join(f"• <b>{s['symbol']}</b> entry ${s['entry']} · stop ${s['stop']} → tgt ${s['target']}"
                             for s in fvg[:6])
    else:
        fvg_line = "• none set up — no forced trades"
    # GEX options assignment
    setup = (gx or {}).get("setup")
    if setup:
        gx_line = (f"• <b>{setup['dir']} SPY</b> ({setup.get('regime')} gamma) entry ${setup['entry']} · "
                   f"stop ${setup['stop']} → tgt ${setup['target']} ({setup.get('rr')}R)")
    elif gx:
        gx_line = (f"• {gx.get('regime')} gamma, flip {gx.get('flip')}, walls "
                   f"{gx.get('put_wall')}/{gx.get('call_wall')} — wait for stack+vol confirm")
    else:
        gx_line = "• GEX unavailable"
    msg = (f"🌅 <b>STAR Overnight Brief — {out['date']}</b>\n"
           f"Regime: <b>{out['regime']}</b> · {rdy}\n"
           f"<i>{out['bias']}</i>\n\n"
           f"📊 <b>FVG — stocks ({len(fvg)}):</b>\n{fvg_line}\n\n"
           f"🎯 <b>GEX — SPY options:</b>\n{gx_line}\n\n"
           f"Focus: FVG stocks + GEX options only. Desks manage to exit.")
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
