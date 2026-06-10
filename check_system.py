import json
from pathlib import Path
from datetime import datetime
import os

print("\n" + "="*80)
print("🌟 STAR TRADING SYSTEM - LIVE STATUS")
print("="*80)

# Check trading engine process
os.system("ps aux | grep fast_trader | grep -v grep | awk '{print \"✅ Trading Engine: PID\", $2, \"- Running\"}'")
os.system("ps aux | grep streamlit | grep -v grep | awk '{print \"✅ Dashboard: PID\", $2, \"- Running\"}'")

print()

# Check JSON files
trades_file = Path("current_trades.json")
signals_file = Path("current_signals.json")

if trades_file.exists():
    with open(trades_file) as f:
        data = json.load(f)
    print(f"📊 TRADES FILE:")
    print(f"   Open trades: {len(data.get('open_trades', {}))}")
    print(f"   Total signals: {len(data.get('signals', []))}")
    print(f"   Balance: ${data.get('balance', 0):,.0f}")
    print(f"   Last update: {data.get('last_update')}")
else:
    print("📊 TRADES FILE: Not yet created (first cycle pending)")

print()

if signals_file.exists():
    with open(signals_file) as f:
        signals = json.load(f)
    print(f"🤖 RECENT SIGNALS: {len(signals)}")
    if signals:
        for sig in signals[-3:]:
            print(f"   • {sig.get('symbol')}: {sig.get('action')} @ ${sig.get('entry_price'):.2f} (conf: {sig.get('confidence'):.0%})")
else:
    print("🤖 RECENT SIGNALS: None yet")

print()
print("="*80)
print("⏳ SYSTEM STATUS: Initializing...")
print("   Next trading cycle: ~5 minutes from startup")
print("   Market: Open (9:30 AM - 4:00 PM ET)")
print("   Symbols analyzed: AAPL, NVDA, TSLA, SPY")
print("="*80 + "\n")
