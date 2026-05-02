import sys
sys.path.insert(0, '.')
from backend.irai.engine import IRAIEngine
import datetime
today = datetime.date.today().isoformat()
e = IRAIEngine()

target = 'WDO$N'
t_weights, t_sigmas, t_alpha, t_intercept, cfg = e._get_model_config(target)

active_factors = cfg['factors']
from backend.irai.engine import resolve_symbol
factor_to_db = {f: resolve_symbol(f) for f in active_factors}
db_factors = list(set(factor_to_db.values()))

import sqlite3, pandas as pd
conn = sqlite3.connect(e.db_path)
data_target = target
all_symbols = list(set([data_target] + db_factors))
placeholders = ','.join(['?'] * len(all_symbols))
query = f"SELECT symbol, timestamp_utc, open FROM market_bars WHERE timeframe = 'M5' AND symbol IN ({placeholders}) AND timestamp_utc >= ? AND timestamp_utc < ? ORDER BY timestamp_utc"
start = f"{today}T00:00:00Z"
end_dt = datetime.datetime.fromisoformat(today) + datetime.timedelta(days=1)
end = end_dt.strftime('%Y-%m-%dT00:00:00Z')
df = pd.read_sql_query(query, conn, params=all_symbols + [start, end])
conn.close()

df['timestamp'] = pd.to_datetime(df['timestamp_utc'])
df['hour'] = df['timestamp'].dt.hour
session_start = cfg.get('session_start_h', 0)
session_end = cfg.get('session_end_h', 24)
session_mask = (df['hour'] >= session_start) & (df['hour'] <= session_end)
df = df[session_mask]

opens = {}
for sym in all_symbols:
    sym_bars = df[df['symbol'] == sym].sort_values('timestamp')
    if len(sym_bars) > 0:
        opens[sym] = float(sym_bars.iloc[0]['open'])
        
print("OPENS:", opens)
if data_target not in opens:
    print(f"FAILED: {data_target} not in opens")
missing = [f for f in active_factors if factor_to_db[f] not in opens]
if missing:
    print(f"FAILED: Missing factors in opens: {missing}")
else:
    print("SUCCESS: All factors present!")
