import sys; sys.path.insert(0, '.')
from backend.db import get_connection

conn = get_connection()

print("=== Distribuicao de horas: WIN$N (ultimo dia disponivel) ===")
rows = conn.execute("""
    SELECT substr(timestamp_utc, 12, 2) as hr, COUNT(*) as n
    FROM market_bars
    WHERE symbol='WIN$N' AND timeframe='M5'
      AND timestamp_utc >= (SELECT MAX(substr(timestamp_utc,1,10)) FROM market_bars WHERE symbol='WIN$N' AND timeframe='M5')
    GROUP BY hr ORDER BY hr
""").fetchall()
for r in rows:
    print(f"  hora {r['hr']}:xx -> {r['n']} barras")

print()
print("=== Distribuicao de horas: US30 (ultimo dia disponivel) ===")
rows2 = conn.execute("""
    SELECT substr(timestamp_utc, 12, 2) as hr, COUNT(*) as n
    FROM market_bars
    WHERE symbol='US30' AND timeframe='M5'
      AND timestamp_utc >= (SELECT MAX(substr(timestamp_utc,1,10)) FROM market_bars WHERE symbol='US30' AND timeframe='M5')
    GROUP BY hr ORDER BY hr
""").fetchall()
for r in rows2:
    print(f"  hora {r['hr']}:xx -> {r['n']} barras")

print()
print("=== asset_models sessions ===")
rows3 = conn.execute("SELECT slug, session_start_h, session_end_h FROM asset_models ORDER BY slug").fetchall()
for r in rows3:
    print(f"  {r['slug']:<10} {r['session_start_h']:>3}h - {r['session_end_h']:>3}h")

conn.close()
