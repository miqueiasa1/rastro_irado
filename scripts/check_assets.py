"""Check current asset models."""
import sqlite3
conn = sqlite3.connect("data/irai.db")
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT target, slug, session_start_h, session_end_h, data_proxy, accuracy, r_squared, factors, calibrated_at "
    "FROM asset_models WHERE active=1 ORDER BY target"
).fetchall()

for r in rows:
    t = r["target"]
    s = r["slug"]
    sh = r["session_start_h"]
    eh = r["session_end_h"]
    p = r["data_proxy"] or "-"
    a = f'{r["accuracy"]:.1f}' if r["accuracy"] else "N/A"
    r2 = f'{r["r_squared"]:.4f}' if r["r_squared"] else "N/A"
    f = r["factors"] or "[]"
    cal = r["calibrated_at"] or "never"
    print(f"{t:12s} slug={s:10s} session={sh:02d}-{eh:02d} proxy={p:8s} acc={a:>6s} r2={r2:>8s}  factors={f}")

print(f"\nTotal: {len(rows)} ativos")
conn.close()
