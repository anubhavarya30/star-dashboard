# STAR

Personal algorithmic trading + research terminal.

## Folder structure

```
star-dashboard/
├── (root)            LIVE SYSTEM — the running terminal (self-contained)
│   ├── terminal_server.py     Bloomberg-style terminal backend (port 8080)
│   ├── terminal.html          the dashboard UI (Lightweight Charts, Mag7, movers)
│   ├── ibkr_live_sync.py      pulls real IBKR account/portfolio from TWS (ib_async)
│   ├── run_sync_loop.py       runs the sync every 30s
│   ├── db.py                  SQLite history layer (snapshots + trade ledger)
│   ├── webull_movers.py       Webull public gainers/losers/active
│   ├── live_account.json      single source of truth for current account state
│   └── star_trading.db        SQLite history
│
├── engine/           TRADING BRAIN — foundation for STAR (the CEO). NOT yet wired.
│   ├── star_brain.py              CEO orchestrator (needs deps de-Supabased)
│   ├── multi_agent_orchestrator.py 7-step workflow (logic still stubbed)
│   ├── agents.py                  4 agents: research / earnings / sentiment / protection
│   ├── agent_aggregator.py        vote aggregation        [TODO: remove Supabase]
│   ├── daily_routine_planner.py   daily plan              [TODO: remove Supabase]
│   ├── data_providers.py          data feeds              [TODO: remove Supabase]
│   ├── trading_signals.py         Volume-Weighted RSI strategy  ✓ clean
│   ├── position_manager.py        position & risk sizing        ✓ clean
│   ├── market_data_provider.py    yfinance market data          ✓ clean
│   ├── indicators.py              technical indicators          ✓ clean
│   ├── strategies.py              strategy definitions          ✓ clean
│   ├── ibkr_connector.py / ibkr_live_trader.py  IBKR execution  ✓ clean
│   └── tradingview_connector.py   TradingView CDP bridge        ✓ clean
│
└── _legacy/          ARCHIVE — superseded prototypes (9 dashboards, Supabase setup,
                      duplicate engines, one-off tests). Kept on disk, gitignored.
```

## Run the live terminal

```bash
# 1. real IBKR sync (needs TWS running + logged in on port 7497)
./venv/bin/python3 run_sync_loop.py &
# 2. terminal server
./venv/bin/python3 terminal_server.py &
#    → http://localhost:8080/
```

## STAR vision (engine/ — to build)

STAR is the "CEO" agent. Supporting agents feed it data/signals; STAR combines
them with the trading concepts in `engine/` (Volume-Weighted RSI + risk sizing)
to make decisions and execute via IBKR.

**Current honest state:** the agent scaffolding exists in `engine/` but is NOT
wired to the live system. Gen-1 (`star_brain` + `agent_aggregator` + `agents`)
needs Supabase removed; Gen-2 (`multi_agent_orchestrator`) needs its stubbed
logic replaced with real analysis. The clean, reusable parts are the strategy
libs (`trading_signals`, `position_manager`, `market_data_provider`, `indicators`).

## Data honesty
- Quotes/charts: yfinance, ~15-min delayed.
- IBKR portfolio: live from TWS but **delayed** prices (no market-data subscription).
- Movers: Webull public ranking (no auth).
- Trade history: real fills only — empty until the account actually trades.
