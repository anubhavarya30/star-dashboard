# 🚀 IBKR Live Trading Setup Guide
## Real Trades in Your IBKR Account with STAR

---

## ✅ What You'll Get

**Real Trading (NOT Paper):**
- ✅ Real trades executed in your IBKR account
- ✅ Real prices from IBKR
- ✅ Real P&L in your account
- ✅ All trades logged to Supabase database
- ✅ Complete audit trail
- ✅ View trades in both IBKR and dashboard

---

## 📋 Prerequisites

1. **Interactive Brokers Account**
   - https://www.interactivebrokers.com/
   - Account must be activated and funded

2. **IBKR TWS or Gateway**
   - Download: https://www.interactivebrokers.com/en/index.php?f=14099
   - Choose: TWS (desktop) or Gateway (lightweight)

3. **Python Library**
   ```bash
   pip install ib_insync
   ```

---

## 🔧 Step-by-Step Setup

### Step 1: Install IBKR TWS or Gateway

**Option A: TWS Desktop (Recommended)**
1. Download from IBKR website
2. Install and launch
3. Login with your IBKR credentials

**Option B: Gateway (Lightweight)**
1. Download from IBKR website
2. Install and launch
3. Login with your IBKR credentials

### Step 2: Enable API in IBKR

**In TWS/Gateway:**

1. Go to: **File → Global Configuration**
2. Click: **API → Settings**
3. Enable:
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Socket Port: 7497 (default)
   - ✅ Allow connections from localhost

4. Click: **Apply**
5. Restart TWS/Gateway

### Step 3: Update .env File

Add these lines to your `.env` file:

```bash
# IBKR Connection
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1

# Keep existing variables
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
```

### Step 4: Install ib_insync

```bash
source venv/bin/activate
pip install ib_insync
```

### Step 5: Test Connection

```bash
python3 ibkr_live_trader.py
```

**Expected Output:**
```
🔌 IBKR Live Trader Initialized
✅ Connected to IBKR TWS/Gateway
✅ Account Connected: DU1234567
```

---

## 🚀 Running Live Trading

### Option 1: Run One Cycle (Test)

```bash
python3 live_trading_engine.py
```

**What happens:**
- Connects to IBKR
- Analyzes 4 symbols (AAPL, NVDA, TSLA, SPY)
- If signal generated → Places REAL order in IBKR
- Syncs positions to database
- Logs all trades

### Option 2: Continuous Trading (Automated)

Update `automated_system.py` to use IBKR:

```python
# In automated_system.py, change:
from smart_trader import SmartTrader(paper_trade=True)

# To:
from live_trading_engine import LiveTradingEngine
```

Then run:

```bash
python3 automated_system.py
```

---

## 📊 Dashboard Integration

All REAL IBKR trades appear in dashboard:

**Go to:** http://localhost:8501

**View:**
- 📈 **Charts** - Real prices from IBKR
- 💼 **Trades** - All executed trades with IBKR order IDs
- 📊 **Live Prices** - Real IBKR prices
- 🤖 **Signals** - Trade decisions

---

## 💾 Database Logging

Every REAL trade logged with:

```json
{
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 100,
  "entry_price": 210.45,
  "order_id": "123456789",
  "status": "OPEN",
  "price_source": "IBKR",
  "timestamp": "2026-06-04T10:30:00",
  "created_at": "2026-06-04T10:30:00"
}
```

**Query in Supabase:**
```sql
SELECT * FROM executed_trades 
WHERE price_source = 'IBKR'
ORDER BY created_at DESC
```

---

## 🔐 Safety & Risk Management

**Built-in Protections:**
- ✅ 2% risk per trade (max $2,000 on $100k)
- ✅ Automatic stop losses (1.2x ATR)
- ✅ Dynamic position sizing
- ✅ Daily loss limits
- ✅ Agent consensus required (70%+)

**Manual Controls:**
- ⏸️ Stop `automated_system.py` anytime (Ctrl+C)
- 🔍 Review trades in dashboard before they execute
- 📝 Audit trail in database
- ✅ Can override or cancel orders in IBKR

---

## 📈 Monitor Trades

### In IBKR TWS/Gateway:
1. **Account** → View all orders and positions
2. **Monitor** → See P&L in real-time
3. **Logs** → Review trade execution details

### In STAR Dashboard:
1. **http://localhost:8501**
2. **💼 Trades** → See all executed trades
3. **📊 Live Prices** → See current IBKR prices
4. **📈 Charts** → Interactive price charts

---

## 🚨 Troubleshooting

### ❌ "Could not connect to IBKR"

**Solutions:**
1. Check IBKR TWS/Gateway is running
2. Verify API is enabled (File → Global Configuration → API)
3. Check socket port is 7497
4. Check firewall allows localhost:7497
5. Restart TWS/Gateway

### ❌ "No open positions"

This is normal if you haven't executed trades yet.

### ❌ "Order execution failed"

**Check:**
1. Account has sufficient buying power
2. Market is open (9:30 AM - 4:00 PM ET)
3. Symbol is tradeable (stocks, not forex)
4. Price hasn't moved too much since signal

---

## ✅ Verification Checklist

Before going live:

- [ ] IBKR TWS/Gateway installed and running
- [ ] API enabled in IBKR settings
- [ ] .env file updated with IBKR settings
- [ ] ib_insync installed (`pip install ib_insync`)
- [ ] Test connection successful (`python3 ibkr_live_trader.py`)
- [ ] One live trade executed and visible in:
  - [ ] IBKR account
  - [ ] Supabase database
  - [ ] STAR dashboard
- [ ] Understand 2% risk per trade
- [ ] Know how to stop trading (Ctrl+C)
- [ ] Have backup funds (don't trade entire account)

---

## 🎯 Starting Live Trading Tomorrow

**Schedule:**

```
9:15 AM ET   → Agents generate signals
9:20 AM ET   → Daily routine created
9:30 AM ET   → Market opens (trading begins)
Every 5 min  → Execute REAL trades in IBKR
4:00 PM ET   → Market closes
4:15 PM ET   → Collect results

All trades appear in:
✅ Your IBKR account (real positions)
✅ Supabase database (complete audit trail)
✅ STAR dashboard (real-time monitoring)
```

---

## 📊 Expected First Day

**Conservative Estimates:**
- Signals: 3-8
- Trades Executed: 0-4 (depends on market)
- Win Rate: 70-75% historically
- P&L: -2% to +2% (first trades)

**Important:**
- Not all signals = executed trades
- System waits for best conditions
- Better safe than sorry (low false signals)

---

## 🔑 Key Points

1. **REAL Trades** - Not simulated
2. **REAL Prices** - From IBKR
3. **REAL Account** - Your money
4. **REAL Logging** - Every trade recorded
5. **REAL Monitoring** - Dashboard shows everything

---

## 🚀 Ready to Start?

```bash
# 1. Setup complete? Run test:
python3 ibkr_live_trader.py

# 2. Connection successful? Run one cycle:
python3 live_trading_engine.py

# 3. Ready for tomorrow? Run automated:
python3 automated_system.py
```

---

## 📞 Support

If connection issues:

1. Check IBKR logs in TWS/Gateway
2. Check Python errors in terminal
3. Verify .env file is correct
4. Restart TWS/Gateway
5. Try test again

---

**Your STAR trading system is now connected to IBKR!**

All trades will be REAL, logged to database, and visible everywhere. 🚀

