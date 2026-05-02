import sqlite3
import pandas as pd
import numpy as np
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "irai.db")

def main():
    conn = sqlite3.connect(DB_PATH)
    
    # Load all M5 bars
    df = pd.read_sql_query(
        "SELECT symbol, timestamp_utc, close FROM market_bars WHERE timeframe='M5'",
        conn,
    )
    conn.close()

    # Pivot to get timestamps as index and symbols as columns
    df_pivot = df.pivot_table(index="timestamp_utc", columns="symbol", values="close")
    
    # We want to calculate the correlation of M5 returns, not prices!
    # Because prices are non-stationary. Wait, the daily script calculated the correlation of daily returns.
    # So we should calculate the correlation of M5 returns.
    returns = df_pivot.pct_change().dropna(how="all")
    
    target = "US500"
    if target not in returns.columns:
        print(f"Target {target} not found")
        return

    # Drop NA for pairwise correlation
    print(f"--- Correlação Pura M5 (Retornos) para {target} ---")
    corrs = {}
    for col in returns.columns:
        if col == target: continue
        # Pairwise dropna to maximize data
        pair = returns[[target, col]].dropna()
        if len(pair) > 100:
            c = np.corrcoef(pair[target], pair[col])[0, 1]
            corrs[col] = abs(c)
            
    # Sort and print
    sorted_factors = sorted(corrs.keys(), key=lambda x: corrs[x], reverse=True)
    for f in sorted_factors:
        print(f"{f:10s} : {corrs[f]:.4f}")

if __name__ == "__main__":
    main()
