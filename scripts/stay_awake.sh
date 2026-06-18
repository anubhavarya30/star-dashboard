#!/usr/bin/env bash
# STAR — keep the server laptop running 24/7, even with the lid CLOSED.
# Run with sudo:  sudo bash scripts/stay_awake.sh
# Reverse later:  sudo pmset -a disablesleep 0   (then normal sleep returns)
set -e
if [ "$(id -u)" -ne 0 ]; then echo "Run with sudo: sudo bash scripts/stay_awake.sh"; exit 1; fi
echo "▶ configuring 24/7 always-on power settings…"
pmset -a sleep 0            # never system-sleep
pmset -a disksleep 0        # never disk-sleep
pmset -a displaysleep 1     # screen can sleep (saves the panel); machine stays up
pmset -a disablesleep 1     # CRITICAL: stay awake with the lid CLOSED (clamshell)
pmset -a powernap 0
pmset -a autopoweroff 0
pmset -a standby 0
echo "✓ done. This Mac will now stay running with the lid closed (keep it plugged in)."
echo "  Current settings:"; pmset -g | grep -E "sleep|disablesleep|displaysleep" || true
echo ""
echo "Tip: also enable auto-login (System Settings → Users & Groups → Auto-login)"
echo "     so launchd jobs come back automatically after a power cut/reboot."
