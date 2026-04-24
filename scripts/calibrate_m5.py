"""
IRAI — Calibração INTRADAY (M5).

Alinha barras M5 de todos os fatores à sessão B3 (10:00-17:55 BRT),
calcula z-scores normalizados por tempo, e estima pesos via
regressão sobre o retorno acumulado do WIN.

Uso: python scripts/calibrate_m5.py [--days 252]
"""

import sqlite3
import os
import sys
import json
import argparse
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from scipy.special import expit  # sigmoid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import get_connection, DB_PATH

os.environ["PYTHONIOENCODING"] = "utf-8"
warnings.filterwarnings("ignore", category=FutureWarning)

# ── Configuração ──────────────────────────────────────────
FACTORS = ["DOL$N", "DI1$N", "VIX", "DXY", "BRENT", "IV_ATM", "CHINA50", "USDMXN", "DE40"]
FACTOR_LABELS = {
    "DOL$N": "dol", "DI1$N": "di", "VIX": "vix",
    "DXY": "dxy", "BRENT": "brent", "IV_ATM": "iv",
    "CHINA50": "china", "USDMXN": "mxn", "DE40": "dax",
}
TARGET = "WIN$N"

EXPECTED_SIGNS = {
    "dol": -1, "di": -1, "vix": -1, "dxy": -1, "brent": +1, "iv": -1,
    "china": +1, "mxn": -1, "dax": +1,
}

# Sessão B3: 10:00 - 17:55 BRT = 13:00 - 20:55 UTC
# Barras M5: 96 barras por sessão (10:00, 10:05, ..., 17:50)
SESSION_START_UTC_HOUR = 13  # 10:00 BRT
SESSION_END_UTC_HOUR = 21    # 18:00 BRT (última barra 17:55 cai aqui)
BARS_PER_SESSION = 96


def load_m5_bars(conn: sqlite3.Connection) -> pd.DataFrame:
    """Carrega todas as barras M5 do banco."""
    symbols = [TARGET] + FACTORS
    placeholders = ",".join(["?"] * len(symbols))
    query = f"""
        SELECT symbol, timestamp_utc, open, high, low, close, volume
        FROM market_bars
        WHERE timeframe = 'M5' AND symbol IN ({placeholders})
        ORDER BY timestamp_utc
    """
    df = pd.read_sql_query(query, conn, params=symbols)
    df["timestamp"] = pd.to_datetime(df["timestamp_utc"])
    df["hour_utc"] = df["timestamp"].dt.hour
    df["date"] = df["timestamp"].dt.date
    print(f"  Total barras M5 carregadas: {len(df):,}")
    for sym in symbols:
        n = len(df[df["symbol"] == sym])
        print(f"    {sym:<12} {n:>8,} barras")
    return df


def detect_timezone(df: pd.DataFrame) -> str:
    """Detecta se timestamps estão em UTC ou BRT baseado na distribuição horária do WIN."""
    win_bars = df[df["symbol"] == TARGET]
    hour_counts = win_bars["hour_utc"].value_counts().sort_index()

    # Se a maioria das barras está entre 10-17, timestamps estão em BRT
    brt_range = hour_counts[(hour_counts.index >= 10) & (hour_counts.index < 18)].sum()
    utc_range = hour_counts[(hour_counts.index >= 13) & (hour_counts.index < 21)].sum()

    if brt_range > utc_range:
        print(f"  Timezone detectado: BRT (offset=-3)")
        return "BRT"
    else:
        print(f"  Timezone detectado: UTC")
        return "UTC"


