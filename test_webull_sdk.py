#!/usr/bin/env python3
"""
Test Webull Python SDK
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*80)
print("🚀 WEBULL SDK TEST")
print("="*80 + "\n")

try:
    from webull import webull
    
    print("✅ webull library imported successfully")
    
    # Initialize Webull
    wb = webull()
    
    print("✅ Webull object created")
    
    # Try to get quote (no auth needed for public data)
    print("\n📊 Fetching AAPL quote...")
    quote = wb.get_quote(stock="AAPL")
    
    if quote:
        print("✅ GOT QUOTE DATA FROM WEBULL!")
        print(f"   Price: ${quote.get('last', 'N/A')}")
        print(f"   Bid: ${quote.get('bid', 'N/A')}")
        print(f"   Ask: ${quote.get('ask', 'N/A')}")
        print(f"   Volume: {quote.get('volume', 'N/A')}")
    else:
        print("⚠️  No quote data returned")
        
except ImportError as e:
    print(f"❌ Could not import webull: {str(e)}")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    print(f"   Type: {type(e).__name__}")

print("\n" + "="*80)
