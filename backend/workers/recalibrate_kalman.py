"""
Recalibração Automática do Kalman V2.

Job noturno que verifica e corrige divergência dos betas Kalman
em relação aos pesos estáticos V1 calibrados.

Executar uma vez por dia após o fechamento da sessão (ex: 18:30 BRT).
Uso: python -m backend.workers.recalibrate_kalman
"""

import sqlite3
import json
import logging
import sys
import os
import numpy as np
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.db import get_connection, DB_PATH, load_kalman_state, save_kalman_state
from backend.irai import model_registry

log = logging.getLogger("recalibrate_kalman")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# Thresholds de divergência
THRESHOLD_RESET = 1.0      # Divergência média > 1.0 → reset completo para V1
THRESHOLD_DECAY = 0.5      # Divergência média > 0.5 → decay suave (70% Kalman + 30% V1)
DECAY_FACTOR = 0.7          # Proporção do beta Kalman mantida no decay


def load_models(conn, session_date: str = None) -> list[dict]:
    """Carrega todos os modelos ativos com seus pesos estáticos.

    Fase 16: com o registro de versões, pesos/fatores vêm da versão vigente na sessão
    (mesma regra do engine); slugs com versões mas sem versão vigente na data são pulados.
    """
    session_date = session_date or date.today().isoformat()
    registry = model_registry.has_registry(conn)
    models = []
    try:
        rows = conn.execute(
            "SELECT target, slug, factors, factor_labels FROM asset_models WHERE active=1"
        ).fetchall()
    except Exception:
        return []

    for row in rows:
        slug = row["slug"]
        factors = json.loads(row["factors"]) if row["factors"] else []
        factor_labels = json.loads(row["factor_labels"]) if row["factor_labels"] else {}

        # Carregar pesos estáticos (V1)
        prefix = f"{slug}_"
        params = conn.execute(model_registry.legacy_params_sql(conn), (f"{prefix}%", f"{prefix}%")).fetchall()

        weights = {}
        intercept = 0.0
        for p in params:
            name = p["param_name"]
            clean = name[len(prefix):] if name.startswith(prefix) else name
            if clean.startswith("w_"):
                weights[clean] = p["value"]
            elif clean == "intercept":
                intercept = p["value"]

        model_version = None
        adopted = False
        if registry and model_registry.slug_has_versions(conn, slug):
            v = model_registry.resolve_version(conn, slug, session_date)
            if v is None:
                log.info(f"  [{slug:12s}] SKIP — sem versão vigente em {session_date}")
                continue
            art = v["artifact"]
            factors = list(art.get("factors", factors))
            factor_labels = dict(art.get("factor_labels", factor_labels))
            w, _s, _a, icpt = model_registry.parse_param_map(art.get("params", {}))
            weights, intercept = w, icpt
            model_version = v["version_id"]
            adopted = model_registry.is_adopted_from_legacy(v)

        # Ordenar labels na mesma ordem dos factors
        ordered_labels = [factor_labels.get(f, f) for f in factors]

        models.append({
            "target": row["target"],
            "slug": slug,
            "factors": factors,
            "factor_labels": factor_labels,
            "ordered_labels": ordered_labels,
            "weights": weights,
            "intercept": intercept,
            "model_version": model_version,
            "adopted_from_legacy": adopted,
        })

    return models


