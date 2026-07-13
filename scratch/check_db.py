"""Quick check: data collection status."""
import sqlite3
import os
import sys
from datetime import date, timedelta

# Force UTF-8 stdout if supported, or just use ASCII for safe logging
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'irai_live.db')
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("=" * 70)
print("IRAI DATA CHECK (DYNAMIC)")
print("=" * 70)

today_str = date.today().isoformat()
yesterday_str = (date.today() - timedelta(days=1)).isoformat()

# 1. Last data per symbol
print("\n=== ULTIMO DADO POR SIMBOLO ===")
rows = conn.execute("""
    SELECT symbol, source, MAX(timestamp_utc) as last_ts, COUNT(*) as total_bars
    FROM market_bars WHERE timeframe='M5'
    GROUP BY symbol, source
    ORDER BY last_ts DESC
""").fetchall()
for r in rows:
    print(f"  {r['symbol']:25s} src={r['source']:10s} last={r['last_ts']}  total={r['total_bars']}")

# 2. Most recent dates
print("\n=== DATAS MAIS RECENTES (TOP 5) ===")
dates = conn.execute("""
    SELECT DISTINCT substr(timestamp_utc, 1, 10) as d
    FROM market_bars WHERE timeframe='M5'
    ORDER BY d DESC LIMIT 5
""").fetchall()
for r in dates:
    print(f"  {r['d']}")

# 3. Today's bars
print(f"\n=== BARRAS DE HOJE ({today_str}) ===")
today = conn.execute(f"""
    SELECT symbol, COUNT(*) as bars, MIN(timestamp_utc) as first_ts, MAX(timestamp_utc) as last_ts
    FROM market_bars
    WHERE timeframe='M5' AND timestamp_utc >= '{today_str}T00:00:00Z'
    GROUP BY symbol ORDER BY symbol
""").fetchall()
if today:
    for r in today:
        print(f"  {r['symbol']:25s} bars={r['bars']:3d}  first={r['first_ts']}  last={r['last_ts']}")
else:
    print("  *** NENHUMA BARRA HOJE AINDA! ***")

# 4. Yesterday's bars for comparison
print(f"\n=== BARRAS DE ONTEM ({yesterday_str}) ===")
yesterday = conn.execute(f"""
    SELECT symbol, COUNT(*) as bars, MIN(timestamp_utc) as first_ts, MAX(timestamp_utc) as last_ts
    FROM market_bars
    WHERE timeframe='M5' AND timestamp_utc >= '{yesterday_str}T00:00:00Z' AND timestamp_utc < '{today_str}T00:00:00Z'
    GROUP BY symbol ORDER BY symbol
""").fetchall()
if yesterday:
    for r in yesterday:
        print(f"  {r['symbol']:25s} bars={r['bars']:3d}  first={r['first_ts']}  last={r['last_ts']}")
else:
    print("  *** NENHUMA BARRA ONTEM! ***")

# 5. Check for gaps - symbols configured in collector vs in DB
collector_symbols = [
    "WIN$N", "WDO$N", "DI1$N",
    "DXY", "BRENT", "CHINA50", "USDMXN", "VIX", "BTCUSD",
    "US500", "US30", "USTEC", "XAUUSD",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
    "CADCHF", "AUDNZD", "EURGBP", "EURCHF", "EURJPY", "GBPJPY", "EURAUD",
    "iSharesBrazil+", "iSharesTreasury20+", "iSharesTreasury10-20+",
    "iSharesTreasury1-3+", "iSharesUSEmerging+", "iSharesCurrencyBond+",
]
db_symbols = set(r['symbol'] for r in rows)
print("\n=== SIMBOLOS FALTANDO NO DB (configurados mas sem dados) ===")
missing = [s for s in collector_symbols if s not in db_symbols]
if missing:
    for s in missing:
        print(f"  [WAIT] {s}")
else:
    print("  Todos os simbolos configurados tem dados no DB")

# 6. Check API health
print("\n=== CHECK API HEALTH ===")
try:
    import urllib.request
    import json
    resp = urllib.request.urlopen("http://localhost:8888/api/health", timeout=5)
    health = json.loads(resp.read())
    print(f"  Status: {health.get('status')}")
    print(f"  Total bars: {health.get('bars_total')}")
    print(f"  Last bar: {health.get('last_bar')}")
    print(f"  Models loaded: {health.get('models_loaded')}")
    print(f"  Targets: {health.get('targets')}")
except Exception as e:
    print(f"  [ERROR] API nao acessivel: {e}")

# 7. Check targets/calibration
print("\n=== TARGETS CALIBRADOS ===")
am_rows = conn.execute("""
    SELECT target, slug, display_name, accuracy, r_squared, calibrated_at, active
    FROM asset_models
    ORDER BY target
""").fetchall()
if am_rows:
    for r in am_rows:
        cal = "[OK]" if r['accuracy'] else "[NO]"
        act = "ATIVO" if r['active'] else "INATIVO"
        # R-squared display
        r_sq = f"{r['r_squared']:.4f}" if r['r_squared'] is not None else "N/A"
        acc = f"{r['accuracy']:.4f}" if r['accuracy'] is not None else "N/A"
        print(f"  {cal} {r['target']:15s} slug={r['slug']:12s} acc={acc:>8}  R2={r_sq:>8}  {act}")
else:
    print("  Nenhum target registrado em asset_models")

# 8. Stale data check - any symbol with last update > 2 hours ago
print("\n=== DADOS POTENCIALMENTE STALE (> 2h sem atualizar) ===")
stale = conn.execute("""
    SELECT symbol, source, MAX(timestamp_utc) as last_ts
    FROM market_bars WHERE timeframe='M5'
    GROUP BY symbol, source
    HAVING last_ts < datetime('now', '-2 hours')
    ORDER BY last_ts DESC
""").fetchall()
if stale:
    for r in stale:
        print(f"  [STALE] {r['symbol']:25s} src={r['source']:10s} last={r['last_ts']}")
else:
    print("  Todos os simbolos atualizados recentemente")

conn.close()
