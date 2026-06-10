import json
from pathlib import Path

state_file = Path("current_trades.json")
with open(state_file) as f:
    state = json.load(f)

print("\n" + "="*80)
print("📊 PAPER TRADES EXECUTED TODAY")
print("="*80)

trades = state.get('open_trades', {})
signals = state.get('signals', [])

print(f"\n✅ OPEN TRADES: {len(trades)}")
print("-" * 80)

for trade_id, trade in trades.items():
    symbol = trade['symbol']
    action = trade['action']
    qty = trade['quantity']
    entry = trade['entry_price']
    sl = trade['stop_loss']
    tp = trade['take_profit']
    time = trade['entry_time'].split('T')[1][:8]
    
    print(f"{symbol:5} | {action:4} x{qty:3} | Entry: ${entry:7.2f} | SL: ${sl:.2f} | TP: ${tp:.2f} | Time: {time}")

print(f"\n📝 SIGNALS: {len(signals)}")
print("-" * 80)

for sig in signals[-5:]:  # Last 5 signals
    symbol = sig['symbol']
    action = sig['action']
    conf = sig['confidence']
    time = sig['timestamp'].split('T')[1][:8]
    print(f"{time} | {symbol} {action:4} (Confidence: {conf:.0%})")

print(f"\n💰 BALANCE: ${state.get('balance', 0):,.0f}")
print(f"⏰ Last Update: {state.get('last_update')}")
print("\n" + "="*80 + "\n")
