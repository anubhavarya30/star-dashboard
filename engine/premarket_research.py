#!/usr/bin/env python3
"""
STAR — premarket research routine (the morning desk).

Runs before the open (launchd, weekdays ~7:45am CDT). Pulls the day's gappers,
grades each through the RUNNERS_PLAYBOOK discipline layer, ranks them (real
watches first, landmines flagged), and writes the watchlist so it's READY when
you wake up:
  - data/premarket/YYYY-MM-DD.md   (human-readable morning brief)
  - data/premarket/latest.json     (served at /api/premarket)

This is the CEO allocating the agents: overnight/premarket research done for you,
so you walk in with a plan instead of chasing whatever's green at the open.
"""
import json
import os
from datetime import datetime

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
OUTDIR = os.path.join(ROOT, "data", "premarket")


def build(max_names=10):
    import sys
    sys.path.insert(0, ROOT)
    sys.path.insert(0, HERE)
    import webull_movers
    import runner_grader as rg

    rows = (webull_movers.movers().get("gainers") or [])[:max_names]
    graded = []
    for r in rows:
        sym = r.get("symbol")
        if not sym:
            continue
        try:
            g = rg.grade(sym)
        except Exception as e:
            g = {"symbol": sym, "verdict": "NO-DATA", "reason": str(e)}
        graded.append(g)

    order = {"EARLY-WATCH": 0, "PULLBACK-WATCH": 1, "DO-NOT-CHASE": 2,
             "NOT-IN-PLAY": 3, "AVOID-LANDMINE": 4, "NO-DATA": 5}
    graded.sort(key=lambda g: (order.get(g.get("verdict"), 9), -(g.get("change_pct") or 0)))

    watches = [g for g in graded if g.get("actionable")]
    watchlist = [g["symbol"] for g in graded
                 if g.get("verdict") != "AVOID-LANDMINE" and (g.get("price") or 0) >= 1][:5]

    out = {"date": datetime.now().strftime("%Y-%m-%d"),
           "generated_at": datetime.now().astimezone().isoformat(),
           "graded": graded, "top_watches": watches, "monitor_watchlist": watchlist}
    _write(out)
    return out


def _write(out):
    os.makedirs(OUTDIR, exist_ok=True)
    json.dump(out, open(os.path.join(OUTDIR, "latest.json"), "w"), indent=2, default=str)
    md = [f"# STAR Morning Brief — {out['date']}", "",
          f"_Generated {out['generated_at'][:19]}. Graded {len(out['graded'])} premarket gappers "
          "against the runner playbook._", ""]
    if out["top_watches"]:
        md += ["## ✅ Watches (only names that pass the rules)", ""]
        for g in out["top_watches"]:
            md.append(f"- **{g['symbol']}** {g.get('change_pct')}% · float "
                      f"{g.get('float_m')}M · ${g.get('price')} — {g['verdict']}: {g['reason']}")
        md.append("")
    else:
        md += ["## ✅ Watches", "", "_None pass the rules premarket — patience, not chasing._", ""]
    md += ["## Full board (graded)", "",
           "| Sym | %Chg | Float | MktCap | Verdict | Note |", "|---|---|---|---|---|---|"]
    for g in out["graded"]:
        md.append(f"| {g['symbol']} | {g.get('change_pct','—')}% | "
                  f"{g.get('float_m','—')}M | {g.get('market_cap_m','—')}M | "
                  f"{g.get('verdict')} | {g.get('reason','')[:70]} |")
    md += ["", f"**Monitor watchlist (for watch_runner.py):** {', '.join(out['monitor_watchlist']) or '—'}",
           "", "_Reminder: before trading any name, check SEC EDGAR for a recent S-1 / 424B5 / ATM "
           "offering — dilution into strength is what kills these runs._"]
    open(os.path.join(OUTDIR, out["date"] + ".md"), "w").write("\n".join(md))


if __name__ == "__main__":
    o = build()
    print(f"STAR Morning Brief {o['date']}: {len(o['graded'])} graded, "
          f"{len(o['top_watches'])} watches, monitor: {o['monitor_watchlist']}")
    for g in o["top_watches"]:
        print(f"  WATCH {g['symbol']:6} {g.get('change_pct')}% {g['verdict']} — {g['reason'][:70]}")
