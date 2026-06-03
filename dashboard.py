"""
dashboard.py
============
Streamlit control panel for Star's autonomous trading system.

Features
--------
* TradingView **Lightweight Charts** (candlesticks) rendered via
  st.components.v1.html() for XAUUSD + the 5 approved NYSE symbols.
* Six sidebar pages, all reading from Supabase:
    1. Gold Monitor (XAUUSD)
    2. Watchlist
    3. Positions
    4. Trades
    5. Agent Signals
    6. Lessons & Mistakes
* Only the 5 approved symbols are ever shown (everything else is hidden).

Env (NEVER hardcode the service_role key — prefer anon/publishable + RLS):
    export SUPABASE_URL="https://<ref>.supabase.co"
    export SUPABASE_KEY="<anon or publishable key>"

Run:  streamlit run dashboard.py
"""
from __future__ import annotations
import os
import json
import datetime as dt
from dotenv import load_dotenv

load_dotenv()

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

APPROVED_SYMBOLS = ["CAT", "JPM", "XOM", "DIS", "NEM"]      # whitelist
GOLD_SYMBOL = "XAUUSD"
CHART_SYMBOLS = [GOLD_SYMBOL] + APPROVED_SYMBOLS

st.set_page_config(page_title="Star • Algo Trading", page_icon="🟡", layout="wide")


# --------------------------------------------------------------------------- #
#  Supabase access
# --------------------------------------------------------------------------- #
@st.cache_resource
def get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except ImportError:
        return None


@st.cache_data(ttl=20)
def fetch_table(name: str, order_col: str | None = None, desc: bool = True) -> pd.DataFrame:
    sb = get_client()
    if sb is None:
        return pd.DataFrame()
    try:
        q = sb.table(name).select("*")
        if order_col:
            q = q.order(order_col, desc=desc)
        rows = q.execute().data
        df = pd.DataFrame(rows)
        # enforce the symbol whitelist anywhere a symbol column exists
        if "symbol" in df.columns:
            allowed = set(APPROVED_SYMBOLS + [GOLD_SYMBOL])
            df = df[df["symbol"].isin(allowed)]
        return df
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Could not load `{name}`: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=20)
def fetch_candles(symbol: str) -> list[dict]:
    """Return [{time, open, high, low, close}, ...] for the chart.

    Reads from an optional `ohlc` table (symbol, ts, open, high, low, close).
    Falls back to an empty list if the table/rows are absent.
    """
    sb = get_client()
    if sb is None:
        return []
    try:
        rows = (sb.table("ohlc").select("ts,open,high,low,close")
                .eq("symbol", symbol).order("ts", desc=False).limit(500).execute().data)
        out = []
        for r in rows:
            ts = r["ts"]
            # lightweight-charts wants UNIX seconds or 'yyyy-mm-dd'
            if isinstance(ts, str):
                ts = int(pd.Timestamp(ts).timestamp())
            out.append({"time": int(ts), "open": r["open"], "high": r["high"],
                        "low": r["low"], "close": r["close"]})
        return out
    except Exception:
        return []


# --------------------------------------------------------------------------- #
#  TradingView Lightweight Charts embed
# --------------------------------------------------------------------------- #
def tradingview_chart(candles: list[dict], title: str, height: int = 440):
    if not candles:
        st.info(f"No candle data in Supabase `ohlc` for {title}. "
                "Populate the `ohlc` table to render the chart.")
        return
    data_json = json.dumps(candles)
    html = f"""
    <div style="font-family:Inter,system-ui,sans-serif;color:#d1d4dc;
                background:#131722;padding:6px 10px;border-radius:8px;">
      <div style="font-weight:600;margin-bottom:4px;">{title}</div>
      <div id="chart" style="height:{height}px;"></div>
    </div>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script>
      const el = document.getElementById('chart');
      const chart = LightweightCharts.createChart(el, {{
        layout: {{ background: {{ color: '#131722' }}, textColor: '#d1d4dc' }},
        grid: {{ vertLines: {{ color: '#1f2733' }}, horzLines: {{ color: '#1f2733' }} }},
        rightPriceScale: {{ borderColor: '#2a2e39' }},
        timeScale: {{ borderColor: '#2a2e39', timeVisible: true, secondsVisible: false }},
        crosshair: {{ mode: 0 }},
      }});
      const series = chart.addCandlestickSeries({{
        upColor: '#26a69a', downColor: '#ef5350',
        wickUpColor: '#26a69a', wickDownColor: '#ef5350', borderVisible: false,
      }});
      series.setData({data_json});
      chart.timeScale().fitContent();
      new ResizeObserver(() => chart.applyOptions({{ width: el.clientWidth }})).observe(el);
    </script>
    """
    components.html(html, height=height + 60)


def metric_row(df: pd.DataFrame, fields: list[tuple[str, str]]):
    cols = st.columns(len(fields))
    for c, (label, key) in zip(cols, fields):
        val = df[key].iloc[0] if (not df.empty and key in df.columns) else "—"
        c.metric(label, val)


