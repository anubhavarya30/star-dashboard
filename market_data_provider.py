#!/usr/bin/env python3
"""
Real Market Data Provider
Fetches REAL OHLCV data from multiple sources (not mock/fake)
Yahoo Finance, IBKR, or TradingView APIs
"""
import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class RealMarketDataProvider:
    """Fetch real market data for trading and backtesting"""

    def __init__(self):
        self.symbols = ["GC=F", "AAPL", "NVDA", "TSLA", "SPY"]
        self.data_cache = {}

    def fetch_real_ohlcv(self, symbol: str, period: str = "5d", interval: str = "1h"):
        """
        Fetch REAL OHLCV data from Yahoo Finance

        Args:
            symbol: Trading symbol (GC=F for gold, etc)
            period: Data range (5d, 1mo, 1y, max)
            interval: Candle interval (1h, 1d, etc)

        Returns:
            DataFrame with REAL market data
        """
        try:
            print(f"📊 Fetching REAL data: {symbol} ({period}, {interval})")

            # Fetch from Yahoo Finance
            data = yf.download(
                symbol,
                period=period,
                interval=interval,
                progress=False,
                threads=False
            )

            if data.empty:
                print(f"⚠️  No data found for {symbol}")
                return None

            # Handle MultiIndex columns
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # Verify data integrity
            if len(data) < 10:
                print(f"⚠️  Insufficient data for {symbol} ({len(data)} candles)")
                return None

            print(f"✅ Got {len(data)} candles of REAL data for {symbol}")
            return data

        except Exception as e:
            print(f"❌ Error fetching data for {symbol}: {str(e)[:60]}")
            return None

    def get_ohlcv_dict(self, symbol: str, period: str = "5d", interval: str = "1h") -> dict:
        """Convert DataFrame to OHLCV dict for signal generation"""
        data = self.fetch_real_ohlcv(symbol, period, interval)

        if data is None or data.empty:
            return None

        return {
            'open': data['Open'].values,
            'high': data['High'].values,
            'low': data['Low'].values,
            'close': data['Close'].values,
            'volume': data['Volume'].values if 'Volume' in data.columns else [1] * len(data),
            'timestamps': data.index.tolist(),
            'last_price': float(data['Close'].iloc[-1]),
            'last_update': datetime.now().isoformat()
        }

    def fetch_historical_data(self, symbol: str, start_date: str, end_date: str = None):
        """
        Fetch REAL historical data for backtesting

        Args:
            symbol: Trading symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD), default today

        Returns:
            DataFrame with daily OHLCV
        """
        try:
            print(f"📈 Fetching REAL historical data: {symbol} ({start_date} to {end_date})")

            if end_date is None:
                end_date = datetime.now().strftime("%Y-%m-%d")

            data = yf.download(
                symbol,
                start=start_date,
                end=end_date,
                progress=False,
                threads=False
            )

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            print(f"✅ Got {len(data)} days of REAL historical data for {symbol}")
            return data

        except Exception as e:
            print(f"❌ Error fetching historical data: {str(e)[:60]}")
            return None

    def verify_data_quality(self, data: pd.DataFrame) -> bool:
        """Verify data integrity before using"""
        if data is None or data.empty:
            return False

        # Check for NaN values
        if data.isnull().any().any():
            print(f"⚠️  Warning: Found NaN values in data")

        # Check for data gaps
        if len(data) < 50:
            print(f"⚠️  Warning: Less than 50 candles ({len(data)})")
            return False

        # Check volume
        if data['Volume'].sum() == 0:
            print(f"⚠️  Warning: Zero volume detected")
            return False

        return True

    def get_all_symbols_data(self, period: str = "5d", interval: str = "1h") -> dict:
        """Fetch REAL data for all trading symbols"""
        all_data = {}

        for symbol in self.symbols:
            ohlcv = self.get_ohlcv_dict(symbol, period, interval)
            if ohlcv is not None:
                all_data[symbol] = ohlcv

        return all_data


class IBKRDataProvider:
    """
    Connect to Interactive Brokers for REAL-TIME prices
    (When ready to use actual IBKR connection)
    """

    def __init__(self):
        self.ib_host = os.getenv("IBKR_HOST", "127.0.0.1")
        self.ib_port = int(os.getenv("IBKR_PORT", "7497"))
        self.ib_client_id = int(os.getenv("IBKR_CLIENT_ID", "1"))

    def connect(self):
        """Connect to IBKR TWS/Gateway"""
        try:
            # pip install ib_insync
            from ib_insync import IB, Stock

            self.ib = IB()
            self.ib.connect(self.ib_host, self.ib_port, clientId=self.ib_client_id)
            print(f"✅ Connected to IBKR at {self.ib_host}:{self.ib_port}")
            return True

        except ImportError:
            print("⚠️  ib_insync not installed. Run: pip install ib_insync")
            return False
        except Exception as e:
            print(f"❌ Failed to connect to IBKR: {str(e)}")
            return False

    def get_live_price(self, symbol: str) -> float:
        """Get REAL LIVE price from IBKR"""
        try:
            from ib_insync import Stock

            contract = Stock(symbol, 'SMART', 'USD')
            ticker = self.ib.reqMktData(contract, '', False, False)
            self.ib.sleep(0.1)

            if ticker.last > 0:
                return float(ticker.last)
            else:
                return None

        except Exception as e:
            print(f"❌ Error getting live price: {str(e)[:60]}")
            return None

    def get_historical_data(self, symbol: str, duration: str = "1 Y", bar_size: str = "1 day"):
        """Get REAL historical data from IBKR"""
        try:
            from ib_insync import Stock

            contract = Stock(symbol, 'SMART', 'USD')
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='MIDPOINT',
                useRTH=True
            )

            df = pd.DataFrame(bars)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            return df

        except Exception as e:
            print(f"❌ Error getting IBKR historical data: {str(e)[:60]}")
            return None


def main():
    """Test real data fetching"""
    print("\n" + "="*80)
    print("🌍 REAL MARKET DATA PROVIDER TEST")
    print("="*80 + "\n")

    provider = RealMarketDataProvider()

    # Test 1: Fetch current data
    print("1️⃣  Fetching REAL current data...")
    data = provider.get_all_symbols_data(period="5d", interval="1h")

    for symbol, ohlcv in data.items():
        if ohlcv:
            print(f"   ✅ {symbol}: ${ohlcv['last_price']:.2f} (Updated: {ohlcv['last_update']})")

    # Test 2: Fetch historical data
    print("\n2️⃣  Fetching REAL historical data for backtesting...")
    hist_data = provider.fetch_historical_data("GC=F", start_date="2023-01-01", end_date="2024-01-01")

    if hist_data is not None:
        print(f"   ✅ Gold: {len(hist_data)} days of REAL data")
        print(f"      Date range: {hist_data.index[0].date()} to {hist_data.index[-1].date()}")
        print(f"      Price range: ${hist_data['Low'].min():.2f} to ${hist_data['High'].max():.2f}")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
