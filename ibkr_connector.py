#!/usr/bin/env python3
"""
IBKR Connector - Proper async handling
Syncs IBKR trades to STAR system
"""
import asyncio
import json
from pathlib import Path
from datetime import datetime

async def sync_ibkr_to_star():
    """Connect to IBKR and sync open positions to STAR"""
    try:
        from ib_insync import IB

        print("\n" + "="*80)
        print("🔗 SYNCING IBKR TO STAR SYSTEM")
        print("="*80 + "\n")

        ib = IB()

        # Connect with unique client ID
        print("📡 Connecting to IBKR at 127.0.0.1:7497...")
        import random
        client_id = random.randint(100, 999)
        await ib.connectAsync('127.0.0.1', 7497, clientId=client_id)

        print("✅ Connected to IBKR\n")

        # Get positions
        print("📊 Fetching open positions from IBKR...")
        await ib.reqPositionsAsync()
        positions = ib.positions()

        print(f"✅ Got {len(positions)} positions from IBKR\n")

        # Load STAR state
        state_file = Path("current_trades.json")
        if state_file.exists():
            with open(state_file) as f:
                star_state = json.load(f)
        else:
            star_state = {"open_trades": {}, "signals": [], "balance": 100000.0}

        # Sync each position
        if positions:
            for pos in positions:
                symbol = pos.contract.symbol
                qty = pos.position
                cost = pos.avgCost

                trade_id = f"IBKR_{symbol}_{datetime.now().timestamp()}"

                star_state["open_trades"][trade_id] = {
                    "id": trade_id,
                    "symbol": symbol,
                    "action": "BUY" if qty > 0 else "SELL",
                    "quantity": abs(int(qty)),
                    "entry_price": float(cost),
                    "entry_time": datetime.now().isoformat(),
                    "status": "OPEN",
                    "confidence": 1.0,
                    "from_ibkr": True,
                    "avg_cost": float(cost)
                }

                print(f"✅ {symbol}: {abs(int(qty))} shares @ ${cost:.2f}")

            # Save to STAR
            with open(state_file, "w") as f:
                json.dump(star_state, f, indent=2, default=str)

            print(f"\n✅ Synced to STAR system")
        else:
            print("ℹ️  No open positions in IBKR")

        ib.disconnect()

        print("\n" + "="*80)
        print("✅ SYNC COMPLETE")
        print("="*80 + "\n")

        return True

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(sync_ibkr_to_star())
