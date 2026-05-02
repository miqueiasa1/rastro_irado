import sqlite3
import datetime
today = datetime.date.today().isoformat()
with sqlite3.connect('data/irai.db') as conn:
    print('DOL$N count today:', conn.execute("SELECT COUNT(*) FROM market_bars WHERE symbol='DOL$N' AND timestamp_utc LIKE ?", (today + '%',)).fetchone()[0])