def build_sessions(df: pd.DataFrame, tz: str) -> dict:
    """
    Agrupa barras por sessão B3.
    Retorna dict: date -> DataFrame com barras alinhadas.
    """
    if tz == "BRT":
        start_h, end_h = 10, 18
    else:
        start_h, end_h = 13, 21

    # Filtrar barras de pregão para o TARGET
    win_bars = df[(df["symbol"] == TARGET) &
                  (df["hour_utc"] >= start_h) &
                  (df["hour_utc"] < end_h)]

    session_dates = sorted(win_bars["date"].unique())
    print(f"  Sessoes detectadas: {len(session_dates)}")

    sessions = {}
    for date in session_dates:
        # Pegar barras do dia para todos os símbolos
        day_mask = (df["date"] == date) & (df["hour_utc"] >= start_h) & (df["hour_utc"] < end_h)
        day_bars = df[day_mask].copy()

        # Verificar se WIN tem barras suficientes
        win_count = len(day_bars[day_bars["symbol"] == TARGET])
        if win_count < 20:  # mínimo de barras para sessão válida
            continue

        sessions[date] = day_bars

    print(f"  Sessoes validas (>=20 barras WIN): {len(sessions)}")
    return sessions


def compute_session_features(sessions: dict, factors: list) -> pd.DataFrame:
    """
    Para cada sessão, computa features intraday:
    - Retorno acumulado de cada fator desde o open
    - Z-scores normalizados por tempo
    - Retorno final do WIN (alvo)
    """
    all_rows = []

    for date, bars in sessions.items():
        # Open de cada símbolo = primeira barra do dia
        opens = {}
        for sym in [TARGET] + factors:
            sym_bars = bars[bars["symbol"] == sym].sort_values("timestamp")
            if len(sym_bars) == 0:
                opens[sym] = None
            else:
                opens[sym] = sym_bars.iloc[0]["open"]

        if opens[TARGET] is None or opens[TARGET] == 0:
            continue

        # Verificar que temos opens para todos os fatores
        missing = [f for f in factors if opens.get(f) is None]
        if len(missing) > 2:  # tolerar até 2 fatores faltando
            continue

        # WIN: pegar close da última barra
        win_bars = bars[bars["symbol"] == TARGET].sort_values("timestamp")
        win_close = win_bars.iloc[-1]["close"]
        win_return = (win_close - opens[TARGET]) / opens[TARGET]
        win_up = 1 if win_return > 0 else 0

        # Para cada barra do WIN, computar z-scores dos fatores
        n_bars = len(win_bars)

        for bar_idx, (_, win_row) in enumerate(win_bars.iterrows()):
            t = (bar_idx + 1) / n_bars  # fração do dia [0, 1]
            if t == 0:
                continue

            row = {
                "date": date,
                "bar_idx": bar_idx,
                "t_frac": t,
                "timestamp": win_row["timestamp"],
                "win_return_current": (win_row["close"] - opens[TARGET]) / opens[TARGET],
                "win_return_final": win_return,
                "win_up": win_up,
            }

            # Computar z-scores para cada fator
            for factor in factors:
                label = FACTOR_LABELS[factor]
                if opens.get(factor) is None or opens[factor] == 0:
                    row[f"z_{label}"] = 0.0
                    row[f"ret_{label}"] = 0.0
                    continue

                # Encontrar barra do fator mais próxima desse timestamp
                factor_bars = bars[bars["symbol"] == factor].sort_values("timestamp")
                closest_mask = factor_bars["timestamp"] <= win_row["timestamp"]
                if closest_mask.sum() == 0:
                    row[f"z_{label}"] = 0.0
                    row[f"ret_{label}"] = 0.0
                    continue

                factor_close = factor_bars[closest_mask].iloc[-1]["close"]
                factor_return = (factor_close - opens[factor]) / opens[factor]
                row[f"ret_{label}"] = factor_return

                # Z-score: z = return / (sigma_daily * sqrt(t))
                # sigma será estimada a partir dos dados
                row[f"z_{label}"] = factor_return  # placeholder; normalizado depois

            all_rows.append(row)

    result = pd.DataFrame(all_rows)
    print(f"  Total observacoes (barra x sessao): {len(result):,}")
    return result


