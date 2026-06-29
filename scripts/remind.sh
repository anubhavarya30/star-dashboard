#!/usr/bin/env bash
cd "$(dirname "$0")/.." || exit 1
./venv/bin/python3 -c "import sys;sys.path.insert(0,'engine');import telegram_alert;telegram_alert.send('🔔 STAR reminder — market closed. Real-time data step: in IBKR Client Portal (website) → Settings → Account Settings → Paper Trading Account → enable Share market data with paper account. THEN relaunch TWS on the server (paper/DU). Then tell Claude check again to wire real-time into the scalp engine.')" >> /tmp/star_remind.log 2>&1
