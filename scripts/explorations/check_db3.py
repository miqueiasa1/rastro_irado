import sqlite3
with sqlite3.connect('data/irai.db') as conn:
    c = conn.cursor()
    print('WDO session_start_h:', c.execute("SELECT session_start_h FROM asset_models WHERE target='WDO$N'").fetchone()[0])
    print('WIN session_start_h:', c.execute("SELECT session_start_h FROM asset_models WHERE target='WIN$N'").fetchone()[0])
