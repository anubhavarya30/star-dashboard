#!/usr/bin/env python3
"""
Create Supabase tables via REST API
"""
import os
import requests
import json

# Load .env
env_path = '/Users/anubhavarya/star/star-dashboard/.env'
with open(env_path) as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Extract project ref
project_ref = SUPABASE_URL.split("//")[1].split(".")[0]

# Use management API
url = f"https://api.supabase.com/api/v1/projects/{project_ref}/query"

sql_script = """
DROP TABLE IF EXISTS agent_logs CASCADE;
DROP TABLE IF EXISTS agent_signals CASCADE;
DROP TABLE IF EXISTS agent_reports CASCADE;
DROP TABLE IF EXISTS star_decision CASCADE;
DROP TABLE IF EXISTS gold_monitor CASCADE;
DROP TABLE IF EXISTS ohlc CASCADE;
DROP TABLE IF EXISTS mistakes CASCADE;
DROP TABLE IF EXISTS watchlist CASCADE;

CREATE TABLE agent_states (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_name TEXT UNIQUE NOT NULL,
  status TEXT DEFAULT 'idle',
  last_signal TEXT,
  last_updated TIMESTAMP DEFAULT now(),
  state JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE agent_reports (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_name TEXT NOT NULL,
  report_type TEXT NOT NULL,
  symbols TEXT[] DEFAULT ARRAY[]::TEXT[],
  findings JSONB NOT NULL,
  confidence FLOAT DEFAULT 0.0,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE agent_signals (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_name TEXT NOT NULL,
  symbol TEXT NOT NULL,
  signal TEXT CHECK (signal IN ('BUY', 'SELL', 'HOLD', 'WAIT')),
  confidence FLOAT DEFAULT 0.0,
  reason TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE star_decision (
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

CREATE TABLE watchlist (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  symbol TEXT UNIQUE NOT NULL,
  strategy TEXT,
  priority INT DEFAULT 5,
  notes TEXT,
  recommended_by TEXT,
  confidence FLOAT DEFAULT 0.0,
  updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE gold_monitor (
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

CREATE TABLE ohlc (
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

CREATE TABLE mistakes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  root_cause TEXT,
  lesson TEXT,
  pattern_tag TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE agent_logs (
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

print("📊 Attempting to create Supabase tables via REST API...\n")

# Try different endpoints
endpoints = [
    f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
    f"https://{project_ref}.supabase.co/rest/v1/rpc/sql",
    f"{SUPABASE_URL}/graphql/v1",
]

headers = {
    "apikey": SUPABASE_KEY,
    "Content-Type": "application/json",
}

for endpoint in endpoints:
    try:
        response = requests.post(
            endpoint,
            json={"query": sql_script},
            headers=headers,
            timeout=10
        )
        print(f"Tried: {endpoint}")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}\n")
    except Exception as e:
        print(f"❌ {endpoint}: {str(e)[:100]}\n")

print("\n⚠️  REST API approach didn't work.")
print("Please create tables manually in Supabase SQL Editor:\n")
print("1. Go to https://app.supabase.com")
print("2. Click 'SQL Editor' → 'New Query'")
print("3. Copy-paste SQL from above")
print("4. Run it")
print("\nOnce done, the agents can run!")
