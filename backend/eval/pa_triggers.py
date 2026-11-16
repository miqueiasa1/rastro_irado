"""
Gatilhos de price action em zonas (fase 20, 20-PLAN-01 §3). Sem lookahead.

Convenções (uma sessão por chamada, barras M5 em ordem):
- Decisão no FECHAMENTO da barra t; entrada na ABERTURA de t+1 (o simulador cuida da entrada).
- Tudo que o gatilho usa vem de barras ≤ t; ATR e meia-largura da zona vêm de barras ≤ t−1
  (`atr_prev[t]`, `hw[t]`). Teste: truncar a série em t não muda nenhum sinal com decisão ≤ t.
- Zona de um nível L: [L − h, L + h]. Suporte = preço chega por cima; resistência = por baixo.

Gatilhos (suporte; resistência é o espelho):
- T0 toque: low_t ≤ L+h, as 3 barras anteriores com low > L+h e último fechamento fora da zona
  acima dela → compra.
- T1 rejeição: na janela de 6 barras desde o toque (T0), low_t ≤ L+h, close_t ≥ L,
  pavio inferior ≥ 0,5·range, close_t ≥ low_t + 0,6·range, range ≥ 0,5·ATR → compra.
- T2 falso rompimento e retomada: na janela, alguma barra j ∈ [t−2, t] (j ≥ toque) com
  low_j < L−h, close_t > L + 0,25·h e nenhum fechamento entre j e t abaixo de L−h−ATR → compra.
- T3 rompimento e reteste: close_j < L−h com close_{j−1} ≥ L−h (rompeu o suporte); em até 6
  barras, high_t ≥ L−h e close_t < L − 0,25·h → VENDA (a favor do rompimento). Se antes disso
  fechar acima de L+h, o rompimento é cancelado.
"""
from __future__ import annotations

import numpy as np

DEFAULT = {
    "outside_bars": 3, "episode_window": 6,
    "t1_wick": 0.5, "t1_close_pos": 0.6, "t1_min_range_atr": 0.5,
    "t2_lookback": 2, "t2_reclaim_h": 0.25, "t2_max_close_below_atr": 1.0,
    "t3_retest_window": 6, "t3_reject_h": 0.25,
}


def true_range(o, h, l, c) -> np.ndarray:
    h = np.asarray(h, float); l = np.asarray(l, float); c = np.asarray(c, float)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    tr[0] = h[0] - l[0]
    return tr


def atr_prev(tr: np.ndarray, n: int = 14, min_bars: int = 5, fallback: float = np.nan) -> np.ndarray:
    """ATR conhecido na decisão da barra t: média dos TR das barras max(0,t−n)..t−1 da sessão."""
    out = np.full(len(tr), fallback, float)
    cs = np.r_[0.0, np.cumsum(tr)]
    for t in range(len(tr)):
        lo = max(0, t - n)
        m = t - lo
        if m >= min_bars:
            out[t] = (cs[t] - cs[lo]) / m
    return out


def _sig(t, trig, side, L, h, role):
    return {"t": int(t), "trigger": trig, "side": int(side), "L": float(L), "hw": float(h), "role": role}


