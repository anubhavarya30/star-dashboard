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
- SEC EDGAR 10-K scanning to auto-detect forensic review items
- Wire forensic score + agent consensus into executor preview ("what STAR would trade")
- Google Calendar push after restart

## 🖥️ Deployment plan — Mac mini (server) + laptop (client)
Mac mini = always-on server; laptop = browser + SSH client.
Constraint: IBKR connection is local → TWS/IB Gateway MUST run on the mini.

Runs on the mini:
1. IB Gateway (lighter than TWS), API on 7497, + IBC (IB Controller) to auto
   restart/re-login through IBKR's daily forced logout.
2. run_sync_loop.py (IBKR sync every 30s)
3. terminal_server.py (dashboard :8080)

Keep alive across reboot/crash: macOS launchd plists (one per service).
Access from laptop: Tailscale (recommended — secure, off-LAN, no open ports) →
  http://mac-mini:8080 ; or LAN (bind 0.0.0.0) ; or SSH tunnel.
Manage from laptop: enable Remote Login (SSH) → git pull + restart; Tailscale SSH.

Caveats:
- Dashboard has NO auth — keep it on Tailscale/LAN, never public-internet.
- IB Gateway needs a logged-in GUI desktop session on the mini (not fully headless).

To build when we start: launchd plists, deploy/ scripts (start/stop/status/update),
make terminal_server bind host configurable via env (default localhost), DEPLOY.md.
Decision needed: Tailscale vs LAN access.
