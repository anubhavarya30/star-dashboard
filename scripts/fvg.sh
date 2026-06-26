#!/usr/bin/env bash
# STAR — FVG sim desk tick (every 10 min, market hours). Forward-tests the FVG edge.
cd "$(dirname "$0")/.." || exit 1
STAR_IBKR_PORT="${STAR_IBKR_PORT:-7497}" ./venv/bin/python3 engine/fvg_desk.py >> /tmp/star_fvg.log 2>&1
