"""
Setup Supabase schema for multi-agent trading system.
Creates all necessary tables for agent communication and workflow.
"""
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Note: Run these SQL commands in Supabase SQL editor manually if needed
print("Creating Supabase schema for multi-agent system...\n")

# Tables to create (copy these to Supabase SQL editor):
schema_sql = """
-- Agent states (active/idle/error)
CREATE TABLE IF NOT EXISTS agent_states (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_name TEXT UNIQUE NOT NULL,
  status TEXT DEFAULT 'idle',
  last_signal TEXT,
  last_updated TIMESTAMP DEFAULT now(),
  state JSONB DEFAULT '{}'::jsonb
);

-- Agent reports (detailed findings)
CREATE TABLE IF NOT EXISTS agent_reports (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_name TEXT NOT NULL,
  report_type TEXT NOT NULL,
  symbols TEXT[] DEFAULT ARRAY[]::TEXT[],
  findings JSONB NOT NULL,
  confidence FLOAT DEFAULT 0.0,
  created_at TIMESTAMP DEFAULT now(),
  FOREIGN KEY (agent_name) REFERENCES agent_states(agent_name)
);

-- Agent signals (buy/sell/hold)
CREATE TABLE IF NOT EXISTS agent_signals (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_name TEXT NOT NULL,
  symbol TEXT NOT NULL,
  signal TEXT CHECK (signal IN ('BUY', 'SELL', 'HOLD')),
  confidence FLOAT DEFAULT 0.0,
  reason TEXT,
  created_at TIMESTAMP DEFAULT now(),
  FOREIGN KEY (agent_name) REFERENCES agent_states(agent_name)
);

-- Star's aggregated decision (CEO layer)
CREATE TABLE IF NOT EXISTS star_decision (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_date DATE DEFAULT CURRENT_DATE,
  symbol TEXT NOT NULL,
  recommended_action TEXT CHECK (recommended_action IN ('BUY', 'SELL', 'HOLD', 'WAIT')),
  vote_tally JSONB DEFAULT '{}'::jsonb,
  reasoning TEXT,
  confidence FLOAT DEFAULT 0.0,
  status TEXT DEFAULT 'pending_approval',
  user_approved BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT now(),
  approved_at TIMESTAMP
);

-- Watchlist (dynamically populated by agents)
CREATE TABLE IF NOT EXISTS watchlist (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  symbol TEXT UNIQUE NOT NULL,
  strategy TEXT,
  priority INT DEFAULT 5,
  notes TEXT,
  recommended_by TEXT,
  confidence FLOAT DEFAULT 0.0,
  updated_at TIMESTAMP DEFAULT now()
);

-- Positions (active trades)
CREATE TABLE IF NOT EXISTS positions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  symbol TEXT NOT NULL,
  direction TEXT CHECK (direction IN ('LONG', 'SHORT')),
  entry_price FLOAT NOT NULL,
  entry_time TIMESTAMP NOT NULL,
  current_price FLOAT,
  qty INT DEFAULT 1,
  strategy TEXT,
  status TEXT DEFAULT 'open',
  agent_protection_signal TEXT,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

-- Trades (completed trades)
CREATE TABLE IF NOT EXISTS trades (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  symbol TEXT NOT NULL,
  direction TEXT,
  entry_price FLOAT,
  exit_price FLOAT,
  entry_time TIMESTAMP,
  exit_time TIMESTAMP,
  pnl FLOAT,
  pnl_pct FLOAT,
  strategy TEXT,
  reason TEXT,
  created_at TIMESTAMP DEFAULT now()
);

-- Gold monitoring (24/7 independent)
CREATE TABLE IF NOT EXISTS gold_monitor (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  symbol TEXT DEFAULT 'XAUUSD',
  price FLOAT,
  rsi FLOAT,
  macd FLOAT,
  macd_hist FLOAT,
  bb_upper FLOAT,
  bb_lower FLOAT,
  signal TEXT CHECK (signal IN ('BUY', 'SELL', 'HOLD')),
  created_at TIMESTAMP DEFAULT now()
);

-- OHLC data (candlesticks for charts)
CREATE TABLE IF NOT EXISTS ohlc (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  symbol TEXT NOT NULL,
  ts TIMESTAMP NOT NULL,
  open FLOAT,
  high FLOAT,
  low FLOAT,
  close FLOAT,
  volume FLOAT DEFAULT 0,
  created_at TIMESTAMP DEFAULT now()
);

-- Mistakes log
CREATE TABLE IF NOT EXISTS mistakes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  root_cause TEXT,
  lesson TEXT,
  pattern_tag TEXT,
  created_at TIMESTAMP DEFAULT now()
);

-- Agent execution log (audit trail)
CREATE TABLE IF NOT EXISTS agent_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_name TEXT NOT NULL,
  action TEXT,
  details JSONB,
  status TEXT DEFAULT 'success',
  error_msg TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_reports_agent ON agent_reports(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_signals_symbol ON agent_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_star_decision_date ON star_decision(decision_date);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_ts ON ohlc(symbol, ts DESC);
"""

print("✅ Schema SQL (copy to Supabase SQL editor):")
print("=" * 80)
print(schema_sql)
print("=" * 80)
print("\n📌 Run the above SQL in your Supabase dashboard:")
print("1. Go to https://app.supabase.com")
print("2. Select your project")
print("3. Click 'SQL Editor' → 'New Query'")
print("4. Paste the SQL above")
print("5. Click 'Run'")
print("\n✅ Then come back here!")
