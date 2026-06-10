#!/usr/bin/env python3
"""
🌟 REAL TRADING DASHBOARD
Live monitoring of IBKR trades, agent decisions, and portfolio performance
"""
import streamlit as st
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
from calendar import monthcalendar, month_name

st.set_page_config(
    page_title="STAR Real Trading",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        [data-testid="collapsedControl"] { display: none }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=5)
def load_current_trades():
    """Load current trades from JSON"""
    if Path("current_trades.json").exists():
        with open("current_trades.json") as f:
            return json.load(f)
    return {"open_trades": {}, "signals": [], "balance": 100000.0}


@st.cache_data(ttl=5)
def load_executed_trades():
    """Load executed trades from JSON"""
    if Path("executed_trades.json").exists():
        with open("executed_trades.json") as f:
            return json.load(f)
    return []


@st.cache_data(ttl=5)
def load_execution_log():
    """Load execution log"""
    if Path("execution_log.json").exists():
        with open("execution_log.json") as f:
            return json.load(f)
    return []


# Load all data
current_trades = load_current_trades()
executed_trades = load_executed_trades()
execution_log = load_execution_log()

# ==================== HEADER ====================
st.markdown("# 🌟 STAR REAL TRADING DASHBOARD")
st.markdown("*Autonomous Trading System - IBKR Live Execution*")
st.divider()

# ==================== TOP METRICS ====================
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    balance = current_trades.get("balance", 100000.0)
    st.metric("Account Balance", f"${balance:,.0f}")

with col2:
    open_count = len(current_trades.get("open_trades", {}))
    st.metric("Open Positions", open_count)

with col3:
    total_trades = len(executed_trades)
    st.metric("Total Trades", total_trades)

with col4:
    pnl = current_trades.get("total_pnl", 0.0)
    st.metric("Total P&L", f"${pnl:+.2f}", delta=f"{pnl/100000*100:+.2f}%")

