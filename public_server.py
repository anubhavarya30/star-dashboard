"""STAR public read-only server (port 8090) — the ONLY thing exposed to the internet.

Serves public.html + /api/public: a whitelisted P&L summary pulled from the private
dashboard on localhost:8080. GET only; no account numbers, balances, positions or
order endpoints ever leave this machine. Never expose terminal_server (8080) itself:
it trusts localhost, so any tunnel pointed at it would bypass its password.
"""
import json
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
PRIVATE = "http://127.0.0.1:8080"
_cache = {"t": 0, "body": b""}


def _get(path):
    with urllib.request.urlopen(PRIVATE + path, timeout=20) as r:
        return json.load(r)


def _num(v):
    return round(float(v), 2) if isinstance(v, (int, float)) else 0.0


def public_snapshot():
    """Whitelist only — add fields here deliberately, never pass raw payloads through."""
    p = _get("/api/star_pnl")
    cal = _get("/api/pnl_calendar").get("days", [])[-30:]
    return {
        "as_of": p.get("date"),
        "today_pnl": _num(p.get("today_pnl")),
        "today_trades": int(p.get("today_trades") or 0),
        "all_pnl": _num(p.get("all_pnl")),
        "all_trades": int(p.get("all_trades") or 0),
        "win_rate": _num(p.get("all_win_rate")),
        "desks": {str(k): {"pnl": _num(v.get("pnl")), "trades": int(v.get("trades") or 0),
                           "wins": int(v.get("wins") or 0)}
                  for k, v in (p.get("by_source") or {}).items() if isinstance(v, dict)},
        "days": [{"date": str(d.get("date")), "pnl": _num(d.get("total")),
                  "trades": int(d.get("trades") or 0)} for d in cal],
        "mode": "paper",
    }


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._send(200, (HERE / "public.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/api/public":
            if time.time() - _cache["t"] > 30:  # shield the private server from traffic
                try:
                    _cache["body"] = json.dumps(public_snapshot()).encode()
                    _cache["t"] = time.time()
                except Exception:
                    if not _cache["body"]:
                        return self._send(503, b'{"error":"STAR server unavailable"}', "application/json")
            return self._send(200, _cache["body"], "application/json")
        self._send(404, b"not found", "text/plain")

    def do_POST(self):  # read-only: refuse every write
        self._send(405, b"read-only", "text/plain")

    do_PUT = do_DELETE = do_PATCH = do_POST


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8090), H).serve_forever()
