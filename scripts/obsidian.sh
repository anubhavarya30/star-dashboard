#!/usr/bin/env bash
cd "$(dirname "$0")/.." || exit 1
./venv/bin/python3 engine/obsidian_export.py >> /tmp/star_obsidian.log 2>&1
