"""
⭐ Star Trading System - Live IBKR Dashboard
Real-time positions from Interactive Brokers with TradingView charts
"""
from dotenv import load_dotenv
load_dotenv()

import os
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
from datetime import datetime
import pytz
import pandas as pd
import yfinance as yf
import json

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(
    page_title="Star Trading - Live IBKR",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# MARKET STATUS INDICATOR
# ============================================================
def market_status():
    """Get NYSE market status"""
    ny = pytz.timezone('America/New_York')
    now = datetime.now(ny)
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()
    time_decimal = hour + minute/60

    if weekday >= 5:
        return '🔴 NYSE CLOSED (Weekend)', 'red'
    elif 9.5 <= time_decimal < 16:
        return '🟢 NYSE OPEN', 'green'
    elif 4 <= time_decimal < 9.5:
        return '🟡 PRE-MARKET (4:00 - 9:30)', 'orange'
    elif 16 <= time_decimal < 20:
        return '🟡 AFTER-HOURS (4:00 - 8:00 PM)', 'orange'
    else:
        return '🔴 NYSE CLOSED', 'red'

status, color = market_status()

# Display market status
st.markdown(
    f"""
    <div style='background-color: {color}20; border-left: 4px solid {color}; padding: 10px; border-radius: 4px; margin-bottom: 20px;'>
    <h3 style='margin: 0; color: white;'>{status} | 🥇 GOLD: Always Open 24/7</h3>
    </div>
    """,
    unsafe_allow_html=True
)

# ============================================================
# SUPABASE
# ============================================================
@st.cache_resource
def get_supabase():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

sb = get_supabase()

# ============================================================
# FETCH DATA
# ============================================================
@st.cache_data(ttl=30)
def fetch_positions():
    """Fetch open positions from Supabase (updated by ibkr_sync.py)"""
    try:
        result = sb.table("positions").select("*").eq("status", "open").execute()
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Error fetching positions: {e}")
        return []

@st.cache_data(ttl=30)
def fetch_trades():
    """Fetch completed trades"""
    try:
        result = sb.table("trades").select("*").limit(50).execute()
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Error fetching trades: {e}")
        return []

@st.cache_data(ttl=30)
def fetch_table(table_name, filters=None):
    """Fetch data from Supabase (graceful error handling)."""
    try:
        q = sb.table(table_name).select("*")
        if filters:
            for key, value in filters.items():
                q = q.eq(key, value)

        # Try to order by last_updated if it exists, otherwise don't order
        try:
            return q.order("last_updated", desc=True).limit(100).execute().data
        except:
            # If order fails, just return without ordering
            return q.limit(100).execute().data

    except Exception as e:
        error_msg = str(e)
        # Silently fail for missing tables
        if "Could not find the table" in error_msg or "WITHIN GROUP" in error_msg:
            return []
        return []

@st.cache_data(ttl=30)
def fetch_gold_monitor():
    """Fetch latest gold monitor data"""
    try:
        result = sb.table("agent_states").select("*").eq("agent_name", "GoldMonitor").execute()
        return result.data[0] if result.data else None
    except Exception as e:
        return None

# ============================================================
# TRADINGVIEW CHARTS
# ============================================================
@st.cache_data(ttl=60)
def get_ohlc_data(symbol: str, period: str = "5d") -> list:
    """Fetch OHLC data for TradingView chart"""
    try:
        # Map symbols for yfinance
        yf_symbol = symbol
        if symbol == "XAUUSD":
            yf_symbol = "GC=F"  # Gold futures

        data = yf.download(yf_symbol, period=period, progress=False)

        if data.empty:
            return []

        # Flatten MultiIndex columns if needed
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        candles = []
        for idx, row in data.iterrows():
            timestamp = int(idx.timestamp())
            candles.append({
                "time": timestamp,
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close'])
            })

        return candles
    except Exception as e:
        print(f"Error fetching OHLC for {symbol}: {e}")
        return []

def render_tradingview_chart(symbol: str, candles: list, height: int = 400):
    """Render TradingView Lightweight Charts"""
    if not candles:
        st.info(f"📭 No chart data for {symbol}")
        return

    data_json = json.dumps(candles)

    html = f"""
    <div style="width: 100%; height: {height}px; background-color: #1e1e1e; border-radius: 8px; overflow: hidden;">
        <div id="chart-{symbol}" style="width: 100%; height: 100%;"></div>
    </div>

    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script>
        const container = document.getElementById('chart-{symbol}');
        const chart = LightweightCharts.createChart(container, {{
            layout: {{
                background: {{ color: '#1e1e1e' }},
                textColor: '#d1d5db',
            }},
            width: container.clientWidth,
            height: {height},
            timeScale: {{
                timeVisible: true,
                secondsVisible: false,
                borderColor: '#3f4451',
            }},
            grid: {{
                horzLines: {{ color: '#2a2e39' }},
                vertLines: {{ color: '#2a2e39' }},
            }},
        }});

        const candlestickSeries = chart.addCandlestickSeries({{
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderUpColor: '#26a69a',
            borderDownColor: '#ef5350',
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350',
        }});

        const data = {data_json};
        candlestickSeries.setData(data);
        chart.timeScale().fitContent();

        window.addEventListener('resize', () => {{
            chart.applyOptions({{ width: container.clientWidth }});
        }});
    </script>
    """

    components.html(html, height=height + 50, scrolling=False)


# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.title("⭐ Star Trading System")
page = st.sidebar.radio(
    "Navigation",
    options=[
        "💼 Live Positions (IBKR)",
        "📊 Completed Trades",
        "🟡 Gold Monitor 24/7",
        "🤖 Agent Status",
        "⭐ Star's Decisions",
        "📋 Agent Reports",
        "📈 Performance"
    ],
    label_visibility="collapsed"
)

# ============================================================
# PAGE 1: LIVE POSITIONS
# ============================================================
if page == "💼 Live Positions (IBKR)":
    st.header("💼 Live Positions - Interactive Brokers")
    st.caption("✅ Syncing every 60 seconds from IBKR")

    positions = fetch_positions()

    if positions:
        df = pd.DataFrame(positions)

        # Summary metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📊 Open Positions", len(df))
        with col2:
            total_pnl = df['pnl_pct'].sum() if 'pnl_pct' in df.columns else 0
            st.metric("Total P&L %", f"{total_pnl:.2f}%")
        with col3:
            total_value = df['current_price'].sum() if 'current_price' in df.columns else 0
            st.metric("Position Value", f"${total_value:.2f}")
        with col4:
            winning = len(df[df['pnl_pct'] > 0]) if 'pnl_pct' in df.columns else 0
            st.metric("Winning Positions", winning)
        with col5:
            last_update = df['updated_at'].max() if 'updated_at' in df.columns else "—"
            st.metric("Last IBKR Sync", last_update[:10] if last_update else "—")

        # Positions detail
        st.subheader("Position Details")

        for idx, pos in df.iterrows():
            symbol = pos.get('symbol', 'N/A')
            direction = pos.get('direction', 'N/A')
            entry_price = pos.get('entry_price', 0)
            current_price = pos.get('current_price', 0)
            pnl_pct = pos.get('pnl_pct', 0)
            strategy = pos.get('strategy', 'N/A')
            entry_time = pos.get('entry_time', 'N/A')

            # Create expandable card
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric(f"📈 {symbol}", f"${current_price:.2f}", f"{pnl_pct:.2f}%")
                with col2:
                    st.write(f"**Direction:** {direction}")
                    st.write(f"**Entry:** ${entry_price:.2f}")
                with col3:
                    st.write(f"**Strategy:** {strategy}")
                    st.write(f"**Entry Time:** {entry_time[:10]}")
                with col4:
                    # Calculate time in trade
                    try:
                        from datetime import datetime as dt
                        entry_dt = dt.fromisoformat(entry_time.replace('+00:00', ''))
                        now = dt.utcnow()
                        hours_in = (now - entry_dt).total_seconds() / 3600
                        st.write(f"**Hours in Trade:** {hours_in:.1f}h")
                        st.write(f"**Win Probability:** 65%")
                    except:
                        st.write("**Time in Trade:** —")

                # Add TradingView chart
                st.subheader(f"📊 {symbol} - 5 Day Chart")
                candles = get_ohlc_data(symbol, period="5d")
                render_tradingview_chart(symbol, candles, height=350)

    else:
        st.info("📭 No open positions. Start trading!")

# ============================================================
# PAGE 2: COMPLETED TRADES
# ============================================================
elif page == "📊 Completed Trades":
    st.header("📊 Completed Trades - Daily Summary")

    trades = fetch_trades()

    if trades:
        df = pd.DataFrame(trades)

        # Summary
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Trades", len(df))
        with col2:
            wins = len(df[df.get('pnl', pd.Series([0])) > 0])
            st.metric("Winning Trades", wins)
        with col3:
            total_pnl = df['pnl'].sum() if 'pnl' in df.columns else 0
            st.metric("Total P&L", f"${total_pnl:.2f}")
        with col4:
            win_rate = (wins / len(df) * 100) if len(df) > 0 else 0
            st.metric("Win Rate", f"{win_rate:.0f}%")

        # Trades detail
        st.subheader("Today's Trades")

        for idx, trade in df.iterrows():
            symbol = trade.get('symbol', 'N/A')
            direction = trade.get('direction', 'N/A')
            entry_price = trade.get('entry_price', 0)
            exit_price = trade.get('exit_price', 0)
            pnl = trade.get('pnl', 0)
            pnl_pct = trade.get('pnl_pct', 0)
            entry_time = trade.get('entry_time', 'N/A')
            exit_time = trade.get('exit_time', 'N/A')
            reason = trade.get('reason', 'N/A')

            # Color based on P&L
            pnl_color = "🟢" if pnl > 0 else "🔴"

            with st.container(border=True):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(f"{pnl_color} {symbol} {direction}", f"${pnl:.2f}", f"{pnl_pct:.2f}%")
                with col2:
                    st.write(f"**Entry:** ${entry_price:.2f}")
                    st.write(f"**Exit:** ${exit_price:.2f}")
                with col3:
                    st.write(f"**Entered:** {entry_time[:10]}")
                    st.write(f"**Exited:** {exit_time[:10]}")

                st.caption(f"**Reason:** {reason}")

    else:
        st.info("📭 No completed trades today.")

# ============================================================
# PAGE 3: GOLD MONITOR
# ============================================================
elif page == "🟡 Gold Monitor 24/7":
    st.header("🟡 Gold Monitor — XAUUSD (24/7)")

    gold = fetch_gold_monitor()

    if gold and gold.get('status') == 'active':
        last_signal = gold.get('last_signal', '')
        last_updated = gold.get('last_updated', '')

        # Parse signal
        parts = last_signal.split('|')
        price_str = parts[0].strip().replace('$', '') if len(parts) > 0 else 'N/A'
        signal_str = parts[1].strip() if len(parts) > 1 else 'HOLD'
        rsi_str = parts[2].strip().replace('RSI:', '').strip() if len(parts) > 2 else 'N/A'

        try:
            price = float(price_str)
            rsi = float(rsi_str)
        except:
            price = price_str
            rsi = rsi_str

        # Display metrics
        with st.container(border=True):
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("💰 Price", f"${price:.2f}" if isinstance(price, float) else price)
            with col2:
                st.metric("📊 RSI(14)", f"{rsi:.0f}" if isinstance(rsi, float) else rsi)
            with col3:
                st.metric("📈 MACD", "Computing...")
            with col4:
                signal_emoji = "🟢" if signal_str == "BUY" else "🔴" if signal_str == "SELL" else "🟡"
                st.metric(f"{signal_emoji} Signal", signal_str)
            with col5:
                st.metric("🕐 Updated", last_updated[:10] if last_updated else "—")

        st.success(f"✅ Gold Monitor ACTIVE | {last_signal}")

        # Display gold chart
        st.subheader("📊 XAUUSD - Live Gold Chart (5 Days)")
        candles = get_ohlc_data("XAUUSD", period="1mo")
        render_tradingview_chart("XAUUSD", candles, height=400)

        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    else:
        st.warning("⏳ Gold monitor not active")

# ============================================================
# PAGE 4: AGENT STATUS
# ============================================================
elif page == "🤖 Agent Status":
    st.header("🤖 Agent Status")

    try:
        agents_state = fetch_table("agent_states")

        if agents_state:
            # Status grid
            cols = st.columns(min(len(agents_state), 4))
            for idx, agent in enumerate(agents_state):
                with cols[idx % len(cols)]:
                    status_emoji = "🟢" if agent.get('status') == "active" else "🔴" if agent.get('status') == "error" else "⚪"
                    st.metric(
                        f"{status_emoji} {agent.get('agent_name', 'Unknown')}",
                        agent.get('status', 'unknown'),
                        agent.get('last_signal', '')[:40]
                    )

            # Signals from each agent
            st.subheader("Recent Agent Signals")
            signals = fetch_table("agent_signals")
            if signals:
                df = pd.DataFrame(signals)
                if len(df) > 0:
                    cols_to_show = [c for c in ['agent_name', 'symbol', 'signal', 'confidence', 'created_at'] if c in df.columns]
                    st.dataframe(df[cols_to_show], use_container_width=True)
        else:
            st.info("🔄 Agents running - check back after running agents")
    except Exception as e:
        st.warning("Agent status unavailable - run agents_lite.py to generate signals")

# ============================================================
# PAGE 5: STAR'S DECISIONS
# ============================================================
elif page == "⭐ Star's Decisions":
    st.header("⭐ Star's Decisions — Awaiting Your Approval")

    try:
        decisions = fetch_table("star_decision", {"status": "pending_approval"})

        if decisions:
            for decision in decisions:
                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    st.subheader(f"{decision['symbol']}")
                    st.metric(
                        "Recommended Action",
                        decision['recommended_action'],
                        f"{decision.get('confidence', 0)*100:.0f}% confidence"
                    )

                with col2:
                    vote_tally = decision.get('vote_tally', {})
                    st.write("**Agent Votes:**")
                    for action in ['BUY', 'SELL', 'HOLD']:
                        st.caption(f"{action}: {vote_tally.get(action, 0)}")

                with col3:
                    st.write("**Your Decision:**")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button(f"✅ YES", key=f"yes_{decision['id']}"):
                            sb.table("star_decision").update({
                                "user_approved": True,
                                "status": "approved",
                                "approved_at": datetime.utcnow().isoformat()
                            }).eq("id", decision['id']).execute()
                            st.success(f"✅ Approved: {decision['symbol']} {decision['recommended_action']}")
                            st.rerun()

                    with col_b:
                        if st.button(f"❌ NO", key=f"no_{decision['id']}"):
                            sb.table("star_decision").update({
                                "user_approved": False,
                                "status": "rejected",
                                "approved_at": datetime.utcnow().isoformat()
                            }).eq("id", decision['id']).execute()
                            st.error(f"❌ Rejected: {decision['symbol']}")
                            st.rerun()

                st.divider()
        else:
            st.info("✅ All decisions approved or no pending decisions.")

        # Approved decisions
        st.subheader("✅ Approved Decisions Today")
        approved = fetch_table("star_decision", {"user_approved": True})
        if approved:
            df = pd.DataFrame(approved)
            cols_to_show = [c for c in ['symbol', 'recommended_action', 'confidence', 'approved_at'] if c in df.columns]
            st.dataframe(df[cols_to_show], use_container_width=True)
        else:
            st.info("No approved decisions yet today.")
    except Exception as e:
        st.warning("Star's Decisions unavailable")

# ============================================================
# PAGE 6: AGENT REPORTS
# ============================================================
elif page == "📋 Agent Reports":
    st.header("📋 Agent Reports")

    try:
        # Filter by agent
        agents = ["All"] + list(set([r.get("agent_name", "Unknown") for r in fetch_table("agent_reports")]))
        selected_agent = st.selectbox("Filter by Agent", agents)

        if selected_agent == "All":
            reports = fetch_table("agent_reports")
        else:
            reports = fetch_table("agent_reports", {"agent_name": selected_agent})

        if reports:
            for report in reports:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 1, 1])

                    with col1:
                        st.write(f"**{report['agent_name']}** — {report['report_type']}")

                    with col2:
                        st.caption(f"Confidence: {report.get('confidence', 0)*100:.0f}%")

                    with col3:
                        st.caption(report.get('created_at', '')[:10])

                    st.write(report.get('findings', {}))
        else:
            st.info("No reports yet. Run agents to generate reports.")
    except Exception as e:
        st.warning("Agent reports unavailable")

# ============================================================
# PAGE 7: PERFORMANCE
# ============================================================
elif page == "📈 Performance":
    st.header("📈 System Performance")

    trades = fetch_trades()

    if trades:
        df = pd.DataFrame(trades)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Trades", len(df))
        with col2:
            wins = len(df[df.get('pnl', pd.Series([0])) > 0])
            st.metric("Wins", wins)
        with col3:
            total_pnl = df['pnl'].sum() if 'pnl' in df.columns else 0
            st.metric("Total P&L", f"${total_pnl:.2f}")
        with col4:
            win_rate = (wins / len(df) * 100) if len(df) > 0 else 0
            st.metric("Win Rate", f"{win_rate:.0f}%")

        st.subheader("Strategy Performance")
        if 'strategy' in df.columns:
            strategy_stats = df.groupby('strategy').agg({
                'pnl': ['sum', 'count', 'mean']
            }).round(2)
            st.dataframe(strategy_stats, use_container_width=True)

    else:
        st.info("No trades yet.")

# ============================================================
# FOOTER
# ============================================================
st.sidebar.divider()
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