def estimate_intraday_sigmas(features: pd.DataFrame) -> dict:
    """Estima volatilidade intraday de cada fator."""
    sigmas = {}
    ret_cols = [c for c in features.columns if c.startswith("ret_")]

    print(f"\n  Volatilidades intraday (std dos retornos por barra):")
    for col in ret_cols:
        label = col.replace("ret_", "")
        # Filtrar última barra de cada sessão (retorno open-to-close)
        last_bars = features.groupby("date").last()
        sigma_session = last_bars[col].std()
        sigmas[label] = sigma_session if sigma_session > 0 else 0.001
        print(f"    {label:<12} sigma_sessao={sigma_session:.6f} ({sigma_session*100:.3f}%)")

    return sigmas


def normalize_zscores(features: pd.DataFrame, sigmas: dict) -> pd.DataFrame:
    """Normaliza retornos para z-scores: z = ret / (sigma * sqrt(t))."""
    df = features.copy()
    for label, sigma in sigmas.items():
        ret_col = f"ret_{label}"
        z_col = f"z_{label}"
        if ret_col in df.columns:
            # z = ret / (sigma * sqrt(t_frac))
            # Evitar divisão por zero para t_frac muito pequeno
            sqrt_t = np.sqrt(df["t_frac"].clip(lower=0.01))
            df[z_col] = df[ret_col] / (sigma * sqrt_t)
    return df


def calibrate_ols(features: pd.DataFrame, factor_labels: list) -> tuple:
    """
    OLS: retorno final do WIN ~ z-scores na última barra do dia.
    Usa apenas a observação final de cada sessão.
    """
    from sklearn.linear_model import LinearRegression

    # Usar última barra de cada sessão
    last_obs = features.groupby("date").last().reset_index()

    z_cols = [f"z_{label}" for label in factor_labels]
    available = [c for c in z_cols if c in last_obs.columns]

    X = last_obs[available].values
    y = last_obs["win_return_final"].values

    # Remover NaN/Inf
    mask = np.isfinite(X).all(axis=1) & np.isfinite(y)
    X = X[mask]
    y = y[mask]

    print(f"\n  OLS (end-of-day z-scores -> WIN return): {len(y)} sessoes")

    # Normalizar
    X_std = X.std(axis=0, keepdims=True)
    X_std[X_std == 0] = 1
    y_std = y.std()
    if y_std == 0:
        raise ValueError("WIN returns have zero variance!")

    X_norm = X / X_std
    y_norm = y / y_std

    model = LinearRegression(fit_intercept=True)
    model.fit(X_norm, y_norm)
    r_squared = model.score(X_norm, y_norm)

    print(f"  R² = {r_squared:.4f}")

    weights = {}
    for i, col in enumerate(available):
        label = col.replace("z_", "")
        w = model.coef_[i]
        expected = EXPECTED_SIGNS.get(label, 0)
        sign_ok = (w * expected > 0) if expected != 0 else True
        check = "OK" if sign_ok else "INVERTIDO!"
        weights[f"w_{label}"] = float(w)
        print(f"    {label:<12} w={w:>+8.4f}  esperado={'+'if expected>0 else '-'}  {check}")

    return weights, r_squared


