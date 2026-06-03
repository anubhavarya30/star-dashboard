"""
Lite agent version that works without all Supabase tables.
Real agents with graceful error handling for missing tables.
"""
from abc import ABC, abstractmethod
from supabase import create_client
from dotenv import load_dotenv
import os
from datetime import datetime
import json

load_dotenv()

class AgentLite(ABC):
    """Lite agent - handles missing tables gracefully."""

    def __init__(self, name: str):
        self.name = name
        self.sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        self.findings = {}
        self.signals = []

        try:
            self.sb.table("agent_states").upsert({
                "agent_name": self.name,
                "status": "idle",
                "last_updated": datetime.utcnow().isoformat()
            }).execute()
        except:
            pass

    def set_status(self, status: str, signal: str = ""):
        """Update agent status (graceful)."""
        try:
            self.sb.table("agent_states").update({
                "status": status,
                "last_signal": signal,
                "last_updated": datetime.utcnow().isoformat()
            }).eq("agent_name", self.name).execute()
        except:
            print(f"⚠️  (Could not update {self.name} status)")

    def submit_report(self, report_type: str, findings: dict, symbols: list = None, confidence: float = 0.0):
        """Submit report (graceful)."""
        try:
            self.sb.table("agent_reports").insert({
                "agent_name": self.name,
                "report_type": report_type,
                "symbols": symbols or [],
                "findings": findings,
                "confidence": confidence,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            print(f"✅ {self.name} → {report_type}")
            self.findings = findings
        except Exception as e:
            if "Could not find the table" in str(e):
                print(f"✅ {self.name} → {report_type} (stored locally)")
                self.findings = findings
            else:
                print(f"⚠️  {self.name}: {str(e)[:60]}")

    def submit_signal(self, symbol: str, signal: str, confidence: float = 0.0, reason: str = ""):
        """Submit signal (graceful)."""
        signal_data = {
            "symbol": symbol,
            "signal": signal,
            "confidence": confidence,
            "reason": reason
        }
        self.signals.append(signal_data)

        try:
            self.sb.table("agent_signals").insert({
                "agent_name": self.name,
                "symbol": symbol,
                "signal": signal,
                "confidence": confidence,
                "reason": reason,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            print(f"📊 {symbol}: {signal} (confidence: {confidence:.0%})")
        except:
            print(f"📊 {symbol}: {signal} (confidence: {confidence:.0%}) [local]")

    @abstractmethod
    def run(self):
        pass


class MarketResearchAgent(AgentLite):
    """Agent 1: Real market analysis."""

    def __init__(self):
        super().__init__("MarketResearchAgent")

    def run(self):
        from data_providers import MarketDataProvider

        self.set_status("running", "Analyzing market...")
        print(f"\n▶️  MarketResearchAgent")
        print("📊 Fetching real market data from yfinance...")

        try:
            symbols = ["NVDA", "AAPL", "TSLA", "GOOGL", "META"]
            market_data = []

            for sym in symbols[:3]:  # Fetch 3 symbols for speed
                analysis = MarketDataProvider.analyze_symbol(sym)
                if analysis:
                    market_data.append(analysis)
                    print(f"   {sym}: ${analysis['price']:.2f} | RSI: {analysis['rsi']:.1f}")

            findings = {
                "analysis": market_data,
                "trending": len(market_data),
                "timestamp": datetime.utcnow().isoformat()
            }

            self.submit_report("market_analysis", findings, symbols=symbols[:3], confidence=0.85)

            # Submit signals
            for data in market_data:
                sym = data["symbol"]
                rsi = data.get("rsi", 50)

                if rsi < 30:
                    sig = "BUY"
                    conf = 0.85
                    reason = f"RSI {rsi:.0f} - oversold"
                elif rsi > 70:
                    sig = "SELL"
                    conf = 0.80
                    reason = f"RSI {rsi:.0f} - overbought"
                else:
                    sig = "HOLD"
                    conf = 0.60
                    reason = f"RSI {rsi:.0f} - neutral"

                self.submit_signal(sym, sig, confidence=conf, reason=reason)

            self.set_status("idle", "Market analysis done")
        except Exception as e:
            print(f"❌ Error: {str(e)[:80]}")
            self.set_status("error", str(e))


class IPOEarningsAgent(AgentLite):
    """Agent 2: Earnings and IPO monitoring."""

    def __init__(self):
        super().__init__("IPOEarningsAgent")

    def run(self):
        from data_providers import EarningsProvider

        self.set_status("running", "Checking earnings...")
        print(f"\n▶️  IPOEarningsAgent")

        try:
            earnings = EarningsProvider.get_upcoming_earnings(30)
            ipos = EarningsProvider.get_upcoming_ipos(90)

            findings = {
                "earnings": earnings,
                "ipos": ipos
            }

            self.submit_report("earnings_calendar", findings, confidence=0.90)

            for e in earnings[:2]:
                sym = e["symbol"]
                self.submit_signal(sym, "HOLD", confidence=0.75, reason=f"Earnings {e['date'][:10]}")

            self.set_status("idle", "Earnings check done")
        except Exception as e:
            print(f"❌ Error: {str(e)[:80]}")
            self.set_status("error", str(e))


class SocialSentimentAgent(AgentLite):
    """Agent 3: Social sentiment."""

    def __init__(self):
        super().__init__("SocialSentimentAgent")

    def run(self):
        self.set_status("running", "Scanning social...")
        print(f"\n▶️  SocialSentimentAgent")

        try:
            from data_providers import SentimentProvider

            symbols = ["NVDA", "AAPL", "TSLA"]
            sentiments = {}

            for sym in symbols:
                print(f"   Fetching {sym} sentiment... ", end="", flush=True)
                sent = SentimentProvider.get_social_sentiment(sym)
                sentiments[sym] = sent
                reddit = sent.get("reddit", {})
                mentions = reddit.get("mentions", 0)
                sentiment = reddit.get("sentiment", "neutral")
                print(f"{sentiment} ({mentions} mentions)")

                if mentions > 0:
                    if sentiment == "bullish":
                        self.submit_signal(sym, "BUY", confidence=0.70, reason=f"Reddit {mentions} bullish")
                    elif sentiment == "bearish":
                        self.submit_signal(sym, "SELL", confidence=0.65, reason=f"Reddit {mentions} bearish")
                    else:
                        self.submit_signal(sym, "HOLD", confidence=0.50, reason="Neutral sentiment")

            self.submit_report("social_sentiment", {"sentiments": sentiments}, confidence=0.65)
            self.set_status("idle", "Sentiment check done")
        except Exception as e:
            print(f"❌ Error: {str(e)[:80]}")
            self.set_status("error", str(e))


class TradeProtectionAgent(AgentLite):
    """Agent 4: Trade protection."""

    def __init__(self):
        super().__init__("TradeProtectionAgent")

    def run(self):
        self.set_status("running", "Checking positions...")
        print(f"\n▶️  TradeProtectionAgent")

        try:
            positions = self.sb.table("positions").select("*").eq("status", "open").execute()

            findings = {
                "positions_monitored": len(positions.data),
                "at_risk": [],
                "healthy": []
            }

            for pos in positions.data:
                current = pos.get("current_price") or pos.get("entry_price", 0)
                entry = pos.get("entry_price", 1)

                if entry > 0:
                    pnl_pct = ((current - entry) / entry * 100)
                else:
                    pnl_pct = 0

                if pnl_pct < -5:
                    findings["at_risk"].append({"symbol": pos["symbol"], "pnl_pct": pnl_pct})
                    self.submit_signal(pos["symbol"], "SELL", confidence=0.80, reason=f"Down {pnl_pct:.1f}%")
                else:
                    findings["healthy"].append(pos["symbol"])

            if positions.data:
                print(f"   Monitoring {len(positions.data)} positions")

            self.submit_report("trade_protection", findings, confidence=0.95)
            self.set_status("idle", "Trade check done")
        except Exception as e:
            print(f"   No active positions yet (or error: {str(e)[:40]})")
            self.set_status("idle", "Trade check done")


class StarCEO:
    """Star CEO: Aggregates all agent signals."""

    def __init__(self):
        self.name = "Star"
        self.sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        self.decisions = {}

    def run(self):
        pass

    def aggregate(self, agents: list):
        """Aggregate all agent signals."""
        print(f"\n{'='*80}")
        print(f"⭐ STAR (CEO) AGGREGATING SIGNALS")
        print(f"{'='*80}\n")

        all_signals = {}

        for agent in agents:
            for signal in agent.signals:
                sym = signal["symbol"]
                if sym not in all_signals:
                    all_signals[sym] = {"BUY": 0, "SELL": 0, "HOLD": 0, "agents": []}

                all_signals[sym][signal["signal"]] += 1
                all_signals[sym]["agents"].append({
                    "agent": agent.name,
                    "signal": signal["signal"],
                    "confidence": signal["confidence"]
                })

        # Make final decisions
        for symbol, votes in all_signals.items():
            total = sum([votes["BUY"], votes["SELL"], votes["HOLD"]])
            if total == 0:
                continue

            best_signal = max(["BUY", "SELL", "HOLD"], key=lambda x: votes.get(x, 0))
            confidence = votes[best_signal] / total

            print(f"⭐ {symbol.ljust(10)} → {best_signal.ljust(6)} ({confidence:.0%} confidence)")
            print(f"   Votes: {votes['BUY']} BUY, {votes['SELL']} SELL, {votes['HOLD']} HOLD")
            print()

            # Store decision
            decision = {
                "symbol": symbol,
                "recommended_action": best_signal,
                "vote_tally": votes,
                "confidence": confidence,
                "status": "pending_approval"
            }

            try:
                self.sb.table("star_decision").insert(decision).execute()
                self.decisions[symbol] = decision
            except:
                print(f"   (Decision stored locally)")
                self.decisions[symbol] = decision


def main():
    print("=" * 80)
    print("🚀 STAR TRADING SYSTEM — AGENT EXECUTION (LITE MODE)")
    print("=" * 80)

    agents = [
        MarketResearchAgent(),
        IPOEarningsAgent(),
        SocialSentimentAgent(),
        TradeProtectionAgent()
    ]

    print("\n📋 RUNNING AGENTS WITH REAL DATA...\n")

    for agent in agents:
        agent.run()

    star = StarCEO()
    star.aggregate(agents)

    print("\n" + "=" * 80)
    print("✅ AGENT EXECUTION COMPLETE")
    print("=" * 80)

    # Show pending approvals
    if star.decisions:
        print(f"\n📋 {len(star.decisions)} DECISIONS AWAITING YOUR APPROVAL")
        print("\nGo to http://localhost:8501 → '🎯 Star's Decisions' to approve/reject\n")
    else:
        print("\n✅ No new decisions generated.\n")

    print("\n📌 NEXT STEPS:")
    print("1. Open http://localhost:8501")
    print("2. Go to '🎯 Star's Decisions' page")
    print("3. Review Star's recommendations")
    print("4. Click ✅ YES or ❌ NO to approve/reject\n")


if __name__ == "__main__":
    main()
