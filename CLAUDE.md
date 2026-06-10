# STAR — Project State & Continuation Notes

> **Read this first when the session restarts. Do NOT pretend to start fresh — continue from here.**
> Last updated: 2026-06-10. User: anubhav.arya789@gmail.com

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
| `star_trading.db` | SQLite; account row updated to REAL values (was fake $100k). |
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

**DONE this session:** `terminal.html` was professionally redesigned via the
ui-ux-pro-max skill — IBM Plex Mono/Sans, OLED-deep dark, amber/green/red
semantics, SVG icons (no emoji), skeleton loaders, focus rings, reduced-motion,
refined Chart.js styling. Data layer unchanged (terminal_server.py endpoints).

If iterating further: only touch UI in terminal.html; keep endpoints intact;
keep data honest (delayed labels, no fabricated entry times).

Pending optional asks (only if user requests): screenshot/visual QA in a
browser; purge Supabase pkg + legacy scripts; push to origin; resolve
paper-vs-live (7497) question.
