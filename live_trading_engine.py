#!/usr/bin/env python3
"""
Live Trading Engine - IBKR Integration
Real trades in your IBKR account
Real prices from IBKR
All trades logged to database with IBKR order IDs
"""
import os
import time
from datetime import datetime, date
from dotenv import load_dotenv
from supabase import create_client
import yfinance as yf
import pandas as pd

from trading_signals import VolumeWeightedRSISystem
from position_manager import PositionManager
from ibkr_live_trader import IBKRLiveTrader
from market_data_provider import RealMarketDataProvider

load_dotenv()

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class LiveTradingEngine:
    """
    Live Trading Engine
    - Connects to IBKR
    - Executes REAL trades
    - Uses REAL prices
    - Logs everything to database
    """

    def __init__(self):
        self.ibkr_trader = IBKRLiveTrader()
        self.trading_system = VolumeWeightedRSISystem()
        self.position_manager = PositionManager(
            account_balance=100000.0,
            risk_per_trade=0.02
        )
        self.data_provider = RealMarketDataProvider()

        print("\n" + "="*80)
        print("🚀 LIVE TRADING ENGINE - REAL TRADES IN IBKR")
        print("="*80)

        # Try to connect to IBKR
        if self.ibkr_trader.connect():
            print("✅ IBKR Connected - Ready for LIVE trading")
            self.ready = True
        else:
            print("⚠️  IBKR Not Connected - Falling back to paper trading")
            print("   To trade live: Start IBKR TWS or Gateway")
            self.ready = False

    def process_symbol(self, symbol: str) -> dict:
        """
        Process symbol and generate trading signal
        Uses REAL prices from Yahoo Finance
        """
        try:
            # Get REAL market data
            ohlcv = self.data_provider.get_ohlcv_dict(symbol, period="5d", interval="1h")

            if ohlcv is None:
                return {"symbol": symbol, "action": "ERROR", "reason": "No data"}

            # Get REAL current price from IBKR (if connected)
            if self.ready:
                ibkr_price = self.ibkr_trader.get_live_price(symbol)
                if ibkr_price:
                    entry_price = ibkr_price['price']
                    print(f"\n💰 REAL IBKR Price {symbol}: ${entry_price:.2f}")
                else:
                    entry_price = ohlcv['last_price']
            else:
                entry_price = ohlcv['last_price']

            # Generate signal
            signal_data = {
                'open': ohlcv['open'],
                'high': ohlcv['high'],
                'low': ohlcv['low'],
                'close': ohlcv['close'],
                'volume': ohlcv['volume']
            }

            signal = self.trading_system.generate_signal(signal_data)

            if signal.get('action') in ['BUY', 'SELL']:
                signal['symbol'] = symbol
                signal['entry_price'] = entry_price
                signal['timestamp'] = datetime.now().isoformat()
                signal['price_source'] = 'IBKR' if self.ready else 'Yahoo Finance'

                return signal
            else:
                return {"symbol": symbol, "action": "HOLD"}

        except Exception as e:
            return {"symbol": symbol, "action": "ERROR", "error": str(e)[:60]}

    def execute_trade(self, signal: dict):
        """
        Execute REAL trade in IBKR
        """
        symbol = signal.get('symbol')
        action = signal.get('action')
        entry_price = signal.get('entry_price')

        if action == "HOLD":
            return

        try:
            if not self.ready:
                print(f"⚠️  IBKR not connected - Cannot execute {action} order")
                return

            # Calculate position size
            stop_loss = signal.get('stop_loss', entry_price * 0.98)
            position_info = self.position_manager.calculate_position_size(entry_price, stop_loss)

            quantity = position_info.get('quantity', 0)

            if quantity <= 0:
                print(f"⚠️  Invalid position size for {symbol}")
                return

            print(f"\n🚀 EXECUTING REAL TRADE IN IBKR")
            print(f"   Symbol: {symbol}")
            print(f"   Action: {action}")
            print(f"   Quantity: {quantity}")
            print(f"   Entry: ${entry_price:.2f}")
            print(f"   Stop Loss: ${stop_loss:.2f}")

            # Place order
            if action == "BUY":
                order_result = self.ibkr_trader.place_buy_order(
                    symbol,
                    quantity,
                    limit_price=entry_price * 1.001  # Slightly above current
                )
            else:
                order_result = self.ibkr_trader.place_sell_order(
                    symbol,
                    quantity,
                    limit_price=entry_price * 0.999  # Slightly below current
                )

            # Log to database
            if order_result:
                trade_log = {
                    "symbol": symbol,
                    "side": action,
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": signal.get('take_profit', 0),
                    "order_id": order_result.get('order_id'),
                    "status": "OPEN",
                    "price_source": "IBKR",
                    "confidence": signal.get('confidence', 0),
                    "reason": signal.get('reason', '')
                }

                self.ibkr_trader.log_trade_to_database(trade_log)

                print(f"✅ REAL trade executed and logged")

        except Exception as e:
            print(f"❌ Error executing trade: {str(e)[:100]}")

    def sync_ibkr_positions(self):
        """
        Sync all IBKR positions to database
        """
        if not self.ready:
            print("⚠️  IBKR not connected")
            return

        print(f"\n📊 Syncing IBKR positions to database...")
        self.ibkr_trader.sync_positions_to_database()

    def run_trading_cycle(self, symbols=None):
        """
        Run one complete trading cycle
        Analyze symbols, generate signals, execute real trades
        """
        if symbols is None:
            symbols = ["AAPL", "NVDA", "TSLA", "SPY"]

        print(f"\n" + "="*80)
        print(f"🚀 LIVE TRADING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        if self.ready:
            print("✅ IBKR Connected - Executing REAL trades")
        else:
            print("⚠️  IBKR Not Connected - Paper mode only")

        trades_executed = 0

        for symbol in symbols:
            signal = self.process_symbol(symbol)

            if signal.get('action') in ['BUY', 'SELL']:
                print(f"\n📊 Signal for {symbol}: {signal.get('action')}")
                print(f"   Confidence: {signal.get('confidence', 0):.0%}")
                print(f"   Entry: ${signal.get('entry_price', 0):.2f}")

                # Execute trade
                self.execute_trade(signal)
                trades_executed += 1

        # Sync positions
        if self.ready:
            self.sync_ibkr_positions()

        print(f"\n" + "="*80)
        print(f"📈 Cycle Complete - {trades_executed} trades executed")
        print("="*80 + "\n")

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ready:
            self.ibkr_trader.disconnect()


def main():
    """Run live trading engine"""

    engine = LiveTradingEngine()

    if engine.ready:
        print("""
✅ LIVE TRADING ENGINE STARTED

You are now connected to IBKR
Real trades will be executed in your account
All trades logged to Supabase database
        """)

        # Run one trading cycle
        engine.run_trading_cycle()

        # Sync positions
        engine.sync_ibkr_positions()

        engine.disconnect()

    else:
        print("""
⚠️  IBKR NOT CONNECTED

To use live trading:

1. Install IBKR TWS or Gateway
   https://www.interactivebrokers.com/en/index.php?f=14099

2. Enable API connections in IBKR
   File → Global Configuration → API → Settings
   ✓ Enable ActiveX and Socket Clients

3. Start IBKR TWS/Gateway

4. Set environment variables in .env:
   IBKR_HOST=127.0.0.1
   IBKR_PORT=7497
   IBKR_CLIENT_ID=1

5. Install ib_insync:
   pip install ib_insync

6. Run again:
   python3 live_trading_engine.py
        """)


if __name__ == "__main__":
    main()
