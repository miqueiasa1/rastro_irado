import sqlite3
import datetime
today = datetime.date.today().isoformat()
with sqlite3.connect('data/irai.db') as conn:
    c = conn.cursor()
    rows = c.execute("SELECT DISTINCT substr(timestamp_utc,12,2) FROM market_bars WHERE symbol='WDO$N' AND timestamp_utc LIKE ?", (today + '%',)).fetchall()
    print('WDO$N Hours:', [r[0] for r in rows])
