import sqlite3
with sqlite3.connect('data/irai.db') as conn:
    row = conn.execute("SELECT divergence_config FROM asset_models WHERE target='WIN$N'").fetchone()
    print('WIN$N divergence_config:', row[0])
    row = conn.execute("SELECT divergence_config FROM asset_models WHERE target='WDO$N'").fetchone()
    print('WDO$N divergence_config:', row[0])
