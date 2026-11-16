"""
Divergência de inclinação rastro × preço (ideia do owner, exemplo WDO 06/11/2026). Sem lookahead.

- Inclinação: OLS da série nas n+1 barras t−n..t da MESMA sessão (n = W/5), em unidades/barra.
- Padronização: σ da inclinação nas sessões ANTERIORES (trailing), nunca a própria sessão.
- Divergência de alta em t: inclinação do rastro > +k·σ_P e do preço < −k·σ_preço (espelho = baixa).
  Episódio começa na primeira barra em que vale (não valia em t−1); direção = a do rastro.
- Gatilho de confirmação: na janela [t, t+M] do episódio, a primeira barra j com
  close_j > high_{j−1} (alta) ou close_j < low_{j−1} (baixa). Decisão no fechamento de j,
  entrada na abertura de j+1 (simulador).
"""
from __future__ import annotations

import numpy as np


def rolling_slope(x: np.ndarray, n: int) -> np.ndarray:
    """Inclinação OLS de x[t−n..t] (NaN se faltar ponto ou t < n)."""
    x = np.asarray(x, float)
    out = np.full(len(x), np.nan)
    if n < 1:
        return out
    tt = np.arange(n + 1, dtype=float)
    tc = tt - tt.mean()
    den = (tc ** 2).sum()
    for t in range(n, len(x)):
        w = x[t - n:t + 1]
        if np.all(np.isfinite(w)):
            out[t] = float((tc * (w - w.mean())).sum() / den)
    return out


def divergence_episodes(sp: np.ndarray, sx: np.ndarray, sig_p: float, sig_x: float, k: float) -> list[tuple[int, int]]:
    """[(t, direção)] do início de cada episódio. sp = inclinação do rastro, sx = do preço."""
    sp = np.asarray(sp, float); sx = np.asarray(sx, float)
    up = (sp > k * sig_p) & (sx < -k * sig_x)
    dn = (sp < -k * sig_p) & (sx > k * sig_x)
    out = []
    for t in range(len(sp)):
        if up[t] and not (t > 0 and up[t - 1]):
            out.append((t, 1))
        elif dn[t] and not (t > 0 and dn[t - 1]):
            out.append((t, -1))
    return out


def pullback_episodes(sx: np.ndarray, sig_x: float, k: float) -> list[tuple[int, int]]:
    """Controle sem rastro: só o recuo do preço (< −k·σ → alta; > +k·σ → baixa)."""
    sx = np.asarray(sx, float)
    up = sx < -k * sig_x
    dn = sx > k * sig_x
    out = []
    for t in range(len(sx)):
        if up[t] and not (t > 0 and up[t - 1]):
            out.append((t, 1))
        elif dn[t] and not (t > 0 and dn[t - 1]):
            out.append((t, -1))
    return out


def confirm(episodes: list[tuple[int, int]], h, l, c, window: int) -> list[dict]:
    """Primeiro fechamento além da máxima/mínima da barra anterior na direção do episódio."""
    h = np.asarray(h, float); l = np.asarray(l, float); c = np.asarray(c, float)
    out, used = [], set()
    for t0, d in episodes:
        for j in range(max(t0, 1), min(len(c), t0 + window + 1)):
            if (d == 1 and c[j] > h[j - 1]) or (d == -1 and c[j] < l[j - 1]):
                if j not in used:
                    out.append({"t": j, "side": d, "t0": t0})
                    used.add(j)
                break
    return sorted(out, key=lambda s: s["t"])


def time_exit_trades(signals: list[dict], o, c, k, cost: float, hold: int = 12, entry_k=(6, 96)) -> list[dict]:
    """Saída só por tempo: entra em open[t+1], sai no fechamento de t+hold (ou última barra)."""
    o = np.asarray(o, float); c = np.asarray(c, float); k = np.asarray(k, int)
    n = len(c)
    out, busy = [], -1
    for s in signals:
        e = s["t"] + 1
        if e >= n or not (entry_k[0] <= k[e] <= entry_k[1]) or e <= busy:
            continue
        x = min(e + hold - 1, n - 1)
        g = (c[x] - o[e]) * s["side"]
        out.append({**s, "entry_i": e, "exit_i": x, "entry": float(o[e]), "exit": float(c[x]),
                    "gross": float(g), "net": float(g - cost)})
        busy = x
    return out