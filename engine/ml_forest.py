"""
STAR — Random Forest signal (consensus + confidence).

WHAT THIS IS
------------
A bunch of decision trees (default 200), each trained on a random slice of
history + a random subset of signals, so they each make different mistakes.
On every new setup all trees vote UP or DOWN; the majority wins (CONSENSUS)
and the vote split is the CONVICTION (CONFIDENCE).

  - consensus()  -> majority vote (1 = up / long, 0 = down / flat)
  - confidence() -> the vote share (e.g. 0.90 = 90/100 trees agree = size up;
                    0.55 = a coin flip = sit out or size small)

HONESTY (project rule — see CLAUDE.md)
-------------------------------------
- NO look-ahead. Validation is WALK-FORWARD: train only on bars BEFORE the bar
  we predict (sklearn TimeSeriesSplit). A model that "predicts" the past it was
  trained on is a lie; this reports OUT-OF-SAMPLE accuracy only.
- The target is the SIGN of the forward N-day return. Features are all computed
  from data available AT the bar (shifted), never the future.
- This module does NOT place trades and is NOT wired to the live desk. It writes
  a verdict. Wiring to real money happens ONLY after it proves out, same bar as
  every other STAR strategy (out-of-sample edge > threshold).

VERDICT RULE (decided upfront, no moving goalposts)
---------------------------------------------------
Out-of-sample directional accuracy > 55% AND simulated profit-factor > 1.3
across the walk-forward test folds  ->  edge is real, promote to forward-test.
Below either  ->  NO EDGE, do not trade it.

CLI
---
  ./venv/bin/python3 engine/ml_forest.py train  NVDA        # fit + walk-forward verdict
  ./venv/bin/python3 engine/ml_forest.py signal NVDA        # consensus + confidence NOW
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit

# ---- config ---------------------------------------------------------------
N_TREES = 200
FWD_DAYS = 5           # predict sign of the return this many bars ahead
CONF_TRADE = 0.58      # below this vote-share the forest "isn't sure" -> sit out
ACC_THRESHOLD = 0.55   # verdict: out-of-sample directional accuracy must beat this
PF_THRESHOLD = 1.30    # verdict: simulated profit-factor must beat this
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "models")

FEATURES = [
    "ret_1", "ret_3", "ret_5", "ret_10",
    "rsi", "ema_ratio_20", "ema_ratio_50",
    "macd_hist", "atr_pct", "bb_pos", "vol_ratio", "mom_20",
]


# ---- data + features (all vectorised, all shifted = no look-ahead) ---------
def _bars(symbol: str, period: str = "5y") -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("yfinance not available")
    h = yf.Ticker(symbol).history(period=period, interval="1d")
    if h is None or len(h) < 260:
        raise RuntimeError(f"not enough history for {symbol} ({0 if h is None else len(h)} bars)")
    return h


def _features(h: pd.DataFrame) -> pd.DataFrame:
    c, hi, lo, v = h["Close"], h["High"], h["Low"], h["Volume"]
    f = pd.DataFrame(index=h.index)

    f["ret_1"] = c.pct_change(1)
    f["ret_3"] = c.pct_change(3)
    f["ret_5"] = c.pct_change(5)
    f["ret_10"] = c.pct_change(10)

    # RSI (Wilder, vectorised over the whole series)
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    f["rsi"] = (100 - 100 / (1 + rs)).fillna(50)

    ema20 = c.ewm(span=20, adjust=False).mean()
    ema50 = c.ewm(span=50, adjust=False).mean()
    f["ema_ratio_20"] = c / ema20 - 1
    f["ema_ratio_50"] = c / ema50 - 1

    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    f["macd_hist"] = (macd - macd.ewm(span=9, adjust=False).mean()) / c

    tr = pd.concat([hi - lo, (hi - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)
    f["atr_pct"] = tr.rolling(14).mean() / c

    mid = c.rolling(20).mean()
    std = c.rolling(20).std()
    f["bb_pos"] = (c - mid) / (2 * std).replace(0, np.nan)

    f["vol_ratio"] = v / v.rolling(20).mean()
    f["mom_20"] = c / c.shift(20) - 1

    # every feature reads data AT the bar; shift by 1 so a row only ever uses
    # information available at the PRIOR close before we act on it.
    return f[FEATURES].shift(1)


def _target(h: pd.DataFrame, fwd: int = FWD_DAYS) -> pd.Series:
    fwd_ret = h["Close"].shift(-fwd) / h["Close"] - 1
    return (fwd_ret > 0).astype(int), fwd_ret


def _dataset(symbol: str):
    h = _bars(symbol)
    X = _features(h)
    y, fwd_ret = _target(h)
    df = X.copy()
    df["_y"] = y
    df["_fwd_ret"] = fwd_ret
    df = df.dropna()
    return df, h


# ---- walk-forward validation (the honest number) --------------------------
def walk_forward(symbol: str, folds: int = 5) -> dict:
    df, _ = _dataset(symbol)
    X = df[FEATURES].values
    y = df["_y"].values
    fwd = df["_fwd_ret"].values

    tscv = TimeSeriesSplit(n_splits=folds)
    correct = total = 0
    wins = losses = 0.0
    traded = 0
    for tr_idx, te_idx in tscv.split(X):
        clf = RandomForestClassifier(
            n_estimators=N_TREES, max_depth=6, min_samples_leaf=20,
            random_state=42, n_jobs=-1,
        )
        clf.fit(X[tr_idx], y[tr_idx])
        proba = clf.predict_proba(X[te_idx])
        # vote share of the winning side = confidence
        conf = proba.max(axis=1)
        vote = proba.argmax(axis=1)
        for j, i in enumerate(te_idx):
            if conf[j] < CONF_TRADE:
                continue  # forest not sure -> sit out
            traded += 1
            up = vote[j] == 1
            r = fwd[i] if up else -fwd[i]  # long if up-vote, short if down-vote
            correct += 1 if r > 0 else 0
            total += 1
            if r > 0:
                wins += r
            else:
                losses += -r

    acc = correct / total if total else 0.0
    pf = wins / losses if losses else (float("inf") if wins else 0.0)
    edge = acc > ACC_THRESHOLD and pf > PF_THRESHOLD
    return {
        "symbol": symbol.upper(),
        "samples": int(len(df)),
        "traded": traded,
        "oos_accuracy": round(acc, 4),
        "profit_factor": round(pf, 3) if pf != float("inf") else None,
        "conf_gate": CONF_TRADE,
        "verdict": "EDGE — promote to forward-test" if edge else "NO EDGE — do not trade",
        "rule": f"acc>{ACC_THRESHOLD} AND pf>{PF_THRESHOLD}",
    }


# ---- fit on ALL history + persist, then read live signal ------------------
def _fit_full(symbol: str):
    df, _ = _dataset(symbol)
    clf = RandomForestClassifier(
        n_estimators=N_TREES, max_depth=6, min_samples_leaf=20,
        random_state=42, n_jobs=-1,
    )
    clf.fit(df[FEATURES].values, df["_y"].values)
    return clf


def signal(symbol: str) -> dict:
    """Consensus + confidence for the MOST RECENT bar. Honest: this uses a model
    fit on all history, so treat it as a live read, NOT a backtest number."""
    clf = _fit_full(symbol)
    h = _bars(symbol)
    x = _features(h).iloc[[-1]].dropna()
    if x.empty:
        return {"symbol": symbol.upper(), "error": "not enough recent data"}
    proba = clf.predict_proba(x.values)[0]
    up = float(proba[1])
    conf = max(up, 1 - up)
    vote = "UP / LONG" if up >= 0.5 else "DOWN / FLAT"
    trees_agree = int(round(conf * N_TREES))
    if conf < CONF_TRADE:
        action = "SIT OUT (forest not sure)"
    elif conf >= 0.75:
        action = "SIZE UP (strong conviction)"
    else:
        action = "SIZE SMALL"
    return {
        "symbol": symbol.upper(),
        "consensus": vote,
        "confidence": round(conf, 3),
        "trees_agree": f"{trees_agree}/{N_TREES}",
        "prob_up": round(up, 3),
        "action": action,
    }


def _save_verdict(v: dict):
    os.makedirs(MODEL_DIR, exist_ok=True)
    path = os.path.join(MODEL_DIR, f"forest_{v['symbol']}.json")
    with open(path, "w") as fh:
        json.dump(v, fh, indent=2)
    return path


if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "train").lower()
    sym = sys.argv[2] if len(sys.argv) > 2 else "NVDA"
    if cmd == "signal":
        print(json.dumps(signal(sym), indent=2))
    else:
        v = walk_forward(sym)
        p = _save_verdict(v)
        print(json.dumps(v, indent=2))
        print(f"\nverdict saved -> {p}")
