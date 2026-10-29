"""
Calibração Universal IRAI — Brute-force automático para qualquer ativo.

Uso:
    python scripts/calibrate_universal.py --target US500
    python scripts/calibrate_universal.py --target XAUUSD
    python scripts/calibrate_universal.py --all          # calibra todos pendentes
    python scripts/calibrate_universal.py --all --force   # recalibra todos
"""
import sqlite3, json, sys, os, argparse
from itertools import combinations
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.optimize import lsq_linear

os.environ["PYTHONIOENCODING"] = "utf-8"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import DB_PATH


# Todos os possíveis fatores
ALL_FACTORS = [
    "WIN$N", "WDO$N", "DI1$N",
    "DXY", "BRENT", "CHINA50", "USDMXN", "VIX", "BTCUSD",
    "US500", "US30", "USTEC", "DE40", "XAUUSD",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
    "CADCHF", "AUDNZD", "EURGBP", "EURCHF", "EURJPY", "GBPJPY", "EURAUD",
    # --- iShares Axi (fatores candidatos, não estão no painel) ---
    "iSharesBrazil+",       # EWZ - proxy bolsa BR
    "iSharesTreasury20+",   # TLT - Treasury longo (20+y)
    "iSharesTreasury10-20+",# TLH - Treasury médio (10-20y)
    "iSharesTreasury1-3+",  # SHY - Treasury curto (1-3y)
    "iSharesUSEmerging+",   # EMB - EM USD Bond
    "iSharesCurrencyBond+", # LEMB - EM Local Currency Bond
    # --- Top 8 Ações IBOV ---
    "VALE3", "PETR4", "ITUB4", "BBDC4", "ELET3", "WEGE3", "ABEV3", "B3SA3",
]

# Pares que compõem o DXY — não podem usar DXY como fator (multicolinearidade)
DXY_COMPONENTS = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF"}


# Alias: target lógico → símbolo nos dados
ALIASES = {"WIN$N_TOP8": "WIN$N"}


def load_daily_returns(conn, session_start_h, session_end_h):
    """Carrega retornos diários de todos os símbolos disponíveis."""
    df = pd.read_sql_query(
        "SELECT symbol, timestamp_utc, open, close FROM market_bars WHERE timeframe='M5'",
        conn,
    )
    df["timestamp"] = pd.to_datetime(df["timestamp_utc"]).dt.tz_localize(None)
    df["hour"] = df["timestamp"].dt.hour
    df["date"] = df["timestamp"].dt.date

    # Filtrar por sessão — MESMA definição usada pelo engine (backend/irai/engine.py):
    #  - Alvos B3 (session_start_h != 0): pregão 09:00–18:30 de Brasília, convertido do relógio do
    #    broker (NY+7) com o DST americano de cada data. Vale para alvo E fatores (o engine mede o
    #    retorno dos fatores a partir da abertura da B3). A data da sessão é a data de Brasília.
    #  - Alvos globais: dia do broker inteiro (00:00–24:00).
    if session_start_h != 0:
        ny_wall = df["timestamp"] - pd.Timedelta(hours=7)
        brt = (ny_wall.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward")
                      .dt.tz_convert("America/Sao_Paulo"))
        brt_minutes = brt.dt.hour * 60 + brt.dt.minute
        df = df[(brt_minutes >= 9 * 60) & (brt_minutes < 18 * 60 + 30)].copy()
        df["date"] = brt[df.index].dt.date
    elif session_end_h != 24:
        df = df[(df["hour"] >= session_start_h) & (df["hour"] < session_end_h)]

    daily = {}
    for sym in df["symbol"].unique():
        s = df[df["symbol"] == sym].sort_values("timestamp")
        d = s.groupby("date").agg(o=("open", "first"), c=("close", "last"), n=("close", "count"))
        d = d[d["n"] >= 10]  # mínimo de barras
        d["ret"] = (d["c"] - d["o"]) / d["o"]
        daily[sym] = d["ret"]

    return daily


