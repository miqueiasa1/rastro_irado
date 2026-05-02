import sys
sys.path.insert(0, '.')
from backend.irai.engine import IRAIEngine
import datetime
today = datetime.date.today().isoformat()
e = IRAIEngine()
target = 'WDO$N'

# Redefine the method with print statements
def trace_compute(self, session_date, target):
    data_target = target
    model_key = data_target.split('$')[0].lower()
    
    t_weights, t_sigmas, t_alpha, t_intercept, cfg = self._get_model_config(target)
    active_factors = cfg["factors"]
    from backend.irai.engine import resolve_symbol
    data_target = cfg.get("data_proxy") or resolve_symbol(target)
    print("DATA_TARGET IS:", repr(data_target))
    
    factor_to_db = {f: resolve_symbol(f) for f in active_factors}
    db_factors = list(set(factor_to_db.values()))
    db_to_factor = {v: k for k, v in factor_to_db.items()}
    
    import sqlite3, pandas as pd
    conn = sqlite3.connect(self.db_path)
    all_symbols = list(set([data_target] + db_factors))
    placeholders = ",".join(["?"] * len(all_symbols))
    query = f"SELECT symbol, timestamp_utc, open FROM market_bars WHERE timeframe = 'M5' AND symbol IN ({placeholders}) AND timestamp_utc >= ? AND timestamp_utc < ? ORDER BY timestamp_utc"
    start = f"{session_date}T00:00:00Z"
    end_dt = datetime.datetime.fromisoformat(session_date) + datetime.timedelta(days=1)
    end = end_dt.strftime("%Y-%m-%dT00:00:00Z")
    df = pd.read_sql_query(query, conn, params=all_symbols + [start, end])
    conn.close()
    
    if df.empty: return "EXIT 1: DF empty"
    
    df["timestamp"] = pd.to_datetime(df["timestamp_utc"])
    df["hour"] = df["timestamp"].dt.hour
    
    target_hours = df[df["symbol"] == data_target]["hour"].value_counts()
    print("TARGET HOURS LENGTH:", len(target_hours))
    if target_hours.empty: return "EXIT 2: target_hours empty"
    
    session_start = cfg.get("session_start_h", 0)
    session_end = cfg.get("session_end_h", 24)
    print("Mask:", session_start, session_end)
    session_mask = (df["hour"] >= session_start) & (df["hour"] <= session_end)
    df = df[session_mask]
    
    opens = {}
    for sym in all_symbols:
        sym_bars = df[df["symbol"] == sym].sort_values("timestamp")
        if len(sym_bars) > 0: opens[sym] = float(sym_bars.iloc[0]["open"])
        
    print("OPENS SYMBOLS:", list(opens.keys()))
    if data_target not in opens: return "EXIT 3: data_target not in opens"
    
    return "SUCCESS: Made it past checks!"

print(trace_compute(e, today, target))
