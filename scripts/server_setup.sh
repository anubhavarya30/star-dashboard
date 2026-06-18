#!/usr/bin/env bash
# STAR — 24/7 server setup. Run this ON THE OLD LAPTOP (the server) from inside
# the cloned repo. Idempotent: safe to re-run. Sets up venv, deps, and installs
# all launchd jobs (rewriting paths to this machine), so STAR runs around the
# clock and auto-restarts on boot/login.
#
#   git clone https://github.com/anubhavarya30/star-dashboard.git
#   cd star-dashboard && bash scripts/server_setup.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
echo "▶ STAR server setup in: $REPO"

# 1) venv + deps
if [ ! -x venv/bin/python3 ]; then
  echo "▶ creating venv…"; python3 -m venv venv
fi
./venv/bin/python3 -m pip install -q --upgrade pip
./venv/bin/python3 -m pip install -q -r requirements.txt
echo "✓ deps installed"

# 2) install all launchd jobs, rewriting hardcoded paths to THIS machine
LA="$HOME/Library/LaunchAgents"; mkdir -p "$LA"
UID_NUM="$(id -u)"
for plist in scripts/com.star.*.plist; do
  label="$(basename "$plist" .plist)"
  # rewrite both the old absolute path and the __REPO__ template token
  sed -e "s#/Users/anubhavarya/star/star-dashboard#$REPO#g" -e "s#__REPO__#$REPO#g" \
      "$plist" > "$LA/$label.plist"
  launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_NUM" "$LA/$label.plist" 2>/dev/null && echo "✓ loaded $label" || echo "… $label (will load on next login)"
done

echo ""
echo "✓ STAR server jobs installed. Verify: launchctl list | grep com.star"
echo ""
echo "STILL TO DO (manual):"
echo "  1. Copy local-only files from your main laptop into $REPO/data/ :"
echo "       data/telegram_config.json   (Telegram creds)"
echo "       data/risk_state.json        (open positions, optional)"
echo "  2. Launch TWS, log into the PAPER (DU) account, API on 7497."
echo "  3. Keep this laptop awake 24/7:  sudo bash scripts/stay_awake.sh"
echo "  4. Dashboard: http://localhost:8080  (or http://<this-laptop-LAN-IP>:8080)"
