#!/usr/bin/env python3
"""
Star Trading System - Database Schema Setup
Creates complete training and operational database
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# ============================================================
# DATABASE SCHEMA DEFINITIONS
# ============================================================

TABLES_TO_CREATE = {

    # 1. MARKET DATA (for training)
    "market_data": {
        "description": "OHLCV data for all symbols - used for algo training",
        "columns": {
            "id": "bigint primary key generated always as identity",
            "symbol": "text not null",
            "date": "timestamp not null",
            "open": "decimal(20,6) not null",
            "high": "decimal(20,6) not null",
            "low": "decimal(20,6) not null",
            "close": "decimal(20,6) not null",
            "volume": "bigint not null",
            "created_at": "timestamp default now()"
        }
    },

    # 2. AGENT SIGNALS (from all agents)
    "agent_signals": {
        "description": "Trading signals from all agents (market research, sentiment, earnings, etc)",
        "columns": {
            "id": "bigint primary key generated always as identity",
            "date": "date not null",
            "agent_name": "text not null",
            "symbol": "text not null",
            "signal": "text not null",  # BUY, SELL, HOLD
            "confidence": "decimal(5,2)",  # 0-100
            "reason": "text",
            "data": "jsonb",  # Raw data from agent
            "created_at": "timestamp default now()"
        }
    },

    # 3. DAILY ROUTINE (planned trades for the day)
    "daily_routine": {
        "description": "Daily trading plan based on agent consensus and market conditions",
        "columns": {
            "id": "bigint primary key generated always as identity",
            "date": "date not null unique",
            "market_outlook": "text",  # Bull, Bear, Neutral
            "strategy": "text",  # Day's strategy
            "high_probability_symbols": "text[]",  # Best opportunities
            "agent_consensus": "jsonb",  # All agent inputs
            "risk_level": "text",  # Low, Medium, High
            "created_at": "timestamp default now()"
        }
    },

    # 4. TRADING DECISIONS (final decision before trade)
    "trading_decisions": {
        "description": "Final trading decisions with agent consensus and market context",
        "columns": {
            "id": "bigint primary key generated always as identity",
            "date": "date not null",
            "time": "time not null",
            "symbol": "text not null",
            "action": "text not null",  # BUY, SELL, HOLD
            "entry_price": "decimal(20,6)",
            "stop_loss": "decimal(20,6)",
            "take_profit": "decimal(20,6)",
            "confidence": "decimal(5,2)",  # 0-100
            "agent_votes": "jsonb",  # {agent_name: signal}
            "market_context": "jsonb",  # RSI, MACD, trend etc
            "executed": "boolean default false",
            "execution_price": "decimal(20,6)",
            "pnl": "decimal(20,6)",
            "reason": "text",
            "created_at": "timestamp default now()"
        }
    },

    # 5. EXECUTED TRADES (actual trades taken)
    "executed_trades": {
        "description": "All trades executed with full details for analysis",
        "columns": {
            "id": "bigint primary key generated always as identity",
            "date": "date not null",
            "time": "time not null",
            "symbol": "text not null",
            "side": "text not null",  # BUY, SELL
            "entry_price": "decimal(20,6) not null",
            "exit_price": "decimal(20,6)",
            "quantity": "integer",
            "stop_loss": "decimal(20,6)",
            "take_profit": "decimal(20,6)",
            "pnl": "decimal(20,6)",
            "pnl_pct": "decimal(10,2)",
            "status": "text",  # Open, Closed, Stopped Out
            "duration_minutes": "integer",
            "agent_decision_id": "bigint references trading_decisions(id)",
            "created_at": "timestamp default now()",
            "closed_at": "timestamp"
        }
    },

    # 6. AGENT PERFORMANCE (tracking each agent accuracy)
    "agent_performance": {
        "description": "Historical performance of each agent's signals",
        "columns": {
            "id": "bigint primary key generated always as identity",
            "date": "date not null",
            "agent_name": "text not null",
            "symbol": "text not null",
            "signal_given": "text not null",  # BUY, SELL, HOLD
            "confidence": "decimal(5,2)",
            "actual_result": "text",  # WIN, LOSS, NEUTRAL
            "pnl_pct": "decimal(10,2)",
            "accuracy_pct": "decimal(5,2)",  # Win rate over time
            "created_at": "timestamp default now()"
        }
    },

    # 7. MARKET CONDITIONS (snapshot of market state)
    "market_conditions": {
        "description": "Daily market conditions for context in training",
        "columns": {
            "id": "bigint primary key generated always as identity",
            "date": "date not null unique",
            "market_trend": "text",  # Uptrend, Downtrend, Sideways
            "volatility": "decimal(10,2)",  # VIX or ATR
            "volume_profile": "text",  # High, Normal, Low
            "sentiment": "text",  # Bullish, Bearish, Neutral
            "open": "time",  # Market open time
            "close": "time",  # Market close time
            "notes": "text",
            "created_at": "timestamp default now()"
        }
    },

    # 8. TRAINING DATA (aggregated for model training)
    "training_data": {
        "description": "Aggregated data for training the trading algorithm",
        "columns": {
            "id": "bigint primary key generated always as identity",
            "date": "date not null",
            "symbol": "text not null",
            "features": "jsonb not null",  # RSI, MACD, BB, Volume, etc
            "agent_signals": "jsonb",  # All agent inputs
            "label": "text not null",  # BUY, SELL, HOLD (actual outcome)
            "profit_pct": "decimal(10,2)",  # Actual profit if followed signal
            "created_at": "timestamp default now()"
        }
    }
}

def create_tables():
    """Create all required tables in Supabase"""
    print("\n" + "="*80)
    print("🗄️  CREATING STAR TRADING DATABASE SCHEMA")
    print("="*80 + "\n")

    for table_name, schema in TABLES_TO_CREATE.items():
        try:
            # Check if table exists
            result = sb.table(table_name).select("*").limit(1).execute()
            print(f"✅ {table_name}: Already exists")
        except:
            print(f"⚠️  {table_name}: Cannot auto-create via SDK")
            print(f"   → Please create via Supabase UI with this structure:")
            print(f"   → Description: {schema['description']}")
            print(f"   → Columns: {list(schema['columns'].keys())}\n")

    print("="*80)
    print("\n📋 To create tables manually in Supabase:")
    print("1. Go to: https://app.supabase.com/")
    print("2. Select your project")
    print("3. SQL Editor → New Query")
    print("4. Copy the SQL schema below:\n")

    print(generate_sql_schema())

def generate_sql_schema():
    """Generate SQL for creating all tables"""
    sql = """
