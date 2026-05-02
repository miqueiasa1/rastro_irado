import sqlite3
with sqlite3.connect('data/irai.db') as conn:
    print('WDO factors:', conn.execute("SELECT factors FROM asset_models WHERE target='WDO$N'").fetchone()[0])
