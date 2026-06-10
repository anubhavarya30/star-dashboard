#!/usr/bin/env python3
"""Test one trading cycle manually"""
import sys
sys.path.insert(0, '/Users/anubhavarya/star/star-dashboard')

from market_data_provider import RealMarketDataProvider
from trading_signals import VolumeWeightedRSISystem
from datetime import datetime

print("\n" + "="*80)
print("🔬 MANUAL TRADING CYCLE TEST")
print("="*80 + "\n")

# Initialize
provider = RealMarketDataProvider()
system = VolumeWeightedRSISystem()

symbols = ["AAPL", "NVDA", "TSLA", "SPY"]

print("📊 Analyzing symbols for trading signals...\n")

signal_count = 0

for symbol in symbols:
    print(f"🔍 {symbol}:")
    
    try:
        # Get real market data
        ohlcv = provider.get_ohlcv_dict(symbol, period="5d", interval="1h")
        
        if not ohlcv:
            print(f"   ⚠️  No data available\n")
            continue
        
        current_price = ohlcv['last_price']
        print(f"   Current price: ${current_price:.2f}")
        
        # Generate signal
        signal_data = {
            'open': ohlcv['open'],
            'high': ohlcv['high'],
            'low': ohlcv['low'],
            'close': ohlcv['close'],
            'volume': ohlcv['volume']
        }
        
        signal = system.generate_signal(signal_data)
        action = signal.get('action')
        confidence = signal.get('confidence', 0)
        
        print(f"   Signal: {action}")
        print(f"   Confidence: {confidence:.1%}")
        
        if action in ['BUY', 'SELL']:
            print(f"   Stop Loss: ${signal.get('stop_loss', 0):.2f}")
            print(f"   Take Profit: ${signal.get('take_profit', 0):.2f}")
            print(f"   Reason: {signal.get('reason', '')}")
            
            if confidence >= 0.70:
                print(f"   ✅ WOULD EXECUTE (confidence >= 70%)")
                signal_count += 1
            else:
                print(f"   ⏸️  Would not execute (confidence < 70%)")
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:50]}\n")
        continue
    
    print()

print("="*80)
print(f"📊 RESULTS: {signal_count} signals ready to execute")
print("="*80 + "\n")
