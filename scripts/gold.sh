#!/usr/bin/env bash
# STAR gold strategy tester — runs ~24/7 (gold futures trade Sun 5pm CT - Fri 4pm CT).
cd "$(dirname "$0")/.." || exit 0
./venv/bin/python3 engine/btc.py >> /tmp/star_btc.log 2>&1   # BTC 24/7 (IBKR paper), runs every day
# daily Telegram scorecard once a day after the stock close (idempotent)
[ "$(date +%H%M)" -ge 1510 ] && ./venv/bin/python3 engine/daily_report.py --send >> /tmp/star_daily.log 2>&1
[ "$(date +%u)" = "6" ] && exit 0   # skip Saturday (gold closed)
./venv/bin/python3 engine/gold.py >> /tmp/star_gold.log 2>&1
