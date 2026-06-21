#!/usr/bin/env bash
# STAR — daily pre-market refresh. IBKR restarts TWS/Gateway once a day, which can
# leave our long-running processes (terminal_server, active_watch) holding a wedged
# ib_async connection. Kicking both well before the 8:30 CT open guarantees they
# reconnect cleanly for the trading day. Installed as com.star.dailyrestart.
set -u
U="$(id -u)"
for job in com.star.terminal com.star.activewatch; do
  launchctl kickstart -k "gui/$U/$job" 2>/dev/null && echo "$(date '+%F %T') kicked $job" || echo "$(date '+%F %T') could not kick $job"
done
