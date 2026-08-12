"""Purge today's stale snapshots so the collector can re-populate them with INSERT OR IGNORE."""
import sqlite3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import DB_PATH
from datetime import date

today = date.today().isoformat()
conn = sqlite3.connect(DB_PATH)
cur = conn.execute("DELETE FROM irai_live_snapshots WHERE session_date = ?", (today,))
conn.commit()
print(f"Deleted {cur.rowcount} stale rows for {today}")
conn.close()
