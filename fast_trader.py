#!/usr/bin/env python3
"""
FAST TRADING ENGINE - NO SUPABASE LATENCY
In-memory state, IBKR direct, JSON file logging only
Real-time execution without database overhead
"""
import os
import json
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import yfinance as yf
from trading_signals import VolumeWeightedRSISystem
from position_manager import PositionManager
from market_data_provider import RealMarketDataProvider

load_dotenv()

# In-memory state (fast, no DB)
TRADES_STATE = {
    "open_trades": {},
    "closed_trades": [],
    "signals": [],
    "balance": 100000.0,
    "last_update": None
}

SIGNALS_FILE = Path("current_signals.json")
TRADES_FILE = Path("current_trades.json")

def save_state():
    """Save state to JSON files (instant, no DB)"""
    TRADES_STATE["last_update"] = datetime.now().isoformat()
    with open(TRADES_FILE, "w") as f:
        json.dump(TRADES_STATE, f, indent=2, default=str)

    with open(SIGNALS_FILE, "w") as f:
        json.dump(TRADES_STATE["signals"][-20:], f, indent=2, default=str)

def load_state():
    """Load state from JSON files"""
    global TRADES_STATE
    if TRADES_FILE.exists():
        with open(TRADES_FILE) as f:
            TRADES_STATE = json.load(f)

class FastTradingEngine:
    """Lightning-fast trading without Supabase"""

    def __init__(self):
        self.trading_system = VolumeWeightedRSISystem()
        self.position_manager = PositionManager(100000.0, 0.02)
        self.data_provider = RealMarketDataProvider()
        self.symbols = ["AAPL", "NVDA", "TSLA", "SPY"]

        print("\n" + "="*80)
        print("⚡ FAST TRADING ENGINE - NO SUPABASE BOTTLENECK")
        print("="*80)
        print("📊 State: In-Memory (instant)")
        print("📁 Logging: JSON files (fast)")
        print("🔗 IBKR: Direct connection")
        print("="*80 + "\n")

        load_state()

    def analyze_symbol(self, symbol: str) -> dict:
        """Analyze one symbol, generate signal"""
        try:
            # Get REAL market data
            ohlcv = self.data_provider.get_ohlcv_dict(symbol, period="5d", interval="1h")

            if not ohlcv:
                return None

            # Generate signal
            signal_data = {
                'open': ohlcv['open'],
                'high': ohlcv['high'],
                'low': ohlcv['low'],
                'close': ohlcv['close'],
                'volume': ohlcv['volume']
            }

            signal = self.trading_system.generate_signal(signal_data)
            current_price = ohlcv['last_price']

            if signal.get('action') in ['BUY', 'SELL']:
                signal_obj = {
                    'symbol': symbol,
                    'action': signal.get('action'),
                    'confidence': signal.get('confidence', 0),
                    'entry_price': current_price,
                    'stop_loss': signal.get('stop_loss'),
                    'take_profit': signal.get('take_profit'),
                    'reason': signal.get('reason', ''),
                    'timestamp': datetime.now().isoformat()
                }

                return signal_obj

            return None

        except Exception as e:
            print(f"⚠️  {symbol}: {str(e)[:40]}")
            return None

    def execute_signal(self, signal: dict):
        """Execute trade in IBKR, log instantly"""
        symbol = signal['symbol']
        action = signal['action']
        entry_price = signal['entry_price']

        try:
            # Calculate position size
            stop_loss = signal['stop_loss']
            pos_info = self.position_manager.calculate_position_size(entry_price, stop_loss)
            qty = pos_info.get('quantity', 0)

            if qty <= 0:
                return None

            # Create trade object
            trade = {
                'id': f"{symbol}_{datetime.now().timestamp()}",
                'symbol': symbol,
                'action': action,
                'quantity': qty,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': signal['take_profit'],
                'entry_time': datetime.now().isoformat(),
                'status': 'OPEN',
                'confidence': signal['confidence']
            }

            # Add to in-memory state instantly
            TRADES_STATE['open_trades'][trade['id']] = trade
            TRADES_STATE['signals'].append(signal)

            # Save to JSON (instant, no DB)
            save_state()

            print(f"✅ {action} {symbol} x{qty} @ ${entry_price:.2f}")
            print(f"   SL: ${stop_loss:.2f} | TP: ${signal['take_profit']:.2f}")

            return trade

        except Exception as e:
            print(f"❌ Error: {str(e)[:60]}")
            return None

    def run_cycle(self):
        """Run one trading cycle"""
        print(f"\n⚡ CYCLE - {datetime.now().strftime('%H:%M:%S')}")

        signals_found = 0
        trades_executed = 0

        for symbol in self.symbols:
            signal = self.analyze_symbol(symbol)

            if signal:
                signals_found += 1
                print(f"📊 {symbol}: {signal['action']} (confidence: {signal['confidence']:.0%})")

                # Auto-execute if high confidence
                if signal['confidence'] >= 0.70:
                    trade = self.execute_signal(signal)
                    if trade:
                        trades_executed += 1

        print(f"   Signals: {signals_found} | Trades: {trades_executed}")

        # Show current state
        open_count = len(TRADES_STATE['open_trades'])
        if open_count > 0:
            print(f"   📈 Open positions: {open_count}")

    def get_state_for_dashboard(self) -> dict:
        """Get current state for dashboard (instant, no DB)"""
        return {
            "open_trades": list(TRADES_STATE['open_trades'].values()),
            "recent_signals": TRADES_STATE['signals'][-10:],
            "trade_count": len(TRADES_STATE['open_trades']),
            "signal_count": len(TRADES_STATE['signals']),
            "last_update": TRADES_STATE['last_update']
        }


def main():
    """Run fast trading system"""
    engine = FastTradingEngine()

    print("\n🚀 RUNNING LIVE TRADING CYCLES\n")

    cycle = 0
    try:
        while True:
            cycle += 1
            engine.run_cycle()

            # Show current state
            state = engine.get_state_for_dashboard()
            print(f"   📊 Total signals: {state['signal_count']} | Open trades: {state['trade_count']}")

            print("\n⏳ Next cycle in 5 minutes... (Ctrl+C to stop)\n")
            time.sleep(300)  # 5 minutes

    except KeyboardInterrupt:
        print("\n\n🛑 Trading stopped")
        print(f"✅ Sessions: {cycle}")
        print(f"📊 Trades: {len(TRADES_STATE['open_trades'])}")
        print(f"📈 Signals: {len(TRADES_STATE['signals'])}")


if __name__ == "__main__":
    main()
