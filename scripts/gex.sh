#!/usr/bin/env bash
# STAR — GEX sim desk tick (every 5 min, market hours). Forward-tests Nick Ireland's
# SPY gamma system (gamma regime + EMA stack + volume) in PAPER with a scorecard.
cd "$(dirname "$0")/.." || exit 1
STAR_IBKR_PORT="${STAR_IBKR_PORT:-7497}" ./venv/bin/python3 engine/gex_desk.py tick >> /tmp/star_gex.log 2>&1
