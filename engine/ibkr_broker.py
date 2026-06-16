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

PORT = 7497
HOST = "127.0.0.1"


def _connect(client_id=88, timeout=10):
    from ib_async import IB
    ib = IB()
    ib.connect(HOST, PORT, clientId=client_id, timeout=timeout)
    return ib


def status():
    """Connection + account-type check. Safe; never places orders."""
    try:
        ib = _connect()
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


if __name__ == "__main__":
    import json
    print(json.dumps(status(), indent=2, default=str))
