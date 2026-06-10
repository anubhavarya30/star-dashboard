#!/usr/bin/env python3
"""Run the real IBKR sync every 30s, forever. Ctrl+C to stop."""
import time
from datetime import datetime
import ibkr_live_sync

while True:
    try:
        ibkr_live_sync.main()
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] loop error: {e}")
    time.sleep(30)
