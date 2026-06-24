#!/usr/bin/env bash
# STAR — intraday scalp desk tick (sim). Hunts oversold-bounce scalps every 2 min
# during market hours. Runs via com.star.scalp.
cd "$(dirname "$0")/.." || exit 1
STAR_IBKR_PORT="${STAR_IBKR_PORT:-7497}" ./venv/bin/python3 engine/scalp_desk.py >> /tmp/star_scalp.log 2>&1
