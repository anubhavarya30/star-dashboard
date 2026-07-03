# STAR — Project State & Continuation Notes

> **Read this first when the session restarts. Do NOT pretend to start fresh — continue from here.**
> Last updated: 2026-07-02. User: anubhav.arya789@gmail.com

---

## 🗓️ Session log — 2026-07-02 (TradingView MCP wired for real backtesting)

**RESUME HERE. First real work: run the FVG backtest in TradingView, then verdict.**

**WHY:** User wants EVERY algo proven in TradingView's Strategy Tester (deep intraday
history) BEFORE it trades real money — "not in our dashboard, in TradingView, full
proof." Correct discipline. Today STAR lost **-$165.15** (19 trades); FVG desk is the
bleeder (-$207 all-time, 2 wins of 12) and was NEVER backtested before going live.

**WHAT GOT DONE:**
1. **`engine/fvg_strategy.pine`** — 1:1 Pine v5 port of `engine/fvg.py` (bullish-FVG
   support long: gap `high[i-2]<low[i]`, entry on retest holding gap + EMA200 uptrend,
   stop `glo*0.997`, 2R target, stop-before-target priority, entry at signal-bar close).
   Committed locally (push to `main` BLOCKED — branch-protected, needs PR).
2. **TradingView MCP discovered + wired into THIS CLI.** User had `tradingview` MCP
   connected only on the **claude.ai desktop app** (78 tools) — NOT this Claude Code CLI
   (separate surface). Found its config in
   `~/Library/Application Support/Claude/claude_desktop_config.json`:
   local stdio server `node /Users/anubhavarya/tradingview-mcp/src/server.js` (NO URL —
   it drives the live TV browser/app via CDP). Added to CLI user scope:
   `claude mcp add tradingview --scope user -- node /Users/anubhavarya/tradingview-mcp/src/server.js`
   → written to `~/.claude.json`. **Persistent.**
3. **Confirmed the server does the FULL loop** (inspected src): `pine_smart_compile`,
   `ui_open_panel(strategy-tester|pine-editor)`, `data_get_strategy_results`,
   `data_get_trades`, `data_get_equity`, chart_set_symbol/timeframe, tv_health_check.
   No copy-paste needed — Claude can drive TV end-to-end once the tools load.

**⚠️ BLOCKER (do FIRST next session):** the TV MCP was added mid-session, so the tools
were NOT loaded in the session that added them. **On restart they auto-load.** Verify:
ToolSearch `select:tv_health_check` should now resolve. Also **TV desktop app must be
OPEN + logged in** (server drives the live app).

