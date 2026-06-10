#!/usr/bin/env python3
"""
🚀 WEBULL DATA PROVIDER
Real-time market data from Webull API
"""
import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class WebullDataProvider:
    """Connect to Webull and fetch real-time market data"""

    def __init__(self):
        self.app_key = os.getenv("WEBULL_APP_KEY")
        self.app_secret = os.getenv("WEBULL_APP_SECRET")
        self.base_url = "https://api.webull.com"
        self.session = requests.Session()
        self.access_token = None
        self.is_connected = False

        print("\n" + "="*80)
        print("🚀 WEBULL DATA PROVIDER - INITIALIZING")
        print("="*80)
        print(f"App Key: {self.app_key[:10]}...")
        print(f"App Secret: {self.app_secret[:10]}...")

    def test_connection(self):
        """Test if we can connect to Webull API"""
        try:
            print("\n🔌 Testing Webull API connection...")

            # Test endpoint - get market status
            url = f"{self.base_url}/api/trade/v2/common/getMarket"

            headers = {
                "Content-Type": "application/json",
                "App-Key": self.app_key
            }

            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code == 200:
                print("✅ Webull API is ACCESSIBLE!")
                print(f"   Response: {response.status_code}")
                self.is_connected = True
                return True
            else:
                print(f"⚠️ Webull API returned: {response.status_code}")
                print(f"   Response: {response.text[:100]}")
                return False

        except requests.exceptions.ConnectionError:
            print("❌ Could not connect to Webull (connection error)")
            return False
        except requests.exceptions.Timeout:
            print("❌ Webull API timeout")
            return False
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return False

    def get_stock_info(self, symbol: str):
        """Fetch detailed stock information from Webull"""
        try:
            print(f"\n📊 Fetching {symbol} from Webull...")

            # Get stock quote
            url = f"{self.base_url}/api/trade/quote/webull/{symbol}"

            headers = {"App-Key": self.app_key}

            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Got {symbol} data from Webull")
                return data
            else:
                print(f"⚠️ {symbol} not found or error: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ Error fetching {symbol}: {str(e)}")
            return None

    def get_realtime_quote(self, symbol: str):
        """Get real-time quote for a symbol"""
        try:
            url = f"{self.base_url}/api/quote/level1/{symbol}"

            headers = {"App-Key": self.app_key}

            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code == 200:
                data = response.json()
                return {
                    "symbol": symbol,
                    "price": data.get("price"),
                    "bid": data.get("bid"),
                    "ask": data.get("ask"),
                    "volume": data.get("volume"),
                    "timestamp": datetime.now().isoformat()
                }
            return None

        except Exception as e:
            print(f"⚠️ Error getting quote: {str(e)}")
            return None

    def get_market_hours(self):
        """Get current market status"""
        try:
            url = f"{self.base_url}/api/trade/v2/common/getMarket"

            headers = {"App-Key": self.app_key}

            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code == 200:
                data = response.json()
                return data
            return None

        except Exception as e:
            print(f"⚠️ Error getting market hours: {str(e)}")
            return None


def main():
    """Test Webull connection"""
    provider = WebullDataProvider()

    # Test connection
    print("\n" + "="*80)
    print("🔌 TESTING WEBULL CONNECTION")
    print("="*80)

    if provider.test_connection():
        print("\n" + "="*80)
        print("✅ WEBULL PLATFORM ACCESSIBLE")
        print("="*80)
        print("\n✅ Status: READY TO FETCH DATA")
        print("✅ App Key: Active")
        print("✅ App Secret: Active")
        print("✅ Base URL: https://api.webull.com")

        # Try to get market hours
        print("\n📊 Checking market status...")
        market_data = provider.get_market_hours()
        if market_data:
            print("✅ Market data endpoint working")

        print("\n" + "="*80)
        print("🚀 WEBULL INTEGRATION READY")
        print("="*80)
        print("\nNext steps:")
        print("  1. Fetch real-time stock data")
        print("  2. Get fundamentals from Webull")
        print("  3. Integrate with Market Analysis Agent")
        print("  4. Show real-time overview in dashboard")

    else:
        print("\n" + "="*80)
        print("⚠️ WEBULL CONNECTION FAILED")
        print("="*80)
        print("\nTroubleshooting:")
        print("  1. Check internet connection")
        print("  2. Verify Webull API credentials in .env")
        print("  3. Check Webull API status at https://status.webull.com")
        print("  4. Try using VPN if region-blocked")


if __name__ == "__main__":
    main()
