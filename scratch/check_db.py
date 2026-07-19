import sqlite3

db_path = "data/irai_live.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("=== Latest bar timestamps in database ===")
symbols = ["WIN$N", "WDO$N", "DI1$N", "EURUSD", "BTCUSD"]
for s in symbols:
    row = conn.execute("SELECT timestamp_utc, close FROM market_bars WHERE symbol = ? ORDER BY timestamp_utc DESC LIMIT 1", (s,)).fetchone()
    if row:
        print(f"Symbol: {s:<10} | Time (UTC): {row['timestamp_utc']} | Close: {row['close']}")
    else:
        print(f"Symbol: {s:<10} | No data found")
