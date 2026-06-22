#!/usr/bin/env bash
cd "$(dirname "$0")/.." || exit 0
./venv/bin/python3 engine/options_desk.py >> /tmp/star_options.log 2>&1
