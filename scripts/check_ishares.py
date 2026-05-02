"""Check iShares data in DB."""
import sqlite3
conn = sqlite3.connect("data/irai.db")
rows = conn.execute(
    "SELECT symbol, COUNT(*), MIN(timestamp_utc), MAX(timestamp_utc) "
    "FROM market_bars WHERE symbol LIKE 'iShares%' GROUP BY symbol"
).fetchall()
for r in rows:
    print(f"{r[0]:30s} {r[1]:>8d} bars  {r[2]} -> {r[3]}")
print()
print(f"Total iShares bars: {sum(r[1] for r in rows)}")
conn.close()
