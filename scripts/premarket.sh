#!/usr/bin/env bash
# STAR — premarket research. Builds the morning runner watchlist BEFORE the open
# so the board is graded and ready when you wake. Installed as a weekday launchd
# job (~7:45am CDT). Output -> data/premarket/ and /tmp/star_premarket.log.
cd "$(dirname "$0")/.." || exit 0
{
  echo "===== premarket research: $(date) ====="
  ./venv/bin/python3 engine/premarket_research.py 2>&1 | grep -vi warning
  echo "----- premarket gap + catalyst scan -----"
  ./venv/bin/python3 engine/premarket_gap.py 2>&1 | grep -vi warning | ./venv/bin/python3 -c "import sys,json;d=json.load(sys.stdin);print(f\"{len(d['gappers'])} gappers:\");[print(f\"  {'FRESH' if g['fresh_catalyst'] else '     '} {g['symbol']:5} {g['gap_pct']:+.0f}% \${g['price']} | {(g['catalyst'] or 'no news')[:70]}\") for g in d['gappers'][:12]]" 2>/dev/null
} >> /tmp/star_premarket.log 2>&1
