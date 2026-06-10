# STAR — Status & TODO

_Last updated: 2026-06-10_

## ✅ Done & working (real, verified)

**Live terminal (http://localhost:8080)**
- Bloomberg-style UI (ui-ux-pro-max: IBM Plex, OLED dark, SVG icons)
- Hamburger menu, 4 views: Research · STAR Agents · P&L Calendar · Forensic Scanner (deep-linkable #agents/#pnl/#forensic)
- Candlestick charts (TradingView Lightweight Charts), timeframes 5MIN/1H/4H/1M/6M/1Y/5Y
- Mag 7 click-to-load rail; Webull movers (gainers/losers/active, public data)
- Market strip, quotes, fundamentals, news (yfinance ~15-min delayed)
- Staleness detection (live dot turns red if a feed stalls)

**Data & history**
- Real IBKR account via ib_async (fixed ib_insync × Python 3.14). Net liq ~$485, AMZN position.
- SQLite history: account/position snapshots + real trade ledger (executions)
- P&L Calendar with real data (today's unrealized; aggregates multiple positions)

**STAR brain (engine/)**
- De-Supabased agents: 5 agents (Technical/Trend/Momentum/Risk/News) + STAR consensus, real signals
- Forensic scanner: 0-100 risk score + cited red flags (insider selling, accruals, financial flags, ISS governance)
- IBKR executor with hard safety caps, preview-only by default (gated off)

**Hygiene** — folder restructure (root/engine/_legacy), README, CLAUDE.md, pushed to GitHub, runtime artifacts untracked.

## ⚠️ Remaining / missed / deferred

1. **Google Calendar phone sync** — connector authorized, but session loaded before that. Needs Claude Code restart, then push P&L event + set daily auto-sync. (Dashboard P&L calendar already works.)
2. **Live trading OFF** — executor built & safe but gated. Nothing trades. $4.54 buying power; agents all HOLD.
3. **Webull trading** — only data works; order execution via APP_KEY/SECRET unproven (official OpenAPI not installed). Not wired.
4. **Forensic review-only items** — Auditor warnings / Related-party / Notes-to-accounts need SEC EDGAR 10-K text parsing (currently linked for manual review). Promoter pledges = N/A (US).
5. **Agents → executor not connected** — STAR decides but doesn't act; forensic score not fed into agent decisions yet.
6. **multi_agent_orchestrator.py** still stubbed (superseded by star_agents.py; not deleted).
7. **Real-time data** — all delayed (no market-data subscription). Deferred until real money.
8. **$1000-from-$100 goal** — not achievable honestly; not encoded into the system.
9. **No automated tests; nothing on a schedule** — agents/executor run on-demand.
10. **Deployment** — see below; not yet set up on the Mac mini.

## 🚀 Next-up candidates
- Deploy to Mac mini (launchd services + remote access) — see DEPLOY.md (to be written)
- SEC EDGAR 10-K scanning to auto-detect forensic review items
- Wire forensic score + agent consensus into executor preview ("what STAR would trade")
- Google Calendar push after restart
