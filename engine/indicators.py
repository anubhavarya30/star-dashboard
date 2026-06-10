"""
Technical Indicators for Algorithmic Trading
RSI, MACD, EMA, ATR, Bollinger Bands
"""
import pandas as pd
import numpy as np


class Indicators:
    """Calculate technical indicators"""

    @staticmethod
    def rsi(prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index)"""
        if len(prices) < period + 1:
            return 50.0

        deltas = prices.diff()
        seed = deltas[:period + 1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period

        if down == 0:
            return 100.0 if up > 0 else 50.0

        rs = up / down
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return float(rsi)

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Calculate ATR (Average True Range)"""
        if len(high) < period:
            return 0.0

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean()
        return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0

    @staticmethod
    def ema(prices: pd.Series, period: int = 20) -> float:
        """Calculate EMA (Exponential Moving Average)"""
        if len(prices) < period:
            return float(prices.iloc[-1])

        ema = prices.ewm(span=period, adjust=False).mean()
        return float(ema.iloc[-1])

    @staticmethod
    def macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        if len(prices) < slow:
            return {"macd": 0, "signal": 0, "histogram": 0}

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
    def bollinger_bands(prices: pd.Series, period: int = 20, std_dev: int = 2) -> dict:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return {"upper": 0, "middle": 0, "lower": 0}

        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)

        return {
            "upper": float(upper.iloc[-1]) if not pd.isna(upper.iloc[-1]) else 0,
            "middle": float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else 0,
            "lower": float(lower.iloc[-1]) if not pd.isna(lower.iloc[-1]) else 0
        }

    @staticmethod
    def volume_ma(volumes: pd.Series, period: int = 20) -> float:
        """Calculate Volume Moving Average"""
        if len(volumes) < period:
            return float(volumes.iloc[-1]) if len(volumes) > 0 else 0

        vol_ma = volumes.rolling(window=period).mean()
        return float(vol_ma.iloc[-1])
