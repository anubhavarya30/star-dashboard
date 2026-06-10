#!/usr/bin/env python3
"""
🌟 STAR DASHBOARD - TRADING JOURNAL + METRICS
Left: Trading Calendar with Daily P&L (Green/Red)
Right: Trading Data, Stats, Recent Trades
"""
import streamlit as st
import json
from pathlib import Path
from datetime import datetime
from calendar import monthcalendar
import pandas as pd

st.set_page_config(page_title="STAR Trading", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>[data-testid='collapsedControl']{display:none}#MainMenu{visibility:hidden}footer{visibility:hidden}</style>", unsafe_allow_html=True)

@st.cache_data(ttl=5)
def load_trades():
    if Path("current_trades.json").exists():
        with open("current_trades.json") as f:
            return json.load(f)
    return {"open_trades": {}, "signals": []}

state = load_trades()

st.title("🌟 STAR Trading Dashboard")

L, R = st.columns([0.3, 0.7], gap="medium")

# ===== LEFT: TRADING CALENDAR =====
with L:
    st.subheader("📅 Trading Calendar")
    
    today = datetime.now()
    m = st.selectbox("Month", range(1, 13), index=today.month-1, label_visibility="collapsed")
    y = st.selectbox("Year", range(2024, 2027), index=0, label_visibility="collapsed")
    
    cal = monthcalendar(y, m)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    # Header
    cols = st.columns(7)
    for i, day in enumerate(days):
        with cols[i]:
            st.write(f"**{day}**")
    
    # Calendar grid
    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            with cols[i]:
                if day > 0:
                    date_str = f"{y:04d}-{m:02d}-{day:02d}"
                    pnl = 0
                    
                    # Calculate P&L for this day
                    for trade_id, trade in state.get("open_trades", {}).items():
                        entry_date = trade.get("entry_time", "").split("T")[0]
                        if entry_date == date_str:
                            pnl += trade.get("pnl", 0)
                    
                    # Color based on P&L
                    if pnl > 0:
                        bg_color = "#90EE90"  # Light green
                        text_color = "#006400"  # Dark green
                    elif pnl < 0:
                        bg_color = "#FFB6C6"  # Light red
                        text_color = "#8B0000"  # Dark red
                    else:
                        bg_color = "#FFFFFF"  # White
                        text_color = "#000000"  # Black
                    
                    st.markdown(
                        f"""
                        <div style='
                            background-color: {bg_color};
                            border: 1px solid #ddd;
                            border-radius: 8px;
                            padding: 8px;
                            text-align: center;
                            height: 70px;
                            display: flex;
                            flex-direction: column;
                            justify-content: center;
                        '>
                            <div style='color: {text_color}; font-weight: bold; font-size: 16px;'>{day}</div>
                            <div style='color: {text_color}; font-size: 12px;'>${pnl:+.0f}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
    
    st.divider()
    st.subheader("📊 Today")
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_pnl = sum(t.get("pnl", 0) for t in state.get("open_trades", {}).values()
                    if t.get("entry_time", "").split("T")[0] == today_str)
    
    col1, col2 = st.columns(2)
    with col1:
        if today_pnl > 0:
            st.metric("P&L", f"${today_pnl:.2f}", delta=f"+${today_pnl:.2f}", delta_color="inverse")
        elif today_pnl < 0:
            st.metric("P&L", f"${today_pnl:.2f}", delta=f"${today_pnl:.2f}", delta_color="inverse")
        else:
            st.metric("P&L", "$0.00")
    
    with col2:
        st.metric("Trades", len(state.get("open_trades", {})))

# ===== RIGHT: TRADING DATA & METRICS =====
with R:
    tab1, tab2, tab3 = st.tabs(["📈 Trades", "📊 Stats", "🤖 Signals"])
    
    # TAB 1: TRADES
    with tab1:
        st.subheader("Open Trades")
        trades = state.get("open_trades", {})
        
        if trades:
            trade_data = []
            for tid, trade in trades.items():
                trade_data.append({
                    "Symbol": trade.get("symbol"),
                    "Action": trade.get("action"),
                    "Qty": trade.get("quantity"),
                    "Entry": f"${trade.get('entry_price', 0):.2f}",
                    "SL": f"${trade.get('stop_loss', 0):.2f}",
                    "TP": f"${trade.get('take_profit', 0):.2f}",
                    "Time": trade.get("entry_time", "").split("T")[1][:5],
                    "P&L": f"${trade.get('pnl', 0):+.2f}"
                })
            
            df = pd.DataFrame(trade_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No open trades")
    
    # TAB 2: STATS
    with tab2:
        st.subheader("Account Statistics")
        
        trades = state.get("open_trades", {})
        signals = state.get("signals", [])
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Account", "$100,000", "Paper")
        
        with col2:
            st.metric("Open Trades", len(trades))
        
        with col3:
            st.metric("Total Signals", len(signals))
        
        with col4:
            total_pnl = sum(t.get("pnl", 0) for t in trades.values())
            st.metric("Total P&L", f"${total_pnl:+.2f}")
        
        st.divider()
        st.write("**Strategy:** Volume-Weighted RSI")
        st.write("**Risk/Trade:** 2% ($2,000)")
        st.write("**Symbols:** AAPL, NVDA, TSLA, SPY")
        st.write("**Status:** ✅ LIVE")
    
    # TAB 3: SIGNALS
    with tab3:
        st.subheader("Recent Signals")
        
        signals = state.get("signals", [])
        
        if signals:
            sig_data = []
            for sig in signals[-10:]:
                sig_data.append({
                    "Symbol": sig.get("symbol"),
                    "Action": sig.get("action"),
                    "Confidence": f"{sig.get('confidence', 0):.0%}",
                    "Price": f"${sig.get('entry_price', 0):.2f}",
                    "Time": sig.get("timestamp", "").split("T")[1][:5]
                })
            
            df = pd.DataFrame(sig_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No signals yet")

# Footer
st.markdown("---")
c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    st.write("⏰ Live")
with c2:
    st.write(f"Last: {state.get('last_update', 'Never').split('T')[1][:8] if 'T' in str(state.get('last_update', '')) else 'Never'}")
with c3:
    st.write(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

# Auto refresh
st.markdown("<script>setTimeout(()=>window.location.reload(),5000);</script>", unsafe_allow_html=True)
