#!/usr/bin/env python3
"""
Background task: Sync real IBKR data and Google Calendar P&L every minute
Keeps dashboard updated with live account balance and P&L events
"""
import schedule
import time
from datetime import datetime
from sync_real_data import update_current_trades, update_calendar_sync

def sync_all():
    """Run all sync tasks"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔄 Syncing real IBKR data...")
    update_current_trades()
    update_calendar_sync()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Sync complete")

def main():
    print("\n" + "="*80)
    print("🔄 REAL DATA SYNC SCHEDULER - Background Task")
    print("="*80)
    print("\nThis will sync real IBKR account data and Google Calendar P&L every 60 seconds")
    print("Press Ctrl+C to stop\n")

    # Schedule task every 60 seconds
    schedule.every(60).seconds.do(sync_all)

    # Run initial sync
    sync_all()

    # Keep scheduler running
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n" + "="*80)
            print("⏹️  SYNC SCHEDULER STOPPED")
            print("="*80 + "\n")
            break
        except Exception as e:
            print(f"❌ Error in scheduler: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
