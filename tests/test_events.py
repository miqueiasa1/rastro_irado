"""Fase 18 — descolamentos como eventos de entrada (P&L líquido de custo, ICs por pregão, BH)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.eval.events import (COST_PTS, bh_adjust, cluster_t, detect_events, event_table,  # noqa: E402
                                 live_spread_events)


def _df(z_by_sess, close_by_sess):
    rows = []
    for s, (z, c) in enumerate(zip(z_by_sess, close_by_sess)):
        for k, (zz, cc) in enumerate(zip(z, c)):
            rows.append({"sess": f"2026-01-{s + 1:02d}", "k": k, "z": zz, "close": cc})
    return pd.DataFrame(rows)


def test_detect_first_cross_only_inside_entry_window():
    z = np.array([0, 0, 0, 0, 0, 0, 2.5, 2.6, 1.0, 2.2, 0, -2.1] + [0] * 100, float)
    sess = np.zeros(len(z), int)
    k = np.arange(len(z))
    ev = detect_events(z, sess, k, 2.0)
    assert ev.tolist() == [6, 9, 11]
    z2 = z.copy()
    z2[2] = 3.0  # antes de 09:30 (k<6): não conta
    assert 2 not in detect_events(z2, sess, k, 2.0)
    # mudança de pregão não conta como cruzamento contínuo
    sess2 = np.r_[np.zeros(7, int), np.ones(len(z) - 7, int)]
    assert 7 not in detect_events(z, sess2, k, 2.0)


def test_event_pnl_is_contrarian_and_net_of_cost():
    n = 40
    z = [0.0] * n
    z[10] = 2.5                     # alvo caro → venda
    close = [100.0] * 11 + [80.0] * (n - 11)  # caiu 20 pts depois do evento
    d = _df([z, z, z], [close, close, close])
    r = event_table(d, "z", 2.0, "WIN$N", horizons=(3,), n_boot=50)
    assert r["events"] == 3
    assert r["gross_15m"] == pytest.approx(20.0)
    assert r["net_15m"] == pytest.approx(20.0 - COST_PTS["WIN$N"])
    assert r["hit_15m"] == 1.0
    seg = event_table(d, "z", 2.0, "WIN$N", horizons=(3,), direction=+1, n_boot=50)
    assert seg["net_15m"] == pytest.approx(-20.0 - COST_PTS["WIN$N"])


def test_coverage_counts_abs_z_above_2():
    z = [0.0] * 10 + [2.5, -2.5] + [0.0] * 8
    d = _df([z], [[100.0] * 20])
    assert event_table(d, "z", 2.0, "WDO$N", n_boot=10)["coverage_abs_gt2"] == pytest.approx(0.1)
    rows = live_spread_events(d.rename(columns={"z": "pair_z"}), target="WDO$N", n_boot=10)
    assert [r["z"] for r in rows] == ["pair_z"]


def test_cluster_t_and_bh():
    rng = np.random.default_rng(0)
    sess = np.repeat(np.arange(30), 4)
    x = rng.normal(1.0, 1.0, len(sess))
    t = cluster_t(x, sess)
    assert t > 3
    assert np.isnan(cluster_t(np.array([1.0, 2.0]), np.array([0, 1])))
    q = bh_adjust([0.01, 0.04, 0.03, 0.2, float("nan")])
    assert q[:4] == pytest.approx([0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.2])
    assert np.isnan(q[4])
