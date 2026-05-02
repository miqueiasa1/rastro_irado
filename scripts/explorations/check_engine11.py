import sys
sys.path.insert(0, '.')
from backend.irai.engine import IRAIEngine
import datetime
today = datetime.date.today().isoformat()
e = IRAIEngine()
snaps = e.compute_from_db(today, 'WDO$N')
print(f'Length of snaps: {len(snaps)}')
if len(snaps) == 0:
    print('Failed. Why?')
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
    
    print('DF empty?', df.empty)
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp_utc'])
        df['hour'] = df['timestamp'].dt.hour
        session_start = cfg.get('session_start_h', 0)
        session_end = cfg.get('session_end_h', 24)
        print('session_start:', session_start, 'session_end:', session_end)
        session_mask = (df['hour'] >= session_start) & (df['hour'] <= session_end)
        df = df[session_mask]
        print('DF empty after mask?', df.empty)
        
        target_hours = df[df["symbol"] == data_target]["hour"].value_counts()
        print('target_hours empty?', target_hours.empty)
        
        opens = {}
        for sym in all_symbols:
            sym_bars = df[df["symbol"] == sym].sort_values("timestamp")
            if len(sym_bars) > 0: opens[sym] = float(sym_bars.iloc[0]["open"])
        
        print('opens WDO$N?', 'WDO$N' in opens)
        missing = [f for f in active_factors if factor_to_db[f] not in opens]
        print('missing in opens?', missing)
