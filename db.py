#!/usr/bin/env python3
"""
STAR — SQLite history layer (single owner of the trade/account history).

Tables (all real data, no seeding):
  account_snapshots   time series of account value (net liq / cash / buying power)
  position_snapshots  time series of each held position + unrealized P&L
  executions          real fills captured from IBKR (dedup by exec_id) — the trade ledger

The sync loop calls record_snapshot() and record_executions() each cycle.
The terminal API reads account_history() / trades() / position_history().
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "star_trading.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,                 -- ISO8601 local
    account_id TEXT,
    net_liquidation REAL,
    cash REAL,
    buying_power REAL,
    gross_position_value REAL
);
CREATE INDEX IF NOT EXISTS idx_acct_ts ON account_snapshots(ts);

CREATE TABLE IF NOT EXISTS position_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    account_id TEXT,
    symbol TEXT NOT NULL,
    quantity REAL,
    avg_cost REAL,
    market_price REAL,
    market_value REAL,
    unrealized_pnl REAL
);
CREATE INDEX IF NOT EXISTS idx_pos_ts ON position_snapshots(ts);
CREATE INDEX IF NOT EXISTS idx_pos_sym ON position_snapshots(symbol);

CREATE TABLE IF NOT EXISTS executions (
    exec_id TEXT PRIMARY KEY,         -- IBKR execution id (dedup)
    ts TEXT,                          -- fill time
    account_id TEXT,
    symbol TEXT,
    side TEXT,                        -- BOT / SLD
    shares REAL,
    price REAL,
    commission REAL,
    realized_pnl REAL,
    recorded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_exec_ts ON executions(ts);
"""


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.executescript(SCHEMA)


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat()


def record_snapshot(payload: dict, min_interval_sec: int = 300):
    """Insert an account + position snapshot. Throttled: skips if the last
    account snapshot is newer than min_interval_sec (keeps history clean)."""
    if payload.get("status") != "connected":
        return False
    with _conn() as c:
        last = c.execute("SELECT ts FROM account_snapshots ORDER BY id DESC LIMIT 1").fetchone()
        if last:
            try:
                age = (datetime.now(timezone.utc).astimezone()
                       - datetime.fromisoformat(last["ts"])).total_seconds()
                if age < min_interval_sec:
                    return False
            except ValueError:
                pass
        ts = _now()
        acct = payload.get("account_id")
        c.execute(
            "INSERT INTO account_snapshots(ts,account_id,net_liquidation,cash,buying_power,gross_position_value)"
            " VALUES(?,?,?,?,?,?)",
            (ts, acct, payload.get("net_liquidation"), payload.get("cash"),
             payload.get("buying_power"), payload.get("gross_position_value")),
        )
        for p in payload.get("positions", []):
            c.execute(
                "INSERT INTO position_snapshots(ts,account_id,symbol,quantity,avg_cost,market_price,market_value,unrealized_pnl)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (ts, acct, p.get("symbol"), p.get("quantity"), p.get("avg_cost"),
                 p.get("market_price"), p.get("market_value"), p.get("unrealized_pnl")),
            )
    return True


def record_executions(execs: list):
    """Upsert real fills. `execs` = list of dicts with exec_id,ts,account_id,
    symbol,side,shares,price,commission,realized_pnl. Dedup by exec_id."""
    if not execs:
        return 0
    n = 0
    with _conn() as c:
        for e in execs:
            cur = c.execute(
                "INSERT OR IGNORE INTO executions"
                "(exec_id,ts,account_id,symbol,side,shares,price,commission,realized_pnl,recorded_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (e.get("exec_id"), e.get("ts"), e.get("account_id"), e.get("symbol"),
                 e.get("side"), e.get("shares"), e.get("price"), e.get("commission"),
                 e.get("realized_pnl"), _now()),
            )
            n += cur.rowcount
    return n


def account_history(limit_days: int = 30):
    with _conn() as c:
        rows = c.execute(
            "SELECT ts,net_liquidation,cash,buying_power,gross_position_value"
            " FROM account_snapshots WHERE ts >= datetime('now', ?) ORDER BY ts ASC",
            (f"-{int(limit_days)} days",),
        ).fetchall()
    return [dict(r) for r in rows]


def trades(limit: int = 200):
    with _conn() as c:
        rows = c.execute(
            "SELECT ts,symbol,side,shares,price,commission,realized_pnl"
            " FROM executions ORDER BY ts DESC LIMIT ?", (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]


def position_history(symbol: str, limit_days: int = 30):
    with _conn() as c:
        rows = c.execute(
            "SELECT ts,quantity,market_price,market_value,unrealized_pnl"
            " FROM position_snapshots WHERE symbol=? AND ts >= datetime('now', ?) ORDER BY ts ASC",
            (symbol.upper(), f"-{int(limit_days)} days"),
        ).fetchall()
    return [dict(r) for r in rows]


def stats():
    with _conn() as c:
        a = c.execute("SELECT count(*) FROM account_snapshots").fetchone()[0]
        p = c.execute("SELECT count(*) FROM position_snapshots").fetchone()[0]
        e = c.execute("SELECT count(*) FROM executions").fetchone()[0]
    return {"account_snapshots": a, "position_snapshots": p, "executions": e}


if __name__ == "__main__":
    init_db()
    print("✅ history schema ready in", DB_PATH.name)
    print("   counts:", stats())
