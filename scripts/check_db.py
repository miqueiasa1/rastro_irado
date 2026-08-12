"""Verify zero-repainting: check pair_z values and immutability."""
import sqlite3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import DB_PATH
from datetime import date

today = date.today().isoformat()
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 1. Check pair_z values for WIN$N
print("=== WIN$N pair_z values (first 10 non-null) ===")
rows = conn.execute("""
    SELECT timestamp_utc, pair_z, pair_factor, pair_beta, pair_signal,
           pair_fixed_z, pair_fixed_factor, is_live_captured, created_at
    FROM irai_live_snapshots
    WHERE target = 'WIN$N' AND session_date = ? AND timeframe = 'M5'
      AND pair_z IS NOT NULL
    ORDER BY timestamp_utc ASC LIMIT 10
""", (today,)).fetchall()
for r in rows:
    print(f"  {r['timestamp_utc']} | pz={r['pair_z']} | factor={r['pair_factor']} | pfz={r['pair_fixed_z']} | pff={r['pair_fixed_factor']} | created={r['created_at']}")

if not rows:
    print("  (No non-null pair_z found)")

# 2. Total bars and pair_z coverage
total = conn.execute("""
    SELECT COUNT(*) as total,
           SUM(CASE WHEN pair_z IS NOT NULL THEN 1 ELSE 0 END) as with_pz,
           SUM(CASE WHEN pair_fixed_z IS NOT NULL THEN 1 ELSE 0 END) as with_pfz
    FROM irai_live_snapshots
    WHERE target = 'WIN$N' AND session_date = ? AND timeframe = 'M5'
""", (today,)).fetchone()
print(f"\n  Total WIN$N bars: {total['total']}, with pair_z: {total['with_pz']}, with pair_fixed_z: {total['with_pfz']}")

# 3. Bars around 10:30 BRT (13:30 UTC)
print("\n=== WIN$N bars 10:00-11:00 BRT (13:00-14:00 UTC) ===")
rows = conn.execute("""
    SELECT timestamp_utc, pair_z, pair_factor, pair_beta, pair_fixed_z, pair_fixed_factor
    FROM irai_live_snapshots
    WHERE target = 'WIN$N' AND session_date = ? AND timeframe = 'M5'
      AND timestamp_utc BETWEEN ?||'T13:00:00' AND ?||'T14:00:00'
    ORDER BY timestamp_utc ASC
""", (today, today, today)).fetchall()
for r in rows:
    print(f"  {r['timestamp_utc']} | pz={r['pair_z']} | factor={r['pair_factor']} | pfz={r['pair_fixed_z']} | pff={r['pair_fixed_factor']}")

# 4. created_at distribution
print("\n=== Created_at distribution ===")
rows = conn.execute("""
    SELECT created_at, COUNT(*) as cnt,
           MIN(timestamp_utc) as first_bar, MAX(timestamp_utc) as last_bar
    FROM irai_live_snapshots
    WHERE target = 'WIN$N' AND session_date = ? AND timeframe = 'M5'
    GROUP BY created_at
    ORDER BY created_at
""", (today,)).fetchall()
for r in rows:
    print(f"  {r['created_at']} -> {r['cnt']} bars ({r['first_bar']} to {r['last_bar']})")

conn.close()
