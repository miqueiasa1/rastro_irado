import sqlite3
import datetime
today = datetime.date.today().isoformat()
with sqlite3.connect('data/irai.db') as conn:
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM market_bars WHERE symbol='WDO$N' AND timestamp_utc LIKE ?", (today + '%',))
    print('WDO$N bars today:', c.fetchone()[0])
    c.execute("SELECT COUNT(*) FROM market_bars WHERE symbol='WIN$N' AND timestamp_utc LIKE ?", (today + '%',))
    print('WIN$N bars today:', c.fetchone()[0])
    c.execute("SELECT COUNT(*) FROM market_bars WHERE symbol='BTCUSD' AND timestamp_utc LIKE ?", (today + '%',))
    print('BTCUSD bars today:', c.fetchone()[0])