def calibrate_alpha_m5(features: pd.DataFrame, weights: dict) -> tuple:
    """
    Logística M5: P(up_final) = sigmoid(alpha * score(t)).
    Usa TODAS as barras, não só end-of-day.
    """
    from sklearn.linear_model import LogisticRegression

    z_cols = [f"z_{k.replace('w_', '')}" for k in weights.keys()]
    available = [c for c in z_cols if c in features.columns]

    # Computar score para cada observação
    scores = np.zeros(len(features))
    for col in available:
        label = col.replace("z_", "")
        w_key = f"w_{label}"
        if w_key in weights:
            scores += weights[w_key] * features[col].fillna(0).values

    features_copy = features.copy()
    features_copy["score"] = scores

    # Remover NaN/Inf
    mask = np.isfinite(scores) & features_copy["win_up"].notna()
    X = scores[mask].reshape(-1, 1)
    y = features_copy.loc[mask, "win_up"].values.astype(int)

    print(f"\n  Logistica M5: {len(y):,} observacoes (todas as barras)")

    # Subsampling: usar 1 barra a cada 6 (30 min) para reduzir autocorrelação
    subsample = np.arange(0, len(X), 6)
    X_sub = X[subsample]
    y_sub = y[subsample]
    print(f"  Subsample (1/6): {len(y_sub):,} observacoes")

    lr = LogisticRegression(fit_intercept=True, solver="lbfgs", max_iter=1000)
    lr.fit(X_sub, y_sub)

    alpha = float(lr.coef_[0][0])
    intercept = float(lr.intercept_[0])
    accuracy = lr.score(X_sub, y_sub)

    print(f"  alpha = {alpha:.4f}")
    print(f"  intercept = {intercept:.4f}")
    print(f"  Acuracia direcional = {accuracy:.1%}")

    # Reliability por bucket
    probs = expit(alpha * X_sub.ravel() + intercept) * 100
    print(f"\n  Reliability por bucket:")
    for lo, hi in [(0, 25), (25, 40), (40, 60), (60, 75), (75, 100)]:
        bucket_mask = (probs >= lo) & (probs < hi)
        if bucket_mask.sum() > 5:
            obs_rate = y_sub[bucket_mask].mean()
            print(f"    P_up [{lo:>3}-{hi:>3}%]: {bucket_mask.sum():>5} obs, "
                  f"taxa real de alta: {obs_rate:.1%}")

    # Análise por fração do dia (t)
    features_copy["p_up"] = expit(alpha * scores + intercept) * 100
    print(f"\n  Discriminacao por hora do dia:")
    features_copy["hour_slot"] = (features_copy["t_frac"] * 8).astype(int)  # 8 slots (~1h cada)
    for slot in range(8):
        slot_data = features_copy[features_copy["hour_slot"] == slot]
        if len(slot_data) > 0:
            # Correlação entre P_up e resultado real
            corr = slot_data[["p_up", "win_up"]].corr().iloc[0, 1]
            mean_pup = slot_data["p_up"].mean()
            actual_up = slot_data["win_up"].mean()
            hour_approx = 10 + slot
            print(f"    ~{hour_approx:02d}:00 BRT: P_up_medio={mean_pup:.1f}%, "
                  f"real_up={actual_up:.1%}, corr={corr:.3f}")

    return alpha, intercept, accuracy


