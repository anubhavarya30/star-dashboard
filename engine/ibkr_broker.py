#!/usr/bin/env python3
"""
STAR — IBKR broker connector for PAPER trading, with a HARDWIRED safety gate.

The #1 rule: never place an automated order on a LIVE account. IBKR paper accounts
are 'DU'-prefixed; live accounts are 'U'-prefixed. place_order() REFUSES unless the
connected account is paper (DU). Even if pointed at a live account by mistake, it
will not trade real money.

To use real IBKR paper trading: in TWS, log into your PAPER account (or toggle
Paper Trading) so the connected account shows 'DU…', then this module can route
orders through IBKR's real fill engine. While a live 'U…' account is connected,
this module is read-only and the desk stays on the simulator.
"""
import os

# Works with TWS (paper 7497) or IB Gateway. We tell IBC to expose Gateway on
# 7497 too (OverrideTwsApiPort), so no change is needed — but allow an override.
PORT = int(os.environ.get("STAR_IBKR_PORT", "7497"))
HOST = os.environ.get("STAR_IBKR_HOST", "127.0.0.1")


def _connect(client_id=88, timeout=10):
    from ib_async import IB
    ib = IB()
    ib.connect(HOST, PORT, clientId=client_id, timeout=timeout)
    return ib


def status(client_id=88):
    """Connection + account-type check. Safe; never places orders."""
    try:
        ib = _connect(client_id=client_id)
    except Exception as e:
        return {"connected": False, "error": f"{type(e).__name__}: {e}",
                "hint": "Start TWS and enable API on port 7497."}
    try:
        accts = ib.managedAccounts()
        acct = accts[0] if accts else None
        is_paper = bool(acct and acct.upper().startswith("DU"))
        nl = None
        try:
            nl = next((float(v.value) for v in ib.accountSummary() if v.tag == "NetLiquidation"), None)
        except Exception:
            pass
        return {"connected": True, "account": acct,
                "type": "paper" if is_paper else "live",
                "is_paper": is_paper, "net_liquidation": nl,
                "can_auto_trade": is_paper,
                "note": "PAPER — safe to auto-trade" if is_paper else
                        "LIVE account — auto-trading BLOCKED by safety gate"}
    finally:
        ib.disconnect()


def place_order(symbol, qty, action="BUY", order_type="MKT", limit_price=None):
    """Place an order ONLY on a verified paper (DU) account. Hard safety gate."""
    from ib_async import Stock, MarketOrder, LimitOrder
    ib = _connect(client_id=89)
    try:
        accts = ib.managedAccounts()
        acct = accts[0] if accts else ""
        if not acct.upper().startswith("DU"):
            return {"ok": False, "blocked": True, "account": acct,
                    "error": f"SAFETY GATE: refusing to trade non-paper account '{acct}'. "
                             "Log into an IBKR PAPER (DU) account first."}
        contract = Stock(symbol.upper(), "SMART", "USD")
        ib.qualifyContracts(contract)
        # We have no IBKR market-data subscription (Error 10089) and plain market
        # orders get cancelled after hours, so use a MARKETABLE LIMIT priced off
        # yfinance (delayed) with outsideRth — this is what actually fills on paper.
        if not limit_price:
            import yfinance as yf
            last = float(yf.Ticker(symbol).fast_info.get("lastPrice"))
            limit_price = round(last * (1.02 if action.upper() == "BUY" else 0.98), 2)
        order = LimitOrder(action, abs(int(qty)), float(limit_price))
        order.tif = "DAY"
        order.outsideRth = True
        trade = ib.placeOrder(contract, order)
        ib.sleep(4)
        return {"ok": True, "account": acct, "symbol": symbol.upper(), "action": action,
                "qty": int(qty), "status": trade.orderStatus.status,
                "filled": trade.orderStatus.filled, "avg_fill": trade.orderStatus.avgFillPrice}
    finally:
        ib.disconnect()


