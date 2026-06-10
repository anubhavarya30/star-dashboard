#!/usr/bin/env python3
"""
Daily Routine Planner - Creates daily trading plan based on:
1. Agent signals and consensus
2. Market conditions
3. Historical patterns
4. Risk management rules
"""
import os
from datetime import datetime, date
from dotenv import load_dotenv
from supabase import create_client
import json
from agent_aggregator import AgentAggregator

load_dotenv()

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class DailyRoutinePlanner:
    """Plans the daily trading routine based on agent consensus"""

    def __init__(self):
        self.aggregator = AgentAggregator()

    def analyze_market_conditions(self):
        """
        Analyze current market conditions:
        - Trend (uptrend, downtrend, sideways)
        - Volatility (high, normal, low)
        - Volume profile
        - Overall sentiment
        """
        try:
            # Try to fetch today's market conditions
            today = date.today()
            result = sb.table("market_conditions").select("*").eq("date", str(today)).execute()

            if result.data:
                return result.data[0]
            else:
                # Default conditions if not available
                return {
                    "date": str(today),
                    "market_trend": "UNKNOWN",
                    "volatility": "NORMAL",
                    "volume_profile": "NORMAL",
                    "sentiment": "NEUTRAL"
                }
        except:
            return {
                "date": str(today),
                "market_trend": "UNKNOWN",
                "volatility": "NORMAL",
                "volume_profile": "NORMAL",
                "sentiment": "NEUTRAL"
            }

    def determine_market_outlook(self, aggregated_signals, market_conditions):
        """
        Determine overall market outlook based on:
        - Agent consensus
        - Market trend
        - Volatility level
        """
        buy_signals = sum(1 for _, data in aggregated_signals.items()
                         if data.get("consensus") == "BUY")
        sell_signals = sum(1 for _, data in aggregated_signals.items()
                          if data.get("consensus") == "SELL")

        if buy_signals > sell_signals:
            outlook = "BULLISH"
        elif sell_signals > buy_signals:
            outlook = "BEARISH"
        else:
            outlook = "NEUTRAL"

        market_trend = market_conditions.get("market_trend", "UNKNOWN")

        if market_trend == "uptrend":
            outlook = "BULLISH"
        elif market_trend == "downtrend":
            outlook = "BEARISH"

        return outlook

    def determine_risk_level(self, outlook, volatility):
        """
        Determine daily risk level based on:
        - Market outlook
        - Volatility
        - Agent confidence
        """
        if volatility == "HIGH":
            return "LOW"  # Lower position size in high volatility
        elif outlook == "NEUTRAL":
            return "MEDIUM"
        elif outlook == "BULLISH":
            return "MEDIUM"  # Moderate risk in bullish markets
        else:
            return "LOW"  # Conservative in bearish markets

    def create_daily_plan(self):
        """
        Create complete daily trading plan

        Returns:
            {
                'date': '2026-06-04',
                'market_outlook': 'BULLISH',
                'risk_level': 'MEDIUM',
                'high_probability_symbols': ['AAPL', 'NVDA'],
                'strategy': 'Focus on oversold reversals in strong uptrend',
                'daily_targets': {
                    'symbol': {
                        'action': 'BUY',
                        'entry_strategy': 'Wait for RSI < 30',
                        'stop_loss_pct': 2,
                        'take_profit_pct': 2
                    }
                }
            }
        """
        print("\n" + "="*80)
        print("📅 GENERATING DAILY TRADING ROUTINE")
        print("="*80)

        # Step 1: Get agent consensus
        print("\n1️⃣  Collecting agent signals...")
        aggregated = self.aggregator.collect_agent_signals()

        # Step 2: Analyze market
        print("\n2️⃣  Analyzing market conditions...")
        market_conditions = self.analyze_market_conditions()
        print(f"   Market Trend: {market_conditions.get('market_trend')}")
        print(f"   Volatility: {market_conditions.get('volatility')}")
        print(f"   Sentiment: {market_conditions.get('sentiment')}")

        # Step 3: Determine outlook
        print("\n3️⃣  Determining market outlook...")
        outlook = self.determine_market_outlook(aggregated, market_conditions)
        print(f"   📊 Today's Outlook: {outlook}")

        # Step 4: Determine risk level
        risk_level = self.determine_risk_level(
            outlook,
            market_conditions.get("volatility", "NORMAL")
        )
        print(f"   ⚠️  Daily Risk Level: {risk_level}")

        # Step 5: Identify high-probability trades
        print("\n4️⃣  Identifying high-probability opportunities...")
        high_prob = self.aggregator.get_high_confidence_signals(aggregated, min_confidence=0.70)

        high_prob_symbols = list(high_prob.keys())
        print(f"   🎯 Found {len(high_prob_symbols)} opportunities: {', '.join(high_prob_symbols)}")

        # Step 6: Create strategy statement
        strategy = self._generate_strategy(outlook, risk_level, high_prob)
        print(f"\n5️⃣  Daily Strategy: {strategy}")

        # Step 7: Create specific targets for each symbol
        daily_targets = self._create_symbol_targets(high_prob, outlook, risk_level)

        # Step 8: Build complete routine
        routine = {
            "date": str(date.today()),
            "market_outlook": outlook,
            "risk_level": risk_level,
            "high_probability_symbols": high_prob_symbols,
            "strategy": strategy,
            "daily_targets": daily_targets,
            "agent_consensus": aggregated,
            "market_conditions": market_conditions,
            "created_at": datetime.now().isoformat()
        }

        return routine

    def _generate_strategy(self, outlook, risk_level, high_prob):
        """Generate natural language strategy statement"""
        strategies = {
            ("BULLISH", "HIGH"): "Aggressive long entries on oversold levels with tight stops",
            ("BULLISH", "MEDIUM"): "Focus on oversold reversals in strong uptrend",
            ("BULLISH", "LOW"): "Conservative long positions only on major support",
            ("NEUTRAL", "HIGH"): "Avoid trading - wait for clearer direction",
            ("NEUTRAL", "MEDIUM"): "Range trading between support/resistance",
            ("NEUTRAL", "LOW"): "Only take high-confidence counter-trend trades",
            ("BEARISH", "HIGH"): "Avoid new short positions - protect existing",
            ("BEARISH", "MEDIUM"): "Short only on bounces to resistance",
            ("BEARISH", "LOW"): "Avoid trading - wait for stabilization"
        }

        key = (outlook, risk_level)
        return strategies.get(key, "Trade with caution")

    def _create_symbol_targets(self, high_prob, outlook, risk_level):
        """Create specific entry/exit targets for each symbol"""
        targets = {}

        risk_multipliers = {
            "LOW": 0.01,     # 1% risk per trade
            "MEDIUM": 0.02,  # 2% risk per trade
            "HIGH": 0.03     # 3% risk per trade (max)
        }

        risk_pct = risk_multipliers.get(risk_level, 0.02)

        for symbol, info in high_prob.items():
            signal = info["consensus"]
            confidence = info["confidence"]

            if signal == "BUY":
                targets[symbol] = {
                    "action": "BUY",
                    "entry_signal": "RSI < 30 + Volume confirm + EMA trend",
                    "entry_strategy": "Place limit order slightly below support",
                    "stop_loss_pct": risk_pct * 100,
                    "take_profit_pct": 2.0,
                    "trailing_stop_pct": 1.0,
                    "confidence": f"{confidence:.0%}",
                    "daily_target_qty": self._calculate_position_size(risk_level),
                    "max_loss_per_trade": f"${2000 * (risk_pct / 0.02):.0f}"
                }
            elif signal == "SELL":
                targets[symbol] = {
                    "action": "SELL",
                    "entry_signal": "RSI > 70 or trend break below EMA",
                    "entry_strategy": "Place limit order slightly above resistance",
                    "stop_loss_pct": risk_pct * 100 * 1.5,  # Wider stop for shorts
                    "take_profit_pct": 1.5,
                    "trailing_stop_pct": 1.0,
                    "confidence": f"{confidence:.0%}",
                    "daily_target_qty": self._calculate_position_size(risk_level),
                    "max_loss_per_trade": f"${2000 * (risk_pct / 0.02):.0f}"
                }

        return targets

    def _calculate_position_size(self, risk_level):
        """Calculate position quantity based on risk level"""
        sizes = {
            "LOW": 50,
            "MEDIUM": 100,
            "HIGH": 150
        }
        return sizes.get(risk_level, 100)

    def save_routine(self, routine):
        """Save daily routine to Supabase"""
        try:
            # Check if routine already exists for today
            today = date.today()
            existing = sb.table("daily_routine").select("*").eq("date", str(today)).execute()

            if existing.data:
                # Update existing
                sb.table("daily_routine").update({
                    "market_outlook": routine["market_outlook"],
                    "strategy": routine["strategy"],
                    "high_probability_symbols": routine["high_probability_symbols"],
                    "risk_level": routine["risk_level"],
                    "agent_consensus": routine["agent_consensus"]
                }).eq("date", str(today)).execute()

                print("✅ Daily routine updated")
            else:
                # Create new
                sb.table("daily_routine").insert({
                    "date": routine["date"],
                    "market_outlook": routine["market_outlook"],
                    "strategy": routine["strategy"],
                    "high_probability_symbols": routine["high_probability_symbols"],
                    "risk_level": routine["risk_level"],
                    "agent_consensus": routine["agent_consensus"]
                }).execute()

                print("✅ Daily routine saved")

            return True

        except Exception as e:
            print(f"⚠️  Could not save routine: {str(e)[:60]}")
            return False

    def print_routine(self, routine):
        """Pretty print the daily routine"""
        print("\n" + "="*80)
        print("📋 TODAY'S TRADING ROUTINE")
        print("="*80)

        print(f"\n📅 Date: {routine['date']}")
        print(f"📊 Market Outlook: {routine['market_outlook']}")
        print(f"⚠️  Risk Level: {routine['risk_level']}")
        print(f"🎯 Strategy: {routine['strategy']}")

        print(f"\n🎪 HIGH-PROBABILITY SYMBOLS ({len(routine['high_probability_symbols'])}):")
        for symbol in routine["high_probability_symbols"]:
            targets = routine["daily_targets"].get(symbol, {})
            print(f"\n   {symbol}")
            print(f"   ├─ Action: {targets.get('action')}")
            print(f"   ├─ Confidence: {targets.get('confidence')}")
            print(f"   ├─ Stop Loss: {targets.get('stop_loss_pct'):.2f}%")
            print(f"   ├─ Take Profit: {targets.get('take_profit_pct'):.1f}%")
            print(f"   └─ Max Loss: {targets.get('max_loss_per_trade')}")

        print("\n" + "="*80)


def main():
    """Generate and save daily routine"""
    planner = DailyRoutinePlanner()

    # Create routine
    routine = planner.create_daily_plan()

    # Print routine
    planner.print_routine(routine)

    # Save to database
    planner.save_routine(routine)


if __name__ == "__main__":
    main()
