#!/usr/bin/env python3
"""
Test Webull Python SDK - Advanced methods
"""
from webull import webull
import json

print("\n" + "="*80)
print("🚀 WEBULL SDK - TESTING ALL DATA METHODS")
print("="*80 + "\n")

wb = webull()

# Test different methods
symbols = ["AAPL", "NVDA", "TSLA"]

for symbol in symbols:
    print(f"\n📊 {symbol}")
    print("─" * 40)
    
    try:
        # Method 1: Quote
        quote = wb.get_quote(stock=symbol)
        if quote:
            print(f"  Quote: {type(quote)}")
            if isinstance(quote, dict):
                print(f"    Keys: {list(quote.keys())[:5]}")
                for k, v in list(quote.items())[:3]:
                    print(f"    {k}: {v}")
        
        # Method 2: Stock info
        info = wb.get_stock_info(stock=symbol)
        if info:
            print(f"\n  Stock Info: {type(info)}")
            if isinstance(info, dict):
                print(f"    Name: {info.get('name', 'N/A')}")
                print(f"    Price: ${info.get('price', 'N/A')}")
                print(f"    Change: {info.get('change', 'N/A')}")
        
        # Method 3: Bars (OHLCV)
        try:
            bars = wb.get_bars(stock=symbol, interval=1440)  # 1440 = daily
            if bars:
                print(f"\n  Bars (Daily): {type(bars)}")
                if isinstance(bars, list) and len(bars) > 0:
                    latest = bars[-1]
                    print(f"    Latest bar: {latest}")
        except:
            pass
            
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:50]}")

print("\n" + "="*80)
print("✅ WEBULL ADVANCED TESTING COMPLETE")
print("="*80 + "\n")
