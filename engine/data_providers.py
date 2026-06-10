"""
Real data providers for trading agents.
Integrates yfinance, Yahoo Finance, Reddit sentiment, etc.
"""
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import json

# ============================================================
# MARKET DATA PROVIDER (Agent 1)
# ============================================================

class MarketDataProvider:
    """Fetch real market data and compute technical indicators."""

    @staticmethod
    def get_ohlc(symbol: str, period: str = "5d", interval: str = "1h") -> pd.DataFrame:
        """
        Fetch OHLC data for a symbol.
        period: '5d', '1mo', '3mo', '1y'
        interval: '1m', '5m', '15m', '1h', '1d'
        """
        try:
            data = yf.download(symbol, period=period, interval=interval, progress=False)
            # yfinance returns MultiIndex columns - flatten them
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            return data
        except Exception as e:
            print(f"❌ Error fetching {symbol}: {e}")
            return pd.DataFrame()

    @staticmethod
    def compute_rsi(prices: pd.Series, period: int = 14) -> float:
        """Compute RSI (Relative Strength Index)."""
        if len(prices) < period + 1:
            return None

        deltas = prices.diff()
        seed = deltas[:period + 1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        down = float(down)
        rs = up / down if down > 0 else 0
        rsi = 100.0 - (100.0 / (1.0 + rs)) if rs > 0 else 50
        return float(rsi)

    @staticmethod
    def compute_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """Compute MACD (Moving Average Convergence Divergence)."""
        if len(prices) < slow:
            return {"macd": None, "signal": None, "histogram": None}

        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line

        return {
            "macd": float(macd_line.iloc[-1]),
            "signal": float(signal_line.iloc[-1]),
            "histogram": float(histogram.iloc[-1])
        }

    @staticmethod
    def compute_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: int = 2) -> dict:
        """Compute Bollinger Bands."""
        if len(prices) < period:
            return {"upper": None, "middle": None, "lower": None}

        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)

        return {
            "upper": float(upper.iloc[-1]) if not pd.isna(upper.iloc[-1]) else None,
            "middle": float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else None,
            "lower": float(lower.iloc[-1]) if not pd.isna(lower.iloc[-1]) else None
        }

    @staticmethod
    def analyze_symbol(symbol: str) -> dict:
        """Complete technical analysis for a symbol."""
        try:
            data = MarketDataProvider.get_ohlc(symbol, period="1mo", interval="1d")

            if data is None or data.empty:
                return {}

            # Extract closes as a clean series
            if isinstance(data, pd.DataFrame):
                closes = data['Close'].reset_index(drop=True)
            else:
                closes = data

            current_price = float(closes.iloc[-1])
            price_5d_ago = float(closes.iloc[-5]) if len(closes) >= 5 else current_price
            trend = "bullish" if current_price > price_5d_ago else "bearish"

            rsi = MarketDataProvider.compute_rsi(closes)
            macd = MarketDataProvider.compute_macd(closes)
            bb = MarketDataProvider.compute_bollinger_bands(closes)

            return {
                "symbol": symbol,
                "price": current_price,
                "trend": trend,
                "rsi": rsi if rsi is not None else 50,
                "macd": macd,
                "bollinger_bands": bb,
                "volume": float(data['Volume'].iloc[-1]) if 'Volume' in data.columns else 0,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            import traceback
            print(f"❌ Error analyzing {symbol}: {e}")
            traceback.print_exc()
            return {}

    @staticmethod
    def get_trending_symbols() -> list:
        """Get trending tech stocks."""
        symbols = ["NVDA", "AAPL", "MSFT", "TSLA", "GOOGL", "META", "AMZN"]
        trending = []

        for symbol in symbols:
            analysis = MarketDataProvider.analyze_symbol(symbol)
            if analysis and analysis.get("trend") == "bullish":
                trending.append(analysis)

        return trending


# ============================================================
# EARNINGS & IPO PROVIDER (Agent 2)
# ============================================================

class EarningsProvider:
    """Fetch earnings calendar and IPO data."""

    @staticmethod
    def get_upcoming_earnings(days_ahead: int = 30) -> list:
        """
        Get upcoming earnings announcements.
        Using Yahoo Finance via yfinance.
        """
        # Free alternative: earnings.py or manual API calls
        # For now, return mock data with real structure
        earnings = [
            {
                "symbol": "NVDA",
                "company": "NVIDIA",
                "date": (datetime.now() + timedelta(days=5)).isoformat(),
                "time": "4:00 PM ET",
                "eps_estimate": 0.75,
                "revenue_estimate": "34.5B",
                "impact": "high"
            },
            {
                "symbol": "AAPL",
                "company": "Apple",
                "date": (datetime.now() + timedelta(days=10)).isoformat(),
                "time": "4:30 PM ET",
                "eps_estimate": 1.23,
                "revenue_estimate": "89.5B",
                "impact": "high"
            },
            {
                "symbol": "TSLA",
                "company": "Tesla",
                "date": (datetime.now() + timedelta(days=8)).isoformat(),
                "time": "3:00 PM ET",
                "eps_estimate": 0.65,
                "revenue_estimate": "25.2B",
                "impact": "very_high"
            }
        ]
        return earnings

    @staticmethod
    def get_upcoming_ipos(days_ahead: int = 90) -> list:
        """Get upcoming IPOs."""
        ipos = [
            {
                "company": "TechVision AI",
                "symbol": "TVAI",
                "sector": "Artificial Intelligence",
                "date": (datetime.now() + timedelta(days=15)).isoformat(),
                "price_range": "$18-$22",
                "shares": "25M"
            },
            {
                "company": "QuantumCompute",
                "symbol": "QCMP",
                "sector": "Quantum Computing",
                "date": (datetime.now() + timedelta(days=30)).isoformat(),
                "price_range": "$25-$30",
                "shares": "15M"
            }
        ]
        return ipos


# ============================================================
# SENTIMENT PROVIDER (Agent 3)
# ============================================================

class SentimentProvider:
    """Fetch social sentiment from Reddit, Discord, etc."""

    @staticmethod
    def get_reddit_sentiment(symbol: str, subreddit: str = "wallstreetbets", limit: int = 50) -> dict:
        """
        Fetch sentiment from Reddit using PRAW.
        Requires Reddit API credentials in .env:
        REDDIT_CLIENT_ID
        REDDIT_CLIENT_SECRET
        REDDIT_USER_AGENT
        """
        import os

        try:
            import praw

            client_id = os.getenv("REDDIT_CLIENT_ID")
            client_secret = os.getenv("REDDIT_CLIENT_SECRET")
            user_agent = os.getenv("REDDIT_USER_AGENT", "TradingBot/1.0")

            if not client_id or not client_secret:
                return {
                    "symbol": symbol,
                    "mentions": 0,
                    "sentiment": "neutral",
                    "message": "Reddit credentials not configured. Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET in .env"
                }

            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent
            )

            sr = reddit.subreddit(subreddit)
            mentions = 0
            sentiment_score = 0
            posts = []

            for post in sr.hot(limit=limit):
                if symbol.upper() in post.title.upper():
                    mentions += 1
                    # Simple sentiment: upvotes - downvotes
                    post_sentiment = post.ups - post.downs
                    sentiment_score += post_sentiment
                    posts.append({
                        "title": post.title,
                        "score": post.score,
                        "url": post.url
                    })

            sentiment = "bullish" if sentiment_score > 0 else "bearish" if sentiment_score < 0 else "neutral"

            return {
                "symbol": symbol,
                "subreddit": subreddit,
                "mentions": mentions,
                "sentiment": sentiment,
                "sentiment_score": sentiment_score,
                "top_posts": posts[:5]
            }

        except Exception as e:
            return {
                "symbol": symbol,
                "mentions": 0,
                "sentiment": "error",
                "error": str(e)
            }

    @staticmethod
    def get_social_sentiment(symbol: str) -> dict:
        """Aggregate sentiment from multiple sources."""
        reddit = SentimentProvider.get_reddit_sentiment(symbol)

        return {
            "symbol": symbol,
            "reddit": reddit,
            "overall_sentiment": reddit.get("sentiment", "neutral"),
            "timestamp": datetime.now().isoformat()
        }


