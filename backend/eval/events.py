"""
Avaliação de sinais de descolamento como EVENTOS de entrada (fases 15/18).

Evento = primeira barra de um episódio em que |z| cruza o limiar (|z_k| ≥ thr e |z_{k−1}| < thr),
dentro da janela de entrada (padrão 09:30–17:00 BRT). Direção contrarian ao descolamento:
z > 0 (alvo caro frente à referência) → venda; z < 0 → compra. Saída a h barras no mesmo pregão
ou no último fechamento. P&L da perna do alvo em pontos de preço, por contrato, líquido do custo
de ida e volta (padrão: 10 pts WIN, 1 pt WDO = 2 ticks).

ICs e t por pregão (eventos do mesmo pregão não são independentes).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .metrics import auc, bootstrap_by_session, session_groups

COST_PTS = {"WIN$N": 10.0, "WDO$N": 1.0}
ENTRY_K = (6, 96)          # 09:30 (k=6) até 17:00 (k=96), barras M5 desde 09:00
REVERT_Z = 0.5


def detect_events(z: np.ndarray, sess: np.ndarray, k: np.ndarray, thr: float,
                  entry_k: tuple = ENTRY_K) -> np.ndarray:
    """Índices das barras de evento (primeiro cruzamento por episódio)."""
    z = np.asarray(z, float)
    prev = np.r_[np.nan, z[:-1]]
    same = np.r_[False, sess[1:] == sess[:-1]]
    prev = np.where(same, prev, np.nan)
    cross = (np.abs(z) >= thr) & ~(np.abs(prev) >= thr) & np.isfinite(z) & same
    cross &= (k >= entry_k[0]) & (k <= entry_k[1])
    return np.flatnonzero(cross)


def cluster_t(x: np.ndarray, sess: np.ndarray) -> float:
    """t da média com variância robusta por pregão (cluster)."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 3:
        return float("nan")
    m = x.mean()
    s = pd.Series(x - m).groupby(np.asarray(sess)).sum().to_numpy()
    G = len(s)
    if G < 3:
        return float("nan")
    var = (s ** 2).sum() / n ** 2 * G / (G - 1)
    return float(m / math.sqrt(var)) if var > 0 else float("nan")


def p_two_sided(t: float) -> float:
    if not np.isfinite(t):
        return float("nan")
    return float(math.erfc(abs(t) / math.sqrt(2)))


