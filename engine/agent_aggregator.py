#!/usr/bin/env python3
"""
Agent Data Aggregator - Collects signals from all trading agents
Prepares consensus data for daily routine planning
"""
import os
from datetime import datetime, date
from dotenv import load_dotenv
from supabase import create_client
import json

load_dotenv()

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class AgentAggregator:
    """Collects and aggregates signals from all agents"""

    def __init__(self):
        self.symbols = ["GC=F", "AAPL", "NVDA", "TSLA", "SPY"]
        self.agents = [
            "MarketResearchAgent",
            "IPOEarningsAgent",
            "SocialSentimentAgent",
            "TradeProtectionAgent",
            "SmartTradingEngine"
        ]

    def collect_agent_signals(self, symbols=None, days=1):
        """
        Collect all agent signals for the day

        Returns:
            {
                'symbol': {
                    'date': '2026-06-04',
                    'signals': [
                        {'agent': 'Agent1', 'signal': 'BUY', 'confidence': 0.85},
                        ...
                    ],
                    'consensus': 'BUY',
                    'buy_votes': 2,
                    'sell_votes': 1,
                    'hold_votes': 1,
                    'avg_confidence': 0.80
                }
            }
        """
        if symbols is None:
            symbols = self.symbols

        today = date.today()
        aggregated = {}

        print(f"\n📊 COLLECTING AGENT SIGNALS FOR {today}")
        print("="*80)

        for symbol in symbols:
            try:
                # Fetch all signals for this symbol from all agents
                result = sb.table("agent_signals").select("*").eq("symbol", symbol).gte(
                    "created_at",
                    f"{today}T00:00:00"
                ).execute()

                signals = result.data if result.data else []

                if signals:
                    # Group by agent
                    signal_list = []
                    for sig in signals:
                        signal_list.append({
                            "agent": sig.get("agent_name", "Unknown"),
                            "signal": sig.get("signal", "HOLD"),
                            "confidence": float(sig.get("confidence", 50)) / 100,
                            "reason": sig.get("reason", ""),
                            "timestamp": sig.get("created_at", "")
                        })

                    # Calculate consensus
                    buy_votes = len([s for s in signal_list if s["signal"] == "BUY"])
                    sell_votes = len([s for s in signal_list if s["signal"] == "SELL"])
                    hold_votes = len([s for s in signal_list if s["signal"] == "HOLD"])

                    total_signals = len(signal_list)
                    consensus = "BUY" if buy_votes > sell_votes else \
                               "SELL" if sell_votes > buy_votes else "HOLD"

                    avg_confidence = sum([s["confidence"] for s in signal_list]) / total_signals

                    aggregated[symbol] = {
                        "date": str(today),
                        "signals": signal_list,
                        "consensus": consensus,
                        "buy_votes": buy_votes,
                        "sell_votes": sell_votes,
                        "hold_votes": hold_votes,
                        "total_votes": total_signals,
                        "avg_confidence": avg_confidence,
                        "confidence_pct": int(avg_confidence * 100)
                    }

                    print(f"\n✅ {symbol}")
                    print(f"   📊 Total Signals: {total_signals}")
                    print(f"   🟢 BUY: {buy_votes} | 🔴 SELL: {sell_votes} | 🟡 HOLD: {hold_votes}")
                    print(f"   🎯 CONSENSUS: {consensus} ({avg_confidence:.0%} confidence)")
                    print(f"   📝 Agents: {', '.join([s['agent'] for s in signal_list])}")

                else:
                    aggregated[symbol] = {
                        "date": str(today),
                        "signals": [],
                        "consensus": "NO_DATA",
                        "message": "No signals collected yet"
                    }
                    print(f"\n⚠️  {symbol}: No signals collected")

            except Exception as e:
                print(f"\n❌ {symbol}: Error - {str(e)[:60]}")
                aggregated[symbol] = {"error": str(e)}

        print("\n" + "="*80)
        return aggregated

    def save_agent_consensus(self, aggregated_data):
        """Save aggregated data to Supabase for reference"""
        try:
            today = date.today()

            # Save consensus data
            sb.table("agent_signals").insert({
                "date": today,
                "agent_name": "AgentConsensus",
                "symbol": "PORTFOLIO",
                "signal": "CONSENSUS",
                "confidence": 85,
                "reason": json.dumps(aggregated_data),
                "data": aggregated_data
            }).execute()

            print("✅ Agent consensus saved to Supabase")
            return True

        except Exception as e:
            print(f"⚠️  Could not save consensus: {str(e)[:60]}")
            return False

    def get_high_confidence_signals(self, aggregated_data, min_confidence=0.75, min_votes=2):
        """
        Get only high-confidence signals with multiple agent agreement

        Returns high-probability trading opportunities
        """
        high_confidence = {}

        for symbol, data in aggregated_data.items():
            if data.get("consensus") != "NO_DATA":
                confidence = data.get("avg_confidence", 0)
                votes = data.get("total_votes", 0)
                consensus = data.get("consensus", "HOLD")

                if confidence >= min_confidence and votes >= min_votes and consensus != "HOLD":
                    high_confidence[symbol] = {
                        "consensus": consensus,
                        "confidence": confidence,
                        "votes": votes,
                        "reason": data.get("signals", [])
                    }

        return high_confidence

    def print_summary(self, aggregated_data):
        """Print trading opportunity summary"""
        print("\n" + "="*80)
        print("📈 TRADING OPPORTUNITIES SUMMARY")
        print("="*80 + "\n")

        buy_opportunities = []
        sell_opportunities = []

        for symbol, data in aggregated_data.items():
            consensus = data.get("consensus")
            confidence = data.get("avg_confidence", 0)

            if consensus == "BUY":
                buy_opportunities.append((symbol, confidence, data.get("total_votes", 0)))
            elif consensus == "SELL":
                sell_opportunities.append((symbol, confidence, data.get("total_votes", 0)))

        if buy_opportunities:
            print("🟢 BUY OPPORTUNITIES:")
            for symbol, conf, votes in sorted(buy_opportunities, key=lambda x: x[1], reverse=True):
                print(f"   {symbol}: {conf:.0%} confidence ({votes} agent votes)")

        if sell_opportunities:
            print("\n🔴 SELL OPPORTUNITIES:")
            for symbol, conf, votes in sorted(sell_opportunities, key=lambda x: x[1], reverse=True):
                print(f"   {symbol}: {conf:.0%} confidence ({votes} agent votes)")

        if not buy_opportunities and not sell_opportunities:
            print("⚠️  No strong consensus opportunities found")

        print("\n" + "="*80)


def main():
    """Run agent aggregator"""
    aggregator = AgentAggregator()

    # Collect all agent signals
    aggregated = aggregator.collect_agent_signals()

    # Show summary
    aggregator.print_summary(aggregated)

    # Save consensus
    aggregator.save_agent_consensus(aggregated)

    # Get high-confidence signals only
    high_conf = aggregator.get_high_confidence_signals(aggregated, min_confidence=0.70, min_votes=2)

    if high_conf:
        print("\n⭐ HIGH-CONFIDENCE TRADING SIGNALS (70%+ confidence, 2+ agent agreement):")
        for symbol, info in high_conf.items():
            print(f"   {symbol}: {info['consensus']} ({info['confidence']:.0%})")


if __name__ == "__main__":
    main()
