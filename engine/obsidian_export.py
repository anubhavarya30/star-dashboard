#!/usr/bin/env python3
"""
STAR — Obsidian vault exporter. Turns STAR's trade ledger + reviews into a linked
markdown vault you open directly in Obsidian: a home dashboard, per-day journal notes
(with Dataview frontmatter), and per-strategy pages. Pull it to your laptop and open
the folder as a vault. Regenerated on a schedule so it stays current.

Vault layout:
  STAR.md                  – home dashboard (P&L, equity, strategy table, recent days)
  Daily/YYYY-MM-DD.md      – daily journal: trades, P&L, tags  (#daily)
  Strategies/<name>.md     – per-strategy page: stats + recent trades  (#strategy)
"""
import os
import sys
from datetime import datetime

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)


def _money(x):
    x = float(x or 0)
    return f"{'+' if x >= 0 else ''}${x:,.2f}"


def export(vault=None):
    import db
    vault = vault or os.path.join(ROOT, "obsidian_vault")
    os.makedirs(os.path.join(vault, "Daily"), exist_ok=True)
    os.makedirs(os.path.join(vault, "Strategies"), exist_ok=True)

    sp = db.star_pnl()
    stats = db.paper_stats()
    rows = db.paper_trades_all(5000)

    # group by date and by source
    by_date, by_src = {}, {}
    for r in rows:
        d = str(r.get("closed_at", ""))[:10]
        if d:
            by_date.setdefault(d, []).append(r)
        by_src.setdefault(r.get("source") or "stock", []).append(r)

    # ---- Strategy pages ----
    for src, trs in by_src.items():
        g = stats.get(src, {})
        net = round(sum((t.get("pnl") or 0) for t in trs), 2)
        lines = [f"---", f"strategy: {src}", f"pnl: {net}", f"trades: {len(trs)}",
                 f"win_rate: {g.get('win_rate', 0)}", f"updated: {datetime.now().isoformat()}", "---",
                 f"# Strategy — {src.upper()}  #strategy", "",
                 f"**Net:** {_money(net)} · **Trades:** {len(trs)} · **Win rate:** {g.get('win_rate',0)}% · "
                 f"**Expectancy:** {g.get('expectancy_r','—')}R", "",
                 "## Recent trades", "", "| Date | Symbol | In | Out | P&L |", "|---|---|---|---|---|"]
        for t in sorted(trs, key=lambda x: str(x.get("closed_at", "")), reverse=True)[:40]:
            sym = str(t.get("symbol", "")).split()[0]
            lines.append(f"| {str(t.get('closed_at',''))[:16].replace('T',' ')} | [[{sym}]] | "
                         f"{t.get('entry')} | {t.get('exit')} | {_money(t.get('pnl'))} |")
        open(os.path.join(vault, "Strategies", f"{src}.md"), "w").write("\n".join(lines))

    # ---- Daily journal notes ----
    for d, trs in by_date.items():
        net = round(sum((t.get("pnl") or 0) for t in trs), 2)
        wins = sum(1 for t in trs if (t.get("pnl") or 0) > 0)
        wr = round(wins / len(trs) * 100, 1) if trs else 0
        srcnet = {}
        for t in trs:
            srcnet[t.get("source") or "stock"] = round(srcnet.get(t.get("source") or "stock", 0) + (t.get("pnl") or 0), 2)
        lines = ["---", f"date: {d}", f"pnl: {net}", f"trades: {len(trs)}", f"win_rate: {wr}", "tags: [daily]", "---",
                 f"# {d}  #daily", "",
                 f"**Net P&L:** {_money(net)} · **Trades:** {len(trs)} · **Win:** {wr}%", "",
                 "**By strategy:** " + " · ".join(f"[[Strategies/{s}|{s}]] {_money(v)}" for s, v in srcnet.items()), "",
                 "## Trades", "", "| Time | Strategy | Symbol | In | Out | P&L |", "|---|---|---|---|---|---|"]
        for t in sorted(trs, key=lambda x: str(x.get("opened_at", ""))):
            sym = str(t.get("symbol", "")).split()[0]
            lines.append(f"| {str(t.get('opened_at',''))[11:16]} | {t.get('source')} | [[{sym}]] | "
                         f"{t.get('entry')} | {t.get('exit')} | {_money(t.get('pnl'))} |")
        open(os.path.join(vault, "Daily", f"{d}.md"), "w").write("\n".join(lines))

    # ---- Visual Dashboard (Obsidian Charts plugin: ```chart blocks) ----
    dates = sorted(by_date.keys())
    daily_pnl = [round(sum((t.get("pnl") or 0) for t in by_date[d]), 2) for d in dates]
    cum, run = [], 0.0
    for v in daily_pnl:
        run = round(run + v, 2); cum.append(run)
    src_names = [s for s, _ in sorted(stats.items(), key=lambda kv: kv[1].get("pnl", 0), reverse=True)]
    src_pnl = [stats[s].get("pnl", 0) for s in src_names]
    src_wr = [stats[s].get("win_rate", 0) for s in src_names]
    daily_colors = ["#2ee6a6" if v >= 0 else "#ff5d6c" for v in daily_pnl]
    src_colors = ["#2ee6a6" if v >= 0 else "#ff5d6c" for v in src_pnl]

    def chart(spec):
        return "```chart\n" + spec.strip() + "\n```\n"

    dash = ["---", f"updated: {datetime.now().isoformat()}", "tags: [dashboard]", "---",
            "# 📊 STAR — Visual Dashboard  #dashboard", "",
            f"**All-time:** {_money(sp['all_pnl'])} · **Today:** {_money(sp['today_pnl'])} · "
            f"**Win rate:** {sp.get('all_win_rate',0)}% · **Trades:** {sp['all_trades']}", "",
            "> [!info] Needs the **Obsidian Charts** community plugin to render these as graphs.", "",
            "## Equity curve (cumulative P&L)", "",
            chart(f"type: line\nlabels: {dates}\nseries:\n  - title: Cumulative $\n    data: {cum}\ntension: 0.3\nfill: true\nwidth: 80%\nbeginAtZero: true"),
            "## Daily P&L", "",
            chart(f"type: bar\nlabels: {dates}\nseries:\n  - title: Daily P&L\n    data: {daily_pnl}\ncolors: {daily_colors}\nwidth: 80%\nbeginAtZero: true"),
            "## P&L by strategy", "",
            chart(f"type: bar\nlabels: {src_names}\nseries:\n  - title: P&L $\n    data: {src_pnl}\ncolors: {src_colors}\nwidth: 70%\nbeginAtZero: true"),
            "## Win rate by strategy (%)", "",
            chart(f"type: bar\nlabels: {src_names}\nseries:\n  - title: Win %\n    data: {src_wr}\nwidth: 70%\nbeginAtZero: true")]
    open(os.path.join(vault, "Dashboard.md"), "w").write("\n".join(dash))

    # ---- Home dashboard ----
    strat_rows = "\n".join(
        f"| [[Strategies/{s}|{s}]] | {g.get('trades',0)} | {g.get('win_rate',0)}% | {_money(g.get('pnl'))} |"
        for s, g in sorted(stats.items(), key=lambda kv: kv[1].get("pnl", 0), reverse=True))
    recent_days = "\n".join(f"- [[Daily/{d}]] — {_money(round(sum((t.get('pnl') or 0) for t in trs),2))}"
                            for d, trs in sorted(by_date.items(), reverse=True)[:10])
    home = ["---", f"updated: {datetime.now().isoformat()}", f"all_time_pnl: {sp['all_pnl']}",
            f"today_pnl: {sp['today_pnl']}", "---",
            "# ⭐ STAR — Trading Vault", "",
            "👉 **[[Dashboard]]** — colorful charts (equity curve, daily P&L, strategy breakdown)", "",
            f"**All-time P&L:** {_money(sp['all_pnl'])} · **Today:** {_money(sp['today_pnl'])} · "
            f"**Win rate:** {sp.get('all_win_rate',0)}% · **Trades:** {sp['all_trades']}", "",
            "## Strategies", "", "| Strategy | Trades | Win% | P&L |", "|---|---|---|---|", strat_rows, "",
            "## Recent days", "", recent_days, "",
            "_Auto-generated by STAR. Dataview-ready frontmatter on every note._"]
    open(os.path.join(vault, "STAR.md"), "w").write("\n".join(home))
    return {"vault": vault, "daily_notes": len(by_date), "strategies": len(by_src),
            "all_pnl": sp["all_pnl"]}


if __name__ == "__main__":
    import json
    print(json.dumps(export(), indent=2, default=str))
