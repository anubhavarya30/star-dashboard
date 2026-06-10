#!/usr/bin/env python3
"""
STAR Automated Trading System
Fully automated execution with NO manual intervention
Runs on schedule, fetches REAL market data, executes trades, collects training data
"""
import os
import time
import schedule
from datetime import datetime, date, time as dtime
import pytz
from dotenv import load_dotenv
from supabase import create_client

from market_data_provider import RealMarketDataProvider
from agent_aggregator import AgentAggregator
from daily_routine_planner import DailyRoutinePlanner
from live_trading_engine import LiveTradingEngine  # IBKR LIVE TRADING
from trading_signals import VolumeWeightedRSISystem
from indicators import Indicators
import json
import pandas as pd

load_dotenv()

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class AutomatedSTARSystem:
    """
    Complete automated trading system
    Runs on schedule with REAL market data
    LIVE TRADING via IBKR (not paper trading)
    """

    def __init__(self):
        self.data_provider = RealMarketDataProvider()
        self.aggregator = AgentAggregator()
        self.planner = DailyRoutinePlanner()
        self.trader = LiveTradingEngine()  # REAL IBKR TRADING
        self.trading_system = VolumeWeightedRSISystem()

        # Market hours (NYSE)
        self.ny_tz = pytz.timezone('America/New_York')
        self.market_open = dtime(9, 30)
        self.market_close = dtime(16, 0)

        print("="*80)
        print("🤖 STAR AUTOMATED TRADING SYSTEM INITIALIZED")
        print("="*80)
        print("\nSchedule:")
        print("  9:15 AM ET  → Collect agent signals (ALL agents run)")
        print("  9:20 AM ET  → Generate daily routine")
        print("  9:30 AM ET  → Market open (start trading)")
        print("  Every 5 min → Execute trades with REAL market data")
        print("  4:00 PM ET  → Market close (stop trading)")
        print("  4:15 PM ET  → Collect results & update metrics")
        print("="*80 + "\n")

    def is_market_open(self) -> bool:
        """Check if NYSE is currently open"""
        now = datetime.now(self.ny_tz)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

        # Market closed on weekends
        if now.weekday() >= 5:
            return False

        return market_open <= now <= market_close

    def collect_agent_signals_automated(self):
        """AUTOMATED: Collect all agent signals with REAL data"""
        print("\n" + "="*80)
        print(f"📊 AUTOMATED SIGNAL COLLECTION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        try:
            signals = self.aggregator.collect_agent_signals()
            self.aggregator.print_summary(signals)
            self.aggregator.save_agent_consensus(signals)

            print("✅ Agent signals collected and saved")
            return signals

        except Exception as e:
            print(f"❌ Error collecting signals: {str(e)[:60]}")
            return {}

    def generate_daily_routine_automated(self):
        """AUTOMATED: Generate daily trading routine"""
        print("\n" + "="*80)
        print(f"📅 AUTOMATED ROUTINE GENERATION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        try:
            routine = self.planner.create_daily_plan()
            self.planner.print_routine(routine)
            self.planner.save_routine(routine)

            print("✅ Daily routine generated and saved")
            return routine

        except Exception as e:
            print(f"❌ Error generating routine: {str(e)[:60]}")
            return {}

    def execute_trading_cycle_automated(self):
        """AUTOMATED: Execute one trading cycle with REAL data"""
        if not self.is_market_open():
            print(f"⏰ Market closed - {datetime.now(self.ny_tz).strftime('%H:%M:%S ET')}")
            return

        try:
            # Reload routine
            self.trader.daily_routine = self.trader._load_daily_routine()

            print("\n" + "="*80)
            print(f"🚀 AUTOMATED TRADING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80)

            # Get high-probability symbols
            symbols = self.trader.daily_routine.get("high_probability_symbols", [])

            if not symbols:
                print("⚠️  No high-probability symbols for this cycle")
                return

            print(f"\n📊 Processing {len(symbols)} symbols with REAL market data:\n")

            trades_executed = 0

            for symbol in symbols:
                # Fetch REAL market data
                ohlcv = self.data_provider.get_ohlcv_dict(symbol, period="5d", interval="1h")

                if ohlcv is None:
                    print(f"⚠️  {symbol}: Could not fetch REAL data")
                    continue

                current_price = ohlcv['last_price']
                print(f"\n{symbol}: ${current_price:.2f} (REAL market price)")

                # Generate signal from REAL data
                signal_data = {
                    'open': ohlcv['open'],
                    'high': ohlcv['high'],
                    'low': ohlcv['low'],
                    'close': ohlcv['close'],
                    'volume': ohlcv['volume']
                }

                technical_signal = self.trading_system.generate_signal(signal_data)

                # Check if should trade
                daily_targets = self.trader.daily_routine.get("daily_targets", {}).get(symbol, {})
                expected_action = daily_targets.get("action", "HOLD")

                if technical_signal.get('action') == expected_action and expected_action != "HOLD":
                    # Create trading decision
                    decision = {
                        "symbol": symbol,
                        "date": date.today(),
                        "time": datetime.now().time().isoformat(),
                        "action": technical_signal.get('action'),
                        "entry_price": current_price,
                        "stop_loss": technical_signal.get("stop_loss"),
                        "take_profit": technical_signal.get("take_profit"),
                        "confidence": technical_signal.get("confidence", 0),
                        "reason": technical_signal.get("reason", ""),
                        "real_market_data": True,
                        "data_timestamp": ohlcv['last_update']
                    }

                    # Execute
                    result = self.trader.execute_decision(decision)
                    if result.get("status") == "executed":
                        trades_executed += 1

            print("\n" + "="*80)
            print(f"✅ CYCLE COMPLETE - {trades_executed} trades executed")
            print("="*80 + "\n")

        except Exception as e:
            print(f"❌ Error in trading cycle: {str(e)[:60]}")

    def backtest_all_symbols_automated(self):
        """AUTOMATED: Backtest strategy on REAL historical data"""
        print("\n" + "="*80)
        print("🔬 AUTOMATED BACKTESTING (REAL HISTORICAL DATA)")
        print("="*80 + "\n")

        symbols_to_test = ["GC=F", "AAPL", "NVDA", "TSLA", "SPY"]
        all_results = []

        for symbol in symbols_to_test:
            print(f"\n📈 Backtesting {symbol} with REAL historical data (1 year)...")

            # Fetch REAL historical data
            hist_data = self.data_provider.fetch_historical_data(
                symbol,
                start_date="2023-06-01",
                end_date="2024-06-01"
            )

            if hist_data is None or len(hist_data) < 100:
                print(f"   ⚠️  Insufficient historical data for {symbol}")
                continue

            # Backtest
            trades = []
            in_trade = False
            entry_price = 0

            for i in range(200, len(hist_data)):  # Need 200 candles for indicators
                window_data = {
                    'open': hist_data['Open'].iloc[:i+1].values,
                    'high': hist_data['High'].iloc[:i+1].values,
                    'low': hist_data['Low'].iloc[:i+1].values,
                    'close': hist_data['Close'].iloc[:i+1].values,
                    'volume': hist_data['Volume'].iloc[:i+1].values if 'Volume' in hist_data.columns else [1] * (i+1)
                }

                signal = self.trading_system.generate_signal(window_data)

                if signal['action'] == 'BUY' and not in_trade:
                    in_trade = True
                    entry_price = hist_data['Close'].iloc[i]

                elif signal['action'] == 'SELL' and in_trade:
                    in_trade = False
                    exit_price = hist_data['Close'].iloc[i]
                    pnl_pct = ((exit_price - entry_price) / entry_price * 100)
                    trades.append({'pnl_pct': pnl_pct})

            # Calculate stats
            if trades:
                wins = len([t for t in trades if t['pnl_pct'] > 0])
                win_rate = (wins / len(trades) * 100) if trades else 0
                avg_pnl = sum([t['pnl_pct'] for t in trades]) / len(trades)
                total_pnl = sum([t['pnl_pct'] for t in trades])

                result = {
                    "symbol": symbol,
                    "total_trades": len(trades),
                    "winning_trades": wins,
                    "win_rate_pct": win_rate,
                    "avg_pnl_pct": avg_pnl,
                    "total_pnl_pct": total_pnl,
                    "backtest_period": "2023-06-01 to 2024-06-01",
                    "data_type": "REAL_HISTORICAL"
                }

                all_results.append(result)

                print(f"   ✅ Total Trades: {len(trades)}")
                print(f"   📈 Win Rate: {win_rate:.1f}%")
                print(f"   💰 Total P&L: {total_pnl:.2f}%")
                print(f"   📊 Avg P&L: {avg_pnl:.2f}%")

        # Summary
        if all_results:
            print("\n" + "="*80)
            print("📊 BACKTEST RESULTS SUMMARY (REAL DATA)")
            print("="*80)

            avg_win_rate = sum([r['win_rate_pct'] for r in all_results]) / len(all_results)
            total_trades = sum([r['total_trades'] for r in all_results])

            print(f"\nStrategy: Volume-Weighted RSI (From Research)")
            print(f"Data Period: 2023-06-01 to 2024-06-01")
            print(f"Data Type: REAL HISTORICAL (from Yahoo Finance)")
            print(f"\nResults:")
            print(f"  Average Win Rate: {avg_win_rate:.1f}%")
            print(f"  Total Trades: {total_trades}")
            print(f"  Symbols Tested: {len(all_results)}")

            for result in all_results:
                print(f"\n  {result['symbol']}: {result['win_rate_pct']:.1f}% ({result['total_trades']} trades)")

        print("\n" + "="*80 + "\n")

        return all_results

    def collect_end_of_day_data(self):
        """AUTOMATED: Collect EOD data and prepare training data"""
        print("\n" + "="*80)
        print(f"📊 END OF DAY DATA COLLECTION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        try:
            # Fetch today's trades
            today = date.today()
            result = sb.table("executed_trades").select("*").eq("date", str(today)).execute()

            trades = result.data if result.data else []

            if trades:
                print(f"\n✅ Collected {len(trades)} trades from today")

                for trade in trades:
                    # Calculate final P&L
                    pnl_pct = ((trade.get('exit_price', 0) - trade.get('entry_price', 0)) /
                              trade.get('entry_price', 1) * 100)

                    # Update trade
                    sb.table("executed_trades").update({
                        "pnl_pct": pnl_pct,
                        "status": "CLOSED"
                    }).eq("id", trade["id"]).execute()

                print("✅ EOD data collected and saved")
            else:
                print("ℹ️  No trades today")

        except Exception as e:
            print(f"❌ Error collecting EOD data: {str(e)[:60]}")

    def schedule_all_tasks(self):
        """Schedule all automated tasks"""
        # Morning routine
        schedule.every().monday.at("09:15").do(self.collect_agent_signals_automated)
        schedule.every().tuesday.at("09:15").do(self.collect_agent_signals_automated)
        schedule.every().wednesday.at("09:15").do(self.collect_agent_signals_automated)
        schedule.every().thursday.at("09:15").do(self.collect_agent_signals_automated)
        schedule.every().friday.at("09:15").do(self.collect_agent_signals_automated)

        schedule.every().monday.at("09:20").do(self.generate_daily_routine_automated)
        schedule.every().tuesday.at("09:20").do(self.generate_daily_routine_automated)
        schedule.every().wednesday.at("09:20").do(self.generate_daily_routine_automated)
        schedule.every().thursday.at("09:20").do(self.generate_daily_routine_automated)
        schedule.every().friday.at("09:20").do(self.generate_daily_routine_automated)

        # Trading cycle (every 5 minutes during market hours)
        schedule.every(5).minutes.do(self.execute_trading_cycle_automated)

        # End of day
        schedule.every().monday.at("16:15").do(self.collect_end_of_day_data)
        schedule.every().tuesday.at("16:15").do(self.collect_end_of_day_data)
        schedule.every().wednesday.at("16:15").do(self.collect_end_of_day_data)
        schedule.every().thursday.at("16:15").do(self.collect_end_of_day_data)
        schedule.every().friday.at("16:15").do(self.collect_end_of_day_data)

        # Weekly backtest
        schedule.every().sunday.at("18:00").do(self.backtest_all_symbols_automated)

    def run(self):
        """Run the automated system"""
        self.schedule_all_tasks()

        print("\n🚀 STAR AUTOMATED SYSTEM RUNNING")
        print("All tasks scheduled. System will run continuously...\n")

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check schedule every minute

        except KeyboardInterrupt:
            print("\n\n🛑 STAR System stopped by user")


def main():
    """Start automated STAR trading system"""
    system = AutomatedSTARSystem()

    # Run initial backtest
    print("\n🔬 Running initial backtesting on REAL historical data...\n")
    system.backtest_all_symbols_automated()

    # Start automated scheduler
    system.run()


if __name__ == "__main__":
    main()
