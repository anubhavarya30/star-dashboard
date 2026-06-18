---
description: Connect to and check the STAR 24/7 trading server (over Tailscale, any network)
allowed-tools: Bash(bash*), Bash(curl*), Bash(ssh*), Bash(tailscale*), Bash(open*)
---

Connect to the STAR trading server and report its live status.

1. Run: `bash /Users/anubhavarya/star/star-dashboard/scripts/connect_server.sh`
2. Summarize for me: market status, IBKR connection, open positions (with live P&L/R),
   and realized P&L today.
3. If Tailscale is logged out, tell me to run `tailscale up` (I'll sign in).
4. If the server is unreachable, tell me the likely fix (server laptop asleep/off, or
   Tailscale down on the server).
5. Offer quick next actions: open the dashboard (`--open`), SSH in, or tail the live log.

The server is at Tailscale IP 100.97.21.122 (user anubhav.arya). It runs 24/7; this
just connects from wherever I am.
