#!/usr/bin/env python3
"""
🧠 STAR BRAIN - Master Trading Orchestrator
Central decision-making system that controls all trading operations
Makes decisions on WHEN and WHAT scripts to run
"""
import json
import time
from datetime import datetime, time as dtime
import pytz
from pathlib import Path

from market_data_provider import RealMarketDataProvider
from trading_signals import VolumeWeightedRSISystem
from position_manager import PositionManager
from daily_routine_planner import DailyRoutinePlanner
from agent_aggregator import AgentAggregator
from ibkr_connector import sync_ibkr_to_star

class STARBrain:
    """Master decision-making system for STAR trading"""

    def __init__(self):
        print("\n" + "="*80)
        print("🧠 STAR BRAIN - INITIALIZING")
        print("="*80)

        # Core systems
        self.data_provider = RealMarketDataProvider()
        self.signal_system = VolumeWeightedRSISystem()
        self.position_manager = PositionManager(100000, 0.02)
        self.planner = DailyRoutinePlanner()
        self.agents = AgentAggregator()

        # State
        self.state_file = Path("current_trades.json")
        self.state = self._load_state()
        self.cycle = 0
        self.symbols = ["AAPL", "NVDA", "TSLA", "SPY"]

        # Market hours (EST)
        self.ny_tz = pytz.timezone('America/New_York')
        self.market_open = dtime(9, 30)
        self.market_close = dtime(16, 0)

        print("✅ Market Data Provider: Ready")
        print("✅ Signal System: Ready")
        print("✅ Position Manager: Ready")
        print("✅ Agent System: Ready")
        print("✅ STAR Brain: ONLINE\n")

    def _load_state(self):
        """Load trading state from JSON"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {
            "open_trades": {},
            "signals": [],
            "balance": 100000.0,
            "daily_pnl": 0,
            "last_update": None
        }

    def _save_state(self):
        """Save state to JSON"""
        self.state["last_update"] = datetime.now().isoformat()
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2, default=str)

    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        now = datetime.now(self.ny_tz)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

        # Closed on weekends
        if now.weekday() >= 5:
            return False

        return market_open <= now <= market_close

    def analyze_symbol(self, symbol: str) -> dict:
        """Analyze one symbol for trading opportunity"""
        try:
            # Fetch REAL market data
            ohlcv = self.data_provider.get_ohlcv_dict(symbol, period="5d", interval="1h")

            if not ohlcv:
                return {"symbol": symbol, "action": "ERROR", "reason": "No data"}

            current_price = ohlcv['last_price']

            # Generate signal
            signal_data = {
                'open': ohlcv['open'],
                'high': ohlcv['high'],
                'low': ohlcv['low'],
                'close': ohlcv['close'],
                'volume': ohlcv['volume']
            }

            signal = self.signal_system.generate_signal(signal_data)

            return {
                "symbol": symbol,
                "action": signal.get('action'),
                "confidence": signal.get('confidence', 0),
                "entry_price": current_price,
                "stop_loss": signal.get('stop_loss'),
                "take_profit": signal.get('take_profit'),
                "reason": signal.get('reason', '')
            }

        except Exception as e:
            return {"symbol": symbol, "action": "ERROR", "error": str(e)[:50]}

    def should_execute_trade(self, signal: dict) -> bool:
        """Decide if signal should become a trade"""
        # Decision logic:
        # 1. Action must be BUY or SELL (not HOLD)
        # 2. Confidence must be >= 65%
        # 3. Position size must be valid
        # 4. Risk management checks pass

        action = signal.get('action')
        confidence = signal.get('confidence', 0)

        if action not in ['BUY', 'SELL']:
            return False

        if confidence < 0.65:
            return False

        # Check position sizing
        entry_price = signal.get('entry_price')
        stop_loss = signal.get('stop_loss')

        pos_info = self.position_manager.calculate_position_size(entry_price, stop_loss)
        if pos_info.get('quantity', 0) <= 0:
            return False

        return True

    def execute_trade(self, signal: dict):
        """Execute a trade decision"""
        symbol = signal['symbol']
        action = signal['action']
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        take_profit = signal['take_profit']
        confidence = signal['confidence']

        # Calculate position size
        pos_info = self.position_manager.calculate_position_size(entry_price, stop_loss)
        quantity = pos_info.get('quantity', 0)

        # Create trade record
        trade_id = f"{symbol}_{datetime.now().timestamp()}"
        trade = {
            "id": trade_id,
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "entry_time": datetime.now().isoformat(),
            "status": "OPEN",
            "confidence": confidence,
            "pnl": 0
        }

        # Add to state
        self.state["open_trades"][trade_id] = trade
        self.state["signals"].append({
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "timestamp": datetime.now().isoformat()
        })

        return trade

    def run_cycle(self):
        """Run one complete decision cycle"""
        self.cycle += 1

        now = datetime.now(self.ny_tz)
        print(f"\n{'='*80}")
        print(f"🧠 STAR BRAIN CYCLE #{self.cycle} - {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"{'='*80}")

        # Decision 1: Is market open?
        if not self.is_market_open():
            print(f"⏰ Market closed - next cycle at 9:30 AM ET tomorrow")
            return

        print("✅ Market is OPEN - Analyzing opportunities\n")

        # Decision 2: Analyze all symbols
        print("📊 SYMBOL ANALYSIS:")
        trades_executed = 0

        for symbol in self.symbols:
            signal = self.analyze_symbol(symbol)

            if signal.get('action') in ['BUY', 'SELL']:
                confidence_str = f"{signal['confidence']:.0%}"
                print(f"   {symbol:5} → {signal['action']:4} (Confidence: {confidence_str})", end="")

                # Decision 3: Should we execute this?
                if self.should_execute_trade(signal):
                    trade = self.execute_trade(signal)
                    print(f" ✅ EXECUTED (qty: {trade['quantity']})")
                    trades_executed += 1
                else:
                    print(f" ⏸️  SKIPPED (confidence too low)")
            else:
                print(f"   {symbol:5} → HOLD")

        # Decision 4: Sync with IBKR if any trades
        if trades_executed > 0:
            print(f"\n📡 Syncing with IBKR...")
            try:
                sync_ibkr_to_star()
                print(f"   ✅ IBKR sync complete")
            except Exception as e:
                print(f"   ⚠️  IBKR sync failed: {str(e)[:40]}")

        # Decision 5: Save state
        self._save_state()

        # Summary
        print(f"\n📈 CYCLE SUMMARY:")
        print(f"   Trades executed: {trades_executed}")
        print(f"   Open positions: {len(self.state['open_trades'])}")
        print(f"   Total signals: {len(self.state['signals'])}")
        print(f"   Balance: ${self.state['balance']:,.0f}")

    def run(self):
        """Run the STAR Brain continuously"""
        print("\n" + "="*80)
        print("🚀 STAR BRAIN - STARTING CONTINUOUS OPERATION")
        print("="*80)
        print("Cycle frequency: Every 60 seconds")
        print("Market hours: 9:30 AM - 4:00 PM ET")
        print("Symbols: AAPL, NVDA, TSLA, SPY")
        print("="*80 + "\n")

        try:
            while True:
                self.run_cycle()
                print(f"\n⏳ Next cycle in 60 seconds... (Ctrl+C to stop)\n")
                time.sleep(60)

        except KeyboardInterrupt:
            print("\n\n🛑 STAR BRAIN SHUTDOWN")
            print(f"Sessions: {self.cycle}")
            print(f"Trades: {len(self.state['open_trades'])}")
            print(f"Signals: {len(self.state['signals'])}")


def main():
    """Start STAR Brain"""
    brain = STARBrain()
    brain.run()


if __name__ == "__main__":
    main()
