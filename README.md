# ⭐ STAR — Autonomous Paper-Trading Terminal

STAR is a self-hosted, 24/7 **paper-trading** research desk: it scans the market,
scores candidates, places **simulated trades through Interactive Brokers' paper
account**, manages them with hard risk rules, and reports to a live dashboard +
Telegram — all running unattended on a dedicated machine.

> ⚠️ **Disclaimer.** Experimental, educational project for **paper trading only**.
> **Not financial advice**, **no proven live edge**, and a hardwired safety gate
> **refuses to trade any non-paper (live) account**. Nothing here is a
> recommendation to trade real money.

---

## What it does
- **Scans** a liquid universe + market movers, premarket gaps, and news catalysts.
- **Scores** each name with a 9-vote trend/momentum framework.
- **Trades** the best setups on **IBKR paper** (gated to `DU…` accounts only).
- **Manages** every position every 60s: breakeven, partial scale-out, trailing stop.
- **Controls risk**: fixed % per trade, daily max-loss circuit breaker, holiday-aware.
- **Reports**: web dashboard, Telegram alerts (entry/exit/EOD P&L), SQLite history.
- **Self-heals**: launchd + a watchdog keep it running across crashes/reboots.

## The live strategy — 9-vote swing
- **Entry** (≥5 of 9 votes): above 200-EMA, EMA stack (8>21>50), EMA8>21, MACD+,
  RSI 50–72, ADX>22, 20-day momentum, volume surge, tight pullback to EMA21.
- **Risk**: stop = entry − 1.5×ATR · target = entry + 3.75×ATR (**2.5:1**).
- **Management**: scale half at +1R, stop→breakeven at +1R, trail above +2R.
- **Hold**: swing (multi-day, to stop/target).
- **Backtest**: +0.175R/trade over ~2,385 trades (daily-bar, pre-cost) — *real but
  unproven live*; the paper desk validates it forward. (EOD-flattening the same
  signal was only +0.012R — holding to target is where the edge lives.)

## Architecture
| Layer | Files |
|---|---|
| Dashboard (HTTP + JSON API, :8080) | `terminal_server.py`, `terminal.html` |
| Trading engine (always-on, 60s loop) | `engine/active_watch.py`, `engine/paper_session.py` |
| Signal / scoring | `engine/star_score.py` (9-vote), `engine/trading_signals.py` (VW-RSI) |
| Risk + ledger | `engine/risk_manager.py`, SQLite `star_trading.db` |
| Broker (paper-gated) | `engine/ibkr_broker.py` (ib_async, port 7497) |
| Backtests | `engine/backtest_9vote.py`, `engine/backtest.py` |
| Research tools | scout, premarket brief, gap+catalyst scanner, runner scanner/grader, GEX radar, breakdown/puts, forensic, gold tester |
| Alerts | `engine/telegram_alert.py` |
| Ops / 24-7 | `scripts/*.sh`, `scripts/com.star.*.plist` (launchd), `engine/watchdog.py` |

## Run it (dev)
```bash
python3 -m venv venv
./venv/bin/python3 -m pip install -r requirements.txt
./venv/bin/python3 terminal_server.py     # dashboard → http://localhost:8080
```
24/7 server deploy, remote access (Tailscale), and IBKR auto-login (IB Gateway +
IBC) live in `scripts/server_setup.sh`, `scripts/stay_awake.sh`, `scripts/setup_ibc.sh`.

## Data & honesty
Real data only (yfinance ~15-min delayed; IBKR paper). **No fabricated/seeded
values** — if a source is down the UI says so. Per-machine live state
(`data/*state*.json`, `data/*_results.csv`, `data/telegram_config.json`, broker
creds) is **gitignored** and never committed.

## Contributing
**Direct pushes to `main` are disabled — open a Pull Request.** All changes go
through PR review before merge.

## License
Personal/educational. No warranty.
