"""
Calibração do nowcast com a correção de unidade β/z e o ruído do Kalman (fase 17, SPEC §8).

Bug (REQ-M01): β é estimado em y = Xβ com RETORNOS brutos, mas o score antigo era Σ βᵢ·zᵢ com
zᵢ = rᵢ/σᵢ — pesos na unidade errada (fatores de σ pequeno ficavam sub-ponderados e os de σ
grande, sobre-ponderados). O preditor linear da regressão é Σ βᵢ·rᵢ = Σ (βᵢ·σᵢ)·zᵢ.

Correção A (mínima): score = Σ βᵢ·σᵢ·zᵢ ÷ score_scale, em que score_scale = desvio de Σ βᵢ·rᵢ na
janela de calibração (o score fica em "desvios", e o limite de divergência V2→V1 de 3,0 continua
comparável). α e intercepto reestimados por logística SEM o clamp visual [1; 3,5] e [±0,25].

Kalman (REQ-M04): R = variância real do resíduo intradiário da observação (retorno % acumulado do
alvo − Σ β·retorno % acumulado dos fatores) nas barras do treino; Q = variância por barra da deriva
dos β, medida pela variação de um pregão para o outro dos β de janelas de 20 pregões.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

from backend.eval.metrics import auc


def score_old(R: np.ndarray, beta: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """Score antigo (com o bug): Σ βᵢ·(rᵢ/σᵢ)."""
    return (R / sigma) @ beta


def score_fixed(R: np.ndarray, beta: np.ndarray, sigma: np.ndarray, scale: float | None = None):
    """Score corrigido: Σ βᵢ·σᵢ·zᵢ = Σ βᵢ·rᵢ, dividido por `scale` (desvio na calibração)."""
    raw = (R / sigma) @ (beta * sigma)
    if scale is None:
        scale = float(np.std(raw)) or 1.0
    return raw / scale, scale


def fit_logistic(score: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """α e intercepto por logística praticamente sem regularização e SEM clamp."""
    lr = LogisticRegression(fit_intercept=True, max_iter=1000, C=1e6)
    lr.fit(score.reshape(-1, 1), y)
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def compare_scores(R: np.ndarray, y_ret: np.ndarray, beta: np.ndarray, sigma: np.ndarray,
                   intercept_ols: float = 0.0, alpha_old: float | None = None, b_old: float | None = None) -> dict:
    """Acurácia/AUC na janela de calibração: regressor (Σβr + c), score antigo e score corrigido."""
    y = (y_ret > 0).astype(int)
    reg = R @ beta + intercept_ols
    s_old = score_old(R, beta, sigma)
    s_new, scale = score_fixed(R, beta, sigma)
    a_new, b_new = fit_logistic(s_new, y)
    a_old_fit, b_old_fit = fit_logistic(s_old, y)
    a_old = alpha_old if alpha_old is not None else a_old_fit
    b_o = b_old if b_old is not None else b_old_fit
    p_old = 1 / (1 + np.exp(-(a_old * s_old + b_o)))
    p_new = 1 / (1 + np.exp(-(a_new * s_new + b_new)))
    return {
        "n_sessions": int(len(y)),
        "acc_regressor": float(np.mean((reg > 0) == (y == 1))),
        "acc_regressor_sem_intercepto": float(np.mean(((R @ beta) > 0) == (y == 1))),
        "base_up": float(np.mean(y)),
        "acc_old": float(np.mean((p_old > 0.5) == (y == 1))),
        "acc_fixed": float(np.mean((p_new > 0.5) == (y == 1))),
        "auc_regressor": auc(reg, y),
        "auc_old": auc(s_old, y),
        "auc_fixed": auc(s_new, y),
        "alpha_fixed": a_new, "intercept_fixed": b_new, "score_scale": scale,
        "alpha_old_used": a_old, "intercept_old_used": b_o,
        "alpha_old_unclamped": a_old_fit, "intercept_old_unclamped": b_old_fit,
    }


def estimate_kalman_noise(cum_target_pct: np.ndarray, cum_factors_pct: np.ndarray, sess: np.ndarray,
                          k: np.ndarray, beta: np.ndarray, step: int = 6, window: int = 20,
                          bars_per_session: int = 113) -> dict:
    """R (%²) e Q (por barra) a partir das barras do treino.

    cum_*: retornos % acumulados desde a abertura (mesma observação do Kalman do engine).
    """
    resid = cum_target_pct - cum_factors_pct @ beta
    ok = np.isfinite(resid) & (k >= 1)
    R = float(np.var(resid[ok]))
    # β por janela de 20 pregões (incrementos de 30 min), variação de um pregão para o outro
    sessions = sorted(set(sess))
    inc = {}
    for s in sessions:
        m = sess == s
        kk, yy, XX = k[m], cum_target_pct[m], cum_factors_pct[m]
        sel = np.flatnonzero((kk + 1) % step == 0)
        if len(sel) < 3:
            continue
        v, V = yy[sel], XX[sel]
        inc[s] = (np.vstack([V[:1], np.diff(V, axis=0)]), np.concatenate([v[:1], np.diff(v)]))
    keys = [s for s in sessions if s in inc]
    betas = []
    for j in range(window, len(keys) + 1):
        X = np.vstack([inc[s][0] for s in keys[j - window:j]])
        y = np.concatenate([inc[s][1] for s in keys[j - window:j]])
        xtx = X.T @ X
        lam = 1e-3 * np.trace(xtx) / max(X.shape[1], 1)
        betas.append(np.linalg.solve(xtx + lam * np.eye(X.shape[1]), X.T @ y))
    if len(betas) >= 3:
        d = np.diff(np.array(betas), axis=0)
        q_session = float(np.median(np.var(d, axis=0)))
        Q = q_session / bars_per_session
    else:
        Q = float("nan")
    return {"kalman_obs_cov": R, "kalman_trans_cov": Q, "resid_std_pct": float(np.sqrt(R)),
            "n_bars": int(ok.sum()), "n_beta_windows": len(betas)}
