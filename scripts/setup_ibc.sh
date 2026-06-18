#!/usr/bin/env bash
# STAR — IB Gateway + IBC (hands-off auto-login) setup. Run on the SERVER laptop.
# Downloads IBC, stages config OUTSIDE the repo (~/ibc), and leaves clear manual
# steps for the parts only you can do (install IB Gateway, enter paper creds).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
IBC_DIR="$HOME/ibc"
IBC_VER="${IBC_VER:-3.20.0}"        # IbcAlpha/IBC release; bump if needed
ZIP="IBCMacos-${IBC_VER}.zip"
URL="https://github.com/IbcAlpha/IBC/releases/download/${IBC_VER}/${ZIP}"

mkdir -p "$IBC_DIR"
echo "▶ downloading IBC ${IBC_VER}…"
if curl -fsSL "$URL" -o "/tmp/$ZIP"; then
  unzip -o -q "/tmp/$ZIP" -d "$IBC_DIR" && echo "✓ IBC unpacked to $IBC_DIR"
  chmod +x "$IBC_DIR"/*.sh 2>/dev/null || true
else
  echo "⚠ couldn't auto-download IBC (version/URL may have changed)."
  echo "  Grab the macOS zip manually: https://github.com/IbcAlpha/IBC/releases"
  echo "  Unzip it into: $IBC_DIR"
fi

# stage the config (only if not already present, so we never clobber real creds)
if [ ! -f "$IBC_DIR/config.ini" ]; then
  cp "$REPO/config/ibc.config.template.ini" "$IBC_DIR/config.ini"
  echo "✓ config staged at $IBC_DIR/config.ini  (FILL IN your paper creds there)"
else
  echo "• $IBC_DIR/config.ini already exists — left it alone"
fi

# install the launchd job with the real home path resolved (not bootstrapped yet —
# do that after creds are in and a manual login works)
LA="$HOME/Library/LaunchAgents"; mkdir -p "$LA"
sed "s#__HOME__#$HOME#g" "$REPO/scripts/com.star.ibgateway.plist" > "$LA/com.star.ibgateway.plist"
echo "✓ launchd job written: $LA/com.star.ibgateway.plist (bootstrap it in step 5)"

cat <<EOF

────────────────── MANUAL STEPS (only you can do) ──────────────────
1. Install IB Gateway (standalone, paper-capable):
     https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
   Note its install path (e.g. /Applications/IB Gateway <ver>).

2. Edit  $IBC_DIR/config.ini  and set:
     IbLoginId=<your PAPER username>
     IbPassword=<your PAPER password>      ← stays local, never committed
   (TradingMode=paper and OverrideTwsApiPort=7497 are already set.)

3. Point IBC at the Gateway install: edit $IBC_DIR/gatewaystart.sh and set
     TWS_MAJOR_VRSN and IBC_INI=$IBC_DIR/config.ini  (and TWS path if prompted).

4. Start it once to verify login:   bash $IBC_DIR/gatewaystart.sh
   Then quit TWS (so 7497 is free) and let IBC/Gateway own 7497.

5. Make it 24/7:  cp $REPO/scripts/com.star.ibgateway.plist ~/Library/LaunchAgents/
                  launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.star.ibgateway.plist

Verify:  ./venv/bin/python3 engine/ibkr_broker.py   → type:paper, can_auto_trade:true
─────────────────────────────────────────────────────────────────────
EOF
