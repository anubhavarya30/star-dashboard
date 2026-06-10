#!/usr/bin/env python3
"""
🌟 STAR DASHBOARD PRO - Professional Trading Interface
Left: Trading Journal Calendar with Daily P&L
Right: Real-time TradingView Interactive Chart
"""
import streamlit as st
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from calendar import monthcalendar, month_name
import yfinance as yf
import plotly.graph_objects as go
import requests

st.set_page_config(
    page_title="STAR Trading Journal",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Hide sidebar and streamlit menu
st.markdown("""
    <style>
        [data-testid="collapsedControl"] { display: none }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        .stApp { margin: 0; padding: 0; }
    </style>
""", unsafe_allow_html=True)

# Top 100 stocks (S&P 100 + Popular)
TOP_100_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JNJ", "V",
    "WMT", "JPM", "PG", "MA", "UNH", "MCD", "INTC", "BA", "VZ", "KO",
    "NFLX", "PEP", "COST", "CSCO", "ABBV", "CRM", "CMG", "ADBE", "NKE", "QCOM",
    "AMD", "AVGO", "ASML", "TJX", "MU", "SBUX", "NOW", "AZO", "BKNG", "GILD",
    "AMAT", "CHTR", "INTU", "ISRG", "LRCX", "MRVL", "MCHP", "SNPS", "SYMC", "TEAM",
    "ZM", "OKTA", "PAYC", "PSTG", "SPLK", "VEEV", "WDAY", "ADSK", "ANSS", "ATVI",
    "CDNS", "CRL", "CYBR", "DDOG", "DYAX", "EQIX", "FAST", "FTNT", "HUBS", "IDXX",
    "ILMN", "JKHY", "KEYS", "LCID", "LULU", "NETS", "NFLX", "NTAP", "PCAR", "PAYX",
    "PSEC", "ROKU", "ROP", "RSTI", "SANM", "SHOP", "SNPS", "SPGI", "SPLK", "SQ",
    "STZ", "SWKS", "TAP", "TTD", "TWILIO", "TWTR", "UBER", "UI", "ZS", "ZM"
]

# Load trade data
@st.cache_data(ttl=5)
def load_trades():
    if Path("current_trades.json").exists():
        with open("current_trades.json") as f:
            return json.load(f)
    return {"open_trades": {}, "signals": []}

state = load_trades()

# Calculate daily P&L
def get_daily_pnl(date_str):
    """Calculate P&L for a specific day"""
    pnl = 0
    trades = state.get("open_trades", {})

    for trade_id, trade in trades.items():
        entry_date = trade.get("entry_time", "").split("T")[0]
        if entry_date == date_str:
            pnl += trade.get("pnl", 0)

    return pnl

# Fetch chart data with retry
@st.cache_data(ttl=30)
def fetch_chart_data(symbol, timeframe):
    """Fetch chart data with error handling"""
    try:
        if timeframe == "1d":
            data = yf.download(symbol, period="1y", progress=False, timeout=10)
        elif timeframe == "1h":
            data = yf.download(symbol, period="60d", interval="1h", progress=False, timeout=10)
        elif timeframe == "15m":
            data = yf.download(symbol, period="30d", interval="15m", progress=False, timeout=10)
        elif timeframe == "5m":
            data = yf.download(symbol, period="7d", interval="5m", progress=False, timeout=10)
        else:  # 1m
            data = yf.download(symbol, period="1d", interval="1m", progress=False, timeout=10)

        if data.empty:
            return None

        return data

    except Exception as e:
        st.error(f"Error fetching data: {str(e)[:50]}")
        return None

# Page 1: Trading Journal + Chart
st.title("🌟 STAR Trading Journal")

col_left, col_right = st.columns([0.3, 0.7], gap="small")

# ==================== LEFT SIDE: TRADING JOURNAL ====================
with col_left:
    st.subheader("📅 Trading Calendar")

    # Calendar header
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

    # Build calendar
    cal = monthcalendar(current_year, current_month)

    # Calendar grid
    days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # Display day headers
    cols_header = st.columns(7)
    for i, day_name in enumerate(days_of_week):
        with cols_header[i]:
            st.write(f"**{day_name}**")

    # Display calendar dates
    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            with cols[i]:
                if day == 0:
                    st.write("")
                else:
                    date_str = f"{current_year:04d}-{current_month:02d}-{day:02d}"
                    pnl = get_daily_pnl(date_str)

                    # Color based on P&L
                    if pnl > 0:
                        color = "lightgreen"
                        text_color = "darkgreen"
                    elif pnl < 0:
                        color = "lightcoral"
                        text_color = "darkred"
                    else:
                        color = "white"
                        text_color = "black"

                    # Display day with P&L
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

    # Daily summary
    st.divider()
    st.subheader("📊 Today's Summary")

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_pnl = get_daily_pnl(today_str)

    col_pnl1, col_pnl2 = st.columns(2)
    with col_pnl1:
        st.metric("Today P&L", f"${today_pnl:+.2f}")
    with col_pnl2:
        st.metric("Open Trades", len(state.get("open_trades", {})))

    # Recent trades
    st.subheader("📈 Recent Trades")
    trades_list = list(state.get("open_trades", {}).values())
    if trades_list:
        for trade in trades_list[-5:]:
            symbol = trade.get("symbol")
            action = trade.get("action")
            qty = trade.get("quantity")
            entry = trade.get("entry_price")

            st.write(f"**{symbol}** {action} x{qty} @ ${entry:.2f}")
    else:
        st.info("No trades yet today")

