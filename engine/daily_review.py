#!/usr/bin/env python3
"""
STAR — daily review + self-improvement agent. After the close (and folded into the
next morning's brief) STAR grades the day, writes data-driven LESSONS, and keeps a
rolling SCOREBOARD of each strategy's real performance from the DB — so it leans into
what's working and flags what isn't. This is the learning loop: the scoreboard is the
honest memory; the lessons are the takeaways; both show on the Market Read.
"""
import json
import os
import sys
import datetime

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
OUTDIR = os.path.join(ROOT, "data", "reviews")


def scoreboard():
    """Rolling performance per strategy from ALL closed trades — STAR's memory of what
    works. Ranked by total P&L; expectancy = avg $/trade."""
    import db
    rows = db.paper_trades_all(5000)
    by = {}
    for r in rows:
        s = r.get("source") or "stock"
        g = by.setdefault(s, {"trades": 0, "wins": 0, "pnl": 0.0})
        g["trades"] += 1
        g["pnl"] = round(g["pnl"] + (r.get("pnl") or 0), 2)
        g["wins"] += 1 if (r.get("pnl") or 0) > 0 else 0
    for g in by.values():
        g["win_rate"] = round(g["wins"] / g["trades"] * 100, 1) if g["trades"] else 0
        g["avg_pnl"] = round(g["pnl"] / g["trades"], 2) if g["trades"] else 0
    return dict(sorted(by.items(), key=lambda kv: kv[1]["pnl"], reverse=True))


def _lessons(by_today, sb):
    """Generate data-driven takeaways — what to repeat, what to stop."""
    out = []
    for s, g in sorted(by_today.items(), key=lambda kv: kv[1]["pnl"]):
        if g["pnl"] < 0:
            out.append(f"❌ {s} lost ${abs(g['pnl'])} today ({g['trades']} trades) — tighten entries / cut faster.")
        elif g["pnl"] > 0:
            out.append(f"✅ {s} made +${g['pnl']} today ({g['trades']} trades) — keep running it.")
    # cross-strategy regime lesson
    st = by_today.get("stock", {}).get("pnl", 0)
    sc = by_today.get("scalp", {}).get("pnl", 0)
    op = by_today.get("option", {}).get("pnl", 0)
    if st < 0 and (sc > 0 or op > 0):
        out.append("🔁 Long swings struggled while scalps/options won — favor short-side & quick trades on risk-off days.")
    # which strategy has the best PROVEN edge (all-time) -> lean in
    if sb:
        best = max(sb.items(), key=lambda kv: kv[1]["avg_pnl"])
        out.append(f"📈 Best proven edge: {best[0]} (+${best[1]['avg_pnl']}/trade over {best[1]['trades']}). Scale this one.")
    return out


def review(date=None):
    import db
    all_rows = db.paper_trades_all(2000)
    today = date or datetime.date.today().isoformat()
    rows = [r for r in all_rows if str(r.get("closed_at", ""))[:10] == today]
    # Morning case: the new day has no trades yet -> review the LAST completed session
    # so the pre-market brief actually shows results, not a blank.
    if not rows and date is None:
        dates = sorted({str(r.get("closed_at", ""))[:10] for r in all_rows if r.get("closed_at")}, reverse=True)
        if dates:
            today = dates[0]
            rows = [r for r in all_rows if str(r.get("closed_at", ""))[:10] == today]
    by = {}
    for r in rows:
        s = r.get("source") or "stock"
        g = by.setdefault(s, {"trades": 0, "wins": 0, "pnl": 0.0})
        g["trades"] += 1
        g["pnl"] = round(g["pnl"] + (r.get("pnl") or 0), 2)
        g["wins"] += 1 if (r.get("pnl") or 0) > 0 else 0
    net = round(sum((r.get("pnl") or 0) for r in rows), 2)
    sb = scoreboard()
    cum = round(sum(v["pnl"] for v in sb.values()), 2)   # all-time cumulative (scaling)
    best = max(rows, key=lambda r: r.get("pnl") or 0, default=None)
    worst = min(rows, key=lambda r: r.get("pnl") or 0, default=None)
    out = {"date": today, "trades": len(rows), "net": net, "cumulative": cum,
           "by_source": by, "scoreboard": sb,
           "best": ({"symbol": best.get("symbol"), "pnl": best.get("pnl")} if best else None),
           "worst": ({"symbol": worst.get("symbol"), "pnl": worst.get("pnl")} if worst else None),
           "lessons": _lessons(by, sb)}
    os.makedirs(OUTDIR, exist_ok=True)
    json.dump(out, open(os.path.join(OUTDIR, f"{today}.json"), "w"), indent=2, default=str)
    json.dump(out, open(os.path.join(OUTDIR, "latest.json"), "w"), indent=2, default=str)
    return out


if __name__ == "__main__":
    print(json.dumps(review(), indent=2, default=str))
