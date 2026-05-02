import sys
sys.path.insert(0, '.')
from backend.irai.engine import IRAIEngine
import datetime
today = datetime.date.today().isoformat()
e = IRAIEngine()

target = 'WDO$N'
data_target = target
model_key = data_target.split('$')[0].lower()
model = e.models[model_key]
cfg = model['config']
active_factors = [f['name'] for f in cfg.get('factors', []) if f.get('active', True)]
from backend.irai.engine import resolve_symbol
factor_to_db = {f: resolve_symbol(f) for f in active_factors}
db_factors = list(set(factor_to_db.values()))

import sqlite3, pandas as pd
conn = sqlite3.connect(e.db_path)
all_symbols = list(set([data_target] + db_factors))
placeholders = ','.join(['?'] * len(all_symbols))
query = f"SELECT symbol, timestamp_utc, open FROM market_bars WHERE timeframe = 'M5' AND symbol IN ({placeholders}) AND timestamp_utc >= ? AND timestamp_utc < ? ORDER BY timestamp_utc"
start = f"{today}T00:00:00Z"
end_dt = datetime.datetime.fromisoformat(today) + datetime.timedelta(days=1)
end = end_dt.strftime('%Y-%m-%dT00:00:00Z')
df = pd.read_sql_query(query, conn, params=all_symbols + [start, end])
conn.close()

print('ALL SYMBOLS:', all_symbols)
print('DF LENGTH:', len(df))
print('DF SYMBOLS:', df['symbol'].unique() if not df.empty else [])

if not df.empty:
    df['timestamp'] = pd.to_datetime(df['timestamp_utc'])
    df['hour'] = df['timestamp'].dt.hour
    
    session_start = cfg.get('session_start_h', 0)
    session_end = cfg.get('session_end_h', 24)
    print(f'Mask: {session_start} to {session_end}')
    session_mask = (df['hour'] >= session_start) & (df['hour'] <= session_end)
    df = df[session_mask]
    print('DF LENGTH AFTER MASK:', len(df))
    print('DF SYMBOLS AFTER MASK:', df['symbol'].unique() if not df.empty else [])
