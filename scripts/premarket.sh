#!/usr/bin/env bash
# STAR — premarket research + MORNING READINESS REPORT. Weekday launchd job
# (~7:45am CDT). Builds the graded watchlist AND confirms the desk is ready to
# trade real IBKR paper at the open. Report waits at data/morning_report.txt
# (and /tmp/star_premarket.log) so it's there when you wake.
cd "$(dirname "$0")/.." || exit 0
REPORT="data/morning_report.txt"
{
  echo "===== STAR MORNING REPORT: $(date) ====="
  echo "--- IBKR paper readiness ---"
  ./venv/bin/python3 engine/ibkr_broker.py 2>/dev/null | ./venv/bin/python3 -c "import sys,json;d=json.load(sys.stdin);print('  IBKR:',('CONNECTED '+str(d.get('account'))+' ('+str(d.get('type'))+') can_auto_trade='+str(d.get('can_auto_trade'))) if d.get('connected') else ('NOT CONNECTED — '+str(d.get('error'))+' -> log into PAPER (DU) TWS on 7497'))" 2>/dev/null
  echo "--- premarket watchlist ---"
  ./venv/bin/python3 engine/premarket_research.py 2>&1 | grep -vi warning
  echo "--- gap + catalyst ---"
  ./venv/bin/python3 engine/premarket_gap.py 2>&1 | grep -vi warning | ./venv/bin/python3 -c "import sys,json;d=json.load(sys.stdin);print(f\"{len(d['gappers'])} gappers:\");[print(f\"  {'FRESH' if g['fresh_catalyst'] else '     '} {g['symbol']:5} {g['gap_pct']:+.0f}% \${g['price']} | {(g['catalyst'] or 'no news')[:70]}\") for g in d['gappers'][:10]]" 2>/dev/null
  echo "--- desk status ---"
  ./venv/bin/python3 -c "import sys;sys.path.insert(0,'engine');import risk_manager as rm;s=rm.status();print('  open',len(s['open_positions']),'| realized today \$'+str(s['realized_pnl']),'| halted',s['halted'],'| desk fires at 8:30 CT')" 2>/dev/null
  echo "===== end report ====="
} > "$REPORT" 2>&1
cat "$REPORT" >> /tmp/star_premarket.log
