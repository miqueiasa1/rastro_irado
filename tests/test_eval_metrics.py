"""
Testes do módulo de métricas e utilitários do harness de assertividade (fase 15).
"""

import os
import sqlite3
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.eval import metrics as M  # noqa: E402
from backend.eval.data import broker_wall_to_brt, connect_ro  # noqa: E402
from backend.eval.report import persist_rows, write_text  # noqa: E402
from backend.timeconv import broker_wall_to_brt_wall  # noqa: E402


def test_auc_matches_sklearn_with_ties():
    sk = pytest.importorskip("sklearn.metrics")
    rng = np.random.default_rng(42)
    s = np.round(rng.random(2000), 2)  # força empates
    y = (rng.random(2000) < 0.3 + 0.4 * s).astype(int)
    assert M.auc(s, y) == pytest.approx(sk.roc_auc_score(y, s), abs=1e-12)


def test_auc_single_class_is_nan():
    assert np.isnan(M.auc([0.1, 0.9], [1, 1]))


def test_brier_and_skill():
    p = np.array([0.8, 0.2, 0.6, 0.4])
    y = np.array([1, 0, 0, 1])
    assert M.brier(p, y) == pytest.approx((0.04 + 0.04 + 0.36 + 0.36) / 4)
    # climatologia: base 0,5 -> Brier ref 0,25
    assert M.brier_skill(p, y) == pytest.approx(1 - 0.2 / 0.25)
    # prever a taxa-base dá BSS = 0
    assert M.brier_skill(np.full(4, 0.5), y) == pytest.approx(0.0)


def test_hit_rate_threshold_counts_as_down():
    assert M.hit_rate([0.5, 0.51], [0, 1]) == 1.0
    assert M.hit_rate([0.5], [1]) == 0.0


def test_ece_and_reliability():
    p = np.full(10, 0.7)
    y = np.array([1] * 5 + [0] * 5)
    assert M.ece(p, y) == pytest.approx(0.2)
    rel = M.reliability_table(np.array([0.0, 0.05, 0.95, 1.0]), np.array([0, 0, 1, 1]))
    assert len(rel) == 10
    assert sum(r["n"] for r in rel) == 4
    assert rel[9]["n"] == 2  # p = 1,0 cai no último bin
    perfect = np.repeat(np.linspace(0.05, 0.95, 10), 1000)
    rng = np.random.default_rng(0)
    yy = (rng.random(len(perfect)) < perfect).astype(int)
    assert M.ece(perfect, yy) < 0.02


def test_session_bootstrap_is_deterministic_and_resamples_sessions():
    rng = np.random.default_rng(1)
    sess = np.repeat([f"2026-08-{d:02d}" for d in range(1, 21)], 50)
    p = rng.random(len(sess))
    y = (rng.random(len(sess)) < p).astype(int)
    a = M.evaluate_probability(p, y, sess, n_boot=200, seed=7)
    b = M.evaluate_probability(p, y, sess, n_boot=200, seed=7)
    c = M.evaluate_probability(p, y, sess, n_boot=200, seed=8)
    assert a == b
    assert (a["auc_lo"], a["auc_hi"]) != (c["auc_lo"], c["auc_hi"])
    assert a["auc_lo"] <= a["auc"] <= a["auc_hi"]
    assert a["n_sessions"] == 20
    groups = M.session_groups(sess)
    assert len(groups) == 20 and all(len(g) == 50 for g in groups)


def test_mean_ci_by_session():
    x = np.ones(100)
    m, lo, hi = M.mean_ci_by_session(x, np.repeat(np.arange(10), 10), n_boot=50)
    assert (m, lo, hi) == (1.0, 1.0, 1.0)


@pytest.mark.parametrize("wall", [
    "2026-07-15 15:00:00",  # verão americano (broker = BRT + 6h)
    "2026-11-10 14:00:00",  # inverno americano (broker = BRT + 5h)
    "2026-03-03 20:25:00",
    "2026-10-30 23:55:00",
])
def test_vectorized_conversion_matches_timeconv(wall):
    got = broker_wall_to_brt(pd.Series([wall + "Z"])).iloc[0].tz_localize(None).to_pydatetime()
    exp = broker_wall_to_brt_wall(datetime.fromisoformat(wall))
    assert got == exp


def test_connect_ro_refuses_writes(tmp_path):
    db = tmp_path / "x.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE t (a INTEGER)")
    c.commit()
    c.close()
    ro = connect_ro(str(db))
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("INSERT INTO t VALUES (1)")
    ro.close()
    with pytest.raises(FileNotFoundError):
        connect_ro(str(tmp_path / "nao_existe.db"))


def test_persist_rows_uses_separate_store_and_is_idempotent(tmp_path):
    row = dict(eval_date="2026-11-10", target="WIN$N", model="nowcast", version_id=None, horizon="60m",
               window_sessions=20, n=10, auc=0.5, auc_lo=0.4, auc_hi=0.6, brier=0.25, bss=0.0, ece=0.01,
               hit=0.5, config_hash="abc", code_git_sha="sha")
    store = tmp_path / "eval" / "forecast_eval.db"
    assert persist_rows(str(store), [row]) == 1
    assert persist_rows(str(store), [row]) == 1
    c = sqlite3.connect(store)
    assert c.execute("SELECT COUNT(*) FROM forecast_eval_daily").fetchone()[0] == 1
    c.close()
    for forbidden in ("irai_live.db", "irai.db", "market_data.db"):
        with pytest.raises(ValueError):
            persist_rows(str(tmp_path / forbidden), [row])


def test_write_text_frozen_is_immutable(tmp_path):
    p = tmp_path / "b.json"
    write_text(str(p), "a\n", overwrite=False)
    with pytest.raises(FileExistsError):
        write_text(str(p), "b\n", overwrite=False)
    assert p.read_bytes() == b"a\n"
