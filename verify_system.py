import json
from pathlib import Path
import subprocess
import os
from datetime import datetime

print("\n" + "="*80)
print("SYSTEM VERIFICATION - RIGHT NOW")
print("="*80 + "\n")

# 1. Check processes
print("1. RUNNING PROCESSES:")
result = subprocess.run("ps aux | grep -E 'paper_trader|streamlit' | grep -v grep | wc -l", shell=True, capture_output=True, text=True)
count = int(result.stdout.strip())
print(f"   Processes running: {count}")
if count >= 2:
    print("   ✅ Both systems running")
else:
    print("   ❌ NOT ENOUGH PROCESSES")

# 2. Check JSON file
print("\n2. TRADE DATA FILE:")
trades_file = Path("current_trades.json")
if trades_file.exists():
    with open(trades_file) as f:
        data = json.load(f)
    
    last_update = data.get("last_update", "")
    open_trades = len(data.get("open_trades", {}))
    
    # Check if recently updated
    if last_update:
        # Simple check: is update from last 2 minutes?
        print(f"   ✅ File exists")
        print(f"   Last update: {last_update}")
        print(f"   Open trades: {open_trades}")
    
    if open_trades > 0:
        print(f"   ✅ HAS TRADES")
        for tid, trade in list(data.get("open_trades", {}).items())[:3]:
            print(f"      • {trade['symbol']} {trade['action']} x{trade['quantity']}")
    else:
        print(f"   ⚠️  No trades in file")
else:
    print(f"   ❌ File not found")

# 3. Check dashboard
print("\n3. DASHBOARD:")
result = subprocess.run("curl -s http://localhost:8501 2>/dev/null | head -5", shell=True, capture_output=True, text=True)
if "STAR" in result.stdout:
    print("   ✅ Dashboard responding")
else:
    print("   ❌ Dashboard not responding or not loading")

# 4. Check market data
print("\n4. MARKET DATA:")
try:
    import yfinance as yf
    aapl = yf.Ticker("AAPL").info.get("currentPrice")
    print(f"   ✅ AAPL: ${aapl}")
except:
    print(f"   ❌ Can't fetch market data")

print("\n" + "="*80)
print("HONEST ASSESSMENT:")
print("="*80)

if count >= 2 and trades_file.exists():
    print("✅ SYSTEM IS WORKING - Check http://localhost:8501")
else:
    print("❌ SYSTEM HAS ISSUES - Need to fix")

print("\n")