def calibrate_target(conn, target, session_start_h=0, session_end_h=24, 
                     data_proxy=None, min_factors=4, max_factors=8):
    """
    Brute-force: testa todas combinações de fatores para o target.
    Retorna: best_factors, best_labels, weights, sigmas, alpha, intercept, r2, accuracy
    """
    data_sym = data_proxy or ALIASES.get(target, target)
    
    print(f"\n{'='*60}")
    print(f"  Calibrando: {target} (dados: {data_sym})")
    print(f"  Sessão: {session_start_h:02d}-{session_end_h:02d} UTC")
    print(f"{'='*60}")
    
    # Regra de Exceção para Momentum Tracker do US30
    if target == "US30":
        min_factors = min(4, min_factors)
        max_factors = min(5, max_factors)
        print("  [regra] Exceção Momentum Tracker ativada para US30 (min_factors=4, max_factors=5, permite US500)")

    daily = load_daily_returns(conn, session_start_h, session_end_h)

    if data_sym not in daily:
        print(f"  [FAIL] Sem dados para {data_sym}")
        return None

    target_ret = daily[data_sym].rename("target")

    # Fatores candidatos
    exclude = {target, data_sym}
    
    # Regras de negócio
    br_assets = {"WIN$N", "WDO$N", "DI1$N"}
    us_indices = {"US500", "US30", "USTEC"}
    
    if target in us_indices:
        # Exceção de Momentum Tracker para o US30 (permitimos US500 na cesta dele)
        if target == "US30":
            exclude.update({"US30", "USTEC"})
        else:
            # US indices não seguem outros US indices
            exclude.update(us_indices)

    if target not in br_assets:
        # Internacional não usa BR
        exclude.update(br_assets)

    if target in DXY_COMPONENTS:
        if target == "EURUSD":
            # Exceção para EURUSD: Permitir o DXY como âncora principal
            min_factors = min(4, min_factors)
            max_factors = min(6, max_factors)
            print("  [regra] Exceção EURUSD: Permitido usar DXY. min_factors=4, max_factors=6")
        else:
            # Majors não usam DXY — são componentes do índice (multicolinearidade)
            exclude.add("DXY")
            print(f"  [regra] {target} é componente do DXY — DXY excluído dos fatores")

    # ── Exclusão de tautologias aritméticas entre crosses ─────────────────
    cross_trios = [
        {"CADCHF", "USDCAD", "USDCHF"},
        {"EURGBP", "EURUSD", "GBPUSD"},
        {"EURCHF", "EURUSD", "USDCHF"},
        {"EURJPY", "EURUSD", "USDJPY"},
        {"GBPJPY", "GBPUSD", "USDJPY"},
        {"EURAUD", "EURUSD", "AUDUSD"},
        {"EURJPY", "GBPJPY", "EURGBP"}, # Descomentado para evitar colinearidade singular (Kalman Filter Issue)
    ]
    for trio in cross_trios:
        if target in trio:
            exclude.update(trio - {target})
            print(f"  [regra] {target} pertence a um trio de cross — excluindo {trio - {target}}")

    # AUDNZD = AUDUSD / NZDUSD  →  excluir AUDUSD para AUDNZD e vice-versa
    # (NZDUSD não está no modelo, então AUDNZD ≈ f(AUDUSD) apenas parcialmente)
    # Mas AUDNZD não pode usar AUDUSD como único fator dominante
    if target == "AUDNZD":
        exclude.add("AUDUSD")
        print(f"  [regra] AUDNZD exclui AUDUSD (correlação estrutural alta)")
    if target == "AUDUSD":
        exclude.add("AUDNZD")
        print(f"  [regra] AUDUSD exclui AUDNZD (correlação estrutural alta)")

    if target == "EURJPY":
        exclude.add("GBPJPY")
        print(f"  [regra] EURJPY exclui GBPJPY (pedido manual)")
    if target == "GBPJPY":
        exclude.add("EURJPY")
        print(f"  [regra] GBPJPY exclui EURJPY (pedido manual)")

    # ── Exclusão de iShares redundantes entre si ───────────────────────────────────
    # Treasuries são altamente correlacionados entre si — no máximo 1 na cesta
    treasuries = {"iSharesTreasury20+", "iSharesTreasury10-20+", "iSharesTreasury1-3+"}
    # EM bonds também correlacionam forte entre si
    em_bonds = {"iSharesUSEmerging+", "iSharesCurrencyBond+"}
    # iSharesBrazil (EWZ) tem correlação estrutural com WIN$N/WDO$N
    if target in {"WIN$N", "WDO$N"}:
        # Para BR assets, EWZ é quase tautologia — excluir
        exclude.add("iSharesBrazil+")
        print(f"  [regra] {target} exclui iSharesBrazil+ (proxy da mesma bolsa)")

    if target == "WIN$N_TOP8":
        top8_basket = ["VALE3", "PETR4", "ITUB4", "BBDC4", "ELET3", "WEGE3", "ABEV3", "B3SA3"]
        available_factors = [f for f in top8_basket if f in daily]
        min_factors = 1 if available_factors else 4
        max_factors = max(len(available_factors), 1)
        print(f"  [regra] WIN$N_TOP8: Forçando fatores da cesta Top 8 IBOV ({len(available_factors)}/8 disponíveis nos dados)")
    else:
        available_factors = [f for f in ALL_FACTORS if f in daily and f not in exclude]

    print(f"  Fatores disponíveis: {len(available_factors)}")
    print(f"  Sessões target: {len(target_ret)}")


    if len(available_factors) < min_factors:
        print(f"  [FAIL] Poucos fatores ({len(available_factors)} < {min_factors})")
        return None

    # Cobertura mínima: fatores com histórico curto (ex.: ações B3 coletadas só desde ago/2026)
    # derrubariam o dropna() de TODAS as sessões. Exige presença em >= 80% das últimas 252 sessões.
    if target != "WIN$N_TOP8":
        # Só dias úteis: ativos 24/7 (BTC) têm sessões de fim de semana em que nenhum fator negocia
        tgt_idx = target_ret.dropna().index
        recent_idx = [d for d in tgt_idx if getattr(d, "weekday", lambda: 0)() < 5][-252:]
        coverage = {f: float(daily[f].reindex(recent_idx).notna().mean()) for f in available_factors}
        low = sorted(f for f, c in coverage.items() if c < 0.8)
        if low:
            print(f"  [cobertura] Excluídos por histórico insuficiente (<80% de {len(recent_idx)} sessões): {', '.join(low)}")
        available_factors = [f for f in available_factors if coverage[f] >= 0.8]
        if len(available_factors) < min_factors:
            print(f"  [FAIL] Poucos fatores com cobertura ({len(available_factors)} < {min_factors})")
            return None

    # Últimos 252 dias úteis
    merged_all = pd.DataFrame({"target": target_ret})
    for f in available_factors:
        label = f.replace("$N", "").lower()
        merged_all[label] = daily[f]
    merged_all = merged_all.dropna().iloc[-252:]
    
    print(f"  Sessões merged: {len(merged_all)}")

    if len(merged_all) < 100:
        print(f"  [FAIL] Poucos dados ({len(merged_all)} < 100)")
        return None

    y_ret = merged_all["target"].values
    y_dir = (y_ret > 0).astype(int)

    # Brute force
    best_score = -float("inf")
    best_result = None
    total_combos = 0

    factor_labels_map = {f: f.replace("$N", "").lower() for f in available_factors}
    available_labels = [factor_labels_map[f] for f in available_factors]

    # Precompute TSS for R2
    tss = np.sum((y_ret - y_ret.mean()) ** 2)
    n_samples = len(y_ret)

    # Precompute correlation matrix and highly correlated pairs (>= 0.80)
    corr_matrix = merged_all[available_labels].corr().abs()
    high_corr_pairs = set()
    for i in range(len(available_labels)):
        for j in range(i + 1, len(available_labels)):
            if corr_matrix.iloc[i, j] >= 0.80:
                high_corr_pairs.add((i, j))

    # Precompute index sets for multicollinearity groups
    treasury_indices = {i for i, f in enumerate(available_factors) 
                        if f in treasuries}
    em_bond_indices = {i for i, f in enumerate(available_factors)
                       if f in em_bonds}

    skipped_multicol = 0

    candidates = []

    for n_factors in range(min_factors, min(max_factors + 1, len(available_factors) + 1)):
        for combo in combinations(range(len(available_factors)), n_factors):
            # Filtro: no máximo 1 Treasury e 1 EM Bond por cesta
            combo_set = set(combo)
            n_treas = len(combo_set & treasury_indices)
            n_em = len(combo_set & em_bond_indices)
            if n_treas > 1 or n_em > 1:
                skipped_multicol += 1
                continue

            # Filtro de correlação: nenhum par na cesta pode ter correlação >= 0.80
            has_high_corr = False
            for i in range(n_factors):
                for j in range(i + 1, n_factors):
                    idx_pair = (combo[i], combo[j]) if combo[i] < combo[j] else (combo[j], combo[i])
                    if idx_pair in high_corr_pairs:
                        has_high_corr = True
                        break
                if has_high_corr:
                    break
            
            if has_high_corr:
                skipped_multicol += 1
                continue

            total_combos += 1
            labels = [available_labels[i] for i in combo]
            factors = [available_factors[i] for i in combo]

            X = merged_all[labels].values
            Xb = np.column_stack([X, np.ones(len(X))])

            try:
                # Stage 1: Fast unconstrained OLS
                beta_ols = np.linalg.lstsq(Xb, y_ret, rcond=None)[0]
                yp_ols = Xb @ beta_ols
                correct = np.sum((yp_ols > 0) == (y_ret > 0))
                acc = correct / len(y_ret)
                
                r2 = 1 - np.sum((y_ret - yp_ols) ** 2) / tss
                adj_r2 = 1 - ((1 - r2) * (n_samples - 1) / (n_samples - n_factors - 1))
                
                score_ols = (acc * 0.7) + (max(0, adj_r2) * 0.3)
                candidates.append((score_ols, combo, labels, factors))
            except Exception:
                continue

    # Stage 2: Constrained sign regression on the top 500 candidates
    candidates.sort(key=lambda x: x[0], reverse=True)
    top_candidates = candidates[:500]

    for score_ols, combo, labels, factors in top_candidates:
        n_factors = len(combo)
        X = merged_all[labels].values
        Xb = np.column_stack([X, np.ones(len(X))])

        # Define sign constraints based on correlation sign
        lb = []
        ub = []
        for label in labels:
            corr = merged_all["target"].corr(merged_all[label])
            if corr >= 0:
                lb.append(0.0)
                ub.append(np.inf)
            else:
                lb.append(-np.inf)
                ub.append(0.0)
        # Intercept has no sign constraint
        lb.append(-np.inf)
        ub.append(np.inf)

        try:
            res = lsq_linear(Xb, y_ret, bounds=(lb, ub))
            beta = res.x
        except Exception:
            continue

        yp = Xb @ beta
        correct = np.sum((yp > 0) == (y_ret > 0))
        acc = correct / len(y_ret)
        
        r2 = 1 - np.sum((y_ret - yp) ** 2) / tss
        adj_r2 = 1 - ((1 - r2) * (n_samples - 1) / (n_samples - n_factors - 1))
        
        score = (acc * 0.7) + (max(0, adj_r2) * 0.3)

        if score > best_score:
            best_score = score
            best_result = {
                "factors": factors,
                "labels": labels,
                "beta": beta,
                "r2": r2,
                "acc": acc,
                "n_factors": n_factors,
            }


    if best_result is None:
        print(f"  Testadas: {total_combos:,} combos ({skipped_multicol:,} descartadas por multicolinearidade)")
        print(f"  [FAIL] Nenhum resultado valido")
        return None

    print(f"  Testadas: {total_combos:,} combos ({skipped_multicol:,} descartadas por multicolinearidade)")
    print(f"  >> Melhor: {best_result['n_factors']} fatores, ACC={best_result['acc']:.1%}, R2={best_result['r2']:.4f}")
    print(f"  Fatores: {', '.join(best_result['factors'])}")

    # Calibrar sigmas e logistic
    labels = best_result["labels"]
    beta = best_result["beta"]
    
    weights = {}
    sigmas = {}
    for i, label in enumerate(labels):
        weights[label] = beta[i]
        sigmas[label] = float(merged_all[label].std())
        print(f"    w_{label:8s} = {beta[i]:+.6f}  s={sigmas[label]:.5f}")

    # Logistic calibration
    scores = np.zeros(len(merged_all))
    for i, label in enumerate(labels):
        z = merged_all[label].values / sigmas[label]
        scores += weights[label] * z

    from sklearn.linear_model import LogisticRegression
    lr = LogisticRegression(fit_intercept=True, max_iter=1000, C=1e6)
    lr.fit(scores.reshape(-1, 1), y_dir)
    raw_alpha = float(lr.coef_[0, 0])
    raw_intercept = float(lr.intercept_[0])

    # --- GUARD RAILS FOR V2 (Kalman Filter Paradigm) ---
    # The V2 engine uses dynamic Kalman weights but relies on these static
    # logistic parameters for scaling the signal to a 0-100 probability.
    # We must clamp alpha to maintain "responsiveness" without becoming binary,
    # and clamp intercept to remain close to neutral (50% base prob).
    alpha = max(1.0, min(3.5, raw_alpha))
    intercept = max(-0.25, min(0.25, raw_intercept))

    if raw_alpha != alpha or raw_intercept != intercept:
        print(f"  [Guard Rails] Ajustado Alpha ({raw_alpha:.4f} -> {alpha:.4f}) e Intercept ({raw_intercept:.4f} -> {intercept:.4f})")
    # ---------------------------------------------------

    p_up = expit(alpha * scores + intercept) * 100
    dir_acc = np.mean((p_up > 50).astype(int) == y_dir) * 100

    print(f"  Logistic: a={alpha:.4f}, intercept={intercept:.4f}, ACC={dir_acc:.1f}%")

    return {
        "factors": best_result["factors"],
        "labels": labels,
        "factor_labels": {f: l for f, l in zip(best_result["factors"], labels)},
        "weights": weights,
        "sigmas": sigmas,
        "alpha": alpha,
        "intercept": intercept,
        "r2": best_result["r2"],
        "accuracy": best_result["acc"] * 100,
        "logistic_acc": dir_acc,
        "n_sessions": len(merged_all),
    }


