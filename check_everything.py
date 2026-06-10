import json
from pathlib import Path
from datetime import datetime
import os

print("\n" + "="*80)
print("🔍 CHECKING EVERYTHING RIGHT NOW")
print("="*80 + "\n")

# 1. Check processes
print("1️⃣ RUNNING PROCESSES:")
os.system("ps aux | grep -E 'fast_trader|streamlit' | grep -v grep | awk '{print \"   ✅\", $11, $12}'")

# 2. Check JSON files
print("\n2️⃣ TRADES JSON:")
trades_file = Path("current_trades.json")
if trades_file.exists():
    with open(trades_file) as f:
        trades = json.load(f)
    print(f"   File exists: ✅")
    print(f"   Open trades: {len(trades.get('open_trades', {}))}")
    print(f"   Signals: {len(trades.get('signals', []))}")
    print(f"   Last update: {trades.get('last_update')}")
    
    if trades.get('open_trades'):
        print(f"\n   TRADES:")
        for trade_id, trade in trades['open_trades'].items():
            print(f"      • {trade['symbol']} {trade['action']} x{trade['quantity']} @ ${trade['entry_price']:.2f}")
else:
    print(f"   File exists: ❌ (not created yet)")

# 3. Check market data
print("\n3️⃣ CHECKING MARKET (TEST):")
try:
    import yfinance as yf
    symbols = ["AAPL", "NVDA", "TSLA", "SPY"]
    for sym in symbols:
        ticker = yf.Ticker(sym)
        price = ticker.info.get('currentPrice', 'N/A')
        print(f"   {sym}: ${price}")
except Exception as e:
    print(f"   Error: {str(e)[:50]}")

# 4. Summary
print("\n4️⃣ SUMMARY:")
if trades_file.exists():
    print(f"   Total trades today: {len(trades.get('open_trades', {}))}")
    print(f"   Dashboard: Should show at http://localhost:8501")
else:
    print(f"   ❌ NO TRADES EXECUTED YET")
    print(f"   Reason: System either hasn't run, or no signals generated")

print("\n" + "="*80 + "\n")