**NEXT SESSION — run the FVG backtest (act, don't ask):**
1. `tv_health_check` → confirm TV reachable.
2. For each of NVDA, AAPL, MSFT, AMD, TSM: `chart_set_symbol` → daily timeframe →
   open pine-editor → paste `engine/fvg_strategy.pine` → `pine_smart_compile` →
   open strategy-tester → `data_get_strategy_results`.
3. **VERDICT RULE (decided upfront, no moving goalposts):** Profit Factor > 1.3 over
   30+ trades → FVG edge real, keep desk live, sync winning params to `engine/fvg.py`.
   Below that → **retire the FVG desk permanently** (stop the -$207 leak).
4. Then repeat the port→prove loop for the other live desks (scalp, stock).

**Today's tape (2026-07-02):** rotation day — Dow +1.1%, S&P flat, Nasdaq -0.8%, VIX
16.15. Tech bled, value bid. STAR by desk all-time: scalp +$21.43, stock -$25.53,
fvg -$207.65 (the problem), gold $0.

---

## 🗓️ Session log — 2026-07-01 (real-time wiring + P&L truth + FVG benched)

**REAL-TIME DATA IS LIVE.** New `engine/realtime_data.py` — unified provider, priority
**Alpaca (free IEX, needs key) → Webull public (no key, ACTIVE now) → yfinance (delayed
fallback)**. Wired into BOTH the scalp engine (confirms/prices entries + exits off the
live price; pre-filters on cheap delayed bars, only fetches RT for candidates to respect
rate limits) AND the dashboard (`terminal_server.quote()` header + mag7 + open-position
P&L now show live price, returns `source`). Alpaca NOT keyed yet on server — drop
key+secret into `data/alpaca_config.json` (gitignored) to auto-promote it to primary.

**P&L NOW RECONCILES TO ONE NUMBER.** Root cause of the "dashboard shows wrong/stale
data" complaints: `/api/paper_trades` `realized_today` was sourced from `risk_manager`
(STOCK desk only) while `/api/star_pnl` + `/api/pnl_calendar` summed all desks from the
`paper_trades` table → three tiles, three numbers. Fixed: `realized_today` now reads
`db.star_pnl()["today_pnl"]`. All P&L surfaces agree. (Dashboard refresh = 20s data +
20s server cache; that was never the bug — the SOURCE was.)

**JEM phantom purged.** A −$132.08 JEM scalp (id 160) from stale pre-fix code (entry
$4.80 < $10 floor, no stop, IBKR rejected → SIM) was distorting P&L. Deleted after
DB backup (`/tmp/star_trading.pre-jem-purge.*.db`). All-time went −$46 → +$85.94.

**CEO narrative fixed (was contradictory + stale).** `star_ceo._narrative()` said
"risk-off" AND "risk appetite is on" together — label came from news regime, rotation
line came independently from yfinance. Worse, `_indices()` pre-open returns YESTERDAY's
daily close-to-close, presented as today's tape. Fixed: tape call anchored to LIVE
overnight futures + regime (one source, can't self-contradict); index moves labelled
"Prior close." Now passes `world` into `_narrative`.

**⚠️ FVG DESK BENCHED (`engine/fvg_desk.py` ENTRIES_ENABLED=False).** Evidence: FVG is
the ONLY losing desk — −$177.75 all-time, 18% win, −$16/trade; it flips STAR from +$131
to −$46. New entries OFF; `manage()` still runs so its open positions (JPM/TSM/AXP) exit
cleanly, no orphans. **Do NOT re-enable on a hunch — pull its backtest first, fix or
retire.** Per-desk all-time: stock +$61.60 (61.5% win, +$4.74/trade = THE edge),
scalp +$69.55 (49% win, +$0.88 thin), gold flat, fvg −$177.75.

**DESK POLICY GOING FORWARD (stop the daily strategy-switching):** stock leads (proven
edge — pending ask: loosen its gate so it trades more than 13×), scalp secondary on RT
feed, FVG benched, gold harmless. Config stays put to build a real sample.

**ruflo installed** dev-scoped in `~/star/ruflo-dev` (NOT in trading repo, NOT on
server) — a Claude Code orchestration harness for BUILDING, not a trading component.

**IBKR:** was blocked at the open by Error 10141 (paper disclaimer); got accepted mid-day
(FVG filled `via ibkr`). Permanent hands-off fix still = IBC (needs creds, not installed).

**FVG-only lockdown incident:** user asked for FVG-only for 2026-07-01; I disabled+booted
scalp/papertrader/activewatch/gold. Watchdog then Telegrammed "activewatch NOT loaded"
every 30min (expected — it was disabled). FVG-only LOST −$132 (5/5 losers). Reverted:
all four desks re-enabled + bootstrapped. Lesson logged: benched winners, ran the loser.

---

## 🖥️ 24/7 SERVER STATE — read FIRST (saved 2026-06-20)
This Mac is now the dedicated 24/7 STAR server. **Repo path is now
`/Users/anubhav.arya/star/star-dashboard`** (note the DOT — different from the old
`/Users/anubhavarya/...` referenced lower in this file). **venv is Python 3.11.3**
(`/usr/local/bin/python3.11`); the old 3.14 venv was rebuilt. Use `./venv/bin/python3`.

**WHAT AUTO-RECOVERS AFTER A CRASH/REBOOT (no human, no Claude needed):**
- macOS **auto-login is ON** (autoLoginUser=anubhav.arya) → Mac logs in itself.
- launchd jobs with RunAtLoad+KeepAlive relaunch on login & restart on crash:
  `com.star.terminal` (dashboard :8080), `com.star.activewatch` (60s engine),
  `com.star.watchdog` (3-min health monitor). Plus scheduled: `com.star.papertrader`
  (5m), `com.star.gold`, `com.star.gexlogger`, `com.star.premarket`, `com.star.openping`,
  `com.star.dailyrestart` (06:07 local — kicks terminal+activewatch so they reconnect
  to IBKR cleanly after TWS's daily restart, before the open).
- Power: `SleepDisabled=1` (clamshell/lid-closed safe). Keep plugged into AC.

**THE ONE GAP — IBKR does NOT auto-relaunch after reboot:** no IBC configured
(`~/ibc/config.ini` absent, `com.star.ibgateway` not installed). After a reboot TWS/
Gateway must be manually relaunched + logged into PAPER (DU) on 7497. The watchdog
catches this and Telegrams `⚠️ IBKR DISCONNECTED`, re-nagging every 30 min. To close
the gap: run `scripts/setup_ibc.sh` and put paper creds in `~/ibc/config.ini` (secrets,
never committed) — user must supply credentials.

**CLAUDE IS NOT A DAEMON:** Claude does NOT auto-restart itself after a crash — the
system is built to recover via launchd without Claude. The in-chat 5-min logs/P&L
display is a session-only cron loop that dies when the Claude session ends.

**REMOTE ACCESS:** Tailscale installed + signed in (anubhav.arya789@). This Mac's
Tailscale IP = **100.97.21.122** → dashboard at `http://100.97.21.122:8080` from any
network (private to your devices). `terminal_server.py` now binds `0.0.0.0` (was
`127.0.0.1`) so LAN (`192.168.1.235:8080`) + Tailscale both work.

**MONITORING/HEALING:** `engine/watchdog.py` checks dashboard, engine, IBKR (via a
FRESH subprocess with dedicated client-id 77 — true broker state, no collision with
engine's 88/89), and halt state; Telegrams on failure AND recovery. If terminal_server's
IBKR view wedges while the broker is reachable, the watchdog auto-restarts terminal
(`_heal_terminal`) and Telegrams. Telegram creds in `data/telegram_config.json`
(chat_id 7435641961). User directive: **act, don't ask; route real decisions to Telegram.**

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
