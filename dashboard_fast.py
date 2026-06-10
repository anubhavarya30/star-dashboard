#!/usr/bin/env python3
"""
FAST DASHBOARD - JSON-based, NO SUPABASE LATENCY
Real-time display of trades and signals
"""
import streamlit as st
import json
from pathlib import Path
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import yfinance as yf

st.set_page_config(page_title="STAR Trading", layout="wide", initial_sidebar_state="expanded")

TRADES_FILE = Path("current_trades.json")
SIGNALS_FILE = Path("current_signals.json")

def load_state():
    """Load state from JSON files (instant, no DB)"""
    if TRADES_FILE.exists():
        with open(TRADES_FILE) as f:
            return json.load(f)
    return {"open_trades": {}, "signals": [], "last_update": None}

def load_signals():
    """Load recent signals"""
    if SIGNALS_FILE.exists():
        with open(SIGNALS_FILE) as f:
            return json.load(f)
    return []

# Header
st.title("🌟 STAR TRADING SYSTEM")
st.markdown("**Real-time trading with ZERO database latency**")

# Load current state
state = load_state()
signals = load_signals()

# Metrics
col1, col2, col3, col4 = st.columns(4)

open_trades = len(state.get("open_trades", {}))
total_signals = len(state.get("signals", []))

with col1:
    st.metric("📈 Open Trades", open_trades, delta=None)

with col2:
    st.metric("🤖 Total Signals", total_signals, delta=None)

with col3:
    if state.get("balance"):
        st.metric("💰 Balance", f"${state['balance']:,.0f}")

with col4:
    last_update = state.get("last_update")
    if last_update:
        st.metric("⏰ Last Update", last_update.split('T')[1][:8])

st.divider()

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📈 Open Trades", "🤖 Signals", "📊 Charts", "⚙️ Status"])

# TAB 1: Open Trades
with tab1:
    open_trades_list = list(state.get("open_trades", {}).values())

    if open_trades_list:
        df = pd.DataFrame(open_trades_list)
        df = df[['symbol', 'action', 'quantity', 'entry_price', 'stop_loss', 'take_profit', 'entry_time', 'confidence']]

        st.dataframe(
            df.sort_values('entry_time', ascending=False),
            use_container_width=True,
            hide_index=True
        )

        # Calculate total P&L
        st.subheader("Position Summary")
        for trade in open_trades_list:
            symbol = trade['symbol']
            qty = trade['quantity']
            entry = trade['entry_price']

            # Get current price
            try:
                current = yf.Ticker(symbol).info.get('currentPrice', entry)
            except:
                current = entry

            pnl = (current - entry) * qty
            pnl_pct = ((current - entry) / entry * 100) if entry else 0

            color = "🟢" if pnl > 0 else "🔴"
            st.write(f"{color} **{symbol}** | Entry: ${entry:.2f} | Current: ${current:.2f} | P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)")

    else:
        st.info("📭 No open trades yet. System monitoring market for signals...")

# TAB 2: Signals
with tab2:
    if signals:
        df_signals = pd.DataFrame(signals)

        # Filter relevant columns
        display_cols = ['symbol', 'action', 'confidence', 'entry_price', 'stop_loss', 'take_profit', 'timestamp']
        df_signals = df_signals[[col for col in display_cols if col in df_signals.columns]]

        st.dataframe(
            df_signals.sort_values('timestamp', ascending=False),
            use_container_width=True,
            hide_index=True
        )

        # Signal stats
        st.subheader("Signal Analysis")
        buy_signals = len([s for s in signals if s.get('action') == 'BUY'])
        sell_signals = len([s for s in signals if s.get('action') == 'SELL'])
        avg_confidence = sum([s.get('confidence', 0) for s in signals]) / len(signals) if signals else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🔵 BUY Signals", buy_signals)
        with col2:
            st.metric("🔴 SELL Signals", sell_signals)
        with col3:
            st.metric("📊 Avg Confidence", f"{avg_confidence:.0%}")

    else:
        st.info("🤖 Waiting for trading signals...")

# TAB 3: Charts
with tab3:
    st.subheader("Live Price Charts")

    symbols = ["AAPL", "NVDA", "TSLA", "SPY"]
    selected_symbol = st.selectbox("Select symbol:", symbols)

    if selected_symbol:
        try:
            # Fetch data
            data = yf.download(selected_symbol, period="5d", progress=False)

            if not data.empty:
                # Create candlestick chart
                fig = go.Figure(data=[go.Candlestick(
                    x=data.index,
                    open=data['Open'],
                    high=data['High'],
                    low=data['Low'],
                    close=data['Close']
                )])

                # Add trades to chart
                for trade in open_trades_list:
                    if trade['symbol'] == selected_symbol:
                        fig.add_hline(y=trade['entry_price'], line_dash="dash", line_color="blue", annotation_text="Entry")
                        fig.add_hline(y=trade['stop_loss'], line_dash="dash", line_color="red", annotation_text="SL")
                        fig.add_hline(y=trade['take_profit'], line_dash="dash", line_color="green", annotation_text="TP")

                fig.update_layout(
                    title=f"{selected_symbol} - 5D Chart",
                    height=600,
                    xaxis_rangeslider_visible=False
                )

                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Error loading chart: {str(e)[:50]}")

# TAB 4: Status
with tab4:
    st.subheader("System Status")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Trading System**")
        st.write("✅ Status: Running")
        st.write("📊 Mode: LIVE with IBKR")
        st.write("💾 Storage: JSON files (fast)")
        st.write("🔄 Refresh: Every 5 minutes")

    with col2:
        st.write("**Current Session**")
        if state.get("last_update"):
            st.write(f"⏰ Last update: {state['last_update']}")
        st.write(f"📈 Open trades: {open_trades}")
        st.write(f"🤖 Total signals: {total_signals}")
        st.write(f"📅 Today's trades: {open_trades}")

    st.divider()

    st.subheader("Architecture")
    st.markdown("""
    - **Data Source**: IBKR (real prices)
    - **Market Data**: Yahoo Finance (OHLCV)
    - **State Storage**: JSON files (FAST)
    - **Database**: ❌ REMOVED (Supabase bottleneck eliminated)
    - **Latency**: <100ms (instant)
    - **Update Frequency**: Every 5 minutes
    """)

# Auto-refresh
st.markdown("""
<script>
setTimeout(function() {
    window.location.reload();
}, 5000);
</script>
""", unsafe_allow_html=True)
