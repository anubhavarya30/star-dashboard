#!/usr/bin/env python3
"""
PAPER TRADER - Simple, direct execution
Simulates trades with REAL market data
Logs everything visibly
"""
import json
import time
from pathlib import Path
from datetime import datetime
import yfinance as yf
from trading_signals import VolumeWeightedRSISystem
from position_manager import PositionManager
from market_data_provider import RealMarketDataProvider

print("\n" + "="*80)
print("📝 STAR PAPER TRADING SYSTEM")
print("="*80)
print("Real market data + Simulated execution")
print("="*80 + "\n")

provider = RealMarketDataProvider()
system = VolumeWeightedRSISystem()
pm = PositionManager(100000, 0.02)

# Load or create state
state_file = Path("current_trades.json")
if state_file.exists():
    with open(state_file) as f:
        state = json.load(f)
else:
    state = {"open_trades": {}, "signals": [], "balance": 100000.0}

def save_state():
    state["last_update"] = datetime.now().isoformat()
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2, default=str)

def execute_cycle():
    """Execute one trading cycle"""
    print(f"\n{'='*80}")
    print(f"🔄 TRADING CYCLE - {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*80}")

    symbols = ["AAPL", "NVDA", "TSLA", "SPY"]
    trades_this_cycle = 0

    for symbol in symbols:
        try:
            # Get real data
            ohlcv = provider.get_ohlcv_dict(symbol, period="5d", interval="1h")
            if not ohlcv:
                continue

            current_price = ohlcv['last_price']

            # Generate signal
            signal_data = {
                'open': ohlcv['open'],
                'high': ohlcv['high'],
                'low': ohlcv['low'],
                'close': ohlcv['close'],
                'volume': ohlcv['volume']
            }

            signal = system.generate_signal(signal_data)
            action = signal.get('action')
            confidence = signal.get('confidence', 0)

            if action in ['BUY', 'SELL'] and confidence >= 0.65:
                # Calculate position
                stop_loss = signal.get('stop_loss', current_price * 0.98)
                pos_info = pm.calculate_position_size(current_price, stop_loss)
                qty = pos_info.get('quantity', 0)

                if qty > 0:
                    trade_id = f"{symbol}_{datetime.now().timestamp()}"
                    trade = {
                        "id": trade_id,
                        "symbol": symbol,
                        "action": action,
                        "quantity": qty,
                        "entry_price": current_price,
                        "stop_loss": stop_loss,
                        "take_profit": signal.get('take_profit', 0),
                        "entry_time": datetime.now().isoformat(),
                        "status": "OPEN",
                        "confidence": confidence
                    }

                    state["open_trades"][trade_id] = trade
                    state["signals"].append({
                        "symbol": symbol,
                        "action": action,
                        "confidence": confidence,
                        "entry_price": current_price,
                        "stop_loss": stop_loss,
                        "take_profit": signal.get('take_profit', 0),
                        "reason": signal.get('reason', ''),
                        "timestamp": datetime.now().isoformat()
                    })

                    print(f"✅ {action:4} {symbol:5} x{qty:3} @ ${current_price:7.2f} | SL: ${stop_loss:.2f} | Conf: {confidence:.0%}")
                    trades_this_cycle += 1
            else:
                print(f"⏸️  {symbol:5} - HOLD (signal: {action}, conf: {confidence:.0%})")

        except Exception as e:
            print(f"❌ {symbol}: {str(e)[:40]}")

    # Save state
    save_state()

    print(f"\n📊 Results: {trades_this_cycle} trades executed")
    print(f"📈 Total open trades: {len(state['open_trades'])}")
    print(f"📝 Total signals: {len(state['signals'])}")

# Run cycles
try:
    cycle = 0
    while True:
        cycle += 1
        execute_cycle()
        print(f"\n⏳ Next cycle in 60 seconds... (Ctrl+C to stop)\n")
        time.sleep(60)  # Every minute for testing

except KeyboardInterrupt:
    print("\n\n🛑 Trading stopped")
    print(f"Sessions: {cycle}")
    print(f"Trades: {len(state['open_trades'])}")
    print(f"Signals: {len(state['signals'])}")
