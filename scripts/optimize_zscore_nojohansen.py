import sqlite3
import os
import sys
import time
import csv
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from pykalman import KalmanFilter
from statsmodels.tsa.vector_ar.vecm import coint_johansen
import argparse
import multiprocessing as mp

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from backend.db import DB_PATH, get_connection
from backend.irai.engine import IRAIEngine

def precompute_single_johansen(args):
    prices_matrix, jl = args
    arr = np.zeros(len(prices_matrix), dtype=bool)
    for i in range(jl, len(prices_matrix)):
        if i % 3 != 0 and i > jl:
            arr[i] = arr[i-1]
            continue
        window = prices_matrix[i - jl : i]
        if np.var(window, axis=0).min() < 1e-10:
            arr[i] = True
            continue
        try:
            result = coint_johansen(window, -1, 1)
            arr[i] = result.lr1[0] > result.cvt[0, 1]
        except Exception:
            arr[i] = True
    return jl, arr

def load_data(target, engine, days_back=90):
    try:
        cfg = engine._get_model_config(target)[4]
        data_target = cfg.get("data_proxy") or target
        factors = cfg["factors"]
        symbols = [data_target] + factors
    except Exception as e:
        print(f"[{target}] Erro ao ler config: {e}")
        return None, None, None

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
        return None, None, None

    df = pd.DataFrame(rows, columns=['symbol', 'timestamp_utc', 'close'])
    df['close'] = df['close'].astype(float)
    df_pivot = df.pivot(index='timestamp_utc', columns='symbol', values='close').dropna()

    if df_pivot.empty:
        return None, None, None

    return df_pivot, data_target, factors

def run_simulation(args):
    y, X_raw, trans_cov, joh_lookback, sig_lookback, z_entry, z_exit, coint_array = args
    
    # Adicionar intercept
    X = np.column_stack([np.ones(len(X_raw)), X_raw])
    
    # Kalman
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
    
    cum_pnl = 0.0
    max_cum_pnl = 0.0
    max_dd = 0.0
    pending_fwd_checks = []
    fwd5_returns = []
    
    in_trade = 0
    entry_price_y = 0.0
    entry_price_X = None
    entry_beta = None
    
    start_idx = max(joh_lookback, sig_lookback)
    for i in range(start_idx, len(y)):
        total_time += 1
        
        # Verificar retornos 5 barras apos ENTRADA
        active_pending = []
        for p in pending_fwd_checks:
            if i >= p['target_bar']:
                pnl_y = current_y - p['entry_y']
                pnl_x = np.dot(p['entry_beta'], current_X - p['entry_X'])
                spread_diff = pnl_y - pnl_x if p['direction'] == 1 else pnl_x - pnl_y
                fwd5_returns.append(spread_diff)
            else:
                active_pending.append(p)
        pending_fwd_checks = active_pending

        # Johansen bypass (Ablation Test)
        is_coint = True
        if is_coint:
            cointegration_time += 1
            
        current_y = y[i]
        current_X = X[i]
        beta = state_means[i]
        pred_y = np.dot(current_X, beta)
        residual = current_y - pred_y
        
        # Sigma
        res_window = []
        for j in range(i - sig_lookback, i):
            pred_j = np.dot(X[j], state_means[j])
            res_window.append(y[j] - pred_j)
        std_res = np.std(res_window)
        z_score = (residual / std_res) if std_res > 0 else 0
            
        # Trade Logic
        if is_coint:
            if in_trade == 0:
                if z_score >= z_entry:
                    in_trade = -1
                    entry_price_y = current_y
                    entry_price_X = current_X
                    entry_beta = beta
                    trades += 1
                    pending_fwd_checks.append({
                        'target_bar': i + 5,
                        'direction': -1,
                        'entry_y': current_y,
                        'entry_X': current_X,
                        'entry_beta': beta
                    })
                elif z_score <= -z_entry:
                    in_trade = 1
                    entry_price_y = current_y
                    entry_price_X = current_X
                    entry_beta = beta
                    trades += 1
                    pending_fwd_checks.append({
                        'target_bar': i + 5,
                        'direction': 1,
                        'entry_y': current_y,
                        'entry_X': current_X,
                        'entry_beta': beta
                    })
            else:
                if (in_trade == 1 and z_score >= -z_exit) or (in_trade == -1 and z_score <= z_exit):
                    # Calcular PnL Real da perna Y e X usando os pesos da entrada
                    pnl_y = current_y - entry_price_y
                    pnl_x = np.dot(entry_beta, current_X - entry_price_X)
                    spread_pnl = pnl_y - pnl_x if in_trade == 1 else pnl_x - pnl_y
                    
                    cum_pnl += spread_pnl
                    if cum_pnl > max_cum_pnl: max_cum_pnl = cum_pnl
                    dd = max_cum_pnl - cum_pnl
                    if dd > max_dd: max_dd = dd
                    
                    if spread_pnl > 0:
                        wins += 1
                    else:
                        losses += 1
                        
                    in_trade = 0
        else:
            if in_trade != 0:
                # Force exit
                pnl_y = current_y - entry_price_y
                pnl_x = np.dot(entry_beta, current_X - entry_price_X)
                spread_pnl = pnl_y - pnl_x if in_trade == 1 else pnl_x - pnl_y
                
                cum_pnl += spread_pnl
                if cum_pnl > max_cum_pnl: max_cum_pnl = cum_pnl
                dd = max_cum_pnl - cum_pnl
                if dd > max_dd: max_dd = dd
                
                if spread_pnl > 0:
                    wins += 1
                else:
                    losses += 1
                    
                in_trade = 0
                
    coint_ratio = cointegration_time / total_time if total_time > 0 else 0
    win_rate = wins / trades if trades > 0 else 0
    
    # Penalizar poucos trades e trades demais (evitar overfitting de ruidos)
    # Target: approx 1 trade/day -> 90 trades in 90 days
    if trades < 30:
        penalty = trades / 30.0
    elif trades > 500:
        penalty = 500.0 / trades
    else:
        penalty = 1.0
        
    fwd5_gains = [r for r in fwd5_returns if r > 0]
    fwd5_losses = [r for r in fwd5_returns if r <= 0]
    
    avg_gain_5b = np.mean(fwd5_gains) if len(fwd5_gains) > 0 else 0.0
    avg_loss_5b = np.mean(fwd5_losses) if len(fwd5_losses) > 0 else 0.0
    win_rate_5b = len(fwd5_gains) / len(fwd5_returns) if len(fwd5_returns) > 0 else 0.0
    
    ret_dd = cum_pnl / max_dd if max_dd > 0 else (cum_pnl if cum_pnl > 0 else 0.0)
    
    profit_factor = wins / max(1, losses)
    fitness = win_rate * coint_ratio * penalty * profit_factor
    
    return {
        'trans_cov': trans_cov,
        'joh_lookback': joh_lookback,
        'sig_lookback': sig_lookback,
        'z_entry': z_entry,
        'z_exit': z_exit,
        'coint_ratio': coint_ratio,
        'win_rate': win_rate,
        'trades': trades,
        'profit_factor': profit_factor,
        'net_pnl': cum_pnl,
        'ret_dd': ret_dd,
        'win_rate_5b': win_rate_5b,
        'avg_gain_5b': avg_gain_5b,
        'avg_loss_5b': avg_loss_5b,
        'fitness': fitness
    }

