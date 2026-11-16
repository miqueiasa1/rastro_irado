"""
Simulador de operações dos alertas da fase 20 (20-PLAN-01 §4). Uma sessão por chamada.

- Entrada na abertura da barra seguinte à decisão (t+1), só se k(t+1) ∈ [6, 96] (09:30–17:00).
- Uma operação aberta por vez (por braço e ativo); sinal durante uma operação é ignorado.
- Stop: compra → min(low_t, L−h) − 0,1·ATR (arredondado para baixo no tick); venda espelhado.
  Risco R = |entrada − stop| precisa estar em [0,5; 2,5]·ATR, senão o sinal é descartado.
- Alvo: o menor entre 1,5R e (próximo nível além de entrada + h) − 0,5·h; arredondado em direção
  à entrada.
- Saída: stop/alvo dentro da barra; se os dois cabem na mesma barra, conta o STOP (conservador);
  gap além do stop sai na abertura; senão, no fechamento da barra t+12 (60 min) ou na última
  barra do pregão.
- Custo por operação (ida e volta) subtraído em pontos.
"""
from __future__ import annotations

import math

import numpy as np

SIM_DEFAULT = {"stop_buffer_atr": 0.1, "risk_atr": (0.5, 2.5), "target_R": 1.5,
               "target_level_h": 0.5, "hold_bars": 12, "entry_k": (6, 96)}


def _floor_tick(x, tick):
    return math.floor(x / tick + 1e-9) * tick


def _ceil_tick(x, tick):
    return math.ceil(x / tick - 1e-9) * tick


def simulate_session(signals: list[dict], o, h, l, c, k, atr, levels: list[float], cost: float,
                     tick: float, p: dict | None = None) -> tuple[list[dict], dict]:
    """Retorna (operações, contagem de descartes)."""
    p = {**SIM_DEFAULT, **(p or {})}
    o = np.asarray(o, float); h = np.asarray(h, float); l = np.asarray(l, float); c = np.asarray(c, float)
    k = np.asarray(k, int); atr = np.asarray(atr, float)
    lv = np.array(sorted(levels), float)
    n = len(c)
    trades, skip = [], {"no_entry": 0, "window": 0, "busy": 0, "risk": 0}
    busy_until = -1
    for s in sorted(signals, key=lambda x: x["t"]):
        t, sd, L, hw = s["t"], s["side"], s["L"], s["hw"]
        e = t + 1
        if e >= n:
            skip["no_entry"] += 1; continue
        if not (p["entry_k"][0] <= k[e] <= p["entry_k"][1]):
            skip["window"] += 1; continue
        if e <= busy_until:
            skip["busy"] += 1; continue
        a = atr[t]
        entry = o[e]
        if sd == 1:
            stop = _floor_tick(min(l[t], L - hw) - p["stop_buffer_atr"] * a, tick)
        else:
            stop = _ceil_tick(max(h[t], L + hw) + p["stop_buffer_atr"] * a, tick)
        R = (entry - stop) * sd
        if not (np.isfinite(R) and R > 0 and p["risk_atr"][0] * a <= R <= p["risk_atr"][1] * a):
            skip["risk"] += 1; continue
        tgt = entry + sd * p["target_R"] * R
        if sd == 1:
            nxt = lv[lv > entry + hw]
            if len(nxt):
                t2 = nxt[0] - p["target_level_h"] * hw
                if t2 > entry:
                    tgt = min(tgt, t2)
            tgt = _floor_tick(tgt, tick)
        else:
            nxt = lv[lv < entry - hw]
            if len(nxt):
                t2 = nxt[-1] + p["target_level_h"] * hw
                if t2 < entry:
                    tgt = max(tgt, t2)
            tgt = _ceil_tick(tgt, tick)
        if (tgt - entry) * sd <= 0:
            tgt = entry + sd * tick
        last = min(e + p["hold_bars"] - 1, n - 1)
        exit_px, reason, xi, amb = None, None, last, False
        for i in range(e, last + 1):
            if sd == 1:
                if i > e and o[i] <= stop:
                    exit_px, reason, xi = o[i], "stop", i; break
                hs, ht = l[i] <= stop, h[i] >= tgt
            else:
                if i > e and o[i] >= stop:
                    exit_px, reason, xi = o[i], "stop", i; break
                hs, ht = h[i] >= stop, l[i] <= tgt
            if hs:
                exit_px, reason, xi, amb = stop, "stop", i, bool(ht); break
            if ht:
                exit_px, reason, xi = tgt, "target", i; break
        if exit_px is None:
            exit_px, reason = c[last], ("time" if last == e + p["hold_bars"] - 1 else "eod")
        gross = (exit_px - entry) * sd
        trades.append({**s, "entry_i": e, "entry": float(entry), "stop": float(stop), "target": float(tgt),
                       "R": float(R), "atr": float(a), "exit_i": int(xi), "exit": float(exit_px),
                       "reason": reason, "ambiguous": amb, "gross": float(gross), "net": float(gross - cost),
                       "net_R": float((gross - cost) / R),
                       "fixed60_net": float((c[last] - entry) * sd - cost)})
        busy_until = xi
    return trades, skip