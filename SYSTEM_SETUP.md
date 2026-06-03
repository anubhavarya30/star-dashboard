# Star Trading System — Multi-Agent Setup Guide

## Architecture Overview

```
Agent 1 (Market Research)  ─┐
Agent 2 (IPO/Earnings)     ─┤
Agent 3 (Social Sentiment) ─┼─→ Star (CEO) ─→ User (Approval)
Agent 4 (Trade Protection) ─┘
                              ↓
                        Dashboard (Real-time)
```

## Step 1: Create Supabase Tables

1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Click **SQL Editor** → **New Query**
4. Run the SQL from `setup_schema.py` output
5. This creates all tables needed for agents to communicate

**Tables created:**
- `agent_states` — Status of each agent
- `agent_reports` — Detailed findings from agents
- `agent_signals` — Buy/Sell/Hold signals
- `star_decision` — Star's aggregated decisions (awaiting approval)
- `watchlist` — Dynamic symbols recommended by agents
- `positions` — Open trades being monitored
- `trades` — Completed trades
- `gold_monitor` — 24/7 gold price monitoring
- `ohlc` — Candlestick data for charts
- `agent_logs` — Audit trail

## Step 2: Run Agents

```bash
cd ~/star-dashboard
source venv/bin/activate
python3 run_agents.py
```

This will:
1. 🤖 **Agent 1** — Analyze market conditions, submit signals
2. 📅 **Agent 2** — Check IPO/earnings calendar, flag events
3. 💬 **Agent 3** — Monitor Reddit/Discord for sentiment, find distress signals
4. 📊 **Agent 4** — Monitor open positions, protect against losses
5. ⭐ **Star** — Aggregate all signals, make final decisions
6. 📋 Generate pending approvals for you

## Step 3: Approve Decisions via Dashboard

```bash
# Terminal 1: Keep this running
streamlit run dashboard_multi_agent.py

# Terminal 2 (or browser)
# Open http://localhost:8501
```

**Dashboard Pages:**
1. **🎯 Star's Decisions** ← YOU approve/reject here
2. **📊 Agent Reports** — See what each agent found
3. **🤖 Agent Status** — Check agent health
4. **💼 Positions & Trades** — View open/completed trades
5. **🟡 Gold Monitor** — 24/7 gold monitoring (independent)
6. **📈 Performance** — Win rate, P&L, strategy stats

## Step 4: Gold Monitor (Optional 24/7 Agent)

Gold runs independently, 24/5. To enable:

```bash
python3 gold_monitor.py &
```

This publishes gold signals to `gold_monitor` table, separate from daily stock decisions.

## Workflow Summary

```
1. Run agents:              python3 run_agents.py
2. Agents submit signals    → Supabase (agent_signals)
3. Star aggregates:         All signals → vote & decide
4. Star creates decisions:  → Supabase (star_decision)
5. Dashboard shows:         Pending approvals for YOU
6. You approve/reject:      ✅ YES or ❌ NO
7. Approved → Execute:      (future: auto-trade or notify)
```

## Key Features

✅ **Fully dynamic** — No hardcoded watchlists
✅ **Real-time** — Agents publish instantly, dashboard refreshes
✅ **Audit trail** — All agent actions logged
✅ **Approval workflow** — You have final say
✅ **Gold 24/7** — Independent of market hours
✅ **Multi-agent voting** — Consensus reduces false signals

## Next Steps

1. Populate `ohlc` table with real price data (optional — for charts)
2. Integrate real data sources:
   - Alpha Vantage / Finnhub for market data
   - SEC API for earnings calendar
   - PRAW for Reddit, Discord API for social sentiment
3. Replace TODO comments in `agents.py` with real logic
4. Set up scheduling (run agents daily at 8 AM ET, etc.)

## Troubleshooting

**"No tables found"**
→ Run the SQL from setup_schema.py in Supabase SQL Editor

**"Supabase not configured"**
→ Check .env has SUPABASE_URL and SUPABASE_KEY

**"No pending decisions"**
→ Run `python3 run_agents.py` to generate fresh decisions

**"Dashboard shows 'Waiting for gold_monitor'"**
→ Run `python3 gold_monitor.py` separately (optional)

---

**Questions?** All agent logic is in `agents.py` — modify to fit your needs! 🚀
