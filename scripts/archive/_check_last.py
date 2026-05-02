import sqlite3
conn = sqlite3.connect('data/irai.db')
c = conn.cursor()
c.execute("SELECT symbol, MAX(timestamp_utc) FROM market_bars WHERE symbol IN ('WIN$N', 'WDO$N', 'US500') GROUP BY symbol")
for row in c.fetchall():
    print(row)
conn.close()