def recalibrate(session_date: str = None, db_path: str = None, timeframe: str = "M5"):
    """Executa a recalibração de todos os modelos ativos."""
    session_date = session_date or date.today().isoformat()
    db_path = db_path or DB_PATH

    conn = get_connection(db_path)
    models = load_models(conn, session_date)

    if not models:
        log.warning("Nenhum modelo ativo encontrado.")
        conn.close()
        return

    log.info(f"Recalibração Kalman V2 — sessão {session_date} — {len(models)} modelos")
    log.info("=" * 60)

    stats = {"ok": 0, "decay": 0, "reset": 0, "skip": 0}

    for model in models:
        slug = model["slug"]
        n_dim = 1 + len(model["factors"])

        mv = model.get("model_version")
        saved = load_kalman_state(conn, slug, timeframe, session_date, expected_dim=n_dim,
                                  model_version=mv, accept_untagged=model.get("adopted_from_legacy", False))
        if not saved:
            log.info(f"  [{slug:12s}] SKIP — sem estado Kalman salvo para {session_date}")
            stats["skip"] += 1
            continue

        betas_kalman = np.array(saved["state_mean"][1:])  # Excluir intercept (beta0)

        # Montar vetor de pesos estáticos na mesma ordem
        static_weights = np.array([
            model["weights"].get(f"w_{label}", 0.0)
            for label in model["ordered_labels"]
        ])

        if len(betas_kalman) != len(static_weights):
            log.warning(f"  [{slug:12s}] SKIP — dimensão incompatível: kalman={len(betas_kalman)} vs static={len(static_weights)}")
            stats["skip"] += 1
            continue

        # Calcular divergência normalizada
        divergence = float(np.mean(np.abs(betas_kalman - static_weights)))
        max_div = float(np.max(np.abs(betas_kalman - static_weights)))
        
        # Detalhar quais fatores mais divergiram
        div_per_factor = np.abs(betas_kalman - static_weights)
        worst_idx = int(np.argmax(div_per_factor))
        worst_label = model["ordered_labels"][worst_idx] if worst_idx < len(model["ordered_labels"]) else "?"

        if divergence > THRESHOLD_RESET:
            # RESET completo → restaurar para pesos V1 com covariância fresca
            new_mean = [model["intercept"]] + static_weights.tolist()
            new_cov = np.eye(n_dim).tolist()
            # Usar timestamp original + sufixo para superar o guard de timestamp
            recalib_ts = saved.get("timestamp_utc", session_date) + "+recalib"
            save_kalman_state(
                conn, slug, timeframe, session_date,
                new_mean, new_cov,
                saved.get("johansen_p", 1.0),
                saved.get("is_cointegrated", True),
                recalib_ts,
                model_version=mv,
            )
            log.warning(
                f"  [{slug:12s}] RESET  divergence={divergence:.3f} max={max_div:.3f} "
                f"worst={worst_label}({div_per_factor[worst_idx]:.3f})"
            )
            stats["reset"] += 1

        elif divergence > THRESHOLD_DECAY:
            # DECAY suave → 70% Kalman + 30% V1
            decayed = DECAY_FACTOR * betas_kalman + (1 - DECAY_FACTOR) * static_weights
            new_mean = [saved["state_mean"][0]] + decayed.tolist()
            recalib_ts = saved.get("timestamp_utc", session_date) + "+recalib"
            save_kalman_state(
                conn, slug, timeframe, session_date,
                new_mean, saved["state_covariance"],
                saved.get("johansen_p", 1.0),
                saved.get("is_cointegrated", True),
                recalib_ts,
                model_version=mv,
            )
            log.info(
                f"  [{slug:12s}] DECAY  divergence={divergence:.3f} max={max_div:.3f} "
                f"worst={worst_label}({div_per_factor[worst_idx]:.3f})"
            )
            stats["decay"] += 1

        else:
            log.info(
                f"  [{slug:12s}] OK     divergence={divergence:.3f} max={max_div:.3f} "
                f"worst={worst_label}({div_per_factor[worst_idx]:.3f})"
            )
            stats["ok"] += 1

    conn.close()

    log.info("=" * 60)
    log.info(
        f"Resultado: {stats['ok']} OK | {stats['decay']} DECAY | "
        f"{stats['reset']} RESET | {stats['skip']} SKIP"
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Recalibração automática do Kalman V2")
    parser.add_argument("--date", default=None, help="Data da sessão (YYYY-MM-DD). Default: hoje")
    parser.add_argument("--db", default=None, help="Caminho do banco de dados")
    parser.add_argument("--timeframe", default="M5", help="Timeframe (M5, M1, etc)")
    args = parser.parse_args()

    recalibrate(session_date=args.date, db_path=args.db, timeframe=args.timeframe)