# --------------------------------------------------------------------------- #
#  Pages
# --------------------------------------------------------------------------- #
def page_gold():
    st.header("🟡 Gold Monitor — XAUUSD")
    states = fetch_table("agent_states")
    gm = states[states.get("agent_name", pd.Series(dtype=str)) == "gold_monitor"] \
        if not states.empty else pd.DataFrame()
    if not gm.empty:
        s = gm.iloc[0].get("state", {})
        s = s if isinstance(s, dict) else json.loads(s or "{}")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Last", s.get("last_price", "—"))
        c2.metric("RSI(14)", s.get("rsi", "—"))
        c3.metric("MACD hist", s.get("macd_hist", "—"))
        c4.metric("Decision", s.get("decision", "—"))
        c5.metric("Score", s.get("composite_score", "—"))
        if s.get("entry"):
            st.caption(f"Plan → entry {s['entry']} · stop {s['stop']} · "
                       f"target {s['target']} · R:R {s.get('risk_reward','—')}")
    else:
        st.info("Waiting for gold_monitor.py to publish to `agent_states`.")
    tradingview_chart(fetch_candles(GOLD_SYMBOL), "XAUUSD — 5m")


def page_watchlist():
    st.header("⭐ Today's Watchlist")
    wl = fetch_table("watchlist", order_col="rank", desc=False)
    if wl.empty:
        st.info("No watchlist rows yet.")
        return
    show = [c for c in ["rank", "symbol", "strategy", "side", "entry", "stop",
                        "target", "rr", "reason"] if c in wl.columns]
    st.dataframe(wl[show], use_container_width=True, hide_index=True)
    sym = st.selectbox("Chart", APPROVED_SYMBOLS)
    tradingview_chart(fetch_candles(sym), f"{sym} — 1h")


def page_positions():
    st.header("💼 Open Positions")
    pos = fetch_table("positions")
    if pos.empty:
        st.info("No open positions.")
        return
    if {"entry_price", "current_price", "qty"}.issubset(pos.columns):
        pos["pnl_pct"] = ((pos["current_price"] / pos["entry_price"] - 1) * 100).round(2)
        pos["pnl"] = ((pos["current_price"] - pos["entry_price"]) * pos["qty"]).round(2)
    st.dataframe(pos, use_container_width=True, hide_index=True)
    if "pnl" in pos.columns:
        st.metric("Total open P&L", f"{pos['pnl'].sum():,.2f}")


def page_trades():
    st.header("📒 Trade Log")
    tr = fetch_table("trades", order_col="entry_time")
    if tr.empty:
        st.info("No trades logged yet.")
        return
    if "pnl" in tr.columns:
        wins = (tr["pnl"] > 0).sum()
        total = tr["pnl"].notna().sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Net P&L", f"{tr['pnl'].sum():,.2f}")
        c2.metric("Win rate", f"{(wins/total*100):.0f}%" if total else "—")
        c3.metric("Trades", len(tr))
    st.dataframe(tr, use_container_width=True, hide_index=True)


def page_signals():
    st.header("🤖 Agent Signals")
    states = fetch_table("agent_states", order_col="updated_at")
    if states.empty:
        st.info("No agent states published.")
        return
    st.dataframe(states[[c for c in ["agent_name", "symbol", "signal", "score",
                                     "updated_at"] if c in states.columns]],
                 use_container_width=True, hide_index=True)


def page_lessons():
    st.header("🧠 Lessons & Mistakes")
    mistakes = fetch_table("mistakes", order_col="created_at")
    if mistakes.empty:
        st.info("No mistakes logged — clean record (so far).")
    else:
        st.subheader("Mistake / root-cause log")
        st.dataframe(mistakes[[c for c in ["symbol", "strategy", "root_cause",
                                           "lesson", "created_at"] if c in mistakes.columns]],
                     use_container_width=True, hide_index=True)
    md = os.path.join(os.path.dirname(__file__), "lessons_learned.md")
    if os.path.exists(md):
        st.subheader("Playbook — lessons_learned.md")
        with open(md, encoding="utf-8") as fh:
            st.markdown(fh.read())


PAGES = {
    "🟡 Gold Monitor": page_gold,
    "⭐ Watchlist": page_watchlist,
    "💼 Positions": page_positions,
    "📒 Trades": page_trades,
    "🤖 Agent Signals": page_signals,
    "🧠 Lessons & Mistakes": page_lessons,
}


def main():
    st.sidebar.title("⭐ Star")
    st.sidebar.caption("Autonomous algo trading")
    if get_client() is None:
        st.sidebar.error("Supabase not configured.\nSet SUPABASE_URL & SUPABASE_KEY.")
    else:
        st.sidebar.success("Supabase connected")
    st.sidebar.markdown("**Approved symbols**")
    st.sidebar.write(", ".join(APPROVED_SYMBOLS))
    choice = st.sidebar.radio("Navigate", list(PAGES.keys()))
    st.sidebar.caption(f"Refreshed {dt.datetime.now():%H:%M:%S}")
    PAGES[choice]()


if __name__ == "__main__":
    main()
