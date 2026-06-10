#!/usr/bin/env python3
"""
🌟 STAR DASHBOARD - FIXED & WORKING
Left: Trading Journal Calendar
Right: Real-time Interactive Chart
"""
import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
from calendar import monthcalendar
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(page_title="STAR Trading", layout="wide", initial_sidebar_state="collapsed")
st.markdown("<style>[data-testid='collapsedControl']{display:none}#MainMenu{visibility:hidden}footer{visibility:hidden}</style>", unsafe_allow_html=True)

TOP_100 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JNJ", "V",
    "WMT", "JPM", "PG", "MA", "UNH", "MCD", "INTC", "BA", "VZ", "KO",
    "NFLX", "PEP", "COST", "CSCO", "ABBV", "CRM", "CMG", "ADBE", "NKE", "QCOM",
    "AMD", "AVGO", "ASML", "TJX", "MU", "SBUX", "NOW", "AZO", "BKNG", "GILD",
    "SPY", "QQQ", "IWM", "DIA", "XLE", "XLF", "XLV", "XLI", "XLY", "XLK"]

@st.cache_data(ttl=60)
def load_trades():
    if Path("current_trades.json").exists():
        with open("current_trades.json") as f:
            return json.load(f)
    return {"open_trades": {}, "signals": []}

@st.cache_data(ttl=60)
def get_data(sym, tf):
    try:
        if tf == "1d":
            d = yf.download(sym, period="1y", progress=False, timeout=10)
        elif tf == "1h":
            d = yf.download(sym, period="60d", interval="1h", progress=False, timeout=10)
        elif tf == "15m":
            d = yf.download(sym, period="30d", interval="15m", progress=False, timeout=10)
        elif tf == "5m":
            d = yf.download(sym, period="7d", interval="5m", progress=False, timeout=10)
        else:
            d = yf.download(sym, period="1d", interval="1m", progress=False, timeout=10)
        return d if not d.empty else None
    except:
        return None

state = load_trades()

st.title("🌟 STAR Trading Dashboard")
L, R = st.columns([0.28, 0.72], gap="small")

with L:
    st.subheader("📅 Trading Calendar")
    today = datetime.now()
    m = st.selectbox("Mo", range(1,13), index=today.month-1, label_visibility="collapsed")
    y = st.selectbox("Yr", range(2024,2027), label_visibility="collapsed")
    
    cal = monthcalendar(y, m)
    for day_names in [["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]]:
        cols = st.columns(7)
        for i, nm in enumerate(day_names):
            cols[i].write(f"**{nm}**")
    
    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            with cols[i]:
                if day > 0:
                    pnl = 0
                    for t in state.get("open_trades",{}).values():
                        if t.get("entry_time","").split("T")[0] == f"{y}-{m:02d}-{day:02d}":
                            pnl += t.get("pnl", 0)
                    color = "lightgreen" if pnl > 0 else ("lightcoral" if pnl < 0 else "white")
                    tc = "darkgreen" if pnl > 0 else ("darkred" if pnl < 0 else "black")
                    st.markdown(f"<div style='background:{color};border-radius:8px;padding:8px;text-align:center;border:1px solid #ddd'><b style='color:{tc}'>{day}</b><br><small>${pnl:+.0f}</small></div>", unsafe_allow_html=True)
    
    st.divider()
    st.subheader("📊 Summary")
    c1, c2 = st.columns(2)
    tpnl = sum(t.get("pnl",0) for t in state.get("open_trades",{}).values() if t.get("entry_time","").split("T")[0]==datetime.now().strftime("%Y-%m-%d"))
    c1.metric("Today", f"${tpnl:+.0f}")
    c2.metric("Trades", len(state.get("open_trades",{})))

with R:
    st.subheader("📈 Real-Time Chart")
    cs, ct = st.columns([0.6, 0.4])
    with cs:
        sym = st.selectbox("Stock", sorted(TOP_100), label_visibility="collapsed", key="s")
    with ct:
        tf = st.selectbox("TF", ["1m","5m","15m","1h","1d"], index=3, label_visibility="collapsed", key="t")
    
    msg = st.empty()
    msg.info(f"Loading {sym}...")
    df = get_data(sym, tf)
    msg.empty()
    
    if df is not None and len(df) > 0:
        try:
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name=sym, increasing_line_color='green', decreasing_line_color='red'
            ))
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Vol', marker_color='rgba(100,100,100,0.3)', yaxis='y2'))
            fig.update_layout(height=650, xaxis_rangeslider_visible=False, yaxis2=dict(title="Vol", overlaying="y", side="right"),
                hovermode='x unified', template="plotly_dark", margin=dict(l=50,r=50,t=40,b=40), title=f"<b>{sym}</b> {tf}")
            st.plotly_chart(fig, use_container_width=True)
            
            st.divider()
            try:
                p = float(df['Close'].iloc[-1])
                pv = float(df['Close'].iloc[-2]) if len(df)>1 else p
                c, cp, h, l = p-pv, (p-pv)/pv*100, float(df['High'].iloc[-1]), float(df['Low'].iloc[-1])
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Price", f"${p:.2f}")
                c2.metric("Change", f"${c:+.2f}")
                c3.metric("Chg%", f"{cp:+.1f}%")
                c4.metric("High", f"${h:.2f}")
                c5.metric("Low", f"${l:.2f}")
            except:
                pass
        except Exception as e:
            st.error(f"Chart Error")
    else:
        st.warning(f"Could not load {sym} - try AAPL or MSFT")

st.markdown("---")
c1,c2,c3=st.columns([1,2,1])
c1.write("⏰ 60s")
c2.write(f"Stocks: {len(TOP_100)} | {datetime.now().strftime('%H:%M:%S')}")
c3.write("✅ LIVE")
