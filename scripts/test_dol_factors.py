"""
Brute-force para DOL/WDO como TARGET.
Testa combos de 4-8 fatores para encontrar modelo robusto.
Usa DOL$N como proxy (cotação idêntica ao WDO$N).
"""
import sqlite3, os, itertools
import pandas as pd
import numpy as np

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "irai.db")
conn = sqlite3.connect(DB)

TARGET = "DOL$N"  # proxy para WDO$N (cotação idêntica)

# Carregar todos os dados
df = pd.read_sql_query(
    "SELECT symbol, timestamp_utc, open, close FROM market_bars WHERE timeframe='M5'", conn)
conn.close()

df["timestamp"] = pd.to_datetime(df["timestamp_utc"])
df["hour"] = df["timestamp"].dt.hour
df["date"] = df["timestamp"].dt.date

# Sessão B3
mode_h = df[df["symbol"] == TARGET]["hour"].mode()
h0, h1 = (10, 18) if mode_h.iloc[0] < 13 else (13, 21)
df = df[(df["hour"] >= h0) & (df["hour"] < h1)]

# Retornos diários
ALL_SYMS = ["WIN$N", "DI1$N", "DXY", "BRENT", "CHINA50", "USDMXN",
            "VIX", "US500", "BTCUSD", "DE40"]

daily = {}
for sym in [TARGET] + ALL_SYMS:
    s = df[df["symbol"] == sym].sort_values("timestamp")
    d = s.groupby("date").agg(o=("open", "first"), c=("close", "last"), n=("close", "count"))
    d = d[d["n"] >= 20]
    d["ret"] = (d["c"] - d["o"]) / d["o"]
    daily[sym] = d["ret"]

merged = pd.DataFrame(daily).dropna(subset=[TARGET])
merged = merged.iloc[-252:]

# Correlações
print("=== CORRELACAO COM DOL/WDO (252 sessoes) ===")
corrs = []
for sym in ALL_SYMS:
    if sym in merged.columns:
        sub = merged[[TARGET, sym]].dropna()
        if len(sub) >= 50:
            c = sub[TARGET].corr(sub[sym])
            corrs.append((sym, c, len(sub)))
corrs.sort(key=lambda x: abs(x[1]), reverse=True)
for sym, c, n in corrs:
    print(f"  {sym:15s} corr={c:+.4f} ({n} obs)")

# Selecionar candidatos com |corr| > 0.05
CANDIDATES = [sym for sym, c, n in corrs if abs(c) > 0.05]
print(f"\n{len(CANDIDATES)} candidatos: {', '.join(CANDIDATES)}")

# Brute-force: testar combos de 3 a 8 fatores
results = []
for r in range(3, min(len(CANDIDATES) + 1, 9)):
    for combo in itertools.combinations(CANDIDATES, r):
        factors = list(combo)
        sub = merged[[TARGET] + factors].dropna()
        if len(sub) < 50:
            continue
        X = sub[factors].values
        y = sub[TARGET].values
        Xb = np.column_stack([X, np.ones(len(X))])
        try:
            beta = np.linalg.lstsq(Xb, y, rcond=None)[0]
        except:
            continue
        yp = Xb @ beta
        ss_res = np.sum((y - yp) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        correct = np.sum((yp > 0) == (y > 0))
        acc = correct / len(y)
        
        # Coeficientes e sinais
        weights = {f: beta[i] for i, f in enumerate(factors)}
        
        results.append({
            "factors": "+".join(factors),
            "n": len(factors),
            "r2": r2,
            "acc": acc,
            "n_obs": len(sub),
            "weights": weights,
        })

results.sort(key=lambda x: x["acc"], reverse=True)

# Mostrar resultados por faixa
print(f"\n{'='*90}")
print(f"TOTAL: {len(results)} combinações testadas")
print(f"{'='*90}")

# Top por número de fatores
for nf in range(3, 9):
    subset = [r for r in results if r["n"] == nf]
    if not subset:
        continue
    best = subset[0]
    print(f"\n--- MELHOR COM {nf} FATORES ---")
    print(f"  {best['factors']}")
    print(f"  ACC={best['acc']:.1%}  R²={best['r2']:.4f}  OBS={best['n_obs']}")

print(f"\n{'='*90}")
print(f"TOP 30 GERAL POR ACURACIA")
print(f"{'='*90}")
print(f"{'#':<4} {'ACC':>6} {'R2':>7} {'N':>3} {'OBS':>5} {'FATORES'}")
print("-" * 90)
for i, r in enumerate(results[:30]):
    print(f"{i+1:<4} {r['acc']:>5.1%} {r['r2']:>7.4f} {r['n']:>3} {r['n_obs']:>5} {r['factors']}")

# Detalhar top 5
print(f"\n{'='*90}")
print(f"DETALHES DOS TOP 5")
print(f"{'='*90}")
for i, r in enumerate(results[:5]):
    print(f"\n#{i+1}: {r['factors']}")
    print(f"  ACC={r['acc']:.1%} | R²={r['r2']:.4f} | {r['n_obs']} obs")
    for f, w in r['weights'].items():
        sym_corr = next((c for s, c, _ in corrs if s == f), 0)
        sign_ok = "✓" if (w > 0 and sym_corr > 0) or (w < 0 and sym_corr < 0) else "⚠"
        print(f"  {f:15s} w={w:+.6f} corr={sym_corr:+.4f} {sign_ok}")
