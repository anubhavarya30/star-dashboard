"""
Agent framework for multi-agent trading system.
Each agent reports findings to Supabase, Star (CEO) aggregates decisions.
"""
from abc import ABC, abstractmethod
from supabase import create_client
from dotenv import load_dotenv
import os
from datetime import datetime
import json

load_dotenv()

class Agent(ABC):
    """Base agent class for all trading agents."""

    def __init__(self, name: str):
        self.name = name
        self.sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        self.status = "idle"
        self.init_agent_state()

    def init_agent_state(self):
        """Initialize agent in agent_states table."""
        self.sb.table("agent_states").upsert({
            "agent_name": self.name,
            "status": "idle",
            "last_updated": datetime.utcnow().isoformat()
        }).execute()

    def set_status(self, status: str, signal: str = ""):
        """Update agent status."""
        self.sb.table("agent_states").update({
            "status": status,
            "last_signal": signal,
            "last_updated": datetime.utcnow().isoformat()
        }).eq("agent_name", self.name).execute()

    def submit_report(self, report_type: str, findings: dict, symbols: list = None, confidence: float = 0.0):
        """Submit a detailed report."""
        self.sb.table("agent_reports").insert({
            "agent_name": self.name,
            "report_type": report_type,
            "symbols": symbols or [],
            "findings": findings,
            "confidence": confidence,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        print(f"✅ {self.name} submitted report: {report_type}")

    def submit_signal(self, symbol: str, signal: str, confidence: float = 0.0, reason: str = ""):
        """Submit a buy/sell/hold signal for a symbol."""
        self.sb.table("agent_signals").insert({
            "agent_name": self.name,
            "symbol": symbol,
            "signal": signal,
            "confidence": confidence,
            "reason": reason,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        print(f"✅ {self.name} signal: {signal} {symbol} (confidence: {confidence})")

    def log_action(self, action: str, details: dict = None, status: str = "success", error: str = ""):
        """Log agent action for audit trail."""
        self.sb.table("agent_logs").insert({
            "agent_name": self.name,
            "action": action,
            "details": details or {},
            "status": status,
            "error_msg": error,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

    @abstractmethod
    def run(self):
        """Execute agent logic. Override in subclasses."""
        pass


class MarketResearchAgent(Agent):
    """Agent 1: Market research and technical analysis."""

    def __init__(self):
        super().__init__("MarketResearchAgent")

    def run(self):
        """Analyze market conditions with real data."""
        from data_providers import MarketDataProvider

        self.set_status("running", "Analyzing market conditions...")
        try:
            # Get trending symbols
            trending = MarketDataProvider.get_trending_symbols()

            findings = {
                "trending_symbols": [s["symbol"] for s in trending],
                "analysis": trending,
                "timestamp": datetime.utcnow().isoformat()
            }

            symbols_list = [s["symbol"] for s in trending]

            self.submit_report(
                report_type="market_analysis",
                findings=findings,
                symbols=symbols_list,
                confidence=0.85
            )

            # Submit signals based on RSI and MACD
            for analysis in trending:
                symbol = analysis["symbol"]
                rsi = analysis.get("rsi", 50)
                macd = analysis.get("macd", {}).get("histogram", 0)

                if rsi < 30 and macd > 0:
                    signal = "BUY"
                    confidence = 0.85
                    reason = f"RSI oversold ({rsi:.1f}) + positive MACD histogram"
                elif rsi > 70 and macd < 0:
                    signal = "SELL"
                    confidence = 0.80
                    reason = f"RSI overbought ({rsi:.1f}) + negative MACD histogram"
                else:
                    signal = "HOLD"
                    confidence = 0.60
                    reason = f"RSI at {rsi:.1f} - consolidating"

                self.submit_signal(symbol, signal, confidence=confidence, reason=reason)

            self.set_status("idle", "Market analysis complete")
            self.log_action("market_analysis", {"symbols": symbols_list}, "success")
        except Exception as e:
            self.set_status("error", str(e))
            self.log_action("market_analysis", {}, "error", str(e))


class IPOEarningsAgent(Agent):
    """Agent 2: IPO and earnings call monitoring."""

    def __init__(self):
        super().__init__("IPOEarningsAgent")

    def run(self):
        """Monitor IPOs and earnings with real calendar data."""
        from data_providers import EarningsProvider

        self.set_status("running", "Checking earnings calendar...")
        try:
            earnings = EarningsProvider.get_upcoming_earnings(days_ahead=30)
            ipos = EarningsProvider.get_upcoming_ipos(days_ahead=90)

            findings = {
                "upcoming_earnings": earnings,
                "upcoming_ipos": ipos,
                "high_impact_events": [e for e in earnings if e.get("impact") in ["high", "very_high"]]
            }

            self.submit_report(
                report_type="earnings_calendar",
                findings=findings,
                confidence=0.90
            )

            # Submit signals for high-impact earnings
            for earning in findings["high_impact_events"]:
                symbol = earning["symbol"]
                impact = earning.get("impact", "high")

                if impact == "very_high":
                    signal = "HOLD"
                    confidence = 0.85
                    reason = f"CRITICAL EARNINGS: {earning['company']} on {earning['date'][:10]} - extreme volatility expected"
                else:
                    signal = "HOLD"
                    confidence = 0.75
                    reason = f"Earnings announcement: {earning['company']} - high volatility risk"

                self.submit_signal(symbol, signal, confidence=confidence, reason=reason)

            self.set_status("idle", "Earnings check complete")
            self.log_action("earnings_check", {"events": len(earnings) + len(ipos)}, "success")
        except Exception as e:
            self.set_status("error", str(e))
            self.log_action("earnings_check", {}, "error", str(e))


class SocialSentimentAgent(Agent):
    """Agent 3: Social sentiment and distress signal monitoring."""

    def __init__(self):
        super().__init__("SocialSentimentAgent")

    def run(self):
        """Monitor social channels for sentiment with real Reddit data."""
        from data_providers import SentimentProvider

        self.set_status("running", "Scanning Reddit, Discord...")
        try:
            # Monitor watchlist symbols
            symbols = ["NVDA", "AAPL", "TSLA", "GOOGL", "META"]
            sentiment_results = {}

            for symbol in symbols:
                sentiment = SentimentProvider.get_social_sentiment(symbol)
                sentiment_results[symbol] = sentiment

            findings = {
                "social_sentiment": sentiment_results,
                "symbols_monitored": symbols,
                "timestamp": datetime.utcnow().isoformat()
            }

            self.submit_report(
                report_type="social_sentiment",
                findings=findings,
                symbols=symbols,
                confidence=0.65
            )

            # Submit signals based on sentiment
            for symbol, sentiment in sentiment_results.items():
                reddit_sentiment = sentiment.get("reddit", {}).get("sentiment", "neutral")
                mentions = sentiment.get("reddit", {}).get("mentions", 0)

                if reddit_sentiment == "bullish" and mentions > 5:
                    signal = "BUY"
                    confidence = 0.70
                    reason = f"Strong bullish sentiment on Reddit ({mentions} mentions)"
                elif reddit_sentiment == "bearish" and mentions > 5:
                    signal = "SELL"
                    confidence = 0.65
                    reason = f"Bearish sentiment on Reddit ({mentions} mentions)"
                else:
                    signal = "HOLD"
                    confidence = 0.55
                    reason = f"Neutral social sentiment ({mentions} mentions)"

                self.submit_signal(symbol, signal, confidence=confidence, reason=reason)

            self.set_status("idle", "Sentiment analysis complete")
            self.log_action("sentiment_check", {"symbols": symbols}, "success")
        except Exception as e:
            self.set_status("error", str(e))
            self.log_action("sentiment_check", {}, "error", str(e))


class TradeProtectionAgent(Agent):
    """Agent 4: Active trade monitoring and protection."""

    def __init__(self):
        super().__init__("TradeProtectionAgent")

    def run(self):
        """Monitor active positions for risk with real price updates."""
        from data_providers import PositionProvider, MarketDataProvider

        self.set_status("running", "Monitoring open positions...")
        try:
            # Get position analysis
            position_provider = PositionProvider(self.sb)
            analysis = position_provider.analyze_positions()

            findings = {
                "total_positions": analysis["total_positions"],
                "at_risk": analysis["at_risk"],
                "healthy": analysis["healthy"],
                "total_pnl": analysis["total_pnl"],
                "total_pnl_pct": analysis["total_pnl_pct"]
            }

            self.submit_report(
                report_type="trade_protection",
                findings=findings,
                confidence=0.95
            )

            # Submit protection signals
            for at_risk_pos in analysis["at_risk"]:
                symbol = at_risk_pos["symbol"]
                pnl_pct = at_risk_pos["pnl_pct"]
                risk_level = at_risk_pos["risk_level"]

                if risk_level == "critical":
                    signal = "SELL"
                    confidence = 0.95
                    reason = f"CRITICAL: Position down {pnl_pct:.2f}% - immediate exit recommended"
                else:
                    signal = "SELL"
                    confidence = 0.85
                    reason = f"Position down {pnl_pct:.2f}% ({risk_level} risk) - consider exit"

                self.submit_signal(symbol, signal, confidence=confidence, reason=reason)

            self.set_status("idle", "Trade protection check complete")
            self.log_action("trade_protection", {
                "monitored": analysis["total_positions"],
                "at_risk": len(analysis["at_risk"])
            }, "success")
        except Exception as e:
            self.set_status("error", str(e))
            self.log_action("trade_protection", {}, "error", str(e))


class StarCEO:
    """Star CEO: Aggregates all agent reports and makes final decision."""

    def __init__(self):
        self.name = "Star"
        self.sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    def aggregate_decisions(self):
        """Aggregate all agent signals into final decisions."""
        print("\n⭐ STAR (CEO) AGGREGATING DECISIONS...\n")

        # Get all recent signals
        signals = self.sb.table("agent_signals").select("*").order("created_at", desc=True).limit(100).execute()

        # Group by symbol
        symbol_votes = {}
        for sig in signals.data:
            sym = sig["symbol"]
            if sym not in symbol_votes:
                symbol_votes[sym] = {"BUY": 0, "SELL": 0, "HOLD": 0, "WAIT": 0, "agents": []}

            symbol_votes[sym][sig["signal"]] += 1
            symbol_votes[sym]["agents"].append({
                "agent": sig["agent_name"],
                "signal": sig["signal"],
                "confidence": sig["confidence"]
            })

        # Make decisions
        for symbol, votes in symbol_votes.items():
            total_votes = sum([votes.get("BUY", 0), votes.get("SELL", 0), votes.get("HOLD", 0)])
            if total_votes == 0:
                continue

            # Simple majority vote
            best_signal = max(["BUY", "SELL", "HOLD"], key=lambda x: votes.get(x, 0))
            confidence = votes[best_signal] / total_votes if total_votes > 0 else 0

            decision = {
                "decision_date": datetime.now().date().isoformat(),
                "symbol": symbol,
                "recommended_action": best_signal,
                "vote_tally": votes,
                "confidence": confidence,
                "status": "pending_approval",
                "created_at": datetime.utcnow().isoformat()
            }

            # Store decision
            self.sb.table("star_decision").insert(decision).execute()

            print(f"⭐ {symbol}: {best_signal} (confidence: {confidence:.0%})")
            print(f"   Votes: {votes['BUY']} BUY, {votes['SELL']} SELL, {votes['HOLD']} HOLD")
            print()

        return symbol_votes

    def get_pending_approvals(self):
        """Get decisions awaiting user approval."""
        decisions = self.sb.table("star_decision").select("*") \
            .eq("status", "pending_approval") \
            .order("created_at", desc=True).execute()
        return decisions.data

    def approve_decision(self, decision_id: str, approved: bool):
        """User approves or rejects a decision."""
        self.sb.table("star_decision").update({
            "user_approved": approved,
            "status": "approved" if approved else "rejected",
            "approved_at": datetime.utcnow().isoformat()
        }).eq("id", decision_id).execute()

        status = "✅ APPROVED" if approved else "❌ REJECTED"
        print(f"{status} decision {decision_id}")
