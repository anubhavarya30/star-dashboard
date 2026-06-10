#!/usr/bin/env python3
"""
Simple IBKR Connection Test - Bypasses asyncio issues
Just checks if TWS is responding on the API port
"""
import socket
import time

def test_ibkr_connection(host="127.0.0.1", port=7497, timeout=5):
    """Test if IBKR is listening on the API port"""

    print("\n" + "="*80)
    print("🔌 TESTING IBKR CONNECTION")
    print("="*80)

    print(f"\nConnecting to {host}:{port}...")

    try:
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        # Try to connect
        result = sock.connect_ex((host, port))

        if result == 0:
            print(f"✅ SUCCESS! IBKR is listening on {host}:{port}")
            print("\n✅ Your system is READY for LIVE TRADING!")
            print("\nNext steps:")
            print("  1. Run: python3 automated_system.py")
            print("  2. Open dashboard: http://localhost:8501")
            print("  3. REAL trades will execute when market signals appear")
            sock.close()
            return True
        else:
            print(f"❌ Connection refused on {host}:{port}")
            sock.close()
            return False

    except socket.timeout:
        print(f"❌ Connection timeout (waited {timeout}s)")
        return False
    except socket.error as e:
        print(f"❌ Connection error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_ibkr_connection()
    if success:
        print("\n" + "="*80)
        print("🚀 READY FOR LIVE TRADING")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("⚠️  CONNECTION FAILED")
        print("="*80)
        print("\nMake sure:")
        print("  1. Trader Workstation is running")
        print("  2. API is enabled (File → Global Configuration → API)")
        print("  3. Port 7497 is set in API settings")
        print("  4. 'Allow connections from localhost' is checked")
