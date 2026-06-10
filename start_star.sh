#!/bin/bash
# 🌟 STAR TRADING SYSTEM - PRODUCTION STARTUP SCRIPT
# Runs 24/7 with error handling and logging

cd /Users/anubhavarya/star/star-dashboard

echo "🚀 STARTING STAR TRADING SYSTEM..."
echo ""

# Activate virtualenv
source venv/bin/activate

# Start STAR Brain (main trading engine)
echo "🧠 Starting STAR Brain..."
nohup python3 star_brain.py >> star_brain.log 2>&1 &
BRAIN_PID=$!
echo "✅ STAR Brain started (PID: $BRAIN_PID)"

# Start Dashboard (monitoring interface)
echo "📊 Starting Dashboard..."
nohup streamlit run dashboard.py --server.port 8501 --logger.level=error >> dashboard.log 2>&1 &
DASH_PID=$!
echo "✅ Dashboard started (PID: $DASH_PID)"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "🌟 STAR TRADING SYSTEM - PRODUCTION MODE"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "✅ STAR Brain:  PID $BRAIN_PID (trading logic)"
echo "✅ Dashboard:   PID $DASH_PID (http://localhost:8501)"
echo ""
echo "📊 Monitoring:"
echo "   • Market: Open 9:30 AM - 4:00 PM ET"
echo "   • Symbols: AAPL, NVDA, TSLA, SPY"
echo "   • Analysis: Every 60 seconds"
echo "   • Decision: Auto-execute on signal"
echo ""
echo "📝 Logs:"
echo "   • star_brain.log (trading decisions)"
echo "   • dashboard.log (interface)"
echo ""
echo "⏱️  Running 24/7 - Check logs for issues"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "To stop: pkill -f star_brain; pkill -f streamlit"
echo "To check: ps aux | grep star_brain"
