#!/usr/bin/env python3
"""
STAR agents — Supabase-free. Real signals from the clean strategy libs.

STAR is the CEO. Supporting agents each analyze a symbol from one angle using
REAL market data (yfinance via market_data_provider) and real indicators; STAR
aggregates their votes into a final decision. No fabricated sentiment scores —
the News agent reports real headline counts, not an invented mood number.

Output is plain JSON (no DB/Supabase dependency) so the terminal can render it.
"""
from datetime import datetime, timezone

import pandas as pd
from market_data_provider import RealMarketDataProvider
from trading_signals import VolumeWeightedRSISystem
from indicators import Indicators
from position_manager import PositionManager

MDP = RealMarketDataProvider()
SIG = VolumeWeightedRSISystem()
IND = Indicators()


def _series(ohlcv):
    return (pd.Series(ohlcv["close"]), pd.Series(ohlcv["high"]),
            pd.Series(ohlcv["low"]), pd.Series(ohlcv["volume"]))


def analyze_symbol(symbol, account_size=485.0, risk_pct=0.02):
    """Run all agents on one symbol and let STAR decide. Returns a dict."""
    # VW-RSI needs 200 bars (volume_period=200); fetch ~1y of daily data
    ohlcv = MDP.get_ohlcv_dict(symbol, period="1y", interval="1d")
    if not ohlcv or len(ohlcv.get("close", [])) < 30:
        return {"symbol": symbol, "error": "insufficient data", "agents": [], "star": None}

    closes, highs, lows, vols = _series(ohlcv)
    price = float(closes.iloc[-1])
    rsi = IND.rsi(closes, 14)
    ema20 = IND.ema(closes, 20)
    ema50 = IND.ema(closes, 50)
    atr = IND.atr(highs, lows, closes, 14)
    macd = IND.macd(closes)
    vol_ma = IND.volume_ma(vols, 20)
    cur_vol = float(vols.iloc[-1])

    agents = []

    # --- Agent 1: Technical (the real VW-RSI strategy) ---
    sig = SIG.generate_signal(ohlcv)
    agents.append({
        "agent": "Technical (VW-RSI)",
        "vote": sig["action"], "confidence": round(sig.get("confidence", 0), 2),
        "detail": sig.get("reason", ""),
    })

    # --- Agent 2: Trend (EMA structure + MACD) ---
    trend_up = price > ema20 > ema50
    trend_dn = price < ema20 < ema50
    macd_up = macd["histogram"] > 0
    tvote = "BUY" if (trend_up and macd_up) else "SELL" if (trend_dn and not macd_up) else "HOLD"
    tconf = 0.7 if (trend_up and macd_up) or (trend_dn and not macd_up) else 0.4
    agents.append({
        "agent": "Trend (EMA/MACD)", "vote": tvote, "confidence": tconf,
        "detail": f"px {price:.2f} vs EMA20 {ema20:.2f}/EMA50 {ema50:.2f}; MACD hist {macd['histogram']:.2f}",
    })

    # --- Agent 3: Momentum (RSI + volume) ---
    vol_ratio = cur_vol / vol_ma if vol_ma else 1
    if rsi < 35 and vol_ratio > 1:
        mvote, mconf = "BUY", 0.65
    elif rsi > 70:
        mvote, mconf = "SELL", 0.6
    else:
        mvote, mconf = "HOLD", 0.4
    agents.append({
        "agent": "Momentum (RSI/Vol)", "vote": mvote, "confidence": mconf,
        "detail": f"RSI {rsi:.1f}, volume {vol_ratio:.2f}x avg",
    })

    # --- Agent 4: Risk (ATR + position sizing, NOT a directional vote) ---
    atr_pct = (atr / price * 100) if price else 0
    pm = PositionManager(account_size, risk_pct)
    stop = price - 1.2 * atr
    size = pm.calculate_position_size(price, stop)
    agents.append({
        "agent": "Risk (ATR/sizing)", "vote": "INFO", "confidence": None,
        "detail": f"ATR {atr_pct:.1f}% of price; max risk ${account_size*risk_pct:.2f} → "
                  f"~{size.get('shares', size.get('quantity', 0))} shares, stop {stop:.2f}",
    })

    # --- Agent 5: News (REAL headline count, no fabricated sentiment) ---
    try:
        import yfinance as yf
        n = len(yf.Ticker(symbol).news or [])
    except Exception:
        n = None
    agents.append({
        "agent": "News (headline flow)", "vote": "INFO", "confidence": None,
        "detail": f"{n} recent headlines" if n is not None else "headlines unavailable",
    })

    # --- STAR (CEO): CALIBRATED consensus ----------------------------------
    # Only Technical/Trend/Momentum cast directional votes (Risk/News are INFO).
    # A VW-RSI "SELL" is an EXIT/overbought signal, not a short-entry — it is
    # HALF-weighted toward bearish. Score is divided by the FULL count of
    # directional agents, so a single lone voter cannot produce false 100%
    # conviction; abstaining (HOLD) agents drag the result toward neutral.
    DIRECTIONAL = ("Technical (VW-RSI)", "Trend (EMA/MACD)", "Momentum (RSI/Vol)")
    score = 0.0
    bull = bear = 0
    exit_flag = False
    for a in agents:
        if a["agent"] not in DIRECTIONAL:
            continue
        cf = a.get("confidence") or 0
        if a["vote"] == "BUY":
            score += cf; bull += 1
        elif a["vote"] == "SELL":
            is_exit = str(a.get("detail", "")).strip().lower().startswith("exit")
            if a["agent"].startswith("Technical") and is_exit:
                score -= cf * 0.5; exit_flag = True   # exit signal, half weight
            else:
                score -= cf
            bear += 1
    net = round(score / len(DIRECTIONAL), 3)  # -1..+1
    if net > 0.25:
        decision, conf = "BUY", round(min(net, 1), 2)
    elif net < -0.25:
        decision, conf = "SELL", round(min(-net, 1), 2)
    else:
        decision, conf = "HOLD", round(1 - min(abs(net) / 0.25, 1) * 0.4, 2)
    reason = (f"{bull} bullish / {bear} bearish of {len(DIRECTIONAL)} agents; net {net:+.2f}"
              + ("; VW-RSI exit-signal half-weighted" if exit_flag else ""))

    return {
        "symbol": symbol, "price": round(price, 2), "rsi": round(rsi, 1),
        "agents": agents,
        "star": {"decision": decision, "confidence": round(conf, 2), "net_score": round(net, 2),
                 "reason": reason},
    }


def run(symbols=("AAPL", "NVDA", "TSLA", "AMZN", "MSFT")):
    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "results": [analyze_symbol(s) for s in symbols],
    }


if __name__ == "__main__":
    import json
    out = run()
    for r in out["results"]:
        if r.get("star"):
            print(f"{r['symbol']:6} → STAR {r['star']['decision']:4} ({r['star']['confidence']}) "
                  f"| {r['star']['reason']}")
        else:
            print(f"{r['symbol']:6} → {r.get('error')}")
