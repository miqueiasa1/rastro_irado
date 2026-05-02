"""Snapshot Wave 1 assets before recalibration."""
import sqlite3, json

TARGETS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF"]

conn = sqlite3.connect("data/irai.db")
conn.row_factory = sqlite3.Row

print("=" * 70)
print("  ESTADO ATUAL — Onda 1 (Forex Majors)")
print("=" * 70)
print(f"  {'Target':10s} {'ACC':>8s} {'R²':>8s} {'#Fats':>6s}  Fatores")
print(f"  {'-'*10} {'-'*8} {'-'*8} {'-'*6}  {'-'*30}")

for t in TARGETS:
    row = conn.execute(
        "SELECT target, accuracy, r_squared, factors FROM asset_models WHERE target=?",
        (t,)
    ).fetchone()
    if row:
        acc = f"{row['accuracy']:.1f}%"
        r2 = f"{row['r_squared']:.4f}"
        factors = json.loads(row['factors']) if row['factors'] else []
        print(f"  {t:10s} {acc:>8s} {r2:>8s} {len(factors):>6d}  {', '.join(factors)}")

conn.close()
