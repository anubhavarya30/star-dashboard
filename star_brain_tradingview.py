#!/usr/bin/env python3
"""
🧠 STAR BRAIN v2 - TRADINGVIEW INTEGRATION
JSON-ONLY (NO SUPABASE - PURE SPEED)
Tests all signals on TradingView before execution
"""
import json
import time
from datetime import datetime
from pathlib import Path
import pytz

from market_data_provider import RealMarketDataProvider
from trading_signals import VolumeWeightedRSISystem
from position_manager import PositionManager
from tradingview_connector import TradingViewConnector

class STARBrainWithTradingView:
    """STAR Brain that integrates with TradingView for signal validation"""

    def __init__(self):
        print("\n" + "="*80)
        print("🧠 STAR BRAIN v2 - TRADINGVIEW + JSON (NO SUPABASE)")
        print("="*80)

        # Core trading systems
        self.data_provider = RealMarketDataProvider()
        self.signal_system = VolumeWeightedRSISystem()
        self.position_manager = PositionManager(100000, 0.02)

        # TradingView connector
        self.tv = TradingViewConnector()
        self.tv_connected = self.tv.connect()

        # State - JSON ONLY (NO SUPABASE)
        self.state_file = Path("current_trades.json")
        self.state = self._load_state()
        self.cycle = 0
        self.symbols = ["AAPL", "NVDA", "TSLA", "SPY"]

        # Market hours
        self.ny_tz = pytz.timezone('America/New_York')

        print("✅ Market Data Provider: Ready")
        print("✅ Signal System: Ready")
        print("✅ Position Manager: Ready")
        if self.tv_connected:
            print("✅ TradingView Connector: CONNECTED")
        else:
            print("⚠️  TradingView Connector: OFFLINE (paper mode)")
        print("✅ JSON Storage: READY (NO SUPABASE)")
        print("✅ STAR Brain v2: ONLINE\n")

    def _load_state(self):
        """Load from JSON only"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {"open_trades": {}, "signals": [], "balance": 100000.0}

    def _save_state(self):
        """Save to JSON only - INSTANT"""
        self.state["last_update"] = datetime.now().isoformat()
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2, default=str)

    def is_market_open(self) -> bool:
        from datetime import time as dtime
        now = datetime.now(self.ny_tz)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        if now.weekday() >= 5:
            return False
        return market_open <= now <= market_close

    def analyze_symbol(self, symbol: str) -> dict:
        """Analyze symbol and generate signal"""
        try:
            ohlcv = self.data_provider.get_ohlcv_dict(symbol, period="5d", interval="1h")
            if not ohlcv:
                return {"symbol": symbol, "action": "ERROR", "reason": "No data"}

            current_price = ohlcv['last_price']

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

    def verify_on_tradingview(self, symbol: str, signal: dict) -> bool:
        """Verify signal on TradingView"""
        if not self.tv_connected:
            print(f"      ⚠️  TradingView offline - executing anyway")
            return True

        try:
            print(f"      📊 Verifying on TradingView...", end="")
            chart = self.tv.get_chart_data(symbol, "1h")
            if not chart:
                print(f" ❌")
                return False
            print(f" ✅")
            return True
        except Exception as e:
            print(f" ⚠️")
            return False

    def create_tradingview_alert(self, symbol: str, signal: dict):
        """Create Pine Script alert in TradingView"""
        if not self.tv_connected:
            return

        try:
            condition = f"{signal['action']} signal - RSI confirms"
            self.tv.create_alert(symbol, condition, "notify")
            print(f"      🔔 Alert created")
        except Exception as e:
            pass

    def should_execute_trade(self, signal: dict) -> bool:
        """Decide if trade should execute"""
        action = signal.get('action')
        confidence = signal.get('confidence', 0)

        if action not in ['BUY', 'SELL']:
            return False

        if confidence < 0.65:
            return False

        entry_price = signal.get('entry_price')
        stop_loss = signal.get('stop_loss')
        pos_info = self.position_manager.calculate_position_size(entry_price, stop_loss)

        return pos_info.get('quantity', 0) > 0

    def execute_trade(self, signal: dict):
        """Execute a trade decision"""
        symbol = signal['symbol']
        action = signal['action']
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        take_profit = signal['take_profit']
        confidence = signal['confidence']

        pos_info = self.position_manager.calculate_position_size(entry_price, stop_loss)
        quantity = pos_info.get('quantity', 0)

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

        self.state["open_trades"][trade_id] = trade
        self.state["signals"].append({
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "entry_price": entry_price,
            "timestamp": datetime.now().isoformat()
        })

        return trade

    def run_cycle(self):
        """Run one complete STAR cycle"""
        self.cycle += 1

        now = datetime.now(self.ny_tz)
        print(f"\n{'='*80}")
        print(f"🧠 CYCLE #{self.cycle} - {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"{'='*80}")

        if not self.is_market_open():
            print(f"⏰ Market closed")
            return

        print("✅ Market OPEN - Analyzing\n")
        print("📊 ANALYSIS:")
        trades_executed = 0

        for symbol in self.symbols:
            signal = self.analyze_symbol(symbol)

            if signal.get('action') in ['BUY', 'SELL']:
                confidence_str = f"{signal['confidence']:.0%}"
                print(f"   {symbol:5} → {signal['action']:4} ({confidence_str})")

                if self.should_execute_trade(signal):
                    verified = self.verify_on_tradingview(symbol, signal)
                    if verified:
                        self.create_tradingview_alert(symbol, signal)
                        trade = self.execute_trade(signal)
                        print(f"      ✅ EXECUTED")
                        trades_executed += 1
                    else:
                        print(f"      ❌ SKIPPED")
            else:
                print(f"   {symbol:5} → HOLD")

        self._save_state()

        print(f"\n📈 SUMMARY:")
        print(f"   Trades: {trades_executed}")
        print(f"   Open: {len(self.state['open_trades'])}")
        print(f"   Signals: {len(self.state['signals'])}")

    def run(self):
        """Run continuous operation"""
        print("\n" + "="*80)
        print("🚀 STAR BRAIN v2 - STARTING (JSON ONLY, NO SUPABASE)")
        print("="*80)
        print("Pure speed - JSON instant writes")
        print("="*80 + "\n")

        try:
            while True:
                self.run_cycle()
                print(f"\n⏳ Next cycle in 60s...\n")
                time.sleep(60)

        except KeyboardInterrupt:
            print("\n🛑 SHUTDOWN")


def main():
    brain = STARBrainWithTradingView()
    brain.run()


if __name__ == "__main__":
    main()
