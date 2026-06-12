#!/usr/bin/env python3
"""
STAR — Backtest engine. Validates a signal on real historical data BEFORE any
money is risked. Built to be honest:

  • NO LOOK-AHEAD: at each bar i the signal sees only data through bar i; entries
    fill at the NEXT bar's open (you can't trade the close you just saw).
  • Realistic exits: stop/target checked intrabar on high/low; gaps fill at open.
  • Costs: commission + slippage (bps) applied to every fill.
  • Risk-based sizing: each trade risks `risk_pct` of current equity (entry→stop).

Reports the metrics that actually matter: win rate, profit factor, expectancy,
max drawdown, Sharpe, and the full equity curve + trade log.
"""
import math
from datetime import datetime, timezone

import pandas as pd
from market_data_provider import RealMarketDataProvider
from trading_signals import VolumeWeightedRSISystem

MDP = RealMarketDataProvider()


def _slice(ohlcv, i):
    return {k: ohlcv[k][: i + 1] for k in ("open", "high", "low", "close", "volume")}


def backtest(symbol, period="2y", starting_equity=10000.0, risk_pct=0.02,
             commission=0.0, slippage_bps=5.0, warmup=205):
    ohlcv = MDP.get_ohlcv_dict(symbol, period=period, interval="1d")
    if not ohlcv or len(ohlcv["close"]) < warmup + 20:
        return {"symbol": symbol.upper(), "error": f"not enough history ({period})",
                "trades": [], "equity_curve": [], "metrics": {}}

    sig = VolumeWeightedRSISystem()
    o, h, l, c = ohlcv["open"], ohlcv["high"], ohlcv["low"], ohlcv["close"]
    ts = ohlcv.get("timestamps") or list(range(len(c)))
    n = len(c)
    slip = slippage_bps / 10000.0

    equity = starting_equity
    pos = None            # {entry, stop, target, shares, entry_i, entry_date}
    trades = []
    curve = []            # (date, equity)

    def dstr(i):
        t = ts[i]
        try:
            return pd.Timestamp(t).strftime("%Y-%m-%d")
        except Exception:
            return str(t)

    pending_entry = None  # signal fires on bar i, we enter at open of i+1

    for i in range(warmup, n):
        # ---- fill a pending entry at THIS bar's open ----
        if pending_entry and pos is None:
            entry = o[i] * (1 + slip)
            stop, target = pending_entry["stop"], pending_entry["target"]
            risk_ps = entry - stop
            if risk_ps > 0:
                shares = int((equity * risk_pct) / risk_ps)
                if shares > 0:
                    equity -= commission
                    pos = {"entry": entry, "stop": stop, "target": target,
                           "shares": shares, "entry_i": i, "entry_date": dstr(i)}
            pending_entry = None

        # ---- manage open position (intrabar stop/target) ----
        if pos:
            exit_price = exit_reason = None
            if l[i] <= pos["stop"]:                       # stop (gap-aware)
                exit_price = min(o[i], pos["stop"]) * (1 - slip)
                exit_reason = "stop"
            elif h[i] >= pos["target"]:                   # target (gap-aware)
                exit_price = max(o[i], pos["target"]) * (1 - slip)
                exit_reason = "target"
            else:
                s = sig.generate_signal(_slice(ohlcv, i))
                if s["action"] == "SELL":
                    exit_price = c[i] * (1 - slip)
                    exit_reason = "signal"
            if exit_price is not None:
                pnl = (exit_price - pos["entry"]) * pos["shares"] - commission
                equity += pnl
                trades.append({
                    "symbol": symbol.upper(), "entry_date": pos["entry_date"],
                    "exit_date": dstr(i), "entry": round(pos["entry"], 2),
                    "exit": round(exit_price, 2), "shares": pos["shares"],
                    "pnl": round(pnl, 2), "pnl_pct": round((exit_price/pos["entry"]-1)*100, 2),
                    "bars_held": i - pos["entry_i"], "reason": exit_reason,
                })
                pos = None

        # ---- look for a new entry (no look-ahead: uses data through i) ----
        if pos is None and pending_entry is None:
            s = sig.generate_signal(_slice(ohlcv, i))
            if s["action"] == "BUY" and s.get("stop_loss") and s.get("take_profit"):
                if s["stop_loss"] < c[i]:  # sane stop
                    pending_entry = {"stop": s["stop_loss"], "target": s["take_profit"]}

        curve.append((dstr(i), round(equity + (
            (c[i] - pos["entry"]) * pos["shares"] if pos else 0), 2)))

    return {"symbol": symbol.upper(), "period": period,
            "starting_equity": starting_equity,
            "trades": trades, "equity_curve": curve,
            "metrics": _metrics(trades, curve, starting_equity),
            "assumptions": {"risk_pct": risk_pct, "commission": commission,
                            "slippage_bps": slippage_bps, "no_lookahead": True,
                            "entry": "next bar open", "data": "yfinance daily"},
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat()}


def _metrics(trades, curve, start):
    if not trades:
        return {"trades": 0, "note": "no trades generated in this window"}
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gross_w = sum(t["pnl"] for t in wins)
    gross_l = -sum(t["pnl"] for t in losses)
    final = curve[-1][1] if curve else start
    # max drawdown on equity curve
    peak = -1e18; mdd = 0
    for _, e in curve:
        peak = max(peak, e)
        mdd = max(mdd, (peak - e) / peak if peak > 0 else 0)
    # Sharpe from daily equity returns (annualized, 252d)
    eq = [e for _, e in curve]
    rets = [(eq[i]/eq[i-1]-1) for i in range(1, len(eq)) if eq[i-1] > 0]
    if len(rets) > 2:
        mu = sum(rets)/len(rets)
        sd = (sum((r-mu)**2 for r in rets)/len(rets)) ** 0.5
        sharpe = (mu/sd*math.sqrt(252)) if sd > 0 else 0
    else:
        sharpe = 0
    return {
        "trades": len(trades), "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins)/len(trades)*100, 1),
        "total_return_pct": round((final/start - 1)*100, 1),
        "final_equity": round(final, 2),
        "profit_factor": round(gross_w/gross_l, 2) if gross_l > 0 else None,
        "avg_win": round(gross_w/len(wins), 2) if wins else 0,
        "avg_loss": round(-gross_l/len(losses), 2) if losses else 0,
        "expectancy": round(sum(t["pnl"] for t in trades)/len(trades), 2),
        "max_drawdown_pct": round(mdd*100, 1),
        "sharpe": round(sharpe, 2),
        "avg_bars_held": round(sum(t["bars_held"] for t in trades)/len(trades), 1),
    }


if __name__ == "__main__":
    import sys, json
    r = backtest(sys.argv[1] if len(sys.argv) > 1 else "AAPL",
                 period=sys.argv[2] if len(sys.argv) > 2 else "2y")
    print(f"\n{r['symbol']} VW-RSI backtest ({r.get('period')}):")
    print(json.dumps(r["metrics"], indent=2))
