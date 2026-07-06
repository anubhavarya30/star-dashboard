#!/usr/bin/env python3
"""
STAR — Black-Scholes option greeks engine (delta, gamma, theta, vega, rho).

Extends engine/gex.py (which does dealer GAMMA only) to the FULL greeks. Same
discipline: every number derives from real market inputs (spot + option chain IV
from yfinance); modeling assumptions are stated, nothing fabricated.

Two layers:
  1. greeks(S,K,T,sigma,...)  -> per-contract greeks for one option (the math).
  2. net_exposure(symbol)     -> dealer NET delta/gamma/theta/vega across the live
                                 chain (SqueezeMetrics convention: dealers long calls,
                                 short puts), i.e. the desk-level risk map.

Greeks conventions (reported the way a trader reads them):
  delta : per $1 move in spot            (calls 0..1, puts -1..0)
  gamma : delta change per $1 move
  theta : P&L per DAY from time decay     (negative for long options) = annual/365
  vega  : P&L per 1 VOL POINT (1%) move   = raw_vega / 100
  rho   : P&L per 1% rate move            = raw_rho / 100
Risk-free r default 0.04; continuous dividend yield q default 0.0.
"""
import math
from datetime import datetime, timezone, date

SQRT2PI = math.sqrt(2 * math.pi)


def _norm_pdf(x):
    return math.exp(-x * x / 2.0) / SQRT2PI


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _d1d2(S, K, T, sigma, r, q):
    vt = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / vt
    return d1, d1 - vt


def _valid(*xs):
    # NaN-safe (x != x is True only for NaN); positives required
    return not any(x != x for x in xs) and all(x > 0 for x in xs)


def bs_price(S, K, T, sigma, r=0.04, q=0.0, kind="call"):
    if not _valid(S, K, T, sigma):
        return 0.0
    d1, d2 = _d1d2(S, K, T, sigma, r, q)
    if kind == "call":
        return S * math.exp(-q * T) * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * math.exp(-q * T) * _norm_cdf(-d1)


def greeks(S, K, T, sigma, r=0.04, q=0.0, kind="call"):
    """Full per-contract greeks. Returns a dict; zeros on degenerate inputs."""
    if not _valid(S, K, T, sigma):
        return {"price": 0.0, "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    d1, d2 = _d1d2(S, K, T, sigma, r, q)
    pdf = _norm_pdf(d1)
    sqrtT = math.sqrt(T)
    disc_r = math.exp(-r * T)
    disc_q = math.exp(-q * T)
    gamma = disc_q * pdf / (S * sigma * sqrtT)
    vega = S * disc_q * pdf * sqrtT                    # per 1.00 vol
    # annual theta, then per-day
    common = -(S * disc_q * pdf * sigma) / (2.0 * sqrtT)
    if kind == "call":
        delta = disc_q * _norm_cdf(d1)
        theta = common - r * K * disc_r * _norm_cdf(d2) + q * S * disc_q * _norm_cdf(d1)
        rho = K * T * disc_r * _norm_cdf(d2)
    else:
        delta = -disc_q * _norm_cdf(-d1)
        theta = common + r * K * disc_r * _norm_cdf(-d2) - q * S * disc_q * _norm_cdf(-d1)
        rho = -K * T * disc_r * _norm_cdf(-d2)
    return {
        "price": round(bs_price(S, K, T, sigma, r, q, kind), 4),
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta / 365.0, 4),   # per day
        "vega": round(vega / 100.0, 4),      # per 1% vol
        "rho": round(rho / 100.0, 4),        # per 1% rate
    }


def position_greeks(qty, S, K, T, sigma, r=0.04, q=0.0, kind="call", mult=100):
    """Greeks for a HELD position: qty contracts (negative = short), x100 multiplier.
    delta -> shares-equivalent; theta/vega -> $ per day / per vol point for the position."""
    g = greeks(S, K, T, sigma, r, q, kind)
    scale = qty * mult
    return {
        "qty": qty, "kind": kind, "strike": K,
        "delta": round(g["delta"] * scale, 2),
        "gamma": round(g["gamma"] * scale, 4),
        "theta": round(g["theta"] * scale, 2),
        "vega": round(g["vega"] * scale, 2),
        "rho": round(g["rho"] * scale, 2),
        "mark": round(g["price"] * mult, 2),
    }


