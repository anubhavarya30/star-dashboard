#!/usr/bin/env bash
cd "$(dirname "$0")/.." || exit 1
STAR_IBKR_PORT="${STAR_IBKR_PORT:-7497}" ./venv/bin/python3 engine/realtime_check.py >> /tmp/star_rtcheck.log 2>&1
