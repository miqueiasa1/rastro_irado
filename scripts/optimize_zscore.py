import sqlite3
import os
import sys
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from pykalman import KalmanFilter
from statsmodels.tsa.vector_ar.vecm import coint_johansen
import argparse

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from backend.db import DB_PATH, get_connection
from backend.irai.engine import IRAIEngine

def johansen_cointegration_test(y, det_order=-1, k_ar_diff=1):
    try:
        result = coint_johansen(y, det_order, k_ar_diff)
        trace_stat = result.lr1[0]
        crit_val_95 = result.cvt[0, 1]
        is_coint = trace_stat > crit_val_95
        p_value = 0.01 if is_coint else 0.5
        return p_value, is_coint
    except Exception:
        return 1.0, False

def load_data(target, engine, days_back=60):
    cfg = engine._get_model_config(target)[4]
    data_target = cfg.get("data_proxy") or target
    factors = cfg["factors"]
    symbols = [data_target] + factors

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    
    conn = get_connection(DB_PATH)
    placeholders = ",".join(["?"] * len(symbols))
    query = f"""
        SELECT symbol, timestamp_utc, close 
        FROM market_bars 
        WHERE timeframe = 'M5' AND symbol IN ({placeholders})
        AND timestamp_utc >= ? AND timestamp_utc <= ?
        ORDER BY timestamp_utc
    """
    rows = conn.execute(query, symbols + [start_date.isoformat() + "Z", end_date.isoformat() + "Z"]).fetchall()
    conn.close()

    if not rows:
        print(f"No data found for {target} and factors.")
        return None, None

    # Pivot table to get a continuous time series
    df = pd.DataFrame(rows, columns=['symbol', 'timestamp_utc', 'close'])
    df['close'] = df['close'].astype(float)
    df_pivot = df.pivot(index='timestamp_utc', columns='symbol', values='close').dropna()

    if df_pivot.empty:
        print(f"No overlapping data found for {target} and factors.")
        return None, None

    return df_pivot, data_target, factors

def run_simulation(df, target_symbol, factors, trans_cov, lookback):
    y = df[target_symbol].values
    X = df[factors].values
    
    # Initialize Kalman
    delta = trans_cov
    trans_cov_mat = delta / (1 - delta) * np.eye(X.shape[1])
    kf = KalmanFilter(
        n_dim_obs=1,
        n_dim_state=X.shape[1],
        initial_state_mean=np.zeros(X.shape[1]),
        initial_state_covariance=np.ones((X.shape[1], X.shape[1])),
        transition_matrices=np.eye(X.shape[1]),
        observation_matrices=X.reshape(X.shape[0], 1, X.shape[1]),
        observation_covariance=1.0,
        transition_covariance=trans_cov_mat
    )
    
    state_means, _ = kf.filter(y)
    
    cointegration_time = 0
    total_time = 0
    trades = 0
    wins = 0
    losses = 0
    
    in_trade = 0 # 1 for long spread, -1 for short spread
    
    prices_matrix = np.column_stack([y, X])
    
    for i in range(lookback, len(y)):
        total_time += 1
        
        # Johansen
        window = prices_matrix[i - lookback : i]
        _, is_coint = johansen_cointegration_test(window)
        if is_coint:
            cointegration_time += 1
            
        # Z-Score approximation
        current_y = y[i]
        current_X = X[i]
        beta = state_means[i]
        pred_y = np.dot(current_X, beta)
        residual = current_y - pred_y
        
        # Calculate rolling std of residuals over the lookback window
        if i >= lookback:
            res_window = []
            for j in range(i - lookback, i):
                pred_j = np.dot(X[j], state_means[j])
                res_window.append(y[j] - pred_j)
            std_res = np.std(res_window)
            if std_res > 0:
                z_score = residual / std_res
            else:
                z_score = 0
        else:
            z_score = 0
            
        # Trade Logic
        if is_coint:
            if in_trade == 0:
                if z_score >= 2.0:
                    in_trade = -1
                    trades += 1
                elif z_score <= -2.0:
                    in_trade = 1
                    trades += 1
            else:
                # Check for exit
                if (in_trade == 1 and z_score >= 0) or (in_trade == -1 and z_score <= 0):
                    wins += 1
                    in_trade = 0
        else:
            # Force exit if cointegration lost
            if in_trade != 0:
                # We consider it a loss if we forced exit due to coint loss
                losses += 1
                in_trade = 0
                
    coint_ratio = cointegration_time / total_time if total_time > 0 else 0
    win_rate = wins / trades if trades > 0 else 0
    
    # Fitness Function
    penalty = 1.0 if trades >= 5 else (trades / 5.0)
    fitness = win_rate * coint_ratio * penalty
    
    return {
        'trans_cov': trans_cov,
        'lookback': lookback,
        'coint_ratio': coint_ratio,
        'win_rate': win_rate,
        'trades': trades,
        'fitness': fitness
    }

def optimize_target(target):
    print(f"\\n--- Optimizing {target} ---")
    engine = IRAIEngine()
    
    df_info = load_data(target, engine, days_back=90) # 3 months back
    if df_info[0] is None:
        return
    df_pivot, data_target, factors = df_info
    
    print(f"Loaded {len(df_pivot)} continuous M5 bars for {data_target} and {len(factors)} factors.")
    
    trans_covs = [1e-4]
    lookbacks = [50, 100, 200]
    
    results = []
    
    total_runs = len(trans_covs) * len(lookbacks)
    run = 1
    for trans_cov in trans_covs:
        for lookback in lookbacks:
            print(f"Running [{run}/{total_runs}] cov={trans_cov}, lookback={lookback}...")
            res = run_simulation(df_pivot, data_target, factors, trans_cov, lookback)
            results.append(res)
            run += 1
            
    # Sort by fitness
    results.sort(key=lambda x: x['fitness'], reverse=True)
    
    print("\\n=== OPTIMIZATION RESULTS ===")
    print(f"{'Cov':<8} | {'Lookback':<8} | {'Coint %':<8} | {'Win %':<8} | {'Trades':<6} | {'Fitness':<8}")
    print("-" * 60)
    for r in results:
        print(f"{r['trans_cov']:<8} | {r['lookback']:<8} | {r['coint_ratio']:.2%} | {r['win_rate']:.2%} | {r['trades']:<6} | {r['fitness']:.4f}")
        
    best = results[0]
    print(f"\\nBEST: Cov={best['trans_cov']}, Lookback={best['lookback']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Optimize IRAI Z-Score Parameters')
    parser.add_argument('--target', type=str, default='WIN$N', help='Target symbol to optimize')
    parser.add_argument('--all', action='store_true', help='Optimize all registered targets')
    
    args = parser.parse_args()
    
    if args.all:
        engine = IRAIEngine()
        for t in engine.registered_targets:
            if t.get("accuracy"):
                optimize_target(t["target"])
    else:
        optimize_target(args.target)