def save_params_m5(conn, weights, sigmas, alpha, intercept, r_squared, accuracy):
    """Grava parâmetros M5 no banco."""
    effective = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor = conn.cursor()

    all_params = {**weights, "alpha": alpha, "intercept": intercept}
    for label, sigma in sigmas.items():
        all_params[f"sigma_{label}_session"] = sigma

    for name, value in all_params.items():
        cursor.execute(
            "INSERT OR REPLACE INTO model_params (param_name, value, effective_from) VALUES (?, ?, ?)",
            (name, value, effective),
        )

    cursor.execute(
        """INSERT OR REPLACE INTO calibration_log
           (calibration_date, window_days, r_squared, params_json, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (effective, 0, r_squared,
         json.dumps(all_params, indent=2),
         f"Calibracao M5 intraday | acc={accuracy:.1%}"),
    )
    conn.commit()
    print(f"\n  Parametros M5 salvos (effective_from={effective})")
    return all_params


def generate_report_m5(weights, sigmas, alpha, intercept, r_squared, accuracy,
                       n_sessions, factor_labels):
    """Gera relatório markdown."""
    report = f"""# IRAI — Calibração Intraday (M5)

**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Sessões analisadas:** {n_sessions}
**R² (OLS end-of-day):** {r_squared:.4f}
**Alpha:** {alpha:.4f}
**Intercept:** {intercept:.4f}
**Acurácia direcional:** {accuracy:.1%}

## Fatores (5 fatores finais)

| Fator | Peso | Sinal Esperado | σ sessão |
|-------|------|----------------|----------|
"""
    for label in factor_labels:
        w = weights.get(f"w_{label}", 0)
        expected = EXPECTED_SIGNS.get(label, 0)
        sign_ok = (w * expected > 0) if expected != 0 else True
        status = "✓" if sign_ok else "⚠️ INV"
        sigma = sigmas.get(label, 0)
        exp_str = "+" if expected > 0 else "−"
        report += f"| {label} | {w:+.4f} | {exp_str} {status} | {sigma:.6f} |\n"

    report += f"""
## Modelo

```
Score(t) = Σ wᵢ · zᵢ(t)
zᵢ(t) = retᵢ(t) / (σᵢ · √t)
P_up(t) = sigmoid(α · Score(t) + intercept)
```

## Parâmetros

```json
{json.dumps({**weights, **{f"sigma_{l}_session": s for l, s in sigmas.items()}, "alpha": alpha, "intercept": intercept}, indent=2)}
```
"""
    return report


def main():
    parser = argparse.ArgumentParser(description="IRAI - Calibracao M5 intraday")
    parser.add_argument("--days", type=int, default=252, help="Dias de sessoes (default: 252)")
    parser.add_argument("--db", default=DB_PATH, help="Caminho do banco SQLite")
    args = parser.parse_args()

    print("=" * 70)
    print("  IRAI — Calibracao Intraday (M5)")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Fatores: {', '.join(FACTOR_LABELS.values())}")
    print(f"  DB: {args.db}")
    print("=" * 70)

    conn = get_connection(args.db)

    # 1. Carregar barras
    print("\n[1/6] Carregando barras M5...")
    bars = load_m5_bars(conn)

    # 2. Detectar timezone
    print("\n[2/6] Detectando timezone...")
    tz = detect_timezone(bars)

    # 3. Construir sessões
    print("\n[3/6] Construindo sessoes B3...")
    sessions = build_sessions(bars, tz)

    if len(sessions) == 0:
        print("  ERRO: Nenhuma sessao valida encontrada!")
        conn.close()
        return

    # Limitar a N dias
    dates = sorted(sessions.keys())
    if len(dates) > args.days:
        dates = dates[-args.days:]
        sessions = {d: sessions[d] for d in dates}
        print(f"  Limitado a ultimas {args.days} sessoes: {len(sessions)}")

    # 4. Computar features
    print("\n[4/6] Computando features intraday...")
    factor_labels = list(FACTOR_LABELS.values())
    features = compute_session_features(sessions, FACTORS)

    if len(features) == 0:
        print("  ERRO: Nenhuma feature computada!")
        conn.close()
        return

    # 5. Estimar sigmas e normalizar z-scores
    print("\n[5/6] Estimando volatilidades e z-scores...")
    sigmas = estimate_intraday_sigmas(features)
    features = normalize_zscores(features, sigmas)

    # 6. Calibrar
    print("\n[6/6] Calibrando modelo...")
    weights, r_squared = calibrate_ols(features, factor_labels)
    alpha, intercept, accuracy = calibrate_alpha_m5(features, weights)

    # Salvar
    all_params = save_params_m5(conn, weights, sigmas, alpha, intercept, r_squared, accuracy)

    # Relatório
    report = generate_report_m5(weights, sigmas, alpha, intercept, r_squared, accuracy,
                                len(sessions), factor_labels)
    report_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "data", "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"calibration_m5_{datetime.now().strftime('%Y%m%d')}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  Relatorio salvo: {report_path}")

    conn.close()

    print(f"\n{'='*70}")
    print(f"  CALIBRACAO M5 CONCLUIDA")
    print(f"  R² = {r_squared:.4f} | alpha = {alpha:.4f} | acc = {accuracy:.1%}")
    print(f"  Pesos: {', '.join(f'{k}={v:+.3f}' for k, v in weights.items())}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
