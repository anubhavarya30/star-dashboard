#!/usr/bin/env bash
# STAR autonomous paper-trading tick. launchd runs this every 15 min; the script
# gates itself to weekday US market hours and no-ops otherwise.
cd "$(dirname "$0")/.." || exit 0
./venv/bin/python3 engine/paper_session.py >> /tmp/star_paper.log 2>&1
