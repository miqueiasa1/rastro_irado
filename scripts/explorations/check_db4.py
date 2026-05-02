import sqlite3
with sqlite3.connect('data/irai.db') as conn:
    c = conn.cursor()
    print('WDO session_end_h:', c.execute("SELECT session_end_h FROM asset_models WHERE target='WDO$N'").fetchone()[0])
