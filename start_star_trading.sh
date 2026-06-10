#!/bin/bash
# Start STAR Trading System - All components

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  🌟 STAR TRADING SYSTEM - COMPLETE STARTUP               ║"
echo "║  Multi-Agent Algorithmic Trading System                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Activate virtual environment
source venv/bin/activate

echo "📋 SELECT STARTUP MODE:"
echo ""
echo "1. QUICK START (Demo) - Run one cycle"
echo "2. DAILY ROUTINE - Generate today's trading plan"
echo "3. FULL SYSTEM - Run everything continuously"
echo "4. DASHBOARD - View all trades in real-time"
echo "5. DATABASE - Setup database schema"
echo ""
read -p "Enter choice (1-5): " choice

case $choice in
    1)
        echo ""
        echo "🚀 Running QUICK START..."
        echo ""
        python3 << 'EOF'
from daily_routine_planner import DailyRoutinePlanner
from agent_aggregator import AgentAggregator

# Collect agent signals
aggregator = AgentAggregator()
signals = aggregator.collect_agent_signals()
aggregator.print_summary(signals)

# Create daily routine
planner = DailyRoutinePlanner()
routine = planner.create_daily_plan()
planner.print_routine(routine)
planner.save_routine(routine)

print("\n✅ Quick start complete!")
print("📊 View results in Supabase dashboard")
EOF
        ;;

    2)
        echo ""
        echo "📅 Generating Daily Routine..."
        echo ""
        python3 daily_routine_planner.py
        ;;

    3)
        echo ""
        echo "🚀 Starting FULL SYSTEM (Continuous Mode)"
        echo "   Press Ctrl+C to stop"
        echo ""
        python3 smart_trader.py
        ;;

    4)
        echo ""
        echo "📊 Starting Streamlit Dashboard..."
        echo "   Open: http://localhost:8501"
        echo ""
        streamlit run dashboard_live.py
        ;;

    5)
        echo ""
        echo "🗄️  Setting up Database..."
        echo ""
        python3 database_schema.py
        ;;

    *)
        echo "Invalid choice!"
        exit 1
        ;;
esac
