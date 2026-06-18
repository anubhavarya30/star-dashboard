#!/usr/bin/env bash
# STAR — connect to the 24/7 server from this laptop, on ANY network (via Tailscale).
# Ensures Tailscale is up, verifies the server is reachable, and prints live status
# + quick-access commands. Safe to run anytime.
SERVER_IP="${STAR_SERVER_IP:-100.97.21.122}"     # server's Tailscale IP (stable)
SERVER_USER="${STAR_SERVER_USER:-anubhav.arya}"
DASH="http://$SERVER_IP:8080"

# locate tailscale CLI (PATH or the macOS app bundle)
TS="$(command -v tailscale || echo /Applications/Tailscale.app/Contents/MacOS/Tailscale)"

echo "🛰  STAR server: $SERVER_IP  (user $SERVER_USER)"
echo "── Tailscale ──"
if [ -x "$TS" ] || command -v tailscale >/dev/null 2>&1; then
  st="$("$TS" status 2>&1 | head -1)"
  if echo "$st" | grep -qi "logged out\|NeedsLogin"; then
    echo "  ⚠ Tailscale is LOGGED OUT. Run:  $TS up   (sign in as anubhav.arya789@)"
    exit 1
  fi
  echo "  ✓ up"
else
  echo "  ⚠ Tailscale not found. Install: https://tailscale.com/download/macos"; exit 1
fi

echo "── Reachability ──"
if curl -s -o /dev/null --max-time 8 "$DASH/"; then
  echo "  ✓ dashboard reachable"
else
  echo "  ✗ can't reach $DASH"
  echo "    fixes: ensure the SERVER laptop is on + Tailscale up there; check it's awake."
  exit 1
fi

echo "── Live STAR status ──"
curl -s --max-time 8 "$DASH/api/calendar"     | python3 -c "import sys,json;d=json.load(sys.stdin);print('  market   :',d.get('note'))" 2>/dev/null
curl -s --max-time 8 "$DASH/api/ibkr_broker"  | python3 -c "import sys,json;d=json.load(sys.stdin);print('  IBKR     :',('connected '+str(d.get('account'))+' '+str(d.get('type'))+' auto='+str(d.get('can_auto_trade'))) if d.get('connected') else 'NOT connected')" 2>/dev/null
curl -s --max-time 8 "$DASH/api/paper_trades" | python3 -c "import sys,json;d=json.load(sys.stdin);print('  realized :','\$'+str(d.get('realized_today')),'| open',len(d.get('open',[])));[print('     ',p['symbol'],p['shares'],'sh @',p['entry'],'now',p.get('current'),'('+str(p.get('r_mult'))+'R)') for p in d.get('open',[])]" 2>/dev/null

echo "── Quick access ──"
echo "  dashboard : $DASH        (also open on phone w/ Tailscale)"
echo "  ssh       : ssh $SERVER_USER@$SERVER_IP"
echo "  logs      : ssh $SERVER_USER@$SERVER_IP 'tail -f /tmp/star_paper.log'"
[ "${1:-}" = "--open" ] && open "$DASH"
