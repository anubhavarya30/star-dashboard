#!/usr/bin/env python3
"""
Smart Trader - Enhanced Trading Engine
Uses daily routine + agent consensus + technical signals to execute trades
Paper trading mode (safe) with full logging for training data
"""
import os
import time
from datetime import datetime, date
from dotenv import load_dotenv
from supabase import create_client
import json

from trading_signals import VolumeWeightedRSISystem
from position_manager import PositionManager
from agent_aggregator import AgentAggregator
from daily_routine_planner import DailyRoutinePlanner
import yfinance as yf
import pandas as pd

load_dotenv()

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class SmartTrader:
    """
    Advanced trading system that combines:
    - Agent signals (consensus)
    - Daily routine (planned trades)
    - Technical analysis (entry/exit)
    - Risk management (position sizing)
    """

    def __init__(self, paper_trade=True):
        self.paper_trade = paper_trade
        self.mode = "PAPER TRADE" if paper_trade else "LIVE"

        self.trading_system = VolumeWeightedRSISystem()
        self.position_manager = PositionManager(
            account_balance=100000.0,
            risk_per_trade=0.02
        )

        self.aggregator = AgentAggregator()
        self.planner = DailyRoutinePlanner()

        # Load today's routine
        self.daily_routine = self._load_daily_routine()

        print(f"\n🚀 Smart Trader Started - Mode: {self.mode}")
        print(f"   Daily Routine: {self.daily_routine.get('market_outlook')} ({self.daily_routine.get('risk_level')} risk)")

    def _load_daily_routine(self):
        """Load or create today's trading routine"""
        try:
            today = date.today()
            result = sb.table("daily_routine").select("*").eq("date", str(today)).execute()

            if result.data:
                return result.data[0]
            else:
                # Create new routine if doesn't exist
                planner = DailyRoutinePlanner()
                routine = planner.create_daily_plan()
                planner.save_routine(routine)
                return routine

        except:
            # Return default if error
            return {
                "market_outlook": "NEUTRAL",
                "risk_level": "MEDIUM",
                "high_probability_symbols": []
            }

    def should_trade_symbol(self, symbol):
        """
        Determine if symbol should be traded based on:
        1. Daily routine (is it in high-probability list?)
        2. Agent consensus (are agents agreeing?)
        3. Risk level (can we afford to trade?)
        """
        high_prob_symbols = self.daily_routine.get("high_probability_symbols", [])

        if symbol not in high_prob_symbols:
            return False, "Not in high-probability list"

        # Check agent consensus
        agent_consensus = self.daily_routine.get("agent_consensus", {})
        symbol_data = agent_consensus.get(symbol, {})

        consensus = symbol_data.get("consensus", "HOLD")
        confidence = symbol_data.get("avg_confidence", 0)

        if consensus == "HOLD" or confidence < 0.70:
            return False, f"Weak consensus ({confidence:.0%})"

        return True, f"Ready - {consensus} ({confidence:.0%} confidence)"

    def process_symbol(self, symbol):
        """
        Process one symbol for trading:
        1. Check if should trade
        2. Fetch market data
        3. Generate signal
        4. Evaluate against daily routine
        5. Create trading decision
        """
        # Check if should trade
        should_trade, reason = self.should_trade_symbol(symbol)

        if not should_trade:
            return {
                "symbol": symbol,
                "action": "SKIP",
                "reason": reason
            }

        # Fetch data
        try:
            data = yf.download(symbol, period="5d", interval="1h", progress=False)

            if data.empty:
                return {"symbol": symbol, "action": "SKIP", "reason": "No data"}

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            ohlcv = {
                'open': data['Open'].values,
                'high': data['High'].values,
                'low': data['Low'].values,
                'close': data['Close'].values,
                'volume': data['Volume'].values if 'Volume' in data.columns else [1] * len(data)
            }

            # Generate signal from technical analysis
            technical_signal = self.trading_system.generate_signal(ohlcv)

            # Get daily targets for this symbol
            daily_targets = self.daily_routine.get("daily_targets", {}).get(symbol, {})

            # Check if signal matches daily routine expectation
            action = technical_signal.get('action', 'HOLD')
            expected_action = daily_targets.get('action', 'HOLD')

            # Only execute if technical signal matches expected action
            if action != expected_action:
                return {
                    "symbol": symbol,
                    "action": "SKIP",
                    "reason": f"Signal mismatch: got {action}, expected {expected_action}"
                }

            if action == "HOLD":
                return {
                    "symbol": symbol,
                    "action": "HOLD",
                    "reason": technical_signal.get("reason", "No clear signal")
                }

            # Create trading decision with agent consensus
            decision = self._create_trading_decision(
                symbol,
                action,
                technical_signal,
                daily_targets
            )

            return decision

        except Exception as e:
            return {
                "symbol": symbol,
                "action": "ERROR",
                "error": str(e)[:60]
            }

    def _create_trading_decision(self, symbol, action, technical_signal, daily_targets):
        """Create a trading decision combining all inputs"""
        agent_consensus = self.daily_routine.get("agent_consensus", {}).get(symbol, {})

        decision = {
            "symbol": symbol,
            "date": date.today(),
            "time": datetime.now().time().isoformat(),
            "action": action,
            "entry_price": technical_signal.get("entry_price"),
            "stop_loss": technical_signal.get("stop_loss"),
            "take_profit": technical_signal.get("take_profit"),
            "confidence": technical_signal.get("confidence", 0),
            "agent_votes": {
                "consensus": agent_consensus.get("consensus"),
                "buy_votes": agent_consensus.get("buy_votes", 0),
                "sell_votes": agent_consensus.get("sell_votes", 0),
                "total_votes": agent_consensus.get("total_votes", 0)
            },
            "market_context": {
                "outlook": self.daily_routine.get("market_outlook"),
                "risk_level": self.daily_routine.get("risk_level"),
                "rsi": technical_signal.get("rsi", None),
                "atr": technical_signal.get("atr", None)
            },
            "reason": technical_signal.get("reason", ""),
            "executed": False
        }

        return decision

    def execute_decision(self, decision):
        """
        Execute trading decision (in paper mode: just log)
        In live mode: would connect to IBKR

        Returns trade execution record
        """
        symbol = decision.get("symbol")
        action = decision.get("action")

        if action == "HOLD" or action == "SKIP":
            return {"status": "skipped", "symbol": symbol}

        try:
            # Create trading decision record
            decision_record = {
                "date": str(decision.get("date")),
                "time": decision.get("time"),
                "symbol": symbol,
                "action": action,
                "entry_price": float(decision.get("entry_price", 0)),
                "stop_loss": float(decision.get("stop_loss", 0)),
                "take_profit": float(decision.get("take_profit", 0)),
                "confidence": float(decision.get("confidence", 0)),
                "agent_votes": decision.get("agent_votes"),
                "market_context": decision.get("market_context"),
                "reason": decision.get("reason", ""),
                "executed": False
            }

            # Save decision to database
            result = sb.table("trading_decisions").insert(decision_record).execute()

            print(f"✅ {action} Decision Created: {symbol} @ {decision.get('entry_price'):.2f}")
            print(f"   Stop: {decision.get('stop_loss'):.2f} | Target: {decision.get('take_profit'):.2f}")
            print(f"   Confidence: {decision.get('confidence'):.0%}")

            # In paper mode, create executed trade record
            if self.paper_trade:
                trade_record = {
                    "date": str(decision.get("date")),
                    "time": decision.get("time"),
                    "symbol": symbol,
                    "side": action,
                    "entry_price": float(decision.get("entry_price", 0)),
                    "quantity": 100,  # Default quantity
                    "stop_loss": float(decision.get("stop_loss", 0)),
                    "take_profit": float(decision.get("take_profit", 0)),
                    "status": "OPEN",
                    "agent_decision_id": result.data[0]["id"] if result.data else None
                }

                sb.table("executed_trades").insert(trade_record).execute()
                print(f"   📝 Trade logged to executed_trades")

            return {
                "status": "executed",
                "symbol": symbol,
                "decision_id": result.data[0]["id"] if result.data else None
            }

        except Exception as e:
            print(f"❌ Error executing decision: {str(e)[:60]}")
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)[:60]
            }

    def run_daily_trading_cycle(self):
        """
        Run complete daily trading cycle:
        1. Load/update daily routine
        2. Check each symbol in routine
        3. Generate trading decisions
        4. Execute trades
        5. Log for training data
        """
        print("\n" + "="*80)
        print(f"📊 STAR TRADING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        symbols_to_trade = self.daily_routine.get("high_probability_symbols", [])
        decisions_made = 0
        trades_executed = 0

        print(f"\n🎯 Trading {len(symbols_to_trade)} symbols from daily routine\n")

        for symbol in symbols_to_trade:
            result = self.process_symbol(symbol)

            if result.get("action") in ["BUY", "SELL"]:
                decisions_made += 1
                execution = self.execute_decision(result)

                if execution.get("status") == "executed":
                    trades_executed += 1

        print("\n" + "="*80)
        print(f"📈 CYCLE SUMMARY")
        print(f"   Symbols analyzed: {len(symbols_to_trade)}")
        print(f"   Decisions made: {decisions_made}")
        print(f"   Trades executed: {trades_executed}")
        print(f"   Mode: {self.mode}")
        print("="*80 + "\n")

        return {
            "symbols_analyzed": len(symbols_to_trade),
            "decisions_made": decisions_made,
            "trades_executed": trades_executed
        }


def main():
    """Run Star Trading system"""
    trader = SmartTrader(paper_trade=True)

    # Run daily cycle
    while True:
        try:
            trader.run_daily_trading_cycle()
            time.sleep(300)  # Run every 5 minutes

        except KeyboardInterrupt:
            print("\n🛑 Smart Trader stopped")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            time.sleep(60)


if __name__ == "__main__":
    main()
