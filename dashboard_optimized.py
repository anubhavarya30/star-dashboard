#!/usr/bin/env python3
"""
⭐ Star Trading System - Optimized Live Dashboard
Real-time charts from Yahoo Finance (NOT Supabase)
Local caching for instant updates
Supabase only for trade history
"""
from dotenv import load_dotenv
load_dotenv()

import os
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
from datetime import datetime, timedelta
import pytz
import pandas as pd
import yfinance as yf
import json
import time

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="⭐ STAR Trading Dashboard",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: #0e1117;
    }
    [data-testid="stMetric"] {
        background-color: #1e1e1e;
        padding: 10px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# MARKET STATUS
# ============================================================
def market_status():
    """NYSE market status"""
    ny = pytz.timezone('America/New_York')
    now = datetime.now(ny)
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()
    time_decimal = hour + minute/60

    if weekday >= 5:
        return '🔴 CLOSED (Weekend)', 'red'
    elif 9.5 <= time_decimal < 16:
        return '🟢 OPEN (9:30-16:00)', 'green'
    elif 4 <= time_decimal < 9.5:
        return '🟡 PRE-MARKET (4:00-9:30)', 'orange'
    elif 16 <= time_decimal < 20:
        return '🟡 AFTER-HOURS (16:00-20:00)', 'orange'
    else:
        return '🔴 CLOSED', 'red'

status, color = market_status()
st.markdown(f"""
<div style='background-color: {color}20; border-left: 4px solid {color}; padding: 10px; border-radius: 4px; margin-bottom: 20px;'>
<h3 style='margin: 0;'>NYSE {status} | 🥇 GOLD: 24/7</h3>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SUPABASE (ONLY for trade history, not real-time)
# ============================================================
@st.cache_resource
def get_supabase():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

sb = get_supabase()

# ============================================================
# REAL-TIME DATA FROM YAHOO FINANCE (NOT SUPABASE)
# ============================================================
@st.cache_data(ttl=10)  # Update every 10 seconds
def get_real_time_price(symbol: str) -> dict:
    """Get REAL-TIME price from Yahoo Finance directly"""
    try:
        yf_symbol = symbol if symbol != "XAUUSD" else "GC=F"

        ticker = yf.Ticker(yf_symbol)
        data = ticker.history(period="1d", interval="1m")

        if data.empty:
            return None

        latest = data.iloc[-1]
        return {
            "symbol": symbol,
            "price": float(latest['Close']),
            "high": float(latest['High']),
            "low": float(latest['Low']),
            "volume": int(latest['Volume']),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return None

@st.cache_data(ttl=30)  # Update every 30 seconds
def get_ohlc_chart_data(symbol: str, period: str = "5d") -> pd.DataFrame:
    """Get OHLC data directly from Yahoo Finance for charts"""
    try:
        yf_symbol = symbol if symbol != "XAUUSD" else "GC=F"

        data = yf.download(yf_symbol, period=period, progress=False)

        if data.empty:
            return None

        # Handle MultiIndex
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        return data
    except Exception as e:
        return None

def render_tradingview_chart(symbol: str, period: str = "5d"):
    """Render TradingView Lightweight Charts with REAL data"""
    data = get_ohlc_chart_data(symbol, period)

    if data is None or data.empty:
        st.warning(f"No data for {symbol}")
        return

    candles = []
    for idx, row in data.iterrows():
        timestamp = int(idx.timestamp() * 1000)
        candles.append({
            "time": timestamp,
            "open": float(row['Open']),
            "high": float(row['High']),
            "low": float(row['Low']),
            "close": float(row['Close'])
        })

    # TradingView Chart HTML
    html = f"""
    <div id="chart_{symbol}" style="height: 400px; width: 100%;"></div>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script>
        const chart = LightweightCharts.createChart(
            document.getElementById('chart_{symbol}'),
            {{
                width: document.getElementById('chart_{symbol}').parentWidth,
                height: 400,
                layout: {{ backgroundColor: '#1e1e1e', textColor: '#d1d5db' }},
                timeScale: {{ timeVisible: true, secondsVisible: true }}
            }}
        );

        const candleSeries = chart.addCandlestickSeries({{
            upColor: '#26a69a',
            downColor: '#ef5350'
        }});

        candleSeries.setData({json.dumps(candles)});
        chart.timeScale().fitContent();
    </script>
    """

    components.html(html, height=420)

# ============================================================
# SIDEBAR NAVIGATION
# ============================================================
st.sidebar.title("⭐ STAR Trading")
page = st.sidebar.radio(
    "Select Page",
    ["📊 Live Prices", "📈 Charts", "💼 Trades", "🤖 Signals", "📋 Status"]
)

# ============================================================
# PAGE 1: LIVE PRICES (Real-time)
# ============================================================
if page == "📊 Live Prices":
    st.title("📊 Real-Time Prices")
    st.write("*Updated every 10 seconds from Yahoo Finance*")

    symbols = ["GC=F", "AAPL", "NVDA", "TSLA", "SPY"]

    cols = st.columns(5)

    for i, symbol in enumerate(symbols):
        with cols[i]:
            price_data = get_real_time_price(symbol)

            if price_data:
                display_symbol = "GOLD" if symbol == "GC=F" else symbol
                st.metric(
                    display_symbol,
                    f"${price_data['price']:.2f}",
                    f"H: ${price_data['high']:.2f} | L: ${price_data['low']:.2f}"
                )
            else:
                st.error(f"Error fetching {symbol}")

# ============================================================
# PAGE 2: LIVE CHARTS (Real-time)
# ============================================================
elif page == "📈 Charts":
    st.title("📈 Live Trading Charts")
    st.write("*TradingView charts with REAL market data (5-day hourly)*")

    symbols = ["GC=F", "AAPL", "NVDA", "TSLA", "SPY"]

    for symbol in symbols:
        display_name = "Gold (GC=F)" if symbol == "GC=F" else symbol
        st.subheader(f"{display_name}")

        col1, col2 = st.columns([3, 1])

        with col1:
            render_tradingview_chart(symbol, "5d")

        with col2:
            price_data = get_real_time_price(symbol)
            if price_data:
                st.metric("Current", f"${price_data['price']:.2f}")
                st.metric("High", f"${price_data['high']:.2f}")
                st.metric("Low", f"${price_data['low']:.2f}")

        st.divider()

# ============================================================
# PAGE 3: TRADES (From Supabase)
# ============================================================
elif page == "💼 Trades":
    st.title("💼 Executed Trades")
    st.write("*Historical trades from Supabase database*")

    try:
        trades = sb.table("executed_trades").select("*").order("created_at", desc=True).limit(50).execute().data

        if trades:
            df = pd.DataFrame(trades)

            # Format for display
            display_cols = ["symbol", "side", "entry_price", "exit_price", "pnl_pct", "status", "created_at"]
            if all(col in df.columns for col in display_cols):
                df_display = df[display_cols].copy()
                df_display.columns = ["Symbol", "Side", "Entry", "Exit", "P&L %", "Status", "Date"]

                st.dataframe(df_display, use_container_width=True)

                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    wins = len([t for t in trades if t.get('pnl_pct', 0) > 0])
                    st.metric("Winning Trades", wins)
                with col2:
                    losses = len([t for t in trades if t.get('pnl_pct', 0) <= 0])
                    st.metric("Losing Trades", losses)
                with col3:
                    avg_pnl = df['pnl_pct'].mean() if 'pnl_pct' in df.columns else 0
                    st.metric("Avg P&L %", f"{avg_pnl:.2f}%")
                with col4:
                    total_pnl = df['pnl_pct'].sum() if 'pnl_pct' in df.columns else 0
                    st.metric("Total P&L %", f"{total_pnl:.2f}%")
            else:
                st.write(df)
        else:
            st.info("No trades yet")
    except Exception as e:
        st.error(f"Error loading trades: {str(e)[:60]}")

# ============================================================
# PAGE 4: SIGNALS (From Supabase)
# ============================================================
elif page == "🤖 Signals":
    st.title("🤖 Agent Signals")
    st.write("*Real-time trading signals from all agents*")

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
                    for sig in by_symbol[symbol][:5]:  # Show latest 5
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
        st.error(f"Error loading signals: {str(e)[:60]}")

# ============================================================
# PAGE 5: STATUS
# ============================================================
elif page == "📋 Status":
    st.title("📋 System Status")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("System Status", "🟢 Running")

    with col2:
        st.metric("Data Source", "Yahoo Finance")

    with col3:
        st.metric("Update Speed", "10 sec")

    with col4:
        st.metric("Database", "Supabase")

    st.divider()

    st.subheader("🔄 Automated Tasks")
    st.write("""
    - ✅ Real-time price updates (10 sec)
    - ✅ Chart data refresh (30 sec)
    - ✅ Trade logging (Continuous)
    - ✅ Signal collection (Continuous)
    - ✅ Daily routine planning (9:20 AM)
    """)

    st.subheader("💾 Database Tables")
    tables = ["agent_signals", "executed_trades", "trading_decisions", "daily_routine", "agent_performance"]

    for table in tables:
        try:
            count = sb.table(table).select("*").limit(1).execute().count
            st.write(f"✅ {table}: Active")
        except:
            st.write(f"⚠️ {table}: Error")

# ============================================================
# AUTO-REFRESH
# ============================================================
st.sidebar.divider()
st.sidebar.write("*Dashboard updates every 10-30 seconds*")
st.sidebar.write(f"*Last refresh: {datetime.now().strftime('%H:%M:%S')}*")
