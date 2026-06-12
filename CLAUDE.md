# STAR — Project State & Continuation Notes

> **Read this first when the session restarts. Do NOT pretend to start fresh — continue from here.**
> Last updated: 2026-06-12. User: anubhav.arya789@gmail.com

---

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