-- Star Trading System - Complete Database Schema
-- Copy this entire script into Supabase SQL Editor and run

-- 1. Market Data Table
CREATE TABLE IF NOT EXISTS market_data (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    date TIMESTAMP NOT NULL,
    open DECIMAL(20,6) NOT NULL,
    high DECIMAL(20,6) NOT NULL,
    low DECIMAL(20,6) NOT NULL,
    close DECIMAL(20,6) NOT NULL,
    volume BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, date)
);

-- 2. Agent Signals Table
CREATE TABLE IF NOT EXISTS agent_signals (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    agent_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    signal TEXT NOT NULL,
    confidence DECIMAL(5,2),
    reason TEXT,
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. Daily Routine Table
CREATE TABLE IF NOT EXISTS daily_routine (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    market_outlook TEXT,
    strategy TEXT,
    high_probability_symbols TEXT[],
    agent_consensus JSONB,
    risk_level TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 4. Trading Decisions Table
CREATE TABLE IF NOT EXISTS trading_decisions (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time TIME NOT NULL,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    entry_price DECIMAL(20,6),
    stop_loss DECIMAL(20,6),
    take_profit DECIMAL(20,6),
    confidence DECIMAL(5,2),
    agent_votes JSONB,
    market_context JSONB,
    executed BOOLEAN DEFAULT FALSE,
    execution_price DECIMAL(20,6),
    pnl DECIMAL(20,6),
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 5. Executed Trades Table
CREATE TABLE IF NOT EXISTS executed_trades (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time TIME NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price DECIMAL(20,6) NOT NULL,
    exit_price DECIMAL(20,6),
    quantity INTEGER,
    stop_loss DECIMAL(20,6),
    take_profit DECIMAL(20,6),
    pnl DECIMAL(20,6),
    pnl_pct DECIMAL(10,2),
    status TEXT,
    duration_minutes INTEGER,
    agent_decision_id BIGINT REFERENCES trading_decisions(id),
    created_at TIMESTAMP DEFAULT NOW(),
    closed_at TIMESTAMP
);

-- 6. Agent Performance Table
CREATE TABLE IF NOT EXISTS agent_performance (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    agent_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    signal_given TEXT NOT NULL,
    confidence DECIMAL(5,2),
    actual_result TEXT,
    pnl_pct DECIMAL(10,2),
    accuracy_pct DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 7. Market Conditions Table
CREATE TABLE IF NOT EXISTS market_conditions (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    market_trend TEXT,
    volatility DECIMAL(10,2),
    volume_profile TEXT,
    sentiment TEXT,
    open TIME,
    close TIME,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 8. Training Data Table
CREATE TABLE IF NOT EXISTS training_data (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    symbol TEXT NOT NULL,
    features JSONB NOT NULL,
    agent_signals JSONB,
    label TEXT NOT NULL,
    profit_pct DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for faster queries
CREATE INDEX idx_market_data_symbol_date ON market_data(symbol, date);
CREATE INDEX idx_agent_signals_date ON agent_signals(date, symbol);
CREATE INDEX idx_trading_decisions_symbol ON trading_decisions(symbol, date);
CREATE INDEX idx_executed_trades_symbol ON executed_trades(symbol, date);
CREATE INDEX idx_agent_performance_agent ON agent_performance(agent_name, date);

-- Enable Row Level Security (optional but recommended)
ALTER TABLE market_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE executed_trades ENABLE ROW LEVEL SECURITY;
    """
    return sql

if __name__ == "__main__":
    create_tables()
