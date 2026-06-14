#!/usr/bin/env python3
"""
STAR — Gamma Exposure (GEX) engine.

Computes a dealer-gamma map from REAL options open-interest (yfinance), using the
Black-Scholes gamma per strike. NOTHING here is fabricated — every number is
derived from the live option chain. Where we make a modeling ASSUMPTION it is
stated plainly, because dealer books are not public:

  Convention (SqueezeMetrics-style): assume dealers are LONG index calls and
  SHORT index puts. Then
       GEX(strike) = gamma * OI * 100 * S^2 * 0.01      (calls: +, puts: -)
  i.e. dollar-gamma per 1% move. Sum over strikes/expiries = net GEX.

Why this matters in a FALLING market:
  - Positive net gamma + spot above the flip  -> dealers hedge AGAINST moves
    (sell rips, buy dips) -> volatility suppressed, price PINS to walls.
  - Negative net gamma (spot below the "gamma flip") -> dealers hedge WITH moves
    (sell weakness, buy strength) -> downside ACCELERATES. This is the regime
    where a falling market trends hard and breakdowns run. THAT is our edge:
    don't fade dips, lean with the momentum down / toward the put wall.
"""
import math
from datetime import datetime, timezone, date

SQRT2PI = math.sqrt(2 * math.pi)


def _norm_pdf(x):
    return math.exp(-x * x / 2.0) / SQRT2PI


def _bs_gamma(S, K, T, sigma, r=0.04):
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    return _norm_pdf(d1) / (S * sigma * math.sqrt(T))


def compute(symbol="SPY", max_expiries=6, strike_pct=0.20):
    """Return the full GEX map for `symbol`. Real options data only."""
    import yfinance as yf
    tk = yf.Ticker(symbol)
    try:
        spot = tk.fast_info.get("last_price") or tk.fast_info.get("lastPrice")
    except Exception:
        spot = None
    if not spot:
        try:
            spot = float(tk.history(period="1d")["Close"].iloc[-1])
        except Exception:
            return {"symbol": symbol.upper(), "error": "no spot price"}
    spot = float(spot)

    expiries = list(getattr(tk, "options", []) or [])
    if not expiries:
        return {"symbol": symbol.upper(), "spot": round(spot, 2),
                "error": "no options chain available for this symbol"}
    expiries = expiries[:max_expiries]

    today = date.today()
    lo, hi = spot * (1 - strike_pct), spot * (1 + strike_pct)
    # per-strike accumulator: strike -> net dollar-gamma per 1% at current spot
    by_strike = {}
    rows = []   # (K, T, sigma, OI, is_call)
    used_expiries = 0
    for exp in expiries:
        try:
            ch = tk.option_chain(exp)
        except Exception:
            continue
        T = max((datetime.strptime(exp, "%Y-%m-%d").date() - today).days, 0) / 365.0
        T = T if T > 0 else 0.5 / 365.0      # 0DTE -> tiny positive T
        used_expiries += 1
        for df, is_call in ((ch.calls, True), (ch.puts, False)):
            for K, oi, iv in zip(df["strike"], df["openInterest"], df["impliedVolatility"]):
                try:
                    K = float(K); oi = float(oi or 0); iv = float(iv or 0)
                except Exception:
                    continue
                if not (lo <= K <= hi) or oi <= 0 or iv <= 0:
                    continue
                rows.append((K, T, iv, oi, is_call))
                g = _bs_gamma(spot, K, T, iv)
                dollar = g * oi * 100 * spot * spot * 0.01
                by_strike[K] = by_strike.get(K, 0.0) + (dollar if is_call else -dollar)

    if not rows:
        return {"symbol": symbol.upper(), "spot": round(spot, 2),
                "error": "options chain had no usable open interest / IV"}

    net_gex = sum(by_strike.values())

    # --- gamma flip: recompute net GEX across a price grid, find zero crossing ---
    def net_at(S):
        tot = 0.0
        for K, T, iv, oi, is_call in rows:
            g = _bs_gamma(S, K, T, iv)
            dollar = g * oi * 100 * S * S * 0.01
            tot += dollar if is_call else -dollar
        return tot
    grid = [spot * (0.85 + 0.30 * i / 60) for i in range(61)]
    profile = [(S, net_at(S)) for S in grid]
    flip = None
    for (s0, g0), (s1, g1) in zip(profile, profile[1:]):
        if g0 == 0 or (g0 < 0 < g1) or (g0 > 0 > g1):
            # linear interpolate the crossing
            flip = s0 if g1 == g0 else s0 + (s1 - s0) * (0 - g0) / (g1 - g0)
            break

    # walls: biggest positive (call wall / resistance-magnet) and most negative (put wall / support)
    strikes_sorted = sorted(by_strike.items(), key=lambda kv: kv[1])
    put_wall = strikes_sorted[0][0] if strikes_sorted else None       # most negative
    call_wall = strikes_sorted[-1][0] if strikes_sorted else None     # most positive
    # top strikes by absolute gamma for the table
    top = sorted(by_strike.items(), key=lambda kv: -abs(kv[1]))[:12]
    top = sorted(top, key=lambda kv: kv[0])

    regime = "positive" if net_gex > 0 else "negative"
    above_flip = (flip is None) or (spot >= flip)

    return {
        "symbol": symbol.upper(), "spot": round(spot, 2),
        "net_gex": net_gex, "regime": regime,
        "gamma_flip": round(flip, 2) if flip else None,
        "above_flip": above_flip,
        "call_wall": call_wall, "put_wall": put_wall,
        "expiries_used": used_expiries,
        "strikes": [{"strike": round(k, 2), "gex": round(v, 0)} for k, v in top],
        "assumption": "dealers long calls / short puts (SqueezeMetrics convention); modeled from real OI",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    }


def agent(symbol="SPY"):
    """Compact GEX read for the STAR Agents area. Honest about the falling-market edge."""
    d = compute(symbol)
    if d.get("error"):
        return {"agent": "GEX (dealer gamma)", "symbol": d["symbol"],
                "vote": "INFO", "regime": None, "detail": d["error"]}
    neg = d["regime"] == "negative"
    below = not d["above_flip"]
    # The edge: negative gamma (esp. below the flip) = downside accelerates.
    if neg and below:
        vote, bias = "DOWNSIDE EDGE", ("Negative gamma & below flip: dealer hedging ACCELERATES "
                                       "selloffs. Edge is SHORT/with-trend-down — don't fade dips; "
                                       f"lean toward put wall {d['put_wall']}.")
    elif neg:
        vote, bias = "UNSTABLE", ("Net negative gamma: moves amplify both ways. Trend-follow, "
                                  "expect bigger ranges.")
    else:
        vote, bias = "PINNED", (f"Positive gamma: vol suppressed, price pins between put wall "
                                f"{d['put_wall']} and call wall {d['call_wall']}. Fade extremes.")
    return {
        "agent": "GEX (dealer gamma)", "symbol": d["symbol"], "vote": vote,
        "regime": d["regime"], "spot": d["spot"], "gamma_flip": d["gamma_flip"],
        "call_wall": d["call_wall"], "put_wall": d["put_wall"],
        "detail": bias, "generated_at": d["generated_at"],
    }


if __name__ == "__main__":
    import sys, json
    print(json.dumps(compute(sys.argv[1] if len(sys.argv) > 1 else "SPY"), indent=2, default=str))
