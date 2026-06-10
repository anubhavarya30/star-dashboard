#!/usr/bin/env python3
"""
STAR — IBKR order execution with HARD SAFETY CAPS.

Defaults are deliberately paranoid:
  • DRY-RUN by default: previews margin impact via whatIfOrder, does NOT transmit.
  • Live transmit requires ALL of: env STAR_LIVE_TRADING=1  AND  confirm=True
    AND every cap below passing.
  • Limit orders only (no market orders) — price bounded to the reference quote.
  • Notional / position / open-count / daily-count caps, symbol whitelist,
    buying-power check.

Nothing here is wired to the web server or to autonomous loops — it must be
called deliberately. This is the capability, gated; not an auto-trader.
"""
import os
import json
import random
from datetime import datetime, timezone
from pathlib import Path

HOST, PORT = "127.0.0.1", 7497
ORDERS_LOG = Path(__file__).parent.parent / "orders_log.json"   # repo root

# ---------------- HARD CAPS ----------------
CAPS = {
    "max_order_notional":    50.0,   # $ max value of a single order
    "max_position_notional": 100.0,  # $ max total exposure per symbol
    "max_open_positions":    5,
    "max_orders_per_day":    10,
    "max_limit_slippage_pct": 0.5,   # limit must be within 0.5% of reference price
    "symbol_whitelist": {"AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
                         "TSLA", "SPY", "QQQ"},
}
LIVE_ENABLED = os.getenv("STAR_LIVE_TRADING", "0") == "1"


def _orders_today():
    if not ORDERS_LOG.exists():
        return []
    try:
        rows = json.loads(ORDERS_LOG.read_text())
    except Exception:
        return []
    today = datetime.now().astimezone().date().isoformat()
    return [r for r in rows if (r.get("ts", "")[:10] == today)]


def _log_order(rec):
    rows = []
    if ORDERS_LOG.exists():
        try:
            rows = json.loads(ORDERS_LOG.read_text())
        except Exception:
            rows = []
    rows.append(rec)
    ORDERS_LOG.write_text(json.dumps(rows, indent=2))


