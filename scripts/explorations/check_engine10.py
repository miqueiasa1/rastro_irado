import sys
sys.path.insert(0, '.')
from backend.irai.engine import IRAIEngine
import datetime
today = datetime.date.today().isoformat()
e = IRAIEngine()

target = 'WDO$N'

# Copy the exact code from compute_from_db to find where it exits
def trace(self, session_date, target):
    session_date = session_date or datetime.date.today().isoformat()
    t_weights, t_sigmas, t_alpha, t_intercept, cfg = self._get_model_config(target)
    active_factors = cfg["factors"]
    active_labels = cfg["labels"]
    self.factor_states = {}
    for symbol, label in active_labels.items():
        self.factor_states[label] = {"symbol": symbol, "label": label}
        
    data_target = cfg.get("data_proxy") or target
    factor_to_db = {f: f for f in active_factors}
    db_factors = list(set(factor_to_db.values()))
    db_to_factor = {v: k for k, v in factor_to_db.items()}
    
    import sqlite3, pandas as pd
    conn = sqlite3.connect(self.db_path)
    all_symbols = list(set([data_target] + db_factors))
    placeholders = ",".join(["?"] * len(all_symbols))
    query = f"SELECT symbol, timestamp_utc, open, high, low, close, real_volume, delta FROM market_bars WHERE timeframe = 'M5' AND symbol IN ({placeholders}) AND timestamp_utc >= ? AND timestamp_utc < ? ORDER BY timestamp_utc"
    start = f"{session_date}T00:00:00Z"
    end_dt = datetime.datetime.fromisoformat(session_date) + datetime.timedelta(days=1)
    end = end_dt.strftime("%Y-%m-%dT00:00:00Z")
    df = pd.read_sql_query(query, conn, params=all_symbols + [start, end])
    conn.close()
    
    if df.empty: return "EXIT 1: df empty"
    
    df["timestamp"] = pd.to_datetime(df["timestamp_utc"])
    df["hour"] = df["timestamp"].dt.hour
    
    session_start = cfg.get("session_start_h", 0)
    session_end = cfg.get("session_end_h", 24)
    duration_h = session_end - session_start
    if duration_h <= 0: duration_h += 24
    
    target_hours = df[df["symbol"] == data_target]["hour"].value_counts()
    if target_hours.empty: return "EXIT 2: target hours empty"
    
    session_mask = (df["hour"] >= session_start) & (df["hour"] <= session_end)
    df = df[session_mask]
    
    opens = {}
    for sym in all_symbols:
        sym_bars = df[df["symbol"] == sym].sort_values("timestamp")
        if len(sym_bars) > 0: opens[sym] = float(sym_bars.iloc[0]["open"])
        
    if data_target not in opens: return "EXIT 3: data_target not in opens"
    
    factor_prices = {}
    for factor in active_factors:
        db_sym = factor_to_db.get(factor, factor)
        fb = df[df["symbol"] == db_sym].sort_values("timestamp")
        if len(fb) > 0: factor_prices[factor] = list(zip(fb["timestamp"], fb["close"].astype(float)))
        else: factor_prices[factor] = []
        
    target_bars = df[df["symbol"] == data_target].sort_values("timestamp")
    n_bars = len(target_bars)
    
    snapshots = []
    return f"EXIT END: loop ran for {n_bars} target bars"

print(trace(e, today, target))
