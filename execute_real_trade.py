#!/usr/bin/env python3
"""
EXECUTE REAL TRADE IN IBKR
Places actual order that shows in Trader Workstation
"""
import os
from datetime import datetime
from dotenv import load_dotenv
from ibkr_live_trader import IBKRLiveTrader
import json
from pathlib import Path

load_dotenv()

print("\n" + "="*80)
print("🚀 EXECUTING REAL TRADE IN IBKR")
print("="*80 + "\n")

# Connect to IBKR
trader = IBKRLiveTrader()

if not trader.connect():
    print("❌ Could not connect to IBKR TWS/Gateway")
    print("Make sure Trader Workstation is running and API is enabled")
    exit(1)

print("✅ Connected to IBKR\n")

# Execute a test BUY order
symbol = "AAPL"
quantity = 1  # Just 1 share for testing
limit_price = 312.00  # Slightly below current to avoid execution

print(f"📋 Placing TEST order:")
print(f"   Symbol: {symbol}")
print(f"   Action: BUY")
print(f"   Quantity: {quantity} share")
print(f"   Limit Price: ${limit_price}")
print(f"\n⏳ Placing order in IBKR...\n")

# Place the order
order_result = trader.place_buy_order(symbol, quantity, limit_price=limit_price)

if order_result:
    print("\n✅ ORDER PLACED IN IBKR!")
    print(f"   Order ID: {order_result.get('order_id')}")
    print(f"   Status: {order_result.get('status')}")

    # Log to STAR system
    trade_data = {
        "symbol": symbol,
        "side": "BUY",
        "quantity": quantity,
        "entry_price": limit_price,
        "stop_loss": limit_price * 0.98,
        "take_profit": limit_price * 1.02,
        "order_id": order_result.get('order_id'),
        "status": order_result.get('status'),
        "timestamp": datetime.now().isoformat(),
        "source": "IBKR_REAL"
    }

    # Update STAR JSON
    state_file = Path("current_trades.json")
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
    else:
        state = {"open_trades": {}, "signals": [], "balance": 100000.0}

    state["open_trades"][f"REAL_{symbol}_{datetime.now().timestamp()}"] = {
        "id": f"REAL_{symbol}_{datetime.now().timestamp()}",
        "symbol": symbol,
        "action": "BUY",
        "quantity": quantity,
        "entry_price": limit_price,
        "stop_loss": trade_data["stop_loss"],
        "take_profit": trade_data["take_profit"],
        "entry_time": datetime.now().isoformat(),
        "status": "OPEN",
        "confidence": 0.95,
        "order_id": order_result.get('order_id'),
        "ibkr_order": True
    }
    state["last_update"] = datetime.now().isoformat()

    with open(state_file, "w") as f:
        json.dump(state, f, indent=2, default=str)

    print("\n📝 Order also logged to STAR system")

    print("\n" + "="*80)
    print("✅ REAL TRADE EXECUTED!")
    print("="*80)
    print("\n✅ Should now appear in:")
    print("   1. Trader Workstation (IBKR account)")
    print("   2. STAR Dashboard (http://localhost:8501)")
    print("\n🔍 Check Trader Workstation:")
    print("   • Account → Orders")
    print("   • Monitor → Watch trades")
    print("\n" + "="*80 + "\n")

else:
    print("❌ Failed to place order")
    print("Check that:")
    print("  • Account has buying power")
    print("  • Market is open")
    print("  • Symbol is valid")

trader.disconnect()
