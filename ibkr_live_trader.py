#!/usr/bin/env python3
"""
IBKR Live Trader Integration
Real trades in Interactive Brokers account
Real prices from IBKR
All trades logged to JSON with IBKR order IDs
"""
import os
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import json

load_dotenv()

class IBKRLiveTrader:
    """
    Live trading integration with Interactive Brokers
    Executes real trades in your IBKR account
    """

    def __init__(self):
        self.host = os.getenv("IBKR_HOST", "127.0.0.1")
        self.port = int(os.getenv("IBKR_PORT", "7497"))
        self.client_id = int(os.getenv("IBKR_CLIENT_ID", "1"))
        self.ib = None
        self.is_connected = False

        print("🔌 IBKR Live Trader Initialized")
        print(f"   Host: {self.host}:{self.port}")
        print(f"   Client ID: {self.client_id}")

    def connect(self):
        """Connect to IBKR TWS/Gateway"""
        try:
            from ib_insync import IB
            import asyncio
            import time

            # Fix: Set up event loop properly before creating IB
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, create one
                if asyncio.get_event_loop().is_closed():
                    asyncio.set_event_loop(asyncio.new_event_loop())
                loop = asyncio.get_event_loop()

                # Run in thread-safe way
                import threading

                def run_connection():
                    ib = IB()
                    ib.connect(self.host, self.port, clientId=self.client_id)
                    return ib

                self.ib = IB()
                self.ib.connect(self.host, self.port, clientId=self.client_id)
                time.sleep(1)

            if self.ib.isConnected():
                self.is_connected = True
                print("✅ Connected to IBKR TWS/Gateway")

                try:
                    # Try to get account info
                    accounts = self.ib.managedAccounts()
                    if accounts:
                        print(f"✅ Account Connected: {accounts[0]}")
                    else:
                        print("✅ Connected to IBKR (Account info pending)")
                except:
                    print("✅ Connected to IBKR (Account info unavailable)")

                return True
            else:
                print("❌ Connection failed - TWS/Gateway not responding")
                print("   Make sure TWS/Gateway is running and API is enabled")
                return False

        except ImportError as e:
            print("❌ ib_insync not installed")
            print("   Run: pip install ib_insync")
            return False
        except Exception as e:
            error_msg = str(e)
            if "Connection refused" in error_msg:
                print("❌ Connection refused - TWS/Gateway not running on port 7497")
                print("   Start TWS/Gateway and try again")
            elif "event loop" in error_msg.lower():
                print("❌ Event loop error - retrying...")
                # Try once more with fresh loop
                try:
                    import asyncio
                    asyncio.set_event_loop(asyncio.new_event_loop())
                    self.ib = IB()
                    self.ib.connect(self.host, self.port, clientId=self.client_id)
                    import time
                    time.sleep(1)
                    if self.ib.isConnected():
                        self.is_connected = True
                        print("✅ Connected to IBKR TWS/Gateway (after retry)")
                        return True
                except:
                    pass
                print("❌ Could not establish connection")
            else:
                print(f"❌ Connection error: {error_msg[:80]}")
            return False

    def get_live_price(self, symbol: str):
        """Get live price from IBKR"""
        if not self.is_connected:
            return None

        try:
            from ib_insync import Stock

            contract = Stock(symbol, 'SMART', 'USD')
            ticker = self.ib.reqMktData(contract, '', False, False)

            # Wait for data
            import time
            time.sleep(0.5)

            if ticker.last > 0:
                return {
                    "symbol": symbol,
                    "price": float(ticker.last),
                    "bid": float(ticker.bid) if ticker.bid else None,
                    "ask": float(ticker.ask) if ticker.ask else None,
                    "volume": int(ticker.volume) if ticker.volume else None,
                    "timestamp": datetime.now().isoformat(),
                    "source": "IBKR"
                }
            return None

        except Exception as e:
            print(f"❌ Error getting price for {symbol}: {str(e)[:60]}")
            return None

    def place_buy_order(self, symbol: str, quantity: int, limit_price: float = None):
        """Place BUY order in IBKR account"""
        if not self.is_connected:
            print("❌ Not connected to IBKR")
            return None

        try:
            from ib_insync import Stock, Order

            contract = Stock(symbol, 'SMART', 'USD')

            # Create order
            if limit_price:
                order = Order()
                order.action = "BUY"
                order.totalQuantity = quantity
                order.orderType = "LMT"
                order.lmtPrice = limit_price
            else:
                order = Order()
                order.action = "BUY"
                order.totalQuantity = quantity
                order.orderType = "MKT"

            # Place order
            trade = self.ib.placeOrder(contract, order)

            if trade:
                print(f"✅ BUY Order Placed: {symbol} x{quantity}")
                print(f"   Order ID: {trade.order.permId}")
                print(f"   Status: {trade.orderStatus.status}")

                return {
                    "symbol": symbol,
                    "side": "BUY",
                    "quantity": quantity,
                    "limit_price": limit_price,
                    "order_id": trade.order.permId,
                    "status": trade.orderStatus.status,
                    "timestamp": datetime.now().isoformat(),
                    "source": "IBKR"
                }
            else:
                print(f"❌ Failed to place BUY order for {symbol}")
                return None

        except Exception as e:
            print(f"❌ Error placing BUY order: {str(e)[:100]}")
            return None

    def place_sell_order(self, symbol: str, quantity: int, limit_price: float = None):
        """Place SELL order in IBKR account"""
        if not self.is_connected:
            print("❌ Not connected to IBKR")
            return None

        try:
            from ib_insync import Stock, Order

            contract = Stock(symbol, 'SMART', 'USD')

            # Create order
            if limit_price:
                order = Order()
                order.action = "SELL"
                order.totalQuantity = quantity
                order.orderType = "LMT"
                order.lmtPrice = limit_price
            else:
                order = Order()
                order.action = "SELL"
                order.totalQuantity = quantity
                order.orderType = "MKT"

            # Place order
            trade = self.ib.placeOrder(contract, order)

            if trade:
                print(f"✅ SELL Order Placed: {symbol} x{quantity}")
                print(f"   Order ID: {trade.order.permId}")
                print(f"   Status: {trade.orderStatus.status}")

                return {
                    "symbol": symbol,
                    "side": "SELL",
                    "quantity": quantity,
                    "limit_price": limit_price,
                    "order_id": trade.order.permId,
                    "status": trade.orderStatus.status,
                    "timestamp": datetime.now().isoformat(),
                    "source": "IBKR"
                }
            else:
                print(f"❌ Failed to place SELL order for {symbol}")
                return None

        except Exception as e:
            print(f"❌ Error placing SELL order: {str(e)[:100]}")
            return None

    def get_positions(self):
        """Get all open positions from IBKR"""
        if not self.is_connected:
            return []

        try:
            positions = self.ib.positions()

            if positions:
                print(f"✅ Got {len(positions)} open positions from IBKR")
                return positions
            else:
                print("ℹ️  No open positions")
                return []

        except Exception as e:
            print(f"❌ Error getting positions: {str(e)[:60]}")
            return []

    def sync_positions_to_database(self):
        """Sync IBKR positions to JSON"""
        if not self.is_connected:
            print("❌ Not connected to IBKR")
            return

        try:
            positions = self.get_positions()
            log_file = Path("executed_trades.json")
            trades = []

            if log_file.exists():
                with open(log_file) as f:
                    trades = json.load(f)

            for pos in positions:
                contract = pos.contract
                symbol = contract.symbol

                # Get current price
                price_data = self.get_live_price(symbol)
                current_price = price_data['price'] if price_data else 0

                # Calculate P&L
                pnl = (current_price - pos.avgCost) * pos.position
                pnl_pct = ((current_price - pos.avgCost) / pos.avgCost * 100) if pos.avgCost else 0

                # Log to JSON
                trades.append({
                    "date": datetime.now().date().isoformat(),
                    "time": datetime.now().time().isoformat(),
                    "symbol": symbol,
                    "side": "BUY" if pos.position > 0 else "SELL",
                    "quantity": abs(int(pos.position)),
                    "entry_price": float(pos.avgCost),
                    "current_price": float(current_price),
                    "pnl": float(pnl),
                    "pnl_pct": float(pnl_pct),
                    "status": "OPEN",
                    "source": "IBKR"
                })

                print(f"✅ {symbol}: Synced to JSON")
                print(f"   Entry: ${pos.avgCost:.2f} | Current: ${current_price:.2f}")
                print(f"   P&L: ${pnl:.2f} ({pnl_pct:.2f}%)")

            with open(log_file, "w") as f:
                json.dump(trades, f, indent=2, default=str)

        except Exception as e:
            print(f"⚠️  Error syncing: {str(e)[:60]}")

    def log_trade_to_database(self, trade_data: dict):
        """Log completed trade to JSON with IBKR details"""
        try:
            log_file = Path("executed_trades.json")
            trades = []

            if log_file.exists():
                with open(log_file) as f:
                    trades = json.load(f)

            # Add IBKR source and timestamp
            trade_data["source"] = "IBKR"
            trade_data["date"] = datetime.now().date().isoformat()
            trade_data["time"] = datetime.now().time().isoformat()
            trades.append(trade_data)

            with open(log_file, "w") as f:
                json.dump(trades, f, indent=2, default=str)

            print(f"✅ Trade logged to JSON")
            print(f"   Symbol: {trade_data.get('symbol')}")
            print(f"   Side: {trade_data.get('side')}")
            print(f"   Quantity: {trade_data.get('quantity')}")
            print(f"   Order ID: {trade_data.get('order_id')}")

        except Exception as e:
            print(f"⚠️  Error logging trade: {str(e)[:60]}")

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib:
            self.ib.disconnect()
            self.is_connected = False
            print("✅ Disconnected from IBKR")


def main():
    """Test IBKR Live Trader"""

    print("\n" + "="*80)
    print("🔌 IBKR LIVE TRADER - SETUP & TEST")
    print("="*80)

    trader = IBKRLiveTrader()

    # Try to connect
    if trader.connect():
        print("\n✅ IBKR Connection Successful!")

        # Get live prices
        print("\n📊 Getting live prices from IBKR...")
        symbols = ["AAPL", "NVDA", "TSLA", "SPY"]

        for symbol in symbols:
            price_data = trader.get_live_price(symbol)
            if price_data:
                print(f"   {symbol}: ${price_data['price']:.2f}")

        # Get positions
        print("\n📈 Getting open positions...")
        trader.sync_positions_to_database()

        # Disconnect
        trader.disconnect()

    else:
        print("\n❌ IBKR Connection Failed")
        print("""
To use live trading:
1. Start IBKR TWS or Gateway
2. Enable API connections
3. Set environment variables:
   IBKR_HOST=127.0.0.1
   IBKR_PORT=7497
   IBKR_CLIENT_ID=1
4. Install: pip install ib_insync
        """)


if __name__ == "__main__":
    main()
