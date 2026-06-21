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


def _ensure_paper_table(c):
    c.execute("""CREATE TABLE IF NOT EXISTS paper_trades(
        id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, symbol TEXT, dir TEXT,
        shares REAL, entry REAL, exit REAL, stop REAL, target REAL,
        pnl REAL, pnl_pct REAL, r_mult REAL, opened_at TEXT, closed_at TEXT,
        duration_min REAL, recorded_at TEXT)""")


def record_paper_trade(rec: dict):
    """Persist one closed paper/gold trade to SQLite for durable analysis."""
    with _conn() as c:
        _ensure_paper_table(c)
        c.execute(
            "INSERT INTO paper_trades(source,symbol,dir,shares,entry,exit,stop,target,"
            "pnl,pnl_pct,r_mult,opened_at,closed_at,duration_min,recorded_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rec.get("source", "stock"), rec.get("symbol"), rec.get("dir", "LONG"),
             rec.get("shares"), rec.get("entry"), rec.get("exit"), rec.get("stop"),
             rec.get("target"), rec.get("pnl"), rec.get("pnl_pct"), rec.get("r_mult"),
             rec.get("opened_at"), rec.get("closed_at"), rec.get("duration_min"), _now()),
        )


def paper_trades_all(limit: int = 500, source: str = None):
    with _conn() as c:
        _ensure_paper_table(c)
        if source:
            rows = c.execute("SELECT * FROM paper_trades WHERE source=? ORDER BY closed_at DESC LIMIT ?",
                             (source, int(limit))).fetchall()
        else:
            rows = c.execute("SELECT * FROM paper_trades ORDER BY closed_at DESC LIMIT ?",
                             (int(limit),)).fetchall()
    return [dict(r) for r in rows]


def paper_stats():
    """Aggregate analysis across all persisted paper trades, by source."""
    rows = paper_trades_all(5000)
    out = {}
    for r in rows:
        g = out.setdefault(r["source"] or "stock",
                           {"trades": 0, "wins": 0, "pnl": 0.0, "r": 0.0})
        g["trades"] += 1
        g["wins"] += 1 if (r.get("pnl") or 0) > 0 or (r.get("r_mult") or 0) > 0 else 0
        g["pnl"] = round(g["pnl"] + (r.get("pnl") or 0), 2)
        g["r"] = round(g["r"] + (r.get("r_mult") or 0), 2)
    for g in out.values():
        g["win_rate"] = round(g["wins"] / g["trades"] * 100, 1) if g["trades"] else 0
        g["expectancy_r"] = round(g["r"] / g["trades"], 2) if g["trades"] else 0
    return out


def round_trips(limit: int = 200):
    """Pair real IBKR fills (BOT->SLD, FIFO per symbol) into round-trip trades
    with entry time, exit time, and HOLD DURATION — the real-trading equivalent of
    the paper-trade history. Only trades STAR places going forward get real entry
    times (IBKR doesn't expose them for pre-existing positions)."""
    from datetime import datetime
    with _conn() as c:
        rows = c.execute(
            "SELECT ts,symbol,side,shares,price,realized_pnl FROM executions ORDER BY ts ASC"
        ).fetchall()
    lots, trips = {}, []
    for r in rows:
        sym = r["symbol"]; side = (r["side"] or "").upper(); sh = r["shares"] or 0
        if side in ("BOT", "BUY"):
            lots.setdefault(sym, []).append({"ts": r["ts"], "shares": sh, "price": r["price"]})
        elif side in ("SLD", "SELL"):
            remain = sh
            while remain > 0 and lots.get(sym):
                lot = lots[sym][0]
                used = min(remain, lot["shares"])
                try:
                    dur = round((datetime.fromisoformat(r["ts"]) - datetime.fromisoformat(lot["ts"])).total_seconds() / 60, 1)
                except Exception:
                    dur = None
                trips.append({
                    "symbol": sym, "shares": used, "entry": lot["price"], "exit": r["price"],
                    "opened_at": lot["ts"], "closed_at": r["ts"], "duration_min": dur,
                    "pnl": round(((r["price"] or 0) - (lot["price"] or 0)) * used, 2),
                    "pnl_pct": round(((r["price"] / lot["price"]) - 1) * 100, 2) if lot["price"] else None,
                })
                lot["shares"] -= used; remain -= used
                if lot["shares"] <= 0:
                    lots[sym].pop(0)
    trips.sort(key=lambda t: t["closed_at"], reverse=True)
    return trips[:limit]


