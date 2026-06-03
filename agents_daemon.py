#!/usr/bin/env python3
"""
Agents Daemon - Runs agents continuously on a schedule.
This keeps agents running in the background, updating decisions regularly.
"""
import subprocess
import time
from datetime import datetime
import sys

def run_agents():
    """Run agents_lite.py and return success status."""
    try:
        print(f"\n{'='*80}")
        print(f"⏰ Running agents at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")

        result = subprocess.run(
            [sys.executable, "agents_lite.py"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            print(result.stdout)
            return True
        else:
            print(f"❌ Agent execution failed:")
            print(result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print("⚠️  Agent execution timeout (5 minutes)")
        return False
    except Exception as e:
        print(f"❌ Error running agents: {e}")
        return False


def main():
    """Run agents on a schedule."""
    print(f"🤖 AGENTS DAEMON STARTED")
    print(f"📋 Agents will run every 10 minutes")
    print(f"🎯 Dashboard: http://localhost:8502")
    print(f"❌ Press Ctrl+C to stop\n")

    # Run immediately on start
    run_agents()

    # Then run on schedule
    interval = 600  # 10 minutes
    last_run = time.time()

    try:
        while True:
            now = time.time()
            if now - last_run >= interval:
                run_agents()
                last_run = now

            time.sleep(5)  # Check every 5 seconds

    except KeyboardInterrupt:
        print("\n\n🛑 Agents daemon stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
