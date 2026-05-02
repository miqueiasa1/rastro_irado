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
all_symbols = list(set([target] + db_factors))
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
        
missing = [f for f in active_factors if factor_to_db[f] not in opens]
target_bars = df[df['symbol'] == target]
print('TARGET BARS:', len(target_bars))
print('MISSING IN OPENS:', missing)

# Call the actual method and see why it returns 0 snaps!
snaps = e.compute_from_db(today, target)
print("ACTUAL SNAPS RETURNED:", len(snaps))