def save_to_db(conn, target, slug, result):
    """Salva pesos no model_params e atualiza asset_models."""
    effective = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prefix = f"{slug}_"

    # Limpar TODOS os params antigos deste slug antes de inserir os novos.
    # Isso evita params de calibrações anteriores (com fatores diferentes)
    # ficarem no banco e causando modelos híbridos incorretos.
    # LIKE com '_' escapado (em LIKE '_' é curinga) e excluindo slugs que começam com este
    # prefixo (ex.: calibrar 'win' NÃO pode apagar os params de 'win_top8').
    def _like_prefix(p):
        return p.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"

    other_slugs = [r[0] for r in conn.execute("SELECT slug FROM asset_models WHERE slug != ?", (slug,))
                   if r[0] and r[0].startswith(prefix)]
    sql = "DELETE FROM model_params WHERE param_name LIKE ? ESCAPE '\\'"
    args = [_like_prefix(prefix)]
    for other in other_slugs:
        sql += " AND param_name NOT LIKE ? ESCAPE '\\'"
        args.append(_like_prefix(f"{other}_"))
    deleted = conn.execute(sql, args).rowcount
    if deleted:
        print(f"  [purge] {deleted} params antigos de '{prefix}' removidos")

    params = []
    for label, w in result["weights"].items():
        params.append((f"{prefix}w_{label}", w, effective))
    for label, s in result["sigmas"].items():
        params.append((f"{prefix}sigma_{label}", s, effective))
    params.append((f"{prefix}alpha", result["alpha"], effective))
    params.append((f"{prefix}intercept", result["intercept"], effective))

    conn.executemany(
        "INSERT INTO model_params (param_name, value, effective_from) VALUES (?, ?, ?)",
        params,
    )

    # Atualizar asset_models
    conn.execute("""
        UPDATE asset_models SET
            factors = ?, factor_labels = ?,
            accuracy = ?, r_squared = ?, n_sessions = ?,
            calibrated_at = ?
        WHERE target = ?
    """, (
        json.dumps(result["factors"]),
        json.dumps(result["factor_labels"]),
        result["accuracy"],
        result["r2"],
        result["n_sessions"],
        effective,
        target,
    ))

    conn.commit()
    print(f"  [OK] Salvos {len(params)} params (prefix='{prefix}') + asset_models atualizado")


