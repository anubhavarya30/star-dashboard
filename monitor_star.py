#!/usr/bin/env python3
"""
🔍 STAR MONITOR - Keeps systems running 24/7
Automatically restarts crashed processes
"""
import subprocess
import time
from datetime import datetime
from pathlib import Path

def check_process(name, command):
    """Check if process is running"""
    result = subprocess.run(
        f"ps aux | grep '{command}' | grep -v grep | wc -l",
        shell=True,
        capture_output=True,
        text=True
    )
    count = int(result.stdout.strip())
    return count > 0

def restart_process(name, script):
    """Restart a crashed process"""
    print(f"🔄 Restarting {name}...")
    subprocess.Popen(
        f"source venv/bin/activate && nohup python3 {script} >> {script.replace('.py', '.log')} 2>&1 &",
        shell=True,
        cwd="/Users/anubhavarya/star/star-dashboard"
    )
    print(f"✅ {name} restarted")

def monitor():
    """Continuous monitoring loop"""
    print("\n" + "="*80)
    print("🔍 STAR MONITOR - STARTING")
    print("="*80)
    print("Monitoring: STAR Brain & Dashboard")
    print("Check interval: Every 30 seconds")
    print("Action: Auto-restart if crashed")
    print("="*80 + "\n")

    restarts = {"star_brain": 0, "dashboard": 0}

    while True:
        now = datetime.now()

        # Check STAR Brain
        if not check_process("STAR Brain", "star_brain.py"):
            print(f"[{now.strftime('%H:%M:%S')}] ❌ STAR Brain down - restarting...")
            restart_process("STAR Brain", "star_brain.py")
            restarts["star_brain"] += 1
            time.sleep(5)
        else:
            print(f"[{now.strftime('%H:%M:%S')}] ✅ STAR Brain running")

        # Check Dashboard
        if not check_process("Dashboard", "streamlit"):
            print(f"[{now.strftime('%H:%M:%S')}] ❌ Dashboard down - restarting...")
            restart_process("Dashboard", "dashboard.py")
            restarts["dashboard"] += 1
            time.sleep(5)
        else:
            print(f"[{now.strftime('%H:%M:%S')}] ✅ Dashboard running")

        # Summary
        print(f"   Total restarts - Brain: {restarts['star_brain']}, Dashboard: {restarts['dashboard']}")
        print()

        # Wait 30 seconds before next check
        time.sleep(30)


if __name__ == "__main__":
    try:
        monitor()
    except KeyboardInterrupt:
        print("\n\n🛑 Monitor stopped")
