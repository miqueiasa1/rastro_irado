"""
Métricas de assertividade para probabilidades binárias (fase 15, SPEC §13 / PRD §7).

Convenções:
- `p` é probabilidade em [0, 1]; `y` é 0/1.
- AUC pelo estatístico de Mann-Whitney com ranks médios (empates contam 0,5).
- Brier skill score contra a taxa-base do próprio conjunto avaliado (climatologia
  in-sample, a mesma convenção da auditoria de 10/11/2026).
- ECE com 10 bins de largura igual em [0, 1], ponderado pelo número de amostras.
- Intervalos de confiança por bootstrap de pregões (reamostra sessões inteiras com
  reposição), com seed fixa para reprodutibilidade.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import rankdata

N_BINS = 10


def _as_arrays(p, y):
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    if p.shape != y.shape:
        raise ValueError("p e y precisam ter o mesmo tamanho")
    return p, y


def auc(score, y) -> float:
    """AUC (Mann-Whitney). Aceita qualquer score ordenável. NaN se só houver uma classe."""
    s, y = _as_arrays(score, y)
    n1 = int((y == 1).sum())
    n0 = int((y == 0).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def brier(p, y) -> float:
    p, y = _as_arrays(p, y)
    if len(p) == 0:
        return float("nan")
    return float(np.mean((p - y) ** 2))


def brier_skill(p, y, base_rate: float | None = None) -> float:
    """1 - Brier / Brier(climatologia). Climatologia = taxa-base do conjunto, salvo se informada."""
    p, y = _as_arrays(p, y)
    if len(p) == 0:
        return float("nan")
    base = float(np.mean(y)) if base_rate is None else float(base_rate)
    ref = float(np.mean((base - y) ** 2))
    if ref == 0:
        return float("nan")
    return 1.0 - brier(p, y) / ref


def hit_rate(p, y, threshold: float = 0.5) -> float:
    """Acerto direcional: prevê alta quando p > threshold (p == threshold conta como baixa)."""
    p, y = _as_arrays(p, y)
    if len(p) == 0:
        return float("nan")
    return float(np.mean((p > threshold) == (y == 1)))


def _bin_index(p, n_bins: int = N_BINS):
    return np.clip((np.asarray(p, dtype=float) * n_bins).astype(int), 0, n_bins - 1)


def reliability_table(p, y, n_bins: int = N_BINS) -> list[dict]:
    """Tabela de confiabilidade: por bin de p, n, p médio e frequência observada de alta."""
    p, y = _as_arrays(p, y)
    idx = _bin_index(p, n_bins)
    rows = []
    for b in range(n_bins):
        m = idx == b
        n = int(m.sum())
        rows.append({
            "bin_lo": b / n_bins,
            "bin_hi": (b + 1) / n_bins,
            "n": n,
            "p_mean": float(p[m].mean()) if n else None,
            "freq_up": float(y[m].mean()) if n else None,
        })
    return rows


def ece(p, y, n_bins: int = N_BINS) -> float:
    """Expected calibration error (fração, não pp)."""
    p, y = _as_arrays(p, y)
    if len(p) == 0:
        return float("nan")
    idx = _bin_index(p, n_bins)
    tot = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.any():
            tot += m.sum() * abs(p[m].mean() - y[m].mean())
    return float(tot / len(p))


def session_groups(sessions) -> list[np.ndarray]:
    """Índices posicionais de cada sessão, em ordem de sessão."""
    sessions = np.asarray(sessions)
    order = np.argsort(sessions, kind="stable")
    s_sorted = sessions[order]
    cuts = np.flatnonzero(s_sorted[1:] != s_sorted[:-1]) + 1
    return np.split(order, cuts)


def bootstrap_by_session(stat_fns: dict, groups: list[np.ndarray], n_boot: int, seed: int,
                         alpha: float = 0.05) -> dict:
    """IC percentil por bootstrap de sessões.

    stat_fns: nome -> função(idx) que devolve o estatístico para as linhas `idx`.
    Retorna nome -> (lo, hi). Determinístico para a mesma seed.
    """
    rng = np.random.default_rng(seed)
    k = len(groups)
    out = {name: [] for name in stat_fns}
    if k == 0 or n_boot <= 0:
        return {name: (float("nan"), float("nan")) for name in stat_fns}
    for _ in range(n_boot):
        pick = rng.integers(0, k, k)
        idx = np.concatenate([groups[i] for i in pick])
        for name, fn in stat_fns.items():
            v = fn(idx)
            if v == v:  # descarta NaN
                out[name].append(v)
    res = {}
    for name, vals in out.items():
        if vals:
            lo, hi = np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
            res[name] = (float(lo), float(hi))
        else:
            res[name] = (float("nan"), float("nan"))
    return res


def evaluate_probability(p, y, sessions, n_boot: int = 1000, seed: int = 0) -> dict:
    """Bloco completo de métricas de uma probabilidade contra um alvo binário."""
    p, y = _as_arrays(p, y)
    sessions = np.asarray(sessions)
    groups = session_groups(sessions)
    ci = bootstrap_by_session(
        {"auc": lambda i: auc(p[i], y[i]), "bss": lambda i: brier_skill(p[i], y[i])},
        groups, n_boot, seed,
    )
    return {
        "n": int(len(p)),
        "n_sessions": int(len(groups)),
        "base_up": float(np.mean(y)) if len(y) else float("nan"),
        "auc": auc(p, y),
        "auc_lo": ci["auc"][0],
        "auc_hi": ci["auc"][1],
        "hit": hit_rate(p, y),
        "brier": brier(p, y),
        "bss": brier_skill(p, y),
        "bss_lo": ci["bss"][0],
        "bss_hi": ci["bss"][1],
        "ece": ece(p, y),
        "reliability": reliability_table(p, y),
    }


def mean_ci_by_session(x, sessions, n_boot: int = 1000, seed: int = 1) -> tuple[float, float, float]:
    """Média de x e IC 95% por bootstrap de sessões."""
    x = np.asarray(x, dtype=float)
    groups = session_groups(sessions)
    ci = bootstrap_by_session({"m": lambda i: float(np.mean(x[i]))}, groups, n_boot, seed)
    return (float(np.mean(x)) if len(x) else float("nan"), ci["m"][0], ci["m"][1])
