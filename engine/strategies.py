"""
strategies.py
=============
Vectorized technical trading strategies (pandas / numpy only).

Design contract
---------------
Every strategy function accepts an OHLCV DataFrame with (at least) the columns:
    ['open', 'high', 'low', 'close', 'volume']
indexed by a DatetimeIndex (ascending), and returns the SAME DataFrame with
indicator columns appended plus a discrete `signal` column in {-1, 0, +1}:
    +1 -> long bias / long entry
     0 -> flat / no edge
    -1 -> short bias / short entry

All math is fully vectorized (no Python loops over rows). A `master_signals`
aggregator blends every strategy into a composite score and an ATR-based
entry/stop/target plan so that NO signal is ever produced without a defined exit.

Author: Star (CEO orchestrator)
"""
from __future__ import annotations
import numpy as np
import pandas as pd

__all__ = [
    "rsi", "macd", "bollinger", "atr", "ema", "vwap", "obv",
    "rsi_mean_reversion", "macd_momentum", "bollinger_breakout",
    "ema_crossover", "volume_weighted_trend", "master_signals",
]

# --------------------------------------------------------------------------- #
#  Core indicator primitives (vectorized)
# --------------------------------------------------------------------------- #
def _wilder_rma(series: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing (RMA) implemented via EWM for speed."""
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    rs = _wilder_rma(gain, period) / _wilder_rma(loss, period).replace(0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(close: pd.Series, period: int = 20, num_std: float = 2.0):
    mid = close.rolling(period, min_periods=period).mean()
    sd = close.rolling(period, min_periods=period).std(ddof=0)
    upper = mid + num_std * sd
    lower = mid - num_std * sd
    width = (upper - lower) / mid.replace(0, np.nan)
    return mid, upper, lower, width


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift()
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return _wilder_rma(tr, period)


def vwap(df: pd.DataFrame, window: int | None = None) -> pd.Series:
    """Rolling VWAP. If window is None -> cumulative (session) VWAP."""
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical * df["volume"]
    if window is None:
        return pv.cumsum() / df["volume"].cumsum().replace(0, np.nan)
    return (pv.rolling(window, min_periods=1).sum()
            / df["volume"].rolling(window, min_periods=1).sum().replace(0, np.nan))


def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume (vectorized)."""
    direction = np.sign(df["close"].diff()).fillna(0.0)
    return (direction * df["volume"]).cumsum()


# --------------------------------------------------------------------------- #
#  Strategy 1 — RSI mean-reversion
# --------------------------------------------------------------------------- #
def rsi_mean_reversion(df: pd.DataFrame, period: int = 14,
                       lower: float = 30.0, upper: float = 70.0) -> pd.DataFrame:
    out = df.copy()
    out["rsi"] = rsi(out["close"], period)
    long_entry = out["rsi"] < lower          # oversold -> revert up
    short_entry = out["rsi"] > upper         # overbought -> revert down
    out["signal"] = np.select([long_entry, short_entry], [1, -1], default=0)
    return out


# --------------------------------------------------------------------------- #
#  Strategy 2 — MACD momentum
# --------------------------------------------------------------------------- #
def macd_momentum(df: pd.DataFrame, fast: int = 12, slow: int = 26,
                  signal: int = 9) -> pd.DataFrame:
    out = df.copy()
    macd_line, signal_line, hist = macd(out["close"], fast, slow, signal)
    out["macd"], out["macd_signal"], out["macd_hist"] = macd_line, signal_line, hist
    cross_up = (macd_line > signal_line) & (macd_line.shift() <= signal_line.shift())
    cross_dn = (macd_line < signal_line) & (macd_line.shift() >= signal_line.shift())
    # hold the regime between crosses, anchored by histogram sign
    regime = np.where(macd_line > signal_line, 1, -1)
    out["signal"] = np.select([cross_up, cross_dn], [1, -1], default=regime)
    return out


# --------------------------------------------------------------------------- #
#  Strategy 3 — Bollinger Band breakout
# --------------------------------------------------------------------------- #
def bollinger_breakout(df: pd.DataFrame, period: int = 20,
                       num_std: float = 2.0) -> pd.DataFrame:
    out = df.copy()
    mid, upper, lower, width = bollinger(out["close"], period, num_std)
    out["bb_mid"], out["bb_upper"], out["bb_lower"], out["bb_width"] = mid, upper, lower, width
    long_break = out["close"] > upper        # close above upper band -> breakout long
    short_break = out["close"] < lower       # close below lower band -> breakout short
    out["signal"] = np.select([long_break, short_break], [1, -1], default=0)
    return out


# --------------------------------------------------------------------------- #
#  Strategy 4 — EMA crossover (trend-following)
# --------------------------------------------------------------------------- #
def ema_crossover(df: pd.DataFrame, fast: int = 9, slow: int = 21) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = ema(out["close"], fast)
    out["ema_slow"] = ema(out["close"], slow)
    out["signal"] = np.where(out["ema_fast"] > out["ema_slow"], 1, -1)
    return out


# --------------------------------------------------------------------------- #
#  Strategy 5 — Volume-weighted trend (VWAP + OBV confirmation)
# --------------------------------------------------------------------------- #
def volume_weighted_trend(df: pd.DataFrame, vwap_window: int = 20,
                          obv_span: int = 20) -> pd.DataFrame:
    out = df.copy()
    out["vwap"] = vwap(out, window=vwap_window)
    out["obv"] = obv(out)
    out["obv_ema"] = ema(out["obv"], obv_span)
    price_above = out["close"] > out["vwap"]
    obv_rising = out["obv"] > out["obv_ema"]
    long_sig = price_above & obv_rising
    short_sig = (~price_above) & (~obv_rising)
    out["signal"] = np.select([long_sig, short_sig], [1, -1], default=0)
    return out


# --------------------------------------------------------------------------- #
#  Master aggregator — blend all strategies + ATR-based exit plan
# --------------------------------------------------------------------------- #
STRATEGY_REGISTRY = {
    "rsi_mean_reversion": rsi_mean_reversion,
    "macd_momentum": macd_momentum,
    "bollinger_breakout": bollinger_breakout,
    "ema_crossover": ema_crossover,
    "volume_weighted_trend": volume_weighted_trend,
}


def master_signals(df: pd.DataFrame,
                   weights: dict | None = None,
                   atr_period: int = 14,
                   stop_mult: float = 1.5,
                   target_mult: float = 2.5,
                   threshold: float = 0.30) -> pd.DataFrame:
    """
    Run every strategy, build a weighted composite score in [-1, +1], and attach
    an ATR-based stop/target so each actionable bar carries a defined exit.

    Returns a DataFrame with one column per strategy signal, `composite_score`,
    a discrete `decision` (LONG/SHORT/FLAT), and entry/stop/target columns.
    """
    if weights is None:
        weights = {k: 1.0 for k in STRATEGY_REGISTRY}

    base = df.copy()
    sig_cols = {}
    for name, fn in STRATEGY_REGISTRY.items():
        sig_cols[f"sig_{name}"] = fn(df)["signal"].astype(float)
    sigs = pd.DataFrame(sig_cols, index=df.index)

    w = pd.Series({f"sig_{k}": v for k, v in weights.items()})
    w = w / w.abs().sum()                      # normalize so score in [-1, 1]
    base = pd.concat([base, sigs], axis=1)
    base["composite_score"] = (sigs * w).sum(axis=1)

    base["decision"] = np.select(
        [base["composite_score"] >= threshold, base["composite_score"] <= -threshold],
        ["LONG", "SHORT"], default="FLAT",
    )

    a = atr(df, atr_period)
    base["atr"] = a
    long_mask = base["decision"] == "LONG"
    short_mask = base["decision"] == "SHORT"
    base["entry"] = np.where(base["decision"] != "FLAT", df["close"], np.nan)
    base["stop"] = np.select(
        [long_mask, short_mask],
        [df["close"] - stop_mult * a, df["close"] + stop_mult * a], default=np.nan)
    base["target"] = np.select(
        [long_mask, short_mask],
        [df["close"] + target_mult * a, df["close"] - target_mult * a], default=np.nan)
    rr = (base["target"] - base["entry"]).abs() / (base["entry"] - base["stop"]).abs()
    base["risk_reward"] = rr.round(2)
    return base


# --------------------------------------------------------------------------- #
#  Self-test with synthetic data
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    idx = pd.date_range("2026-01-01", periods=300, freq="h")
    rng = np.random.default_rng(7)
    price = 400 + np.cumsum(rng.normal(0, 0.6, len(idx)))
    demo = pd.DataFrame({
        "open": price + rng.normal(0, 0.2, len(idx)),
        "high": price + np.abs(rng.normal(0.5, 0.3, len(idx))),
        "low": price - np.abs(rng.normal(0.5, 0.3, len(idx))),
        "close": price,
        "volume": rng.integers(1_000, 50_000, len(idx)).astype(float),
    }, index=idx)

    res = master_signals(demo)
    print(res[["close", "composite_score", "decision",
               "entry", "stop", "target", "risk_reward"]].tail(10).to_string())
    print("\nDecision distribution:")
    print(res["decision"].value_counts())
