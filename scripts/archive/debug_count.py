import sqlite3

conn = sqlite3.connect('data/irai.db')
c = conn.execute('SELECT target, data_proxy FROM asset_models').fetchall()
for t, dp in c:
    d = dp or t
    cnt = conn.execute(f"SELECT COUNT(*) FROM market_bars WHERE symbol='{d}' AND timeframe='M5'").fetchone()[0]
    print(f"{t} (proxy: {d}): {cnt} bars")
