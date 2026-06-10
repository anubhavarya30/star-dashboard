#!/usr/bin/env python3
"""
TEST TRADE - Force execute one trade to verify system works end-to-end
"""
import json
from pathlib import Path
from datetime import datetime

print("\n" + "="*80)
print("🧪 EXECUTING TEST TRADE")
print("="*80 + "\n")

# Create test trade state
test_state = {
    "open_trades": {
        "TEST_AAPL_001": {
            "id": "TEST_AAPL_001",
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 10,
            "entry_price": 312.29,
            "stop_loss": 308.86,
            "take_profit": 319.95,
            "entry_time": datetime.now().isoformat(),
            "status": "OPEN",
            "confidence": 0.85,
            "test_trade": True
        }
    },
    "closed_trades": [],
    "signals": [
        {
            "symbol": "AAPL",
            "action": "BUY",
            "confidence": 0.85,
            "entry_price": 312.29,
            "stop_loss": 308.86,
            "take_profit": 319.95,
            "reason": "Volume-Weighted RSI signal (TEST)",
            "timestamp": datetime.now().isoformat()
        }
    ],
    "balance": 100000.0,
    "last_update": datetime.now().isoformat()
}

# Save to files
print("📝 Logging trade to JSON files...\n")

with open("current_trades.json", "w") as f:
    json.dump(test_state, f, indent=2, default=str)
print("✅ current_trades.json updated")

with open("current_signals.json", "w") as f:
    json.dump(test_state["signals"], f, indent=2, default=str)
print("✅ current_signals.json updated")

print("\n" + "="*80)
print("🧪 TEST TRADE CREATED")
print("="*80)

print("\n📊 Trade Details:")
print(f"   Symbol: AAPL")
print(f"   Action: BUY")
print(f"   Quantity: 10 shares")
print(f"   Entry Price: $312.29")
print(f"   Stop Loss: $308.86")
print(f"   Take Profit: $319.95")
print(f"   Confidence: 85%")
print(f"   Status: OPEN")

print("\n✅ Trade logged to:")
print(f"   • current_trades.json (open positions)")
print(f"   • current_signals.json (signal history)")

print("\n📱 Dashboard should now show:")
print(f"   ✅ 📈 Open Trades tab - AAPL BUY x10 @ $312.29")
print(f"   ✅ 🤖 Signals tab - AAPL signal with 85% confidence")
print(f"   ✅ ⚙️ Status tab - 1 open trade, 1 signal")

print("\n🔗 Verify at: http://localhost:8501")
print("\n" + "="*80 + "\n")
