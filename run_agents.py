#!/usr/bin/env python3
"""
Run all trading agents and Star's aggregation.
Agents publish findings to Supabase, Star makes final decisions.
"""
from agents import (
    MarketResearchAgent,
    IPOEarningsAgent,
    SocialSentimentAgent,
    TradeProtectionAgent,
    StarCEO
)
import time

def main():
    print("=" * 80)
    print("🚀 STAR TRADING SYSTEM — AGENT EXECUTION")
    print("=" * 80)

    # Initialize all agents
    agents = [
        MarketResearchAgent(),
        IPOEarningsAgent(),
        SocialSentimentAgent(),
        TradeProtectionAgent()
    ]

    star = StarCEO()

    # Run all agents
    print("\n📋 RUNNING AGENTS...\n")
    for agent in agents:
        print(f"\n▶️  Running {agent.name}...")
        agent.run()
        time.sleep(1)

    # Star aggregates decisions
    print("\n" + "=" * 80)
    print("⭐ STAR MAKING FINAL DECISION...")
    print("=" * 80)
    star.aggregate_decisions()

    # Show pending approvals
    print("\n" + "=" * 80)
    print("📋 PENDING USER APPROVALS")
    print("=" * 80)
    pending = star.get_pending_approvals()
    if pending:
        print(f"\n🔔 {len(pending)} decisions awaiting your approval!")
        print("\nGo to http://localhost:8501 → '🎯 Star's Decisions' to approve/reject\n")
    else:
        print("\n✅ No pending decisions.\n")

    print("=" * 80)

if __name__ == "__main__":
    main()
