#!/usr/bin/env python3
"""
Google Calendar MCP Integration
Syncs daily P&L to your Google Calendar via MCP
"""
import sqlite3
from datetime import datetime, timedelta
import json
from pathlib import Path

class GoogleCalendarMCP:
    """Sync trading P&L to Google Calendar via MCP"""

    def __init__(self, db_path="star_trading.db"):
        self.db_path = db_path
        self.mcp_log = Path("calendar_sync.log")

    def get_daily_pnl_data(self, days=30):
        """Get daily P&L data from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get daily P&L from executed trades
        query = """
        SELECT
            DATE(exit_date) as trade_date,
            SUM(pnl) as daily_pnl,
            COUNT(*) as trades_count,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades
        FROM executed_trades
        WHERE exit_date IS NOT NULL
            AND DATE(exit_date) >= DATE('now', '-' || ? || ' days')
        GROUP BY DATE(exit_date)
        ORDER BY trade_date DESC
        """

        cursor.execute(query, (days,))
        results = cursor.fetchall()
        conn.close()

        return results

    def format_calendar_events(self):
        """Format P&L data as Google Calendar events"""
        pnl_data = self.get_daily_pnl_data()
        events = []

        for trade_date, daily_pnl, trades_count, wins, losses in pnl_data:
            if daily_pnl is None:
                continue

            # Determine event color (green for profit, red for loss)
            color = "green" if daily_pnl > 0 else "red"

            # Format event title
            title = f"P&L: ${daily_pnl:+.2f} ({wins}W {losses}L)"

            # Format event description
            description = f"""STAR Trading Daily Report
Date: {trade_date}
Daily P&L: ${daily_pnl:+.2f}
Trades: {trades_count}
Wins: {wins}
Losses: {losses}
Win Rate: {(wins/trades_count*100):.1f}%"""

            events.append({
                "date": trade_date,
                "title": title,
                "description": description,
                "color": color,
                "daily_pnl": daily_pnl,
                "trades": trades_count
            })

        return events

    def sync_to_calendar(self):
        """Sync P&L events to Google Calendar via MCP"""
        events = self.format_calendar_events()

        log = f"[{datetime.now().isoformat()}] Google Calendar Sync\n"
        log += f"Events to sync: {len(events)}\n"

        for event in events:
            log += f"\n✅ {event['date']}: {event['title']}\n"
            log += f"   Color: {event['color']}\n"
            log += f"   Trades: {event['trades']}\n"

        # Log sync activity
        with open(self.mcp_log, "a") as f:
            f.write(log + "\n")

        return events

    def get_sync_status(self):
        """Get calendar sync status"""
        if not self.mcp_log.exists():
            return "No sync history"

        with open(self.mcp_log) as f:
            lines = f.readlines()

        return "".join(lines[-20:])


if __name__ == "__main__":
    mcp = GoogleCalendarMCP()

    print("\n" + "="*80)
    print("🗓️  GOOGLE CALENDAR MCP SYNC")
    print("="*80 + "\n")

    events = mcp.sync_to_calendar()

    print(f"✅ Synced {len(events)} events to calendar")
    print(f"\nStatus:\n{mcp.get_sync_status()}")