def _yearfrac(expiry_str):
    try:
        exp = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        days = (exp - date.today()).days
        return max(days, 0) / 365.0, days
    except Exception:
        return 0.0, 0


def net_exposure(symbol="SPY", max_expiries=6, strike_pct=0.20, r=0.04):
    """Dealer NET greeks across the live chain (real OI + IV from yfinance).
    Convention (same as gex.py): dealers LONG calls, SHORT puts. Returns net
    dollar-greek exposures + per-expiry breakdown. Honest about the assumption."""
    import yfinance as yf
    tk = yf.Ticker(symbol)
    try:
        spot = float(tk.fast_info.get("lastPrice"))
    except Exception:
        return {"symbol": symbol.upper(), "error": "no spot price"}
    if not spot or spot <= 0:
        return {"symbol": symbol.upper(), "error": "no spot price"}

    try:
        expiries = list(tk.options)[:max_expiries]
    except Exception:
        expiries = []
    if not expiries:
        return {"symbol": symbol.upper(), "spot": round(spot, 2), "error": "no option expiries"}

    lo, hi = spot * (1 - strike_pct), spot * (1 + strike_pct)
    net = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    used = []
    for exp in expiries:
        T, days = _yearfrac(exp)
        if T <= 0:
            continue
        try:
            ch = tk.option_chain(exp)
        except Exception:
            continue
        for df, kind, sign in ((ch.calls, "call", +1), (ch.puts, "put", -1)):
            for _, row in df.iterrows():
                K = float(row.get("strike") or 0)
                if K < lo or K > hi:
                    continue
                oi = float(row.get("openInterest") or 0)
                iv = float(row.get("impliedVolatility") or 0)
                if oi <= 0 or iv <= 0:
                    continue
                g = greeks(spot, K, T, iv, r=r, kind=kind)
                # dealer sign: long calls (+), short puts (-); scale by OI*100
                w = sign * oi * 100
                net["delta"] += g["delta"] * w
                net["gamma"] += g["gamma"] * w * spot   # $-gamma per $1 (shares) ~ keep raw*OI
                net["theta"] += g["theta"] * w
                net["vega"] += g["vega"] * w
        used.append(exp)

    return {
        "symbol": symbol.upper(), "spot": round(spot, 2),
        "net_delta": round(net["delta"], 0),
        "net_gamma": round(net["gamma"], 0),
        "net_theta": round(net["theta"], 0),
        "net_vega": round(net["vega"], 0),
        "expiries_used": used,
        "assumption": "dealers long calls / short puts (SqueezeMetrics convention); greeks from real OI+IV",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    }


def agent(symbol="SPY"):
    """Compact net-greeks read for the STAR dashboard."""
    d = net_exposure(symbol)
    if d.get("error"):
        return {"agent": "Greeks (net dealer)", "symbol": d["symbol"], "detail": d["error"]}
    nd, ng, nt, nv = d["net_delta"], d["net_gamma"], d["net_theta"], d["net_vega"]
    bias = ("Net long gamma — dealers dampen moves (pin/mean-revert)."
            if ng > 0 else "Net short gamma — dealers amplify moves (trend/accelerate).")
    return {"agent": "Greeks (net dealer)", "symbol": d["symbol"], "spot": d["spot"],
            "net_delta": nd, "net_gamma": ng, "net_theta": nt, "net_vega": nv,
            "detail": bias, "generated_at": d["generated_at"]}


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) > 1 and sys.argv[1] == "one":
        # quick per-contract check: greeks.py one S K days iv call|put
        S, K, days, iv, kind = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), sys.argv[6]
        print(json.dumps(greeks(S, K, days / 365.0, iv, kind=kind), indent=2))
    else:
        print(json.dumps(net_exposure(sys.argv[1] if len(sys.argv) > 1 else "SPY"), indent=2, default=str))
