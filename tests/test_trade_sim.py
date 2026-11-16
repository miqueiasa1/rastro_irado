"""Fase 20 — simulador de operações (stop/alvo/tempo, ambiguidade, custos, uma operação por vez)."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.eval.trade_sim import simulate_session  # noqa: E402

N = 30


def _flat(px=100.0):
    o = np.full(N, px); h = o + 0.5; l = o - 0.5; c = o.copy()
    return o, h, l, c


def _sig(t, side=1, L=99.0, hw=1.0):
    return {"t": t, "side": side, "L": L, "hw": hw, "trigger": "T1", "role": "sup"}


K = np.arange(N) + 6          # todas as barras dentro da janela de entrada
A = np.full(N, 2.0)


def test_target_hit_and_cost():
    o, h, l, c = _flat()
    l[5] = 98.0                       # barra do gatilho: stop = min(98, 98) − 0,2 → 97,5 (tick 0,5)
    h[8] = 104.0                      # alvo 1,5R = 100 + 3,75 → 103,5
    tr, _ = simulate_session([_sig(5)], o, h, l, c, K, A, [], cost=1.0, tick=0.5)
    t = tr[0]
    assert t["stop"] == 97.5 and t["R"] == 2.5 and t["target"] == 103.5
    assert t["reason"] == "target" and t["exit"] == 103.5 and t["net"] == 103.5 - 100 - 1.0


def test_ambiguous_bar_counts_stop():
    o, h, l, c = _flat()
    l[5] = 98.0
    h[7], l[7] = 104.0, 97.0
    t = simulate_session([_sig(5)], o, h, l, c, K, A, [], cost=0.0, tick=0.5)[0][0]
    assert t["reason"] == "stop" and t["ambiguous"] and t["exit"] == 97.5


def test_gap_through_stop_exits_at_open():
    o, h, l, c = _flat()
    l[5] = 98.0
    o[8], h[8], l[8], c[8] = 96.0, 96.5, 95.5, 96.0
    t = simulate_session([_sig(5)], o, h, l, c, K, A, [], cost=0.0, tick=0.5)[0][0]
    assert t["reason"] == "stop" and t["exit"] == 96.0


def test_time_exit_after_12_bars_and_next_level_target():
    o, h, l, c = _flat()
    l[5] = 98.0
    c[17] = 101.0
    t = simulate_session([_sig(5)], o, h, l, c, K, A, [99.0, 102.0], cost=0.0, tick=0.5)[0][0]
    assert t["target"] == 101.5          # próximo nível 102 − 0,5·h(1) < 1,5R
    assert t["reason"] == "time" and t["exit_i"] == 17 and t["exit"] == 101.0


def test_one_position_at_a_time_and_risk_filter():
    o, h, l, c = _flat()
    l[5] = 98.0
    tr, sk = simulate_session([_sig(5), _sig(7)], o, h, l, c, K, A, [], cost=0.0, tick=0.5)
    assert len(tr) == 1 and sk["busy"] == 1
    l2 = l.copy(); l2[5] = 90.0          # risco > 2,5·ATR → descarta
    tr2, sk2 = simulate_session([_sig(5)], o, h, l2, c, K, A, [], cost=0.0, tick=0.5)
    assert tr2 == [] and sk2["risk"] == 1


def test_entry_window_and_short_mirror():
    o, h, l, c = _flat()
    k = K.copy(); k[6] = 97
    _, sk = simulate_session([_sig(5)], o, h, l, c, k, A, [], cost=0.0, tick=0.5)
    assert sk["window"] == 1
    h[5] = 102.0; l[9] = 95.0
    t = simulate_session([_sig(5, side=-1, L=101.0)], o, h, l, c, K, A, [], cost=0.0, tick=0.5)[0][0]
    assert t["stop"] == 102.5 and t["reason"] == "target" and t["gross"] > 0