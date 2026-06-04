"""
Star Trading Dashboard — Multi-Agent Workflow
Shows real-time agent reports, signals, Star's decisions, and user approval panel.
"""
from dotenv import load_dotenv
load_dotenv()

import os
import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
from datetime import datetime, timedelta
import plotly.express as px

@st.cache_resource
def get_supabase():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

sb = get_supabase()

st.set_page_config(
    page_title="Star • Multi-Agent Trading System",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar navigation
st.sidebar.title("⭐ Star Trading System")
page = st.sidebar.radio(
    "Navigation",
    options=[
        "💼 Positions & Trades",
        "🟡 Gold Monitor 24/7",
        "🤖 Agent Status",
        "📈 Performance",
        "🎯 Star's Decisions",
        "📊 Agent Reports"
    ],
    label_visibility="collapsed"
)

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
        # Silently fail for missing tables - don't show error
        if "Could not find the table" in error_msg or "WITHIN GROUP" in error_msg:
            return []
        # Only show errors for other issues
        if "Error" not in str(type(e)):
            pass  # Silent fail for expected errors
        return []

# ============================================================
# PAGE 1: STAR'S DECISIONS (CEO APPROVAL PANEL)
# ============================================================
if page == "🎯 Star's Decisions":
    st.header("⭐ Star's Decisions — Awaiting Your Approval")

    decisions = fetch_table("star_decision", {"status": "pending_approval"})

    if decisions:
        for decision in decisions:
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.subheader(f"{decision['symbol']}")
                st.metric(
                    "Recommended Action",
                    decision['recommended_action'],
                    f"{decision['confidence']*100:.0f}% confidence"
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
        st.dataframe(df[['symbol', 'recommended_action', 'confidence', 'approved_at']], use_container_width=True)
    else:
        st.info("No approved decisions yet today.")

# ============================================================
# PAGE 2: AGENT REPORTS
# ============================================================
elif page == "📊 Agent Reports":
    st.header("📊 Agent Reports")

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

                st.write(json.dumps(report.get('findings', {}), indent=2))
    else:
        st.info("No reports yet. Run agents to generate reports.")

# ============================================================
# PAGE 3: AGENT STATUS
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
# PAGE 4: POSITIONS & TRADES
# ============================================================
elif page == "💼 Positions & Trades":
    st.header("💼 Positions & Trades")

    col1, col2 = st.tabs(["Open Positions", "Completed Trades"])

    with col1:
        st.subheader("Open Positions")
        try:
            positions = fetch_table("positions")
            if positions:
                df = pd.DataFrame(positions)
                # Calculate P&L
                if 'current_price' in df.columns and 'entry_price' in df.columns:
                    df['pnl'] = df['current_price'] - df['entry_price']
                    df['pnl_pct'] = ((df['current_price'] - df['entry_price']) / df['entry_price'] * 100).round(2)

                # Show key columns
                cols_to_show = ['symbol', 'direction', 'entry_price', 'current_price', 'pnl_pct', 'strategy']
                cols_available = [c for c in cols_to_show if c in df.columns]

                st.dataframe(df[cols_available].head(10), use_container_width=True)

                # Summary metrics
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Total Positions", len(df))
                with col_b:
                    if 'pnl' in df.columns:
                        total_pnl = df['pnl'].sum()
                        st.metric("Total P&L", f"${total_pnl:.2f}")
                with col_c:
                    if 'pnl_pct' in df.columns:
                        avg_pnl = df['pnl_pct'].mean()
                        st.metric("Avg P&L %", f"{avg_pnl:.2f}%")
            else:
                st.info("No positions found")
        except Exception as e:
            st.warning(f"Could not load positions: {str(e)[:100]}")

    with col2:
        st.subheader("Completed Trades")
        try:
            trades = fetch_table("trades")
            if trades:
                df = pd.DataFrame(trades)

                # Show key columns
                cols_to_show = ['symbol', 'direction', 'entry_price', 'exit_price', 'pnl', 'pnl_pct', 'strategy']
                cols_available = [c for c in cols_to_show if c in df.columns]

                st.dataframe(df[cols_available].head(10), use_container_width=True)

                # P&L chart
                if 'pnl_pct' in df.columns and len(df) > 0:
                    fig = px.bar(df, x='symbol', y='pnl_pct', title="P&L by Symbol", color='pnl_pct',
                                color_continuous_scale='RdYlGn')
                    st.plotly_chart(fig, use_container_width=True)

                    # Summary
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Total Trades", len(df))
                    with col_b:
                        if 'pnl' in df.columns:
                            total_pnl = df['pnl'].sum()
                            st.metric("Total P&L", f"${total_pnl:.2f}")
                    with col_c:
                        if 'pnl_pct' in df.columns:
                            win_count = len(df[df['pnl_pct'] > 0])
                            win_rate = (win_count / len(df) * 100) if len(df) > 0 else 0
                            st.metric("Win Rate", f"{win_rate:.0f}%")
            else:
                st.info("No trades found")
        except Exception as e:
            st.warning(f"Could not load trades: {str(e)[:100]}")

# ============================================================
# PAGE 5: GOLD MONITOR (24/7)
# ============================================================
elif page == "🟡 Gold Monitor 24/7":
    st.header("🟡 Gold Monitor — XAUUSD (24/7)")

    try:
        # Get gold monitor data from agent_states
        agents = fetch_table("agent_states")
        gold_agent = next((a for a in agents if a.get('agent_name') == 'GoldMonitor'), None)

        if gold_agent and gold_agent.get('status') == 'active':
            # Parse last_signal for live data
            last_signal = gold_agent.get('last_signal', '')
            last_updated = gold_agent.get('last_updated', '')

            # Extract values from last_signal (format: "$4462.40 | HOLD | RSI: 65")
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

            st.success(f"✅ Gold Monitor ACTIVE | Last: {last_signal}")
            st.caption("Monitoring XAUUSD 24/7 | Updates every 60 seconds")

            # Show refresh info
            if st.button("🔄 Refresh Data"):
                st.rerun()

        else:
            st.warning("⏳ Waiting for gold_monitor.py to publish data...")
            st.error("Start gold monitor with:")
            st.code("python3 gold_monitor.py")

    except Exception as e:
        st.error(f"Gold Monitor Error: {str(e)[:100]}")
        st.info("Make sure gold_monitor.py is running: `ps aux | grep gold_monitor`")

# ============================================================
# PAGE 6: PERFORMANCE
# ============================================================
elif page == "📈 Performance":
    st.header("📈 System Performance")

    try:
        # Get trades data
        trades = fetch_table("trades")
        positions = fetch_table("positions")

        col1, col2, col3, col4 = st.columns(4)

        if trades:
            df = pd.DataFrame(trades)

            wins = len(df[df.get('pnl', pd.Series([0])) > 0]) if 'pnl' in df.columns else 0
            total_pnl = df['pnl'].sum() if 'pnl' in df.columns else 0
            win_rate = (wins / len(df) * 100) if len(df) > 0 else 0

            with col1:
                st.metric("Total Trades", len(df))
            with col2:
                st.metric("Winning Trades", wins)
            with col3:
                st.metric("Total P&L", f"${total_pnl:.2f}")
            with col4:
                st.metric("Win Rate", f"{win_rate:.0f}%")

            # Strategy performance
            if 'strategy' in df.columns:
                st.subheader("Strategy Performance")
                strategy_stats = df.groupby('strategy').agg({
                    'pnl': ['sum', 'count', 'mean']
                }).round(2)
                st.dataframe(strategy_stats, use_container_width=True)

            # P&L by symbol
            if 'symbol' in df.columns and 'pnl' in df.columns:
                st.subheader("P&L by Symbol")
                symbol_stats = df.groupby('symbol')['pnl'].agg(['sum', 'count', 'mean']).round(2)
                fig = px.bar(symbol_stats.reset_index(), x='symbol', y='sum', title="Total P&L by Symbol",
                            color='sum', color_continuous_scale='RdYlGn')
                st.plotly_chart(fig, use_container_width=True)

        if positions:
            st.subheader("Open Positions Summary")
            df_pos = pd.DataFrame(positions)
            st.metric("Open Positions", len(df_pos))

    except Exception as e:
        st.warning(f"Performance: {str(e)[:100]}")

# Footer
st.sidebar.divider()
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
