#!/usr/bin/env bash
# STAR — open ping. Fires ~8:45am CT (after the first desk tick) and sends a macOS
# notification with the first-fill status. Reliable local "ping" since the
# assistant can't self-wake to the open.
cd "$(dirname "$0")/.." || exit 0
TODAY=$(date +%Y-%m-%d)
FILL=$(grep "$TODAY" /tmp/star_paper.log 2>/dev/null | grep -E "ENTER|EXIT" | tail -1)
if [ -n "$FILL" ]; then
  MSG="First fill: ${FILL#* }"
else
  STATUS=$(./venv/bin/python3 -c "import sys;sys.path.insert(0,'engine');import risk_manager as rm;s=rm.status();print(f\"open {len(s['open_positions'])}, realized \${s['realized_pnl']}, no new fill yet\")" 2>/dev/null)
  MSG="No fill yet at open — ${STATUS:-desk running}"
fi
osascript -e "display notification \"$MSG\" with title \"STAR — Market Open\" sound name \"Glass\"" 2>/dev/null
echo "$(date) PING: $MSG" >> /tmp/star_ping.log