def main():
    parser = argparse.ArgumentParser(description="Calibração Universal IRAI")
    parser.add_argument("--target", type=str, help="Símbolo alvo (ex: US500)")
    parser.add_argument("--all", action="store_true", help="Calibrar todos os targets")
    parser.add_argument("--force", action="store_true", help="Recalibrar mesmo já calibrados")
    parser.add_argument("--min-factors", type=int, default=6)
    parser.add_argument("--max-factors", type=int, default=8)
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.all:
        if args.force:
            rows = conn.execute("SELECT * FROM asset_models WHERE active=1").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM asset_models WHERE active=1 AND (calibrated_at IS NULL OR accuracy IS NULL)"
            ).fetchall()
        targets = [(r["target"], r["slug"], r["session_start_h"], r["session_end_h"], r["data_proxy"]) for r in rows]
    elif args.target:
        row = conn.execute("SELECT * FROM asset_models WHERE target=?", (args.target,)).fetchone()
        if row:
            targets = [(row["target"], row["slug"], row["session_start_h"], row["session_end_h"], row["data_proxy"])]
        else:
            print(f"Target {args.target} not found in asset_models")
            return
    else:
        parser.print_help()
        return

    print(f"\nCalibrando {len(targets)} targets...")

    results_summary = []
    for target, slug, s_start, s_end, proxy in targets:
        result = calibrate_target(
            conn, target, s_start, s_end, proxy,
            args.min_factors, args.max_factors,
        )
        if result:
            save_to_db(conn, target, slug, result)
            results_summary.append((target, result["accuracy"], result["r2"], result["logistic_acc"], len(result["factors"])))
        else:
            results_summary.append((target, None, None, None, 0))

    # Summary
    print(f"\n{'='*60}")
    print(f"  RESUMO CALIBRAÇÃO")
    print(f"{'='*60}")
    print(f"  {'Target':12s} {'ACC':>8s} {'R2':>8s} {'LogACC':>8s} {'#Fats':>6s}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*6}")
    for target, acc, r2, lacc, nf in results_summary:
        if acc:
            print(f"  {target:12s} {acc:7.1f}% {r2:7.4f} {lacc:7.1f}% {nf:5d}")
        else:
            print(f"  {target:12s}  FAILED")
    
    conn.close()


if __name__ == "__main__":
    main()
