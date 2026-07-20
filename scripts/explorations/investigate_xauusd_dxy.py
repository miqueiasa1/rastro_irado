import sqlite3
import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calibrate_universal
from calibrate_universal import load_daily_returns, ALL_FACTORS, DB_PATH

def analyze():
    conn = sqlite3.connect(DB_PATH)
    daily = load_daily_returns(conn, 0, 24)
    
    if "XAUUSD" not in daily or "DXY" not in daily:
        print("Missing data for XAUUSD or DXY")
        return
        
    xau = daily["XAUUSD"].rename("XAUUSD")
    df = pd.DataFrame({"XAUUSD": xau})
    
    for f in ALL_FACTORS:
        if f in daily and f != "XAUUSD":
            df[f] = daily[f]
            
    df = df.dropna().iloc[-252:]
    
    print(f"Data shape: {df.shape}")
    
    # Calculate correlations with XAUUSD
    corrs = df.corr()["XAUUSD"].sort_values(ascending=False)
    print("\n--- Correlations with XAUUSD ---")
    print(corrs)
    
    # Calculate directional accuracy of DXY alone on XAUUSD
    y_ret = df["XAUUSD"].values
    dxy_ret = df["DXY"].values
    
    # Are they inverse? Usually gold and USD are inversely correlated.
    # Let's check DXY beta
    Xb = np.column_stack([dxy_ret, np.ones(len(dxy_ret))])
    beta = np.linalg.lstsq(Xb, y_ret, rcond=None)[0]
    yp = Xb @ beta
    acc = np.mean((yp > 0) == (y_ret > 0))
    r2 = 1 - np.sum((y_ret - yp)**2) / np.sum((y_ret - y_ret.mean())**2)
    score = (acc * 0.7) + (max(0, r2) * 0.3)
    
    print(f"\n--- DXY Alone vs XAUUSD ---")
    print(f"Beta: {beta[0]:.6f}")
    print(f"R2: {r2:.4f}")
    print(f"Acc: {acc:.1%}")
    print(f"Score: {score:.4f}")
    
    # Current best factors from FACTOR_MAP.md
    current_best = ["AUDNZD", "AUDUSD", "USDMXN", "USDCHF", "EURGBP", "VIX", "CHINA50", "BRENT"]
    X_best = df[current_best].values
    Xb_best = np.column_stack([X_best, np.ones(len(X_best))])
    beta_best = np.linalg.lstsq(Xb_best, y_ret, rcond=None)[0]
    yp_best = Xb_best @ beta_best
    acc_best = np.mean((yp_best > 0) == (y_ret > 0))
    r2_best = 1 - np.sum((y_ret - yp_best)**2) / np.sum((y_ret - y_ret.mean())**2)
    score_best = (acc_best * 0.7) + (max(0, r2_best) * 0.3)
    
    print(f"\n--- Current Best 8 Factors (from FACTOR_MAP.md) ---")
    print(f"R2: {r2_best:.4f}")
    print(f"Acc: {acc_best:.1%}")
    print(f"Score: {score_best:.4f}")

    # Substitute one factor with DXY to see if it improves
    print("\n--- Substituting factors with DXY ---")
    for i in range(len(current_best)):
        test_factors = current_best.copy()
        test_factors[i] = "DXY"
        
        X_test = df[test_factors].values
        Xb_test = np.column_stack([X_test, np.ones(len(X_test))])
        beta_test = np.linalg.lstsq(Xb_test, y_ret, rcond=None)[0]
        yp_test = Xb_test @ beta_test
        acc_test = np.mean((yp_test > 0) == (y_ret > 0))
        r2_test = 1 - np.sum((y_ret - yp_test)**2) / np.sum((y_ret - y_ret.mean())**2)
        score_test = (acc_test * 0.7) + (max(0, r2_test) * 0.3)
        
        diff = score_test - score_best
        print(f"Replace {current_best[i]:10s} with DXY -> Acc: {acc_test:.1%}, R2: {r2_test:.4f}, Score: {score_test:.4f} (Diff: {diff:+.4f})")
        
    # Check multicollinearity of DXY with the best factors
    print("\n--- Correlation of DXY with Current Best Factors ---")
    dxy_corrs = df[current_best + ["DXY"]].corr()["DXY"].drop("DXY").sort_values(ascending=False)
    print(dxy_corrs)

if __name__ == '__main__':
    analyze()
