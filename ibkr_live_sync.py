#!/usr/bin/env python3
"""
STAR — IBKR Live Sync (single source of truth)

Connects to TWS on port 7497 using ib_async, pulls the REAL account summary
and portfolio (with IBKR-computed P&L from free delayed prices), and writes
ONE file the dashboard reads: live_account.json

No seeded data. No fake balances. If TWS is down, it writes a clear error
status instead of pretending.
"""
import json
import random
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).parent / "live_account.json"
HOST = "127.0.0.1"
PORT = 7497

# Tags we care about from the account summary (all USD)
WANT = {
    "NetLiquidation", "TotalCashValue", "BuyingPower",
    "AvailableFunds", "GrossPositionValue",
    "UnrealizedPnL", "RealizedPnL",
}


def write(payload: dict):
    payload["last_update"] = datetime.now(timezone.utc).astimezone().isoformat()
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(OUT)  # atomic


def fetch():
    from ib_async import IB

    ib = IB()
    ib.connect(HOST, PORT, clientId=random.randint(100, 9999), timeout=20)
    ib.reqMarketDataType(3)  # 3 = free delayed data (no subscription needed)

    accounts = ib.managedAccounts()
    account_id = accounts[0] if accounts else "UNKNOWN"

    # --- account summary (real) ---
    summary = {}
    for v in ib.accountValues():
        if v.tag in WANT and v.currency in ("USD", ""):
            try:
                summary[v.tag] = float(v.value)
            except ValueError:
                summary[v.tag] = v.value

    # --- portfolio (real, IBKR-computed P&L) ---
    ib.sleep(2)  # let delayed prices arrive
    positions = []
    for p in ib.portfolio():
        positions.append({
            "symbol": p.contract.symbol,
            "sec_type": p.contract.secType,
            "quantity": p.position,
            "avg_cost": round(p.averageCost, 4),
            "market_price": round(p.marketPrice, 2) if p.marketPrice == p.marketPrice else None,  # nan-safe
            "market_value": round(p.marketValue, 2),
            "unrealized_pnl": round(p.unrealizedPNL, 2),
            "realized_pnl": round(p.realizedPNL, 2),
            # IBKR API does NOT expose entry time for pre-existing positions.
            "entry_time": None,
        })

    # --- real executions/fills (this session/day only; dedup by execId downstream) ---
    executions = []
    try:
        for f in ib.fills():
            ex = f.execution
            cr = getattr(f, "commissionReport", None)
            executions.append({
                "exec_id": ex.execId,
                "ts": str(ex.time),
                "account_id": ex.acctNumber or account_id,
                "symbol": f.contract.symbol,
                "side": ex.side,                       # BOT / SLD
                "shares": float(ex.shares),
                "price": float(ex.price),
                "commission": float(getattr(cr, "commission", 0) or 0),
                "realized_pnl": float(getattr(cr, "realizedPNL", 0) or 0),
            })
    except Exception:
        pass

    ib.disconnect()

    return {
        "status": "connected",
        "account_id": account_id,
        "net_liquidation": summary.get("NetLiquidation"),
        "cash": summary.get("TotalCashValue"),
        "buying_power": summary.get("BuyingPower"),
        "available_funds": summary.get("AvailableFunds"),
        "gross_position_value": summary.get("GrossPositionValue"),
        "unrealized_pnl": summary.get("UnrealizedPnL"),
        "realized_pnl": summary.get("RealizedPnL"),
        "positions": positions,
        "executions": executions,
        "price_source": "IBKR delayed (no real-time subscription)",
    }


def main():
    try:
        payload = fetch()
        write(payload)
        # persist to SQLite history (throttled snapshot + dedup'd executions)
        try:
            import db
            db.init_db()
            saved = db.record_snapshot(payload)
            n_exec = db.record_executions(payload.get("executions", []))
            if saved:
                print("   📀 snapshot saved to history")
            if n_exec:
                print(f"   📀 {n_exec} new execution(s) recorded")
        except Exception as de:
            print(f"   ⚠ history write skipped: {type(de).__name__}: {de}")
        print(f"✅ Synced real IBKR account {payload['account_id']}")
        print(f"   Net Liquidation: ${payload['net_liquidation']:,.2f}")
        print(f"   Cash: ${payload['cash']:,.2f}   Buying Power: ${payload['buying_power']:,.2f}")
        for p in payload["positions"]:
            print(f"   {p['symbol']}: {p['quantity']} @ ${p['avg_cost']:.2f} "
                  f"→ ${p['market_price']} (P&L ${p['unrealized_pnl']:+.2f})")
    except Exception as e:
        write({"status": "error", "error": f"{type(e).__name__}: {e}", "positions": []})
        print(f"❌ Sync failed: {type(e).__name__}: {e}")
        print("   Is TWS running and logged in on port 7497?")


if __name__ == "__main__":
    main()