def optimize_phase1(target, df_pivot, data_target, factors):
    print(f"[{target}] Iniciando Fase 1 (Core)...")
    trans_covs = [1e-3, 1e-4, 1e-5]
    joh_lookbacks = [50, 100, 150]
    sig_lookbacks = [20, 50, 100]
    
    y = df_pivot[data_target].values
    X = df_pivot[factors].values
    prices_matrix = np.column_stack([y, X])
    
    cores = max(1, mp.cpu_count() - 2)
    
    print(f"[{target}] Ignorando Johansen (Ablation)...")
    coint_dict = {}
    dummy_arr = np.ones(len(prices_matrix), dtype=bool)
    for jl in joh_lookbacks:
        coint_dict[jl] = dummy_arr
    
    tasks = []
    for tc in trans_covs:
        for jl in joh_lookbacks:
            for sl in sig_lookbacks:
                tasks.append((y, X, tc, jl, sl, 1.5, 0.5, coint_dict[jl]))
                
    with mp.Pool(cores) as pool:
        results = pool.map(run_simulation, tasks)
        
    results.sort(key=lambda x: x['fitness'], reverse=True)
    best = results[0]
    print(f"[{target}] Fase 1 Melhor: Cov={best['trans_cov']}, Joh={best['joh_lookback']}, Sig={best['sig_lookback']} (Fit: {best['fitness']:.4f})")
    return best

def main():
    engine = IRAIEngine()
    targets = [t["target"] for t in engine.registered_targets if t.get("accuracy")]
    
    print(f"Iniciando Otimização V2 para {len(targets)} ativos. Puxando 90 dias M5...")
    
    phase1_results = []
    
    for t in targets:
        df_pivot, data_target, factors = load_data(t, engine, days_back=90)
        if df_pivot is None:
            print(f"[{t}] Sem dados suficientes, pulando.")
            continue
            
        best_p1 = optimize_phase1(t, df_pivot, data_target, factors)
        best_p1['target'] = t
        phase1_results.append(best_p1)
        
    # Salvar Phase 1 No Johansen
    df_p1 = pd.DataFrame(phase1_results)
    df_p1.to_csv('zscore_nojohansen_results.csv', index=False)
    print("Fase 1 (Sem Johansen) completa. Salvo em zscore_nojohansen_results.csv")

if __name__ == "__main__":
    mp.freeze_support()
    main()
