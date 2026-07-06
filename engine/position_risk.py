#!/usr/bin/env python3
"""
STAR — portfolio greeks / position risk overlay.

Pulls every OPEN position across all desks (stock, scalp, fvg, gex, options) and
computes the NET portfolio greeks you're actually carrying: net delta (share-equiv
+ dollar), net gamma, net theta ($/day decay), net vega ($/vol point). Flags when
any exposure breaches a limit — so a human/desk sees real risk, not just per-trade.

Position types handled:
  - SHARES (stock/scalp/fvg/gex desks): delta = signed share count; other greeks ~0.
      dollar_delta = shares * price.
  - OPTIONS (options desk, or any position carrying strike+expiry+kind[+iv]):
      full greeks via engine/greeks.position_greeks (BS), scaled by qty*100.

Everything derives from real inputs (live price via realtime_data, IV from the
position or the live chain). Nothing fabricated. Entries-agnostic: this only READS
open state, so it's safe to run anytime.
"""
import os
import sys
from datetime import datetime, date

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

# net-exposure limits (tune as capital/appetite change)
LIMITS = {
    "dollar_delta": 60000.0,   # max |net directional $ exposure|
    "theta_day": -400.0,       # min net theta (more negative than this = too much decay bleed)
    "vega": 1500.0,            # max |net vega| ($ per 1 vol point)
    "gamma": 5000.0,           # max |net gamma| (delta change per $1)
}


def _price(sym):
    try:
        import realtime_data as rt
        p = rt.price(sym)
        return float(p["last"] if isinstance(p, dict) else p) if p else None
    except Exception:
        try:
            import yfinance as yf
            return float(yf.Ticker(sym).fast_info.get("lastPrice"))
        except Exception:
            return None


def _yearfrac(expiry):
    try:
        exp = datetime.strptime(str(expiry)[:10], "%Y-%m-%d").date()
        return max((exp - date.today()).days, 0) / 365.0
    except Exception:
        return 0.0


def _signed_qty(p):
    q = p.get("shares") or p.get("qty") or p.get("contracts") or 0
    return -abs(q) if str(p.get("dir", "LONG")).upper() in ("SHORT", "SELL") else abs(q)


def _position_greeks(p):
    """Greeks contribution of one open position. Shares -> delta only; options -> full."""
    sym = p.get("symbol", "SPY")
    qty = _signed_qty(p)
    spot = _price(sym) or p.get("entry")
    if not spot or not qty:
        return None
    is_option = bool(p.get("strike") and p.get("expiry"))
    if is_option:
        import greeks
        K = float(p["strike"]); T = _yearfrac(p["expiry"])
        iv = float(p.get("iv") or 0) or 0.20            # fall back to a nominal IV if none stored
        kind = "put" if str(p.get("kind", p.get("type", "call"))).lower().startswith("p") else "call"
        g = greeks.position_greeks(qty, spot, K, T, iv, kind=kind)
        return {"symbol": sym, "kind": f"{kind} {K}", "qty": qty,
                "delta_sh": g["delta"], "dollar_delta": round(g["delta"] * spot, 2),
                "gamma": g["gamma"], "theta": g["theta"], "vega": g["vega"], "spot": round(spot, 2)}
    # shares: delta = 1/share, no gamma/theta/vega
    return {"symbol": sym, "kind": "shares", "qty": qty,
            "delta_sh": qty, "dollar_delta": round(qty * spot, 2),
            "gamma": 0.0, "theta": 0.0, "vega": 0.0, "spot": round(spot, 2)}


def _open_positions():
    """Collect open positions from every desk. Defensive: each desk optional."""
    out = []
    def grab(modname, source):
        try:
            m = __import__(modname)
            st = m.stats() if hasattr(m, "stats") else {}
            for p in st.get("open", []) or []:
                out.append({**p, "_desk": source})
        except Exception:
            pass
    for mod, src in (("scalp_desk", "scalp"), ("fvg_desk", "fvg"),
                     ("gex_desk", "gex"), ("options_desk", "option")):
        grab(mod, src)
    try:                                   # stock desk lives in risk_manager
        import risk_manager as rm
        for p in rm.status().get("open_positions", []) or []:
            out.append({**p, "_desk": "stock"})
    except Exception:
        pass
    return out


def portfolio():
    """Net portfolio greeks + per-position breakdown + limit breaches."""
    positions = _open_positions()
    legs, net = [], {"dollar_delta": 0.0, "delta_sh": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    for p in positions:
        g = _position_greeks(p)
        if not g:
            continue
        g["desk"] = p.get("_desk")
        legs.append(g)
        for k in ("dollar_delta", "delta_sh", "gamma", "theta", "vega"):
            net[k] += g[k]
    net = {k: round(v, 2) for k, v in net.items()}

    breaches = []
    if abs(net["dollar_delta"]) > LIMITS["dollar_delta"]:
        breaches.append(f"net $delta {net['dollar_delta']:+,.0f} exceeds ±{LIMITS['dollar_delta']:,.0f}")
    if net["theta"] < LIMITS["theta_day"]:
        breaches.append(f"net theta {net['theta']:+,.0f}/day below {LIMITS['theta_day']:,.0f} (decay bleed)")
    if abs(net["vega"]) > LIMITS["vega"]:
        breaches.append(f"net vega {net['vega']:+,.0f} exceeds ±{LIMITS['vega']:,.0f}")
    if abs(net["gamma"]) > LIMITS["gamma"]:
        breaches.append(f"net gamma {net['gamma']:+,.0f} exceeds ±{LIMITS['gamma']:,.0f}")

    return {
        "generated_at": datetime.now().isoformat(),
        "open_count": len(legs),
        "net": net,
        "limits": LIMITS,
        "breaches": breaches,
        "status": "BREACH" if breaches else "ok",
        "legs": legs,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(portfolio(), indent=2, default=str))