def event_table(df: pd.DataFrame, z_col: str, thr: float, target: str, horizons=(3, 6, 12),
                cost: float | None = None, direction: int = -1, n_boot: int = 300, seed: int = 0,
                entry_k: tuple = ENTRY_K) -> dict:
    """Estatística dos eventos de um z. `df` precisa de: sess, k, close, z_col e, para a
    decomposição do fechamento do gap, `gap` (log) e `rT` (log desde a abertura).

    direction = −1: contrarian (aposta que o descolamento fecha); +1: segue o descolamento.
    """
    cost = COST_PTS.get(target, 0.0) if cost is None else cost
    d = df.reset_index(drop=True)
    sess = d.sess.to_numpy()
    k = d.k.to_numpy()
    z = d[z_col].to_numpy(float)
    close = d.close.to_numpy(float)
    ev = detect_events(z, sess, k, thr, entry_k)
    out = {"z": z_col, "thr": thr, "direction": "contrarian" if direction < 0 else "segue",
           "events": int(len(ev)), "sessions": int(len(np.unique(sess))),
           "per_session": float(len(ev) / max(1, len(np.unique(sess)))),
           "coverage_abs_gt2": float(np.nanmean(np.abs(z[np.isfinite(z)]) > 2)) if np.isfinite(z).any() else None}
    if len(ev) == 0:
        return out
    sgn = direction * np.sign(z[ev])
    # índice da última barra de cada pregão
    last_of = pd.Series(np.arange(len(d))).groupby(sess).transform("max").to_numpy()
    hz = list(horizons) + ["close"]
    for h in hz:
        if h == "close":
            j = last_of[ev]
            lab = "close"
        else:
            j = ev + h
            lab = f"{h * 5}m"
        ok = (j <= last_of[ev]) & (j != ev)
        jj = np.where(ok, j, ev)
        gross = sgn * (close[jj] - close[ev])
        net = gross - cost
        e_s = sess[ev][ok]
        net, gross = net[ok], gross[ok]
        if len(net) == 0:
            continue
        t = cluster_t(net, e_s)
        groups = session_groups(e_s)
        ci = bootstrap_by_session({"m": lambda i: float(np.mean(net[i]))}, groups, n_boot, seed)
        out[f"n_{lab}"] = int(len(net))
        out[f"hit_{lab}"] = float((net > 0).mean())
        out[f"gross_{lab}"] = float(gross.mean())
        out[f"net_{lab}"] = float(net.mean())
        out[f"net_{lab}_lo"], out[f"net_{lab}_hi"] = ci["m"]
        out[f"t_{lab}"] = t
        out[f"p_{lab}"] = p_two_sided(t)
    # O gap fecha? |z| volta abaixo de 0,5 até 60 min / até o fechamento; e quem fecha o gap
    if "gap" in d and "rT" in d:
        gap = d.gap.to_numpy(float)
        rT = d.rT.to_numpy(float)
        closed60, closed_any, share_target = [], [], []
        for e in ev:
            end = last_of[e]
            seg = np.abs(z[e + 1:end + 1])
            hit = np.flatnonzero(seg < REVERT_Z)
            closed_any.append(len(hit) > 0)
            closed60.append(len(hit) > 0 and hit[0] < 12)
            j = min(e + 12, end)
            dg = gap[j] - gap[e]
            if np.isfinite(dg) and abs(dg) > 0 and np.sign(dg) == -np.sign(gap[e]):
                share_target.append((rT[j] - rT[e]) / dg)
        out["gap_closed_60m"] = float(np.mean(closed60))
        out["gap_closed_session"] = float(np.mean(closed_any))
        out["gap_close_share_by_target_60m"] = float(np.median(share_target)) if share_target else None
    return out


def bar_predictive(df: pd.DataFrame, z_col: str, y_cols=("y15", "y30", "y60")) -> dict:
    """AUC de −z (contrarian) contra o sinal do retorno futuro, em todas as barras com z."""
    out = {}
    z = df[z_col].to_numpy(float)
    for c in y_cols:
        y = df[c].to_numpy(float)
        ok = np.isfinite(z) & np.isfinite(y) & (y != 0)
        out[f"auc_{c}"] = auc(-z[ok], (y[ok] > 0).astype(int)) if ok.sum() > 50 else None
    return out


def bh_adjust(pvals: list[float]) -> list[float]:
    """Benjamini–Hochberg (FDR). NaN passa direto."""
    p = np.asarray(pvals, float)
    ok = np.isfinite(p)
    q = np.full_like(p, np.nan)
    if ok.sum() == 0:
        return q.tolist()
    pv = p[ok]
    order = np.argsort(pv)
    m = len(pv)
    ranked = pv[order] * m / (np.arange(m) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    tmp = np.empty(m)
    tmp[order] = np.minimum(ranked, 1.0)
    q[ok] = tmp
    return q.tolist()


def live_spread_events(df: pd.DataFrame, z_cols=("pair_fixed_z", "pair_z", "price_diverge_z"),
                       target: str = "WIN$N", thr: float = 2.0, n_boot: int = 300, seed: int = 0) -> list[dict]:
    """Para o relatório diário: cobertura do z (% |z| > 2) e P&L por evento dos z gravados ao vivo.

    `df`: barras ao vivo com sess, k, close (preço da barra M5) e as colunas de z.
    """
    rows = []
    for zc in z_cols:
        if zc not in df or df[zc].notna().sum() == 0:
            continue
        r = event_table(df, zc, thr, target, horizons=(3, 6, 12), n_boot=n_boot, seed=seed)
        rows.append(r)
    return rows
