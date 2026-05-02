import sys
sys.path.insert(0, '.')
from backend.irai.engine import IRAIEngine
import datetime
today = datetime.date.today().isoformat()
e = IRAIEngine()

def trace_compute(self, session_date, target):
    data_target = target or self.default_target
    model_key = data_target.split('$')[0].lower()
    model = self.models[model_key]
    cfg = model['config']
    active_factors = [f['name'] for f in cfg.get('factors', []) if f.get('active', True)]
    from backend.irai.engine import resolve_symbol
    factor_to_db = {f: resolve_symbol(f) for f in active_factors}
    db_factors = list(set(factor_to_db.values()))
    
    import sqlite3, pandas as pd
    conn = sqlite3.connect(self.db_path)
    all_symbols = list(set([data_target] + db_factors))
    placeholders = ','.join(['?'] * len(all_symbols))
    query = f"SELECT symbol, timestamp_utc, open FROM market_bars WHERE timeframe = 'M5' AND symbol IN ({placeholders}) AND timestamp_utc >= ? AND timestamp_utc < ? ORDER BY timestamp_utc"
    start = f"{session_date}T00:00:00Z"
    end_dt = datetime.datetime.fromisoformat(session_date) + datetime.timedelta(days=1)
    end = end_dt.strftime('%Y-%m-%dT00:00:00Z')
    df = pd.read_sql_query(query, conn, params=all_symbols + [start, end])
    conn.close()
    
    if df.empty: return 'Empty DF'
    
    df['timestamp'] = pd.to_datetime(df['timestamp_utc'])
    df['hour'] = df['timestamp'].dt.hour
    target_hours = df[df['symbol'] == data_target]['hour'].value_counts()
    if target_hours.empty: return 'No target hours'
    
    session_start = cfg.get('session_start_h', 0)
    session_end = cfg.get('session_end_h', 24)
    session_mask = (df['hour'] >= session_start) & (df['hour'] <= session_end)
    df = df[session_mask]
    
    opens = {}
    for sym in all_symbols:
        sym_bars = df[df['symbol'] == sym].sort_values('timestamp')
        if len(sym_bars) > 0:
            opens[sym] = float(sym_bars.iloc[0]['open'])
            
    if data_target not in opens: return 'Target not in opens'
    
    missing = [f for f in active_factors if factor_to_db[f] not in opens]
    if missing: return f'Missing factors in opens: {missing}'
    
    return 'Success (past opens)'

print(trace_compute(e, today, 'WDO$N'))
