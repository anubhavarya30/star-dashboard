#!/usr/bin/env bash
# STAR — premarket research. Builds the morning runner watchlist BEFORE the open
# so the board is graded and ready when you wake. Installed as a weekday launchd
# job (~7:45am CDT). Output -> data/premarket/ and /tmp/star_premarket.log.
cd "$(dirname "$0")/.." || exit 0
{
  echo "===== premarket research: $(date) ====="
  ./venv/bin/python3 engine/premarket_research.py 2>&1 | grep -vi warning
} >> /tmp/star_premarket.log 2>&1
