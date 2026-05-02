import sqlite3
conn = sqlite3.connect('data/irai.db')
cols = [r[1] for r in conn.execute('PRAGMA table_info(asset_models)').fetchall()]
print('Colunas:', cols)
rows = conn.execute("SELECT target, calibrated_at, accuracy FROM asset_models WHERE target IN ('CADCHF','AUDNZD')").fetchall()
for r in rows: print(r)
conn.close()
