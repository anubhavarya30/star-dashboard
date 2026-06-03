from supabase import create_client
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import random

load_dotenv()
sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

now = datetime.utcnow()

# Seed trades
trades = []
for i in range(10):
    entry = now - timedelta(hours=random.randint(1,48))
    exit_t = entry + timedelta(minutes=random.randint(15,120))
    pnl = round(random.uniform(-200, 800), 2)
    trades.append({
        "symbol": random.choice(["XAUUSD","AAPL","NVDA","TSLA","SPY"]),
        "strategy": random.choice(["RSI_MeanReversion","MACD_Momentum","BB_Breakout","EMA_Cross"]),
        "entry_time": entry.isoformat(),
        "entry_price": round(random.uniform(150, 3300), 2),
        "exit_time": exit_t.isoformat(),
        "exit_price": round(random.uniform(150, 3300), 2),
        "pnl": pnl,
        "direction": random.choice(["LONG","SHORT"]),
        "reason": "Signal confirmed on multi-timeframe"
    })
sb.table("trades").insert(trades).execute()
print("✅ trades seeded")

# Seed positions
positions = []
for sym in ["XAUUSD","AAPL","NVDA","TSLA","SPY"]:
    entry_price = round(random.uniform(150, 3300), 2)
    current_price = entry_price * random.uniform(0.97, 1.04)
    pnl_pct = round((current_price - entry_price) / entry_price * 100, 2)
    positions.append({
        "symbol": sym,
        "direction": random.choice(["LONG","SHORT"]),
        "entry_time": (now - timedelta(hours=random.randint(1,8))).isoformat(),
        "entry_price": entry_price,
        "current_price": round(current_price, 2),
        "pnl_pct": pnl_pct,
        "strategy": random.choice(["RSI_MeanReversion","MACD_Momentum","BB_Breakout"]),
        "status": "open"
    })
sb.table("positions").insert(positions).execute()
print("✅ positions seeded")

# Seed agent_states
agents = [
    {"agent_name": "Star", "status": "active", "last_signal": "XAUUSD LONG signal detected - RSI oversold"},
    {"agent_name": "NewsAgent", "status": "active", "last_signal": "Fed rate decision pending - high volatility expected"},
    {"agent_name": "IPOAgent", "status": "active", "last_signal": "3 new IPOs this week - monitoring"},
    {"agent_name": "EarningsAgent", "status": "active", "last_signal": "NVDA earnings call in 2 days"},
    {"agent_name": "GoldMonitor", "status": "active", "last_signal": "Gold above 200 EMA - bullish bias"},
]
sb.table("agent_states").upsert(agents).execute()
print("✅ agent_states seeded")

# Seed watchlist
watchlist = [
    {"symbol": "XAUUSD", "strategy": "RSI_MeanReversion + MACD", "priority": 1, "notes": "24/7 Gold monitor - primary"},
    {"symbol": "NVDA", "strategy": "EMA_Crossover + Volume", "priority": 2, "notes": "High momentum AI stock"},
    {"symbol": "AAPL", "strategy": "BB_Breakout", "priority": 3, "notes": "Earnings play"},
    {"symbol": "TSLA", "strategy": "MACD_Momentum", "priority": 4, "notes": "High volatility"},
    {"symbol": "SPY", "strategy": "Trend_Following", "priority": 5, "notes": "Market direction gauge"},
]
sb.table("watchlist").upsert(watchlist).execute()
print("✅ watchlist seeded")

# Seed mistakes
mistakes_data = [
    {"root_cause": "Entered trade against major trend", "lesson": "Always check 4H trend before entering on 15M signal", "pattern_tag": "counter_trend"},
    {"root_cause": "No stop loss set", "lesson": "Always set stop loss before entry, no exceptions", "pattern_tag": "risk_management"},
    {"root_cause": "Overtraded during news event", "lesson": "Avoid trading 30 mins before/after major news", "pattern_tag": "news_risk"},
    {"root_cause": "Ignored RSI divergence", "lesson": "RSI divergence overrides momentum signals", "pattern_tag": "divergence"},
    {"root_cause": "FOMO entry at resistance", "lesson": "Wait for pullback confirmation, never chase breakouts", "pattern_tag": "fomo"},
]
sb.table("mistakes").insert(mistakes_data).execute()
print("✅ mistakes seeded")

print("\n🚀 All tables seeded! Dashboard should now show live data.")