# ==================== RIGHT SIDE: TRADINGVIEW CHART ====================
with col_right:
    st.subheader("📈 Real-time Chart")

    # Symbol selector - TOP 100 STOCKS
    symbol = st.selectbox(
        "Select Symbol (Top 100)",
        sorted(TOP_100_STOCKS),
        index=sorted(TOP_100_STOCKS).index("AAPL"),
        key="chart_symbol",
        label_visibility="collapsed"
    )

    # Timeframe selector
    timeframe = st.selectbox(
        "Timeframe",
        ["1m", "5m", "15m", "1h", "1d"],
        index=3,
        key="chart_timeframe",
        label_visibility="collapsed"
    )

    # Fetch and display chart
    with st.spinner(f"Loading {symbol} chart..."):
        data = fetch_chart_data(symbol, timeframe)

    if data is not None and not data.empty:
        try:
            # Create interactive candlestick chart
            fig = go.Figure(data=[go.Candlestick(
                x=data.index,
                open=data['Open'],
                high=data['High'],
                low=data['Low'],
                close=data['Close'],
                name=symbol,
                increasing_line_color='green',
                decreasing_line_color='red'
            )])

            # Add volume as subplot
            fig.add_trace(go.Bar(
                x=data.index,
                y=data['Volume'],
                name='Volume',
                marker_color='rgba(128,128,128,0.5)',
                yaxis='y2'
            ))

            # Update layout
            fig.update_layout(
                title=f"<b>{symbol}</b> - {timeframe}",
                height=700,
                xaxis_rangeslider_visible=False,
                yaxis2=dict(
                    title="Volume",
                    overlaying="y",
                    side="right"
                ),
                hovermode='x unified',
                margin=dict(l=50, r=50, t=40, b=40),
                template="plotly_dark",
                font=dict(size=12),
                xaxis_title="Time",
                yaxis_title="Price"
            )

            # Display chart
            st.plotly_chart(fig, use_container_width=True)

            # Chart controls
            col_ctrl1, col_ctrl2, col_ctrl3 = st.columns(3)
            with col_ctrl1:
                if st.button("🔍 Zoom In", key="zoom_in"):
                    st.info("Use mouse wheel to zoom")
            with col_ctrl2:
                if st.button("🔄 Pan", key="pan"):
                    st.info("Click and drag to pan")
            with col_ctrl3:
                if st.button("↻ Reset", key="reset"):
                    st.cache_data.clear()
                    st.rerun()

            # Chart info
            st.divider()
            current_price = data['Close'].iloc[-1]
            prev_close = data['Close'].iloc[-2] if len(data) > 1 else current_price
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0
            high = data['High'].iloc[-1]
            low = data['Low'].iloc[-1]

            info_col1, info_col2, info_col3, info_col4, info_col5 = st.columns(5)
            with info_col1:
                st.metric("Price", f"${current_price:.2f}")
            with info_col2:
                st.metric("Change", f"${change:+.2f}")
            with info_col3:
                st.metric("Change %", f"{change_pct:+.2f}%")
            with info_col4:
                st.metric("High", f"${high:.2f}")
            with info_col5:
                st.metric("Low", f"${low:.2f}")

        except Exception as e:
            st.error(f"Error rendering chart: {str(e)[:50]}")
            st.info("Please try a different symbol or timeframe")

    else:
        st.warning(f"⚠️ Could not load chart data for {symbol}")
        st.info("Try a different symbol or timeframe")

# Bottom: Auto-refresh indicator
st.markdown("---")
col_refresh1, col_refresh2, col_refresh3 = st.columns([1, 3, 1])
with col_refresh1:
    st.write("⏰ Auto-refresh: 5s")
with col_refresh2:
    st.write(f"Stocks: {len(TOP_100_STOCKS)} available")
with col_refresh3:
    st.write(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

# Auto-refresh
st.markdown("""
<script>
setTimeout(function() {
    window.location.reload();
}, 5000);
</script>
""", unsafe_allow_html=True)
