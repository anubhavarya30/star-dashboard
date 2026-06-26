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


def star_pnl():
    """ONE unified STAR P&L across every source (stock + options + gold). Returns
    today's realized, all-time realized, counts, and the per-source split — so the
    dashboard shows a single honest STAR number instead of a $0 stock tile while the
    options desk is green."""
    import datetime
    rows = paper_trades_all(5000)
    today = datetime.date.today().isoformat()
    tot = {"date": today, "today_pnl": 0.0, "today_trades": 0, "all_pnl": 0.0,
           "all_trades": 0, "all_wins": 0, "by_source": {}}
    for r in rows:
        pnl = float(r.get("pnl") or 0)
        src = r.get("source") or "stock"
        bs = tot["by_source"].setdefault(src, {"pnl": 0.0, "trades": 0, "wins": 0})
        bs["pnl"] = round(bs["pnl"] + pnl, 2); bs["trades"] += 1
        bs["wins"] += 1 if pnl > 0 else 0
        tot["all_pnl"] = round(tot["all_pnl"] + pnl, 2); tot["all_trades"] += 1
        tot["all_wins"] += 1 if pnl > 0 else 0
        if str(r.get("closed_at", ""))[:10] == today:
            tot["today_pnl"] = round(tot["today_pnl"] + pnl, 2); tot["today_trades"] += 1
    tot["all_win_rate"] = round(tot["all_wins"] / tot["all_trades"] * 100, 1) if tot["all_trades"] else 0
    return tot


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
    """Daily realized P&L for the calendar — derived from the SAME paper_trades
    ledger as STAR P&L (star_pnl) and the strategy table, so EVERY P&L view in the
    dashboard reconciles to ONE number. (Previously triple-sourced from executions +
    paper_results.csv + snapshots, which double-counted and diverged from the desk
    ledger — that's what made the calendar and the Paper page disagree.)"""
    from datetime import timedelta
    cutoff = (datetime.now().astimezone().date() - timedelta(days=int(days))).isoformat()
    by = {}
    for r in paper_trades_all(8000):
        d = str(r.get("closed_at", ""))[:10]
        if not d or d < cutoff:
            continue
        e = by.setdefault(d, {"date": d, "realized": 0.0, "unrealized": 0.0, "trades": 0, "total": 0.0})
        e["realized"] = round(e["realized"] + (r.get("pnl") or 0), 2)
        e["trades"] += 1
    for e in by.values():
        e["total"] = e["realized"]
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
