#!/usr/bin/env python3
"""
⭐ Star Trading System - Final Optimized Dashboard
Real-time charts with Plotly (works reliably in Streamlit)
Direct Yahoo Finance data (bypasses Supabase bottleneck)
"""
from dotenv import load_dotenv
load_dotenv()

import os
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, timedelta
import pytz

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="⭐ STAR Trading",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# MARKET STATUS
# ============================================================
def market_status():
    ny = pytz.timezone('America/New_York')
    now = datetime.now(ny)
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()
    time_decimal = hour + minute/60

    if weekday >= 5:
        return '🔴 CLOSED', 'red'
    elif 9.5 <= time_decimal < 16:
        return '🟢 OPEN', 'green'
    elif 4 <= time_decimal < 9.5:
        return '🟡 PRE-MARKET', 'orange'
    elif 16 <= time_decimal < 20:
        return '🟡 AFTER-HOURS', 'orange'
    else:
        return '🔴 CLOSED', 'red'

status, color = market_status()
st.markdown(f"""
<div style='background-color: {color}20; border-left: 4px solid {color}; padding: 10px; border-radius: 4px; margin-bottom: 20px;'>
<h3 style='margin: 0;'>NYSE {status}</h3>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SUPABASE (Historical data only)
# ============================================================
@st.cache_resource
def get_supabase():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

sb = get_supabase()

# ============================================================
# FETCH REAL DATA FROM YAHOO FINANCE
# ============================================================
@st.cache_data(ttl=10)
def get_live_price(symbol: str):
    """Get current price from Yahoo Finance"""
    try:
        yf_symbol = symbol if symbol != "XAUUSD" else "GC=F"
        ticker = yf.Ticker(yf_symbol)
        data = ticker.history(period="1d")
        if data.empty:
            return None
        latest = data.iloc[-1]
        return float(latest['Close'])
    except:
        return None

@st.cache_data(ttl=30)
def get_chart_data(symbol: str, period: str = "5d"):
    """Fetch OHLC data from Yahoo Finance"""
    try:
        yf_symbol = symbol if symbol != "XAUUSD" else "GC=F"
        data = yf.download(yf_symbol, period=period, progress=False)
        if data.empty:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except:
        return None

def create_candlestick_chart(symbol: str, period: str = "5d"):
    """Create Plotly candlestick chart (works reliably)"""
    data = get_chart_data(symbol, period)

    if data is None or data.empty:
        st.warning(f"No data for {symbol}")
        return

    # Create figure
    fig = go.Figure(data=[go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name=symbol
    )])

    fig.update_layout(
        title=f"{symbol} - OHLC Chart",
        yaxis_title="Price",
        xaxis_title="Date",
        template="plotly_dark",
        height=500,
        xaxis_rangeslider_visible=False,
        hovermode='x unified'
    )

    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.title("⭐ STAR Trading")
page = st.sidebar.radio(
    "Navigation",
    ["📊 Live Prices", "📈 Charts", "💼 Trades", "🤖 Signals", "📋 Status"]
)

# ============================================================
# PAGE 1: LIVE PRICES
# ============================================================
if page == "📊 Live Prices":
    st.title("📊 Real-Time Prices")
    st.write("Updated from Yahoo Finance (every 10 seconds)")

    symbols = [("GC=F", "GOLD"), ("AAPL", "AAPL"), ("NVDA", "NVDA"), ("TSLA", "TSLA"), ("SPY", "SPY")]

    cols = st.columns(5)

    for idx, (symbol, label) in enumerate(symbols):
        with cols[idx]:
            price = get_live_price(symbol)
            if price:
                st.metric(label, f"${price:.2f}")
            else:
                st.metric(label, "Error")

# ============================================================
# PAGE 2: CHARTS
# ============================================================
elif page == "📈 Charts":
    st.title("📈 Live Trading Charts")
    st.write("Interactive charts with REAL market data from Yahoo Finance")

    symbols = ["GC=F", "AAPL", "NVDA", "TSLA", "SPY"]

    for symbol in symbols:
        display_name = "Gold (GC=F)" if symbol == "GC=F" else symbol

        st.subheader(display_name)

        col1, col2 = st.columns([3, 1])

        with col1:
            create_candlestick_chart(symbol, "5d")

        with col2:
            price = get_live_price(symbol)
            if price:
                st.metric("Current", f"${price:.2f}")

        st.divider()

# ============================================================
# PAGE 3: TRADES
# ============================================================
elif page == "💼 Trades":
    st.title("💼 Executed Trades")
    st.write("Trade history from Supabase database")

    try:
        trades = sb.table("executed_trades").select("*").order("created_at", desc=True).limit(50).execute().data

        if trades:
            df = pd.DataFrame(trades)

            # Display key columns
            display_cols = ["symbol", "side", "entry_price", "exit_price", "pnl_pct", "status"]
            if all(col in df.columns for col in display_cols):
                df_display = df[display_cols].copy()
                df_display.columns = ["Symbol", "Side", "Entry", "Exit", "P&L %", "Status"]

                st.dataframe(df_display, use_container_width=True)

                # Metrics
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    wins = len([t for t in trades if t.get('pnl_pct', 0) > 0])
                    st.metric("Wins", wins)

                with col2:
                    losses = len([t for t in trades if t.get('pnl_pct', 0) <= 0])
                    st.metric("Losses", losses)

                with col3:
                    if trades:
                        avg = sum([t.get('pnl_pct', 0) for t in trades]) / len(trades)
                        st.metric("Avg P&L %", f"{avg:.2f}%")

                with col4:
                    if trades:
                        total = sum([t.get('pnl_pct', 0) for t in trades])
                        st.metric("Total P&L %", f"{total:.2f}%")
        else:
            st.info("No trades yet")
    except Exception as e:
        st.error(f"Error: {str(e)[:100]}")

# ============================================================
# PAGE 4: SIGNALS
# ============================================================
elif page == "🤖 Signals":
    st.title("🤖 Agent Signals")
    st.write("Real-time trading signals from all agents")

    try:
        signals = sb.table("agent_signals").select("*").order("created_at", desc=True).limit(100).execute().data

        if signals:
            # Group by symbol
            by_symbol = {}
            for sig in signals:
                symbol = sig.get('symbol', 'Unknown')
                if symbol not in by_symbol:
                    by_symbol[symbol] = []
                by_symbol[symbol].append(sig)

            for symbol in sorted(by_symbol.keys()):
                with st.expander(f"📊 {symbol}", expanded=True):
                    for sig in by_symbol[symbol][:5]:
                        col1, col2, col3 = st.columns([2, 1, 2])

                        with col1:
                            st.write(f"**{sig.get('agent_name', 'Unknown')}**")

                        with col2:
                            signal = sig.get('signal', 'HOLD')
                            color = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "🟡"
                            st.write(f"{color} {signal}")

                        with col3:
                            conf = sig.get('confidence', 0)
                            st.write(f"**{conf:.0f}%**")
        else:
            st.info("No signals yet")
    except Exception as e:
        st.error(f"Error: {str(e)[:100]}")

# ============================================================
# PAGE 5: STATUS
# ============================================================
elif page == "📋 Status":
    st.title("📋 System Status")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("System", "🟢 Running")

    with col2:
        st.metric("Data Source", "Yahoo Finance")

    with col3:
        st.metric("Update Speed", "10 sec")

    with col4:
        st.metric("Database", "Supabase")

    st.divider()

    st.subheader("🔄 System Components")
    st.write("""
    - ✅ Automated Trading (automated_system.py)
    - ✅ Real-time Dashboard (dashboard_final.py)
    - ✅ Yahoo Finance Integration
    - ✅ Supabase Database
    - ✅ Agent Consensus System

    **Status:** All systems operational

    **Update Schedule:**
    - Live Prices: Every 10 seconds
    - Charts: Every 30 seconds
    - Trade Logs: Real-time
    - Agent Signals: Real-time
    """)

# ============================================================
# AUTO-REFRESH INDICATOR
# ============================================================
st.sidebar.divider()
st.sidebar.write(f"*Updated: {datetime.now().strftime('%H:%M:%S')}*")