with col5:
    win_rate = 0
    if total_trades > 0:
        wins = current_trades.get("winning_trades", 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    st.metric("Win Rate", f"{win_rate:.1f}%")

st.divider()

# ==================== TABS ====================
tab1, tab2, tab3, tab4 = st.tabs(["📈 Open Positions", "📊 Trade History", "🧠 Agent Decisions", "📅 Calendar"])

# ==================== TAB 1: OPEN POSITIONS ====================
with tab1:
    st.subheader("Currently Open Positions")

    open_trades = current_trades.get("open_trades", {})

    if open_trades:
        trades_data = []
        total_unrealized_pnl = 0

        for trade_id, trade in open_trades.items():
            trades_data.append({
                "Symbol": trade.get("symbol"),
                "Action": trade.get("action"),
                "Qty": trade.get("quantity"),
                "Entry $": f"${trade.get('entry_price', 0):.2f}",
                "Stop Loss": f"${trade.get('stop_loss', 0):.2f}",
                "Take Profit": f"${trade.get('take_profit', 0):.2f}",
                "Status": trade.get("status"),
                "Order ID": trade.get("order_id", "Paper"),
                "Confidence": f"{trade.get('confidence', 0):.0%}",
                "Entry Time": trade.get("entry_time", "")[:19]
            })

        df_trades = pd.DataFrame(trades_data)
        st.dataframe(df_trades, use_container_width=True, hide_index=True)

        col_empty, col_button = st.columns([0.8, 0.2])
        with col_button:
            if st.button("🔄 Refresh"):
                st.cache_data.clear()
                st.rerun()
    else:
        st.info("No open positions")

# ==================== TAB 2: TRADE HISTORY ====================
with tab2:
    st.subheader("Executed Trades")

    if executed_trades:
        trades_hist = []

        for trade in executed_trades:
            pnl = trade.get("pnl", 0)
            pnl_pct = trade.get("pnl_pct", 0)

            trades_hist.append({
                "Date": trade.get("date", ""),
                "Time": trade.get("time", ""),
                "Symbol": trade.get("symbol"),
                "Side": trade.get("side"),
                "Qty": trade.get("quantity"),
                "Entry $": f"${trade.get('entry_price', 0):.2f}",
                "Exit $": f"${trade.get('current_price', 0):.2f}",
                "P&L $": f"${pnl:+.2f}",
                "P&L %": f"{pnl_pct:+.2f}%",
                "Source": trade.get("source", "UNKNOWN")
            })

        df_history = pd.DataFrame(trades_hist)
        st.dataframe(df_history, use_container_width=True, hide_index=True)

        # P&L Summary
        st.divider()
        total_pnl = sum([t.get("pnl", 0) for t in executed_trades])
        winning = sum([1 for t in executed_trades if t.get("pnl", 0) > 0])
        losing = sum([1 for t in executed_trades if t.get("pnl", 0) < 0])

        col_summary1, col_summary2, col_summary3 = st.columns(3)
        with col_summary1:
            st.metric("Total P&L", f"${total_pnl:+.2f}")
        with col_summary2:
            st.metric("Winning Trades", f"{winning}/{len(executed_trades)}")
        with col_summary3:
            st.metric("Losing Trades", f"{losing}/{len(executed_trades)}")
    else:
        st.info("No executed trades yet")

# ==================== TAB 3: AGENT DECISIONS ====================
with tab3:
    st.subheader("Recent Agent Decisions & Reasoning")

    if execution_log:
        decisions = []

        for entry in execution_log:
            if entry.get("event") == "TRADE_EXECUTED":
                trade = entry.get("trade", {})
                decisions.append({
                    "Time": entry.get("timestamp", "")[:19],
                    "Symbol": trade.get("symbol"),
                    "Decision": trade.get("action"),
                    "Confidence": f"{trade.get('confidence', 0):.0%}",
                    "Market Score": f"{entry.get('market_score', 0):.0f}/100",
                    "Sentiment Score": f"{entry.get('sentiment_score', 0):.0f}/100",
                    "Reasoning": trade.get("reasoning", "")[:60],
                    "Status": trade.get("status")
                })

        if decisions:
            df_decisions = pd.DataFrame(decisions)
            st.dataframe(df_decisions, use_container_width=True, hide_index=True)
        else:
            st.info("No agent decisions yet")
    else:
        st.info("No execution log")

# ==================== TAB 4: CALENDAR ====================
with tab4:
    st.subheader("Trading Calendar - Daily P&L")

    col_left, col_right = st.columns([0.3, 0.7])

    with col_left:
        today = datetime.now()
        current_month = st.selectbox(
            "Month",
            range(1, 13),
            index=today.month - 1,
            label_visibility="collapsed"
        )
        current_year = st.selectbox(
            "Year",
            range(2024, 2027),
            index=0,
            label_visibility="collapsed"
        )

        # Calculate daily P&L
        def get_daily_pnl(date_str):
            pnl = 0
            for trade in executed_trades:
                if trade.get("date") == date_str:
                    pnl += trade.get("pnl", 0)
            return pnl

        cal = monthcalendar(current_year, current_month)
        days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        cols_header = st.columns(7)
        for i, day_name in enumerate(days_of_week):
            with cols_header[i]:
                st.write(f"**{day_name}**")

        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day == 0:
                        st.write("")
                    else:
                        date_str = f"{current_year:04d}-{current_month:02d}-{day:02d}"
                        pnl = get_daily_pnl(date_str)

                        if pnl > 0:
                            color = "lightgreen"
                            text_color = "darkgreen"
                        elif pnl < 0:
                            color = "lightcoral"
                            text_color = "darkred"
                        else:
                            color = "white"
                            text_color = "black"

                        st.markdown(f"""
                            <div style='
                                background-color: {color};
                                border-radius: 8px;
                                padding: 10px;
                                text-align: center;
                                border: 1px solid #ddd;
                            '>
                                <span style='color: {text_color}; font-weight: bold;'>{day}</span><br>
                                <span style='color: {text_color}; font-size: 0.8em;'>
                                    ${pnl:+.0f}
                                </span>
                            </div>
                        """, unsafe_allow_html=True)

    with col_right:
        st.subheader("Monthly Statistics")

        # Get trades for the selected month
        monthly_trades = [
            t for t in executed_trades
            if t.get("date", "").startswith(f"{current_year:04d}-{current_month:02d}")
        ]

        if monthly_trades:
            monthly_pnl = sum([t.get("pnl", 0) for t in monthly_trades])
            monthly_wins = sum([1 for t in monthly_trades if t.get("pnl", 0) > 0])
            monthly_losses = sum([1 for t in monthly_trades if t.get("pnl", 0) < 0])

            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                st.metric("Month P&L", f"${monthly_pnl:+.2f}")
            with col_stat2:
                win_pct = (monthly_wins / len(monthly_trades) * 100) if monthly_trades else 0
                st.metric("Win Rate", f"{win_pct:.1f}%")

            col_stat3, col_stat4 = st.columns(2)
            with col_stat3:
                st.metric("Winning Trades", monthly_wins)
            with col_stat4:
                st.metric("Losing Trades", monthly_losses)

            # Daily P&L chart
            daily_pnl_data = {}
            for trade in monthly_trades:
                date = trade.get("date")
                if date not in daily_pnl_data:
                    daily_pnl_data[date] = 0
                daily_pnl_data[date] += trade.get("pnl", 0)

            if daily_pnl_data:
                dates = sorted(daily_pnl_data.keys())
                pnls = [daily_pnl_data[d] for d in dates]

                fig = go.Figure()
                colors = ['green' if p > 0 else 'red' for p in pnls]
                fig.add_trace(go.Bar(
                    x=dates,
                    y=pnls,
                    marker_color=colors,
                    name="Daily P&L"
                ))
                fig.update_layout(
                    title="Daily P&L",
                    xaxis_title="Date",
                    yaxis_title="P&L ($)",
                    height=300,
                    showlegend=False,
                    template="plotly_dark"
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trades for selected month")

# ==================== FOOTER ====================
st.divider()
col_refresh, col_status, col_time = st.columns([0.2, 0.6, 0.2])

with col_refresh:
    if st.button("🔄 Refresh All"):
        st.cache_data.clear()
        st.rerun()

with col_status:
    # Check system status
    if current_trades.get("open_trades"):
        status = "🟢 TRADING ACTIVE"
    else:
        status = "🟡 WAITING FOR SIGNALS"
    st.write(status)

with col_time:
    st.write(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

# Auto-refresh every 5 seconds
st.markdown("""
<script>
setTimeout(function() {
    window.location.reload();
}, 5000);
</script>
""", unsafe_allow_html=True)