def detect_level(o, h, l, c, L, hw, atr, roles=("sup", "res"), p: dict | None = None) -> list[dict]:
    """Sinais T0–T3 para UM nível (L e hw podem variar por barra; valores congelados por episódio)."""
    p = {**DEFAULT, **(p or {})}
    o = np.asarray(o, float); h = np.asarray(h, float); l = np.asarray(l, float); c = np.asarray(c, float)
    L = np.broadcast_to(np.asarray(L, float), c.shape)
    hw = np.broadcast_to(np.asarray(hw, float), c.shape)
    atr = np.asarray(atr, float)
    n = len(c)
    out: list[dict] = []
    last_side = 0
    ep = {"sup": None, "res": None}       # (t0, L0, h0, fired:set)
    brk = {"sup": None, "res": None}      # (j, L0, h0)
    nb = p["outside_bars"]
    for t in range(n):
        Lt, ht, a = L[t], hw[t], atr[t]
        if not (np.isfinite(Lt) and np.isfinite(ht) and np.isfinite(a)):
            continue
        top, bot = Lt + ht, Lt - ht
        rng = h[t] - l[t]
        # ── T0: entrada na zona após nb barras fora ───────────────────────
        if "sup" in roles and t >= nb and last_side == 1 and l[t] <= top and np.all(l[t - nb:t] > top):
            ep["sup"] = (t, Lt, ht, set())
            out.append(_sig(t, "T0", +1, Lt, ht, "sup"))
        if "res" in roles and t >= nb and last_side == -1 and h[t] >= bot and np.all(h[t - nb:t] < bot):
            ep["res"] = (t, Lt, ht, set())
            out.append(_sig(t, "T0", -1, Lt, ht, "res"))
        # ── T1/T2 dentro da janela do episódio ─────────────────────────────
        for role, sd in (("sup", +1), ("res", -1)):
            e = ep[role]
            if e is None:
                continue
            t0, L0, h0, fired = e
            if t - t0 > p["episode_window"] - 1:
                ep[role] = None
                continue
            if sd == 1:
                ztop, zbot = L0 + h0, L0 - h0
                if "T1" not in fired and rng >= p["t1_min_range_atr"] * a and rng > 0 and l[t] <= ztop \
                        and c[t] >= L0 and (min(o[t], c[t]) - l[t]) >= p["t1_wick"] * rng \
                        and c[t] >= l[t] + p["t1_close_pos"] * rng:
                    fired.add("T1"); out.append(_sig(t, "T1", +1, L0, h0, role))
                if "T2" not in fired and c[t] > L0 + p["t2_reclaim_h"] * h0:
                    j0 = max(t0, t - p["t2_lookback"])
                    js = [j for j in range(j0, t + 1) if l[j] < zbot]
                    if js and np.all(c[js[0]:t + 1] >= zbot - p["t2_max_close_below_atr"] * a):
                        fired.add("T2"); out.append(_sig(t, "T2", +1, L0, h0, role))
            else:
                ztop, zbot = L0 + h0, L0 - h0
                if "T1" not in fired and rng >= p["t1_min_range_atr"] * a and rng > 0 and h[t] >= zbot \
                        and c[t] <= L0 and (h[t] - max(o[t], c[t])) >= p["t1_wick"] * rng \
                        and c[t] <= h[t] - p["t1_close_pos"] * rng:
                    fired.add("T1"); out.append(_sig(t, "T1", -1, L0, h0, role))
                if "T2" not in fired and c[t] < L0 - p["t2_reclaim_h"] * h0:
                    j0 = max(t0, t - p["t2_lookback"])
                    js = [j for j in range(j0, t + 1) if h[j] > ztop]
                    if js and np.all(c[js[0]:t + 1] <= ztop + p["t2_max_close_below_atr"] * a):
                        fired.add("T2"); out.append(_sig(t, "T2", -1, L0, h0, role))
        # ── T3: rompimento e reteste ───────────────────────────────────────
        for role in ("sup", "res"):
            b = brk[role]
            if b is None or role not in roles:
                continue
            j, L0, h0 = b
            if t - j > p["t3_retest_window"]:
                brk[role] = None
                continue
            if role == "sup":
                if c[t] > L0 + h0:
                    brk[role] = None
                elif h[t] >= L0 - h0 and c[t] < L0 - p["t3_reject_h"] * h0:
                    out.append(_sig(t, "T3", -1, L0, h0, role)); brk[role] = None
            else:
                if c[t] < L0 - h0:
                    brk[role] = None
                elif l[t] <= L0 + h0 and c[t] > L0 + p["t3_reject_h"] * h0:
                    out.append(_sig(t, "T3", +1, L0, h0, role)); brk[role] = None
        if t >= 1 and np.isfinite(L[t - 1]) and np.isfinite(hw[t - 1]):
            if "sup" in roles and c[t] < bot and c[t - 1] >= L[t - 1] - hw[t - 1]:
                brk["sup"] = (t, Lt, ht)
            if "res" in roles and c[t] > top and c[t - 1] <= L[t - 1] + hw[t - 1]:
                brk["res"] = (t, Lt, ht)
        if c[t] > top:
            last_side = 1
        elif c[t] < bot:
            last_side = -1
    return out


def detect_session(o, h, l, c, levels: list[float], hw, atr, p: dict | None = None) -> list[dict]:
    """Sinais de todos os níveis (constantes) de uma sessão, ordenados por t."""
    out = []
    for L in levels:
        for s in detect_level(o, h, l, c, L, hw, atr, p=p):
            out.append(s)
    order = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}
    return sorted(out, key=lambda s: (s["t"], order[s["trigger"]], s["L"]))


def rolling_levels(h, l, lookback: int = 12) -> tuple[np.ndarray, np.ndarray]:
    """Níveis do controle P1: mínimo/máximo das `lookback` barras ANTERIORES (t−lookback..t−1)."""
    h = np.asarray(h, float); l = np.asarray(l, float)
    n = len(h)
    lo = np.full(n, np.nan); hi = np.full(n, np.nan)
    for t in range(lookback, n):
        lo[t] = l[t - lookback:t].min()
        hi[t] = h[t - lookback:t].max()
    return lo, hi