def position_history(symbol: str, limit_days: int = 30):
    with _conn() as c:
        rows = c.execute(
            "SELECT ts,quantity,market_price,market_value,unrealized_pnl"
            " FROM position_snapshots WHERE symbol=? AND ts >= datetime('now', ?) ORDER BY ts ASC",
            (symbol.upper(), f"-{int(limit_days)} days"),
        ).fetchall()
    return [dict(r) for r in rows]


def pnl_calendar(days: int = 35):
    """Daily P&L for the calendar. Realized P&L per day from the executions
    ledger, PLUS today's live unrealized P&L from open positions
    (live_account.json) — so an open AMZN at -$17 shows as today's -$17, and
    multiple open positions are summed."""
    import json
    with _conn() as c:
        rows = c.execute(
            "SELECT date(ts) d, COALESCE(SUM(realized_pnl),0) r, COUNT(*) n"
            " FROM executions WHERE ts >= date('now', ?) GROUP BY date(ts)",
            (f"-{int(days)} days",),
        ).fetchall()
    by = {r["d"]: {"date": r["d"], "realized": round(r["r"], 2),
                   "unrealized": 0.0, "trades": r["n"]} for r in rows}

    today = datetime.now().astimezone().date().isoformat()

    # historical per-day unrealized mark: sum the LAST snapshot of each day
    with _conn() as c:
        snaps = c.execute(
            "SELECT d, SUM(unrealized_pnl) u FROM ("
            "  SELECT date(ts) d, ts, unrealized_pnl,"
            "         RANK() OVER (PARTITION BY date(ts) ORDER BY ts DESC) rk"
            "  FROM position_snapshots WHERE ts >= date('now', ?)"
            ") WHERE rk = 1 GROUP BY d",
            (f"-{int(days)} days",),
        ).fetchall()
    for s in snaps:
        if s["d"] == today:
            continue  # today uses the live value below, not a stale snapshot
        e = by.get(s["d"], {"date": s["d"], "realized": 0.0, "unrealized": 0.0, "trades": 0})
        e["unrealized"] = round(s["u"] or 0.0, 2)
        by[s["d"]] = e

    # today's LIVE unrealized from open positions (fresher than any snapshot)
    unreal = 0.0
    connected = False
    lf = DB_PATH.parent / "live_account.json"
    if lf.exists():
        try:
            d = json.loads(lf.read_text())
            if d.get("status") == "connected":
                connected = True
                unreal = sum((p.get("unrealized_pnl") or 0) for p in d.get("positions", []))
        except Exception:
            pass
    if connected and (unreal or today in by):
        e = by.get(today, {"date": today, "realized": 0.0, "unrealized": 0.0, "trades": 0})
        e["unrealized"] = round(unreal, 2)
        by[today] = e

    # fold in the autonomous PAPER desk's daily results (data/paper_results.csv).
    # The desk's trades aren't in db.executions (no live IBKR sync when they filled),
    # so the calendar would otherwise show $0 even though the desk made +$74. This
    # makes the P&L Calendar match the Paper Trading tab.
    import csv as _csv
    pr = DB_PATH.parent / "data" / "paper_results.csv"
    if pr.exists():
        try:
            for row in _csv.DictReader(pr.open()):
                dt = row.get("date")
                if not dt:
                    continue
                e = by.get(dt, {"date": dt, "realized": 0.0, "unrealized": 0.0, "trades": 0})
                e["realized"] = round(e["realized"] + float(row.get("net_pnl") or 0), 2)
                e["trades"] = e["trades"] + int(row.get("trades") or 0)
                by[dt] = e
        except Exception:
            pass

    for e in by.values():
        e["total"] = round(e["realized"] + e["unrealized"], 2)
    return sorted(by.values(), key=lambda x: x["date"])


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
