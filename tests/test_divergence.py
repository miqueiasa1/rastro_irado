"""Fase 20 (divergência) — inclinação, episódios, confirmação e saída por tempo, sem lookahead."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.eval.divergence import (confirm, divergence_episodes, pullback_episodes,  # noqa: E402
                                     rolling_slope, time_exit_trades)


def test_rolling_slope_exact_and_causal():
    x = np.array([1, 2, 3, 5, 9, np.nan, 1, 2, 3], float)
    s = rolling_slope(x, 2)
    assert np.isnan(s[1]) and s[2] == 1.0 and s[3] == 1.5
    assert np.isnan(s[5]) and np.isnan(s[6]) and np.isnan(s[7]) and s[8] == 1.0
    y = np.cumsum(np.random.default_rng(1).normal(size=60))
    full = rolling_slope(y, 6)
    for cut in (10, 30, 59):
        np.testing.assert_array_equal(rolling_slope(y[:cut], 6), full[:cut])


def test_divergence_episode_starts_and_directions():
    sp = np.array([0, 2, 2, 0, -2, -2], float)
    sx = np.array([0, -2, -2, 0, 2, 0], float)
    ep = divergence_episodes(sp, sx, 1.0, 1.0, 1.0)
    assert ep == [(1, 1), (4, -1)]
    assert pullback_episodes(sx, 1.0, 1.0) == [(1, 1), (4, -1)]


def test_confirm_first_close_beyond_prior_extreme():
    h = np.array([10, 10, 10, 10, 10], float)
    l = np.array([9, 9, 9, 9, 9], float)
    c = np.array([9.5, 9.5, 9.8, 10.5, 11], float)
    s = confirm([(1, 1)], h, l, c, window=6)
    assert s == [{"t": 3, "side": 1, "t0": 1}]
    assert confirm([(1, -1)], h, l, c, window=6) == []


def test_time_exit_and_one_position():
    o = np.arange(30, dtype=float)
    c = o + 0.5
    k = np.arange(30) + 6
    tr = time_exit_trades([{"t": 2, "side": 1}, {"t": 5, "side": 1}, {"t": 20, "side": -1}], o, c, k, cost=1.0)
    assert len(tr) == 2
    assert tr[0]["entry_i"] == 3 and tr[0]["exit_i"] == 14 and tr[0]["gross"] == 14.5 - 3
    assert tr[1]["entry_i"] == 21 and tr[1]["net"] == -(29.5 - 21) - 1.0