import sqlite3
conn = sqlite3.connect('data/irai.db')
conn.execute("UPDATE asset_models SET data_proxy = NULL WHERE target = 'WDO$N'")
conn.commit()
conn.close()
print("Updated WDO$N data_proxy to NULL")