def place_order(symbol, side, quantity, limit_price=None, confirm=False, dry_run=True):
    """Validate against caps, preview via whatIf, and (only if fully authorized)
    transmit a LIMIT order. Returns a structured result dict — never raises for
    a rejected cap; it reports why."""
    symbol = symbol.upper()
    side = side.upper()
    result = {"symbol": symbol, "side": side, "quantity": quantity,
              "limit_price": limit_price, "transmitted": False, "checks": [],
              "ts": datetime.now(timezone.utc).astimezone().isoformat()}

    def reject(msg):
        result["status"] = "REJECTED"
        result["reason"] = msg
        result["checks"].append("✗ " + msg)
        return result

    # ---- static validation (no connection needed) ----
    if side not in ("BUY", "SELL"):
        return reject(f"side must be BUY/SELL, got {side}")
    if symbol not in CAPS["symbol_whitelist"]:
        return reject(f"{symbol} not in whitelist")
    if not isinstance(quantity, int) or quantity <= 0:
        return reject(f"quantity must be positive int, got {quantity}")
    if len(_orders_today()) >= CAPS["max_orders_per_day"]:
        return reject(f"daily order cap reached ({CAPS['max_orders_per_day']})")
    result["checks"].append("✓ symbol whitelisted, side/qty valid, under daily cap")

    from ib_async import IB, Stock, LimitOrder
    ib = IB()
    try:
        ib.connect(HOST, PORT, clientId=random.randint(100, 9999), timeout=20)
        ib.reqMarketDataType(3)

        # reference price — use yfinance (reliable delayed quote; IBKR API has no
        # market-data subscription on this account so reqMktData returns nan)
        c = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(c)
        ref = None
        try:
            import yfinance as yf
            fi = yf.Ticker(symbol).fast_info
            ref = fi.get("lastPrice") or fi.get("previousClose")
        except Exception:
            pass
        if ref is None or ref != ref:
            ib.disconnect()
            return reject("no reference price available")

        # limit price: default to ref, validate slippage band
        lp = float(limit_price) if limit_price else round(float(ref), 2)
        slip = abs(lp - ref) / ref * 100
        if slip > CAPS["max_limit_slippage_pct"]:
            ib.disconnect()
            return reject(f"limit {lp} is {slip:.2f}% from ref {ref:.2f} "
                          f"(> {CAPS['max_limit_slippage_pct']}% cap)")
        result["limit_price"] = lp
        result["ref_price"] = round(float(ref), 2)

        notional = quantity * lp
        result["notional"] = round(notional, 2)

        # ---- cap checks ----
        if notional > CAPS["max_order_notional"]:
            ib.disconnect()
            return reject(f"order notional ${notional:.2f} > cap ${CAPS['max_order_notional']}")

        # buying power + existing exposure + open count
        bp = next((float(v.value) for v in ib.accountValues()
                   if v.tag == "BuyingPower" and v.currency == "USD"), 0.0)
        result["buying_power"] = bp
        port = ib.portfolio()
        held = next((p for p in port if p.contract.symbol == symbol), None)
        held_notional = abs(held.marketValue) if held else 0.0
        if side == "BUY":
            if notional > bp:
                ib.disconnect()
                return reject(f"notional ${notional:.2f} > buying power ${bp:.2f}")
            if held_notional + notional > CAPS["max_position_notional"]:
                ib.disconnect()
                return reject(f"would exceed per-symbol cap "
                              f"(${held_notional:.2f}+${notional:.2f} > ${CAPS['max_position_notional']})")
            if not held and len(port) >= CAPS["max_open_positions"]:
                ib.disconnect()
                return reject(f"max open positions reached ({CAPS['max_open_positions']})")
        result["checks"].append(f"✓ notional ${notional:.2f} within all caps; BP ${bp:.2f}")

        # ---- whatIf preview (margin impact, no transmit) — timeout-guarded so a
        #      slow/blocking API response can never hang the executor ----
        order = LimitOrder(side, quantity, lp)
        order.transmit = False
        try:
            import asyncio
            whatif = ib.run(asyncio.wait_for(ib.whatIfOrderAsync(c, order), timeout=6))
            result["preview"] = {
                "init_margin_after": getattr(whatif, "initMarginAfter", None),
                "maint_margin_after": getattr(whatif, "maintMarginAfter", None),
                "commission": getattr(whatif, "commission", None),
                "equity_with_loan_after": getattr(whatif, "equityWithLoanAfter", None),
            }
            result["checks"].append("✓ whatIf preview computed")
        except Exception as we:
            result["preview"] = None
            result["checks"].append(f"⚠ whatIf preview skipped ({type(we).__name__})")

        # ---- transmit gate ----
        if dry_run or not confirm or not LIVE_ENABLED:
            gate = []
            if dry_run: gate.append("dry_run=True")
            if not confirm: gate.append("confirm=False")
            if not LIVE_ENABLED: gate.append("STAR_LIVE_TRADING!=1")
            result["status"] = "PREVIEW_ONLY"
            result["reason"] = "not transmitted — gated by: " + ", ".join(gate)
            ib.disconnect()
            _log_order({**result})
            return result

        # ---- LIVE transmit ----
        order.transmit = True
        trade = ib.placeOrder(c, order)
        ib.sleep(3)
        result["transmitted"] = True
        result["status"] = trade.orderStatus.status
        result["order_id"] = trade.order.orderId
        result["checks"].append(f"✓ TRANSMITTED — status {result['status']}")
        ib.disconnect()
        _log_order({**result})
        return result

    except Exception as e:
        try:
            ib.disconnect()
        except Exception:
            pass
        return reject(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    sym = args[0] if args else "AAPL"
    qty = int(args[1]) if len(args) > 1 else 1
    print(f"LIVE_ENABLED={LIVE_ENABLED}  (set STAR_LIVE_TRADING=1 to allow real transmit)")
    r = place_order(sym, "BUY", qty, dry_run=True)
    print(json.dumps(r, indent=2, default=str))
