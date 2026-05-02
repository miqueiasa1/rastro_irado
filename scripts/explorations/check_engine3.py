import sys
sys.path.insert(0, '.')
from backend.irai.engine import IRAIEngine
import datetime
today = datetime.date.today().isoformat()
e = IRAIEngine()

import pandas as pd
import sqlite3

target = 'WDO$N'
model_key = target.split("$")[0].lower()
model = e.models.get(model_key)
active_factors = [f["name"] for f in model.config.get("factors", []) if f.get("active", True)]
from backend.irai.engine import resolve_symbol
factor_to_db = {f: resolve_symbol(f) for f in active_factors}
db_factors = list(set(factor_to_db.values()))

conn = sqlite3.connect(e.db_path)
all_symbols = list(set([target] + db_factors))
placeholders = ",".join(["?"] * len(all_symbols))
query = f"SELECT symbol, timestamp_utc, open, high, low, close, real_volume, delta FROM market_bars WHERE timeframe = 'M5' AND symbol IN ({placeholders}) AND timestamp_utc >= ? AND timestamp_utc < ? ORDER BY timestamp_utc"
start = f"{today}T00:00:00Z"
end_dt = datetime.datetime.fromisoformat(today) + datetime.timedelta(days=1)
end = end_dt.strftime("%Y-%m-%dT00:00:00Z")

df = pd.read_sql_query(query, conn, params=all_symbols + [start, end])
print('Total rows in df:', len(df))
print('Symbols in df:', df['symbol'].unique())
for s in all_symbols:
    count = len(df[df['symbol'] == s])
    print(f"{s}: {count} bars")

print('Opens:')
opens = {}
for sym in all_symbols:
    sym_bars = df[df["symbol"] == sym].sort_values("timestamp_utc")
    if len(sym_bars) > 0:
        opens[sym] = float(sym_bars.iloc[0]["open"])
print(opens)
if target not in opens:
    print(f"{target} not in opens!")
