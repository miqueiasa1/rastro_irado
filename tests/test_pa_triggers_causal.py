"""Fase 20 — gatilhos de price action (casos à mão e causalidade por truncamento)."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.eval.pa_triggers import atr_prev, detect_level, detect_session, rolling_levels, true_range  # noqa: E402


def _bars(rows):
    a = np.array(rows, float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def test_atr_prev_uses_only_past_bars():
    tr = np.array([1, 2, 3, 4, 5, 6, 100], float)
    a = atr_prev(tr, n=14, min_bars=5, fallback=9.0)
    assert np.all(a[:5] == 9.0)
    assert a[5] == np.mean(tr[:5]) and a[6] == np.mean(tr[:6])   # barra 6 (TR=100) não entra em a[6]


def test_t0_and_t1_rejection_at_support():
    # nível 100, h=2; preço vem de cima, toca e rejeita com pavio
    rows = [(110, 111, 109, 110)] * 4 + [(106, 106.5, 99.0, 105.5)] + [(105.5, 107, 105, 106)] * 3
    o, h, l, c = _bars(rows)
    sig = detect_level(o, h, l, c, 100.0, 2.0, np.full(len(c), 3.0))
    trig = [(s["t"], s["trigger"], s["side"]) for s in sig]
    assert (4, "T0", 1) in trig and (4, "T1", 1) in trig
    assert all(s["side"] == 1 for s in sig if s["trigger"] in ("T0", "T1"))


def test_t2_sweep_and_reclaim():
    rows = [(110, 111, 109, 110)] * 4 + [(103, 103.5, 101.5, 102)] + [(102, 102.5, 96.5, 97.5)] + [(97.5, 103.5, 97, 103)]
    o, h, l, c = _bars(rows)
    sig = detect_level(o, h, l, c, 100.0, 2.0, np.full(len(c), 3.0))
    assert ("T2", 1, 6) in [(s["trigger"], s["side"], s["t"]) for s in sig]


def test_t3_break_and_retest_short():
    rows = [(110, 111, 109, 110)] * 4 + [(104, 104, 101, 101.5), (101.5, 101.6, 96, 96.5),
                                          (96.5, 98.5, 96, 97), (97, 98.2, 96.5, 99.0)]
    o, h, l, c = _bars(rows)
    sig = detect_level(o, h, l, c, 100.0, 2.0, np.full(len(c), 3.0))
    t3 = [s for s in sig if s["trigger"] == "T3"]
    assert len(t3) == 1 and t3[0]["side"] == -1 and t3[0]["t"] == 6


def test_resistance_mirror():
    rows = [(90, 91, 89, 90)] * 4 + [(94, 101, 93.5, 94.5)] + [(94.5, 95, 93, 94)] * 2
    o, h, l, c = _bars(rows)
    sig = detect_level(o, h, l, c, 100.0, 2.0, np.full(len(c), 3.0))
    assert ("T0", -1) in [(s["trigger"], s["side"]) for s in sig]
    assert ("T1", -1) in [(s["trigger"], s["side"]) for s in sig]


def test_truncation_invariance_random_walk():
    rng = np.random.default_rng(7)
    for _ in range(25):
        n = 113
        c = 1000 + np.cumsum(rng.normal(0, 4, n))
        o = np.r_[c[0], c[:-1]] + rng.normal(0, 1, n)
        h = np.maximum(o, c) + np.abs(rng.normal(0, 2, n))
        l = np.minimum(o, c) - np.abs(rng.normal(0, 2, n))
        levels = list(np.round(rng.uniform(c.min(), c.max(), 3), 1))
        a = atr_prev(true_range(o, h, l, c), fallback=5.0)
        hw = np.maximum(0.5 * a, 2.0)
        full = detect_session(o, h, l, c, levels, hw, a)
        for cut in (20, 50, 80, 112):
            part = detect_session(o[:cut], h[:cut], l[:cut], c[:cut], levels, hw[:cut], atr_prev(true_range(o[:cut], h[:cut], l[:cut], c[:cut]), fallback=5.0))
            assert [s for s in full if s["t"] < cut] == part
        lo, hi = rolling_levels(h, l, 12)
        assert np.isnan(lo[11]) and lo[12] == l[:12].min() and hi[30] == h[18:30].max()