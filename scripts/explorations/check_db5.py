import sqlite3
with sqlite3.connect('data/irai.db') as conn:
    print('DOL$N count:', conn.execute("SELECT COUNT(*) FROM market_bars WHERE symbol='DOL$N'").fetchone()[0])
