# STAR — Project State & Continuation Notes

> **Read this first when the session restarts. Do NOT pretend to start fresh — continue from here.**
> Last updated: 2026-06-12. User: anubhav.arya789@gmail.com

---

## 🔁 RESUME AFTER RESTART — read FIRST (saved 2026-06-17, ~1pm CDT)
User restarted laptop for a software update. Pick up EXACTLY here. Don't re-derive.

**WHERE WE ARE:** Full autonomous paper-trading desk is LIVE on **real IBKR paper**
(account **DUQ923304** on port 7497 — DU=paper, safe). Today's results: realized
**+$12.30** (QURE scaled half at +1R), open: **QURE 5sh @ $44.78 (stop=breakeven,
runner risk-free)**, **HOOD 4sh @ $102.80 (stop $95.47)**. Positions live in
`data/risk_state.json`.

**AFTER REBOOT — do these (act, don't ask):**
1. **Relaunch terminal_server** (nohup dies on reboot):
   `nohup ./venv/bin/python3 terminal_server.py >/tmp/star_terminal.log 2>&1 &` → http://localhost:8080/
2. **TWS must be relaunched + logged into the PAPER (DU) account** on 7497, API
   enabled — or the desk can't place IBKR paper trades. Verify: `/api/ibkr_broker`
   should read `type:paper, can_auto_trade:true`. (Live account U25701222 is BLOCKED
   by the safety gate — never auto-trade it.)
3. **launchd jobs auto-resume on login** (no action): `com.star.activewatch` (60s
   always-on engine — manages trades breakeven/trail/scale, enters on 9-vote score),
   `com.star.premarket` (7:45am brief+gap scan), `com.star.openping` (8:45am phone
   ping), `com.star.gold` (24/7 gold tester), `com.star.gexlogger` (3:15pm). Verify:
   `launchctl list | grep com.star`.

**LOCAL-ONLY files (survive reboot, NOT in git — don't lose):**
`data/telegram_config.json` (Telegram bot creds, reused from ~/gold-trading-bot),
`data/risk_state.json` (open positions), `.claude/settings.local.json` (hooks+perms).

**THE BRAIN (current):** desk enters via `engine/star_score.py` = gold-bot **9-vote
tech score (≥5, or ≥7 pre-holiday) + 2.5:1 ATR risk** (ported from
~/gold-trading-bot/morning_screener.py). Manages every 60s via `engine/active_watch.py`:
breakeven at +1R, scale half at +1R, trail 0.5R above +2R. Market-calendar aware
(`engine/market_calendar.py` — no trading on holidays e.g. Fri Jun 19 Juneteenth;
stricter pre-holiday). Telegram alerts on entry/scale/exit (`engine/telegram_alert.py`).
Risk gate `engine/risk_manager.py` (15%/trade, $150 daily max). Dashboard Paper tab
shows live P&L + market-status badge.

**Everything is committed + pushed to origin/main.** Autosave Stop hook keeps it that way.

---

## ⚙️ WORKING STYLE (user directive, 2026-06-17)
**ACT, don't ask.** Do NOT end turns with "want me to do X?" permission questions
and wait. The user wants decisive execution: build → wire → test → commit → push,
then report what was done. Only pause for genuine forks: (a) anything risking REAL
money / the live IBKR account (hard safety line), (b) a true either/or preference
that changes direction. Otherwise pick the sensible path and ship it.


## 🗓️ Session log — 2026-06-12 (signal + backtest work)

Laptop crashed overnight; resumed from this file. Recovered last night's task from
the Claude session JSONL (`~/.claude/projects/-Users-anubhavarya-star-star-dashboard/`):
the ask was **"build the backtest engine"** + **"add a backtest tab to the hamburger menu."**

What got done today (all committed, then pushed to origin/main):
- **`engine/backtest.py`** — no-look-ahead backtest engine (entries fill next-bar
  open, intrabar stop/target, commission+slippage, risk-based sizing; reports win
  rate, profit factor, expectancy, max DD, Sharpe, equity curve + trade log).
- **`engine/indicators.py`** — fixed a **frozen RSI** bug (it was seeded from the
  OLDEST `period` bars, so it never reflected recent price). Now Wilder/EWM.
- **Backtest tab** in `terminal.html` + **`/api/backtest?sym=&period=`** in
  `terminal_server.py` (EDGE/MARGINAL/NO-EDGE verdict, metrics grid, trade log).
- **Runner Scanner tickers are now clickable** → load the internal detail view;
  **hover shows Finviz/StockAnalysis**; a SOURCE row links Yahoo/Finviz/
  StockAnalysis/SEC per name (research → source provenance, for auditable trades).
- **`engine/trading_signals.py`** — **CRITICAL FIX.** The VW-RSI BUY rule required
  `RSI<30 AND price>=EMA50` simultaneously → impossible on daily data (verified: 0
  occurrences in 5y on NVDA), so the signal **never traded**. Redefined as
  **pullback-in-uptrend**: RSI in 35–50 band, price >= EMA50, volume >= 1.3x avg.
  Now generates trades — but sample is tiny (2–8 trades/5y/name) and shows **no
  proven edge yet**. Do NOT trade real money on it; it needs a real sample.
- **`engine/star_vwrsi_strategy.pine`** — 1:1 Pine Script port for the user's
  **TradingView premium** Strategy Tester (intraday + deep history). TradingView
  can't be API'd for backtesting; loop is: user tunes in TV → tells Claude winning
  settings → Claude syncs both `trading_signals.py` and the `.pine`.

**GEX Radar (added 2026-06-14):** `engine/gex.py` computes dealer gamma from REAL
yfinance options OI (Black-Scholes gamma, SqueezeMetrics convention — assumption
stated honestly). Endpoints `/api/gex` + `/api/gex_agent`. New "GEX Radar"
hamburger tab shows regime (pos/neg gamma), gamma flip, call/put walls, per-strike
gamma bars, and the falling-market edge (negative gamma below flip = downside
accelerates). A GEX agent banner sits at the top of the STAR Agents view. NOTE:
GEX is an index/options game (SPY/QQQ/IWM) — separate from the daily-equity VW-RSI
signal; needs real-time/options data to trade for real (we have neither yet).

**GEX forward-test (2026-06-14):** can't backtest GEX historically (free data gone,
yfinance has no options history). Instead `engine/gex_logger.py` logs real daily
GEX to `data/gex_history.csv`; `scripts/log_gex.sh` runs it for SPY/QQQ/IWM via a
**launchd agent weekdays 3:15pm** (`com.star.gexlogger`, plist in scripts/ +
~/Library/LaunchAgents/; survives a closed laptop — runs missed jobs on wake;
logs to /tmp/star_gex.log). Manage: `launchctl list | grep gexlogger`,
`launchctl kickstart -k gui/$(id -u)/com.star.gexlogger` to run now. (Cron removed.)
`gex_logger.py test SPY` reports the negative-gamma→next-day-downside edge once 20+
days are logged. User has Webull options ($500) as the eventual execution venue.

**RUNNERS SME track (2026-06-15):** user chose low-float momentum runners as the
niche to master. Built:
- `RUNNERS_PLAYBOOK.md` — discipline core (2 setups, hard risk rules: ≤$25/trade,
  $50 daily max, no sub-$1/nano-caps, never chase; position-size math; dilution).
- `engine/runner_grader.py` + `/api/runner_grade` — grades live movers by lifecycle
  (EARLY/PULLBACK-WATCH vs DO-NOT-CHASE vs AVOID-LANDMINE). Extension driven by %
  already run (a name up 200% is never "early").
- `engine/watch_runner.py` — live BASKET monitor (5 names), flags Setup B (VWAP
  reclaim) on any; writes /tmp/star_runner_status.json. Run: `nohup ./venv/bin/
  python3 engine/watch_runner.py 120 &` (auto-picks watchlist) or pass symbols.
- **Premarket research routine**: `engine/premarket_research.py` +
  `scripts/premarket.sh` via **launchd `com.star.premarket` weekdays 7:45am** —
  grades the morning gappers, writes `data/premarket/<date>.md` + `latest.json`
  (served at `/api/premarket`). The morning watchlist is ready before the open.
- **Risk Manager attached to the brain** (`engine/risk_manager.py`): hard pre-trade
  gate (sizes by 5% risk/trade=$25, caps cost at 60% equity, enforces daily max
  loss $50 and total open-risk budget across trades, min 1.5 R:R) + post-trade
  check (R-multiple, trail/scale/exit actions) + daily P&L state in
  data/risk_state.json (resets each day; halts trading when daily limit hit).
  Endpoints `/api/risk_check?sym=&entry=&stop=&target=` and `/api/risk_status`.
  Wired into watch_runner triggers so every signal comes pre-sized + approved.
  Philosophy: take risk, but every position sized so a loss is survivable —
  rules are numbers, not caveats.
  **User-set 2026-06-15:** risk_pct raised 5%->15% ($75/trade), daily_pct 10%->30%
  ($150/day) so a 15% trade fits, max_pos_pct 90%, min_rr 1.2 (scalps).
- **Daily Trade Picker** (`engine/daily_trade.py`, `/api/daily_trade`): user wants a
  trade EVERY day. Picks the best graded setup, sizes it via the risk gate, returns
  one trade card with a quality grade (A=clean setup, C=forced/low-quality on a flat
  day — labeled honestly, never refuses). Caveat baked in: delayed data + no broker
  API, so it's a PLAN to execute on Webull, not an auto-scalp.
- KEY LESSON surfaced live: forensic scanner returns false "LOW RISK" on micro-caps
  (no yfinance fundamentals) — real risk is in SEC filings. Most days the right
  call is NO TRADE (protect the ~$985: $485 IBKR + $500 Webull options).

**VW-RSI status:** with 2R target + loosened filters, basket PF = 1.05 (marginal,
name-dependent). Not a robust edge. Next: regime/name filtering or replace signal.

**Open next steps:** (1) user tunes the Pine strategy on intraday/runner names to
find a real edge; (2) keep `.pine` and `trading_signals.py` in sync; (3) optional
TradingView alert → webhook → IBKR bridge for live execution (NOT built yet);
(4) loosen filters to get a 30+ trade sample before trusting any metric.

**Auto-save is ON.** A Stop hook in `.claude/settings.local.json` auto-commits any
uncommitted changes when Claude finishes a turn — the user should NOT have to ask
to "save" anymore. (See `scripts/autosave.sh`.)

---

## ⚠️ Hard-won truths (do not repeat past mistakes)

1. **Be honest about data. No fake/seeded values.** Earlier in this project the
   dashboard showed a **fake $100,000 balance** for days because the IBKR
   connection silently failed and the code fell back to seeded data. The user
   was (rightly) angry. Always show real data or an honest "not connected" error.

2. **Root cause of the fake data:** `ib_insync 0.9.86` is **incompatible with
   Python 3.14** (error: `"Timeout should be used inside a task"`). It never
   connected to TWS. **Fix: use `ib_async`** (maintained successor, same API,
   `from ib_async import IB`). This works.

3. **Don't over-claim with emoji checklists.** The user explicitly disliked the
   earlier hype-y "✅ ALL DONE" style. Verify with real output, state limits plainly.

---

## Environment

- Working dir: `/Users/anubhavarya/star/star-dashboard`
- **Always use the venv python:** `./venv/bin/python3` (Python 3.14.5)
- Key installed pkgs: `ib_async`, `nest_asyncio`, `yfinance 1.4.1`, `pandas`, `requests`, `uvicorn`
- `ib_insync` is installed but **BROKEN on 3.14 — do not use it.**
- Not a git repo? It IS a git repo. Branch `main`, ahead of origin (local commits only, nothing pushed).

## Real IBKR account facts (verified live from TWS)

- **TWS listens on port 7497 only** (live port 7496 is NOT open). User said: **use 7497**.
- Account **U25701222**, type INDIVIDUAL.
- **Net Liquidation ≈ $485**, **Cash/Buying Power = $4.54**.
- One position: **AMZN 2 @ $247.73** (delayed price ~$240, unrealized P&L ≈ −$15).
- **No real-time market-data subscription** (Error 10089) → we use IBKR **delayed** data (`reqMarketDataType(3)`, free).
- **Entry time for the AMZN position is UNAVAILABLE** from the API (bought in a past session; IBKR doesn't expose entry timestamps for pre-existing positions). Only trades STAR places going forward can have recorded entry times. Do not fabricate it.
- OPEN QUESTION the user is checking: whether 7497 is their **paper** account
  (7497 is IBKR's paper default; $485/$4.54 looks like play money) vs a live
  account configured on 7497. Account # U25701222 is live-format. Unresolved.

## NOT using Supabase
Active core is Supabase-free. ~24 legacy scripts still reference it and the
`supabase` pkg is still in the venv, but nothing running uses it. User asked to
confirm this (done). Optional cleanup pending (uninstall pkg + archive legacy scripts).

---

## CLEAN CORE (what actually runs — built this session)

| File | Role |
|------|------|
| `ibkr_live_sync.py` | Connects TWS (7497, ib_async), pulls real account summary + portfolio (IBKR P&L via delayed prices), writes **`live_account.json`** (single source of truth). Honest error on failure. |
| `run_sync_loop.py` | Runs the sync every 30s forever. |
| `live_account.json` | The real account snapshot. **Only file the dashboards should read for account data.** |
| `dashboard.html` | Simple clean single-page account monitor (port 9000). |
| **`terminal_server.py`** | **Bloomberg-style terminal backend (port 8080).** stdlib http.server + yfinance. Endpoints: `/api/quote`, `/api/history`, `/api/profile`, `/api/news`, `/api/market`, `/api/portfolio`. 20s TTL cache. |
| **`terminal.html`** | **Bloomberg-style terminal UI** — amber/black monospace, ticker command bar, live index strip, quote header, Chart.js price chart with 1M/6M/1Y/5Y, key-stats grid, company profile, news, and a real IBKR portfolio panel. |
| **`db.py`** | **SQLite history layer.** Tables: `account_snapshots`, `position_snapshots`, `executions` (real fills, dedup by exec_id). API: record_snapshot (throttled 5min), record_executions, account_history(), trades(), position_history(). |
| `star_trading.db` | SQLite; now holds the history tables above + legacy `accounts` row. |
| **`webull_movers.py`** | Top gainers/losers/most-active via Webull's PUBLIC ranking endpoint (no login; sidesteps the old OAuth failure). changeRatio is a fraction → ×100. |
| `google_calendar_mcp.py` | P&L→Google Calendar sync (only real closed trades; currently 0). Not central. |

Archived/contradicting fake files moved to `_archive_fake/` (gitignored):
`current_trades.json`, `ibkr_positions.json`, `calendar_sync.json`,
`executed_trades.json`, `execution_log.json`, `sync_real_data.py`,
`schedule_real_data_sync.py`.

There are ~55 OLD scripts (dashboard_*.py, agents*.py, star_brain*.py, etc.) =
legacy sprawl, not part of the clean core. Leave unless asked to clean.

## How to run

```bash
cd /Users/anubhavarya/star/star-dashboard
# real IBKR sync loop (needs TWS running + logged in on 7497):
nohup ./venv/bin/python3 run_sync_loop.py >/tmp/star_sync.log 2>&1 &
# Bloomberg-style terminal:
nohup ./venv/bin/python3 terminal_server.py >/tmp/star_terminal.log 2>&1 &
#   → open http://localhost:8080/
# simple account monitor (optional): http://localhost:9000/dashboard.html
```

All endpoints verified returning REAL data (NVDA, AAPL, S&P/Nasdaq/Dow/VIX/BTC/10Y,
profile, 8 news headlines, IBKR portfolio).

---

## ▶️ NEXT STEP (resume here)

**FOLDER RESTRUCTURED (see README.md):**
- root = LIVE terminal (terminal_server.py, terminal.html, ibkr_live_sync.py,
  run_sync_loop.py, db.py, webull_movers.py, live_account.json, star_trading.db).
  Self-contained; imports nothing from engine/. Still running on :8080.
- engine/ = STAR trading-brain FOUNDATION (not wired): star_brain (CEO),
  multi_agent_orchestrator, agents, trading_signals, position_manager,
  market_data_provider, indicators, strategies, ibkr_*, tradingview_connector,
  + agent_aggregator/daily_routine_planner/data_providers (still Supabase — fix first).
- _legacy/ = archived prototypes (gitignored, on disk).
- .claude/skills/ (ui-ux-pro-max plugin) gitignored.

**The STAR vision (next real work):** STAR = CEO agent. Supporting agents in
engine/ feed it data/signals; STAR combines them with the trading concepts
(VW-RSI in trading_signals.py + risk in position_manager.py) to trade via IBKR.
Honest state: agents are half-stubbed / half-Supabase-dead and NOT wired to the
live system. To build it: (1) de-Supabase agent_aggregator/daily_routine_planner/
data_providers, (2) replace multi_agent_orchestrator stub logic with real analysis,
(3) wire STAR output → ibkr_live_trader, (4) record fills via db.executions.

Run cmds now: `./venv/bin/python3 run_sync_loop.py &` and
`./venv/bin/python3 terminal_server.py &` → http://localhost:8080/

Pending optional: visual browser QA (done once); push to origin; real-time data
subscription (deferred by user until real money); resolve paper-vs-live (7497).
