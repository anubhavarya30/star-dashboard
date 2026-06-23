#!/usr/bin/env bash
# STAR — CEO pre-market orchestrator. Assigns the worker agents, builds the day's
# ranked watchlist + brief, Telegrams it, and stages data/premarket/watchlist.json
# so the desk trades it at the open. Runs weekdays ~7:50am CT via com.star.ceo.
cd "$(dirname "$0")/.." || exit 1
STAR_IBKR_PORT="${STAR_IBKR_PORT:-7497}" ./venv/bin/python3 engine/star_ceo.py >> /tmp/star_ceo.log 2>&1