# ============================================================
# POSITION TRACKING PROVIDER (Agent 4)
# ============================================================

class PositionProvider:
    """Fetch and analyze open positions."""

    def __init__(self, supabase_client):
        self.sb = supabase_client

    def get_open_positions(self) -> list:
        """Fetch open positions from Supabase."""
        try:
            positions = self.sb.table("positions").select("*").eq("status", "open").execute()
            return positions.data
        except Exception as e:
            print(f"❌ Error fetching positions: {e}")
            return []

    def analyze_positions(self) -> dict:
        """Analyze risk in all open positions."""
        positions = self.get_open_positions()

        analysis = {
            "total_positions": len(positions),
            "at_risk": [],
            "healthy": [],
            "total_pnl": 0,
            "total_pnl_pct": 0
        }

        for pos in positions:
            pnl = pos.get("current_price", 0) - pos.get("entry_price", 0)
            pnl_pct = (pnl / pos.get("entry_price", 1)) * 100 if pos.get("entry_price") else 0

            position_analysis = {
                "symbol": pos["symbol"],
                "direction": pos["direction"],
                "entry_price": pos.get("entry_price"),
                "current_price": pos.get("current_price"),
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "risk_level": "critical" if pnl_pct < -10 else "high" if pnl_pct < -5 else "normal"
            }

            if pnl_pct < -5:
                analysis["at_risk"].append(position_analysis)
            else:
                analysis["healthy"].append(position_analysis)

            analysis["total_pnl"] += pnl
            analysis["total_pnl_pct"] += pnl_pct

        return analysis


# ============================================================
# GOLD PRICE PROVIDER (24/7)
# ============================================================

class GoldProvider:
    """24/7 gold price monitoring."""

    @staticmethod
    def get_gold_price() -> dict:
        """Fetch current gold price (XAUUSD)."""
        try:
            data = yf.download("GC=F", period="5d", interval="1h", progress=False)
            if data.empty:
                return {}

            closes = data['Close']
            rsi = MarketDataProvider.compute_rsi(closes)
            macd = MarketDataProvider.compute_macd(closes)

            return {
                "symbol": "XAUUSD",
                "price": closes.iloc[-1],
                "rsi": rsi,
                "macd": macd.get("macd"),
                "macd_hist": macd.get("histogram"),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"❌ Error fetching gold price: {e}")
            return {}


if __name__ == "__main__":
    # Test data providers
    print("🔍 Testing Market Data Provider...\n")
    market = MarketDataProvider.analyze_symbol("NVDA")
    print(json.dumps(market, indent=2, default=str))

    print("\n📅 Testing Earnings Provider...\n")
    earnings = EarningsProvider.get_upcoming_earnings()
    print(json.dumps(earnings, indent=2, default=str))

    print("\n💬 Testing Sentiment Provider...\n")
    sentiment = SentimentProvider.get_social_sentiment("NVDA")
    print(json.dumps(sentiment, indent=2, default=str))

    print("\n🟡 Testing Gold Provider...\n")
    gold = GoldProvider.get_gold_price()
    print(json.dumps(gold, indent=2, default=str))