def place_option_order(symbol, expiry, strike, right, qty, limit_price, action="BUY"):
    """Place an OPTION order on a verified paper (DU) account. Same safety gate.
    expiry 'YYYY-MM-DD', right 'C'/'P', limit_price from the option chain (we have
    no IBKR option data, so the caller prices it off yfinance)."""
    from ib_async import Option, LimitOrder
    ib = _connect(client_id=91)
    try:
        accts = ib.managedAccounts()
        acct = accts[0] if accts else ""
        if not acct.upper().startswith("DU"):
            return {"ok": False, "blocked": True, "account": acct,
                    "error": f"SAFETY GATE: refusing to trade non-paper account '{acct}'."}
        exp = expiry.replace("-", "")  # ib wants YYYYMMDD
        contract = Option(symbol.upper(), exp, float(strike), right.upper()[0], "SMART")
        contract.multiplier = "100"
        ib.qualifyContracts(contract)
        # marketable limit to cross the (wide) option spread on a paper fill
        lp = round(float(limit_price) * (1.10 if action.upper() == "BUY" else 0.90), 2)
        order = LimitOrder(action, abs(int(qty)), lp)
        order.tif = "DAY"
        trade = ib.placeOrder(contract, order)
        ib.sleep(5)
        return {"ok": True, "account": acct, "symbol": symbol.upper(),
                "contract": f"{symbol.upper()} {expiry} {strike}{right.upper()[0]}",
                "action": action, "qty": int(qty), "status": trade.orderStatus.status,
                "filled": trade.orderStatus.filled, "avg_fill": trade.orderStatus.avgFillPrice}
    finally:
        ib.disconnect()


def place_option_spread(symbol, expiry, long_strike, short_strike, right, qty,
                        long_price, short_price, action="OPEN"):
    """Place a vertical DEBIT spread on a paper (DU) account by legging in two
    options (BUY the long strike, SELL the short strike). action 'OPEN' buys the
    spread; 'CLOSE' reverses (sell the long, buy back the short). Same safety gate."""
    from ib_async import Option, LimitOrder
    ib = _connect(client_id=92)
    try:
        accts = ib.managedAccounts()
        acct = accts[0] if accts else ""
        if not acct.upper().startswith("DU"):
            return {"ok": False, "blocked": True, "account": acct,
                    "error": f"SAFETY GATE: refusing to trade non-paper account '{acct}'."}
        exp = expiry.replace("-", "")
        r = right.upper()[0]
        long_act = "BUY" if action.upper() == "OPEN" else "SELL"
        short_act = "SELL" if action.upper() == "OPEN" else "BUY"
        out = {}
        for leg, strike, act, px in (("long", long_strike, long_act, long_price),
                                     ("short", short_strike, short_act, short_price)):
            c = Option(symbol.upper(), exp, float(strike), r, "SMART")
            c.multiplier = "100"
            ib.qualifyContracts(c)
            lp = round(float(px) * (1.10 if act == "BUY" else 0.90), 2)
            o = LimitOrder(act, abs(int(qty)), lp); o.tif = "DAY"
            t = ib.placeOrder(c, o); ib.sleep(4)
            out[leg] = {"action": act, "strike": strike, "status": t.orderStatus.status,
                        "filled": t.orderStatus.filled, "avg_fill": t.orderStatus.avgFillPrice}
        lf = out["long"]; sf = out["short"]
        both = bool(lf["filled"]) and bool(sf["filled"])
        net = None
        if lf["avg_fill"] and sf["avg_fill"]:
            net = round(float(lf["avg_fill"]) - float(sf["avg_fill"]), 2)
        return {"ok": True, "account": acct, "symbol": symbol.upper(),
                "spread": f"{symbol.upper()} {expiry} {long_strike}/{short_strike}{r}",
                "filled": both, "net_debit": net, "legs": out}
    finally:
        ib.disconnect()


def fills():
    """Authoritative IBKR order/fill history from the connected account — proof of
    what actually executed (vs our own ledger)."""
    ib = _connect(client_id=90)
    try:
        accts = ib.managedAccounts()
        acct = accts[0] if accts else ""
        ib.reqExecutions()
        ib.sleep(2)
        out = []
        for f in ib.fills():
            ex, c = f.execution, f.contract
            out.append({"time": str(ex.time), "symbol": c.symbol, "secType": c.secType,
                        "side": ex.side, "shares": float(ex.shares), "price": float(ex.price),
                        "avg_price": float(ex.avgPrice)})
        return {"account": acct, "type": "paper" if acct.upper().startswith("DU") else "live",
                "count": len(out), "fills": out}
    finally:
        ib.disconnect()


if __name__ == "__main__":
    import json, sys
    cid = int(os.environ.get("STAR_IBKR_STATUS_CID", "88"))
    print(json.dumps(fills() if (len(sys.argv) > 1 and sys.argv[1] == "fills") else status(cid), indent=2, default=str))
