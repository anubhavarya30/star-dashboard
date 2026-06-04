#!/usr/bin/env python3
"""
Smart Trading Engine - Production Grade
Volume-Weighted RSI System with Risk Management
Paper Trade Mode: All trades logged to Supabase without execution
"""
import os
import time
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
import yfinance as yf
import pandas as pd

from trading_signals import VolumeWeightedRSISystem
from position_manager import PositionManager

load_dotenv()

class SmartTradingEngine:
    """Production trading engine with paper trading mode"""

    def __init__(self, paper_trade: bool = True):
        self.paper_trade = paper_trade
        self.trading_system = VolumeWeightedRSISystem()
        self.position_manager = PositionManager(
            account_balance=100000.0,  # $100k account
            risk_per_trade=0.02  # 2% per trade
        )

        self.sb = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )

        self.mode = "PAPER TRADE" if paper_trade else "LIVE"
        print(f"🤖 Smart Trading Engine Started - Mode: {self.mode}")

    def process_symbol(self, symbol: str) -> dict:
        """
        Process one symbol and generate trading signal

        Returns:
            {
                'symbol': str,
                'action': 'BUY' | 'SELL' | 'HOLD',
                'confidence': float,
                'entry_price': float,
                'stop_loss': float,
                'take_profit': float
            }
        """
        try:
            # Fetch OHLCV data
            data = yf.download(symbol, period="5d", interval="1h", progress=False)

            if data.empty:
                return {"symbol": symbol, "action": "HOLD", "reason": "No data"}

            # Flatten columns if MultiIndex
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            ohlcv = {
                'open': data['Open'].values,
                'high': data['High'].values,
                'low': data['Low'].values,
                'close': data['Close'].values,
                'volume': data['Volume'].values if 'Volume' in data.columns else [1] * len(data)
            }

            # Generate signal
            signal = self.trading_system.generate_signal(ohlcv)
            signal['symbol'] = symbol
            signal['timestamp'] = datetime.utcnow().isoformat()

            return signal

        except Exception as e:
            return {
                "symbol": symbol,
                "action": "HOLD",
                "error": str(e)
            }

    def log_trade(self, signal: dict):
        """Log trade to Supabase (paper or live)"""
        try:
            if signal['action'] == 'BUY':
                # Log as potential position
                self.sb.table("agent_signals").insert({
                    "agent_name": "SmartTradingEngine",
                    "symbol": signal['symbol'],
                    "signal": "BUY",
                    "confidence": signal.get('confidence', 0),
                    "reason": signal.get('reason', ''),
                    "created_at": datetime.utcnow().isoformat()
                }).execute()

                print(f"✅ SIGNAL: {signal['symbol']} BUY @ {signal['entry_price']:.2f} "
                      f"(Conf: {signal['confidence']:.0%} | SL: {signal['stop_loss']:.2f})")

            elif signal['action'] == 'SELL':
                self.sb.table("agent_signals").insert({
                    "agent_name": "SmartTradingEngine",
                    "symbol": signal['symbol'],
                    "signal": "SELL",
                    "confidence": signal.get('confidence', 0),
                    "reason": signal.get('reason', ''),
                    "created_at": datetime.utcnow().isoformat()
                }).execute()

                print(f"🔴 EXIT: {signal['symbol']} SELL - {signal.get('reason', '')}")

        except Exception as e:
            print(f"⚠️ Error logging signal: {str(e)[:60]}")

    def run_trading_cycle(self, symbols: list = None):
        """
        Run one complete trading cycle

        Args:
            symbols: List of symbols to analyze. Default: XAUUSD, AAPL, NVDA, TSLA, SPY
        """
        if symbols is None:
            symbols = ["XAUUSD", "AAPL", "NVDA", "TSLA", "SPY"]

        print(f"\n{'='*70}")
        print(f"🔄 Trading Cycle Start - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

        signals_generated = 0
        buy_signals = 0

        for symbol in symbols:
            signal = self.process_symbol(symbol)

            if signal['action'] in ['BUY', 'SELL']:
                self.log_trade(signal)
                signals_generated += 1

                if signal['action'] == 'BUY':
                    buy_signals += 1

        print(f"\n{'='*70}")
        print(f"📊 Cycle Summary:")
        print(f"  Symbols analyzed: {len(symbols)}")
        print(f"  Signals generated: {signals_generated}")
        print(f"  BUY signals: {buy_signals}")
        print(f"  Mode: {self.mode}")
        print(f"{'='*70}\n")

        return {
            "symbols_analyzed": len(symbols),
            "signals_generated": signals_generated,
            "buy_signals": buy_signals
        }

    def backtest_strategy(self, symbol: str = "XAUUSD", period: str = "1y") -> dict:
        """
        Backtest the strategy on historical data

        Returns performance metrics
        """
        print(f"\n📈 Backtesting {symbol} ({period})...")

        try:
            data = yf.download(symbol, period=period, progress=False)

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            trades = []
            in_trade = False
            entry_price = 0
            signals = []

            # Process each row
            for i in range(len(data) - 1):
                window_data = {
                    'open': data['Open'].iloc[:i+1].values,
                    'high': data['High'].iloc[:i+1].values,
                    'low': data['Low'].iloc[:i+1].values,
                    'close': data['Close'].iloc[:i+1].values,
                    'volume': data['Volume'].iloc[:i+1].values if 'Volume' in data.columns else [1] * (i+1)
                }

                signal = self.trading_system.generate_signal(window_data)

                if signal['action'] == 'BUY' and not in_trade:
                    in_trade = True
                    entry_price = data['Close'].iloc[i]
                    signals.append(('BUY', i, entry_price))

                elif signal['action'] == 'SELL' and in_trade:
                    in_trade = False
                    exit_price = data['Close'].iloc[i]
                    pnl_pct = ((exit_price - entry_price) / entry_price * 100)
                    trades.append({
                        'entry': entry_price,
                        'exit': exit_price,
                        'pnl_pct': pnl_pct,
                        'status': 'win' if pnl_pct > 0 else 'loss'
                    })
                    signals.append(('SELL', i, exit_price, pnl_pct))

            # Calculate stats
            if trades:
                wins = len([t for t in trades if t['pnl_pct'] > 0])
                win_rate = wins / len(trades) * 100
                avg_pnl = sum([t['pnl_pct'] for t in trades]) / len(trades)
                total_pnl = sum([t['pnl_pct'] for t in trades])

                return {
                    "symbol": symbol,
                    "period": period,
                    "total_trades": len(trades),
                    "winning_trades": wins,
                    "win_rate_pct": win_rate,
                    "avg_pnl_pct": avg_pnl,
                    "total_pnl_pct": total_pnl,
                    "best_trade": max([t['pnl_pct'] for t in trades]),
                    "worst_trade": min([t['pnl_pct'] for t in trades])
                }
            else:
                return {"symbol": symbol, "trades": 0}

        except Exception as e:
            return {"error": str(e)}


def main():
    """Run trading engine"""
    engine = SmartTradingEngine(paper_trade=True)

    # Backtest first
    print("\n🔬 BACKTESTING STRATEGY")
    print("="*70)
    backtest_result = engine.backtest_strategy("XAUUSD", "1y")
    print(f"Backtest Results:")
    print(f"  Total Trades: {backtest_result.get('total_trades', 0)}")
    print(f"  Win Rate: {backtest_result.get('win_rate_pct', 0):.1f}%")
    print(f"  Total P&L: {backtest_result.get('total_pnl_pct', 0):.2f}%")
    print(f"  Avg P&L: {backtest_result.get('avg_pnl_pct', 0):.2f}%")

    # Run live trading cycle
    while True:
        try:
            engine.run_trading_cycle()
            time.sleep(300)  # Run every 5 minutes

        except KeyboardInterrupt:
            print("\n🛑 Trading engine stopped")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            time.sleep(60)


if __name__ == "__main__":
    main()
