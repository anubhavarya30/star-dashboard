#!/usr/bin/env bash
# STAR — daily GEX snapshot. Logs real dealer-gamma for the index ETFs into
# data/gex_history.csv so the negative-gamma edge can be forward-tested.
# Installed as a weekday cron job (see crontab). Safe to run by hand anytime.
cd "$(dirname "$0")/.." || exit 0
PY="./venv/bin/python3"
{
  echo "===== GEX log run: $(date) ====="
  for sym in SPY QQQ IWM; do
    "$PY" engine/gex_logger.py log "$sym" 2>&1 | grep -vi warning
  done
} >> /tmp/star_gex.log 2>&1
