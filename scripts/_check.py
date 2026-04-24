from backend.db import get_connection
conn = get_connection()
r = conn.execute(
    "SELECT timestamp_utc FROM market_bars WHERE symbol='WIN$N' AND timeframe='M5' ORDER BY timestamp_utc DESC LIMIT 5"
).fetchall()
for row in r:
    print(row["timestamp_utc"])
conn.close()
