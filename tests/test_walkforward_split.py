"""Fase 18 — splits walk-forward com purge/embargo por sessão (SPEC §6, REQ-T02)."""
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.eval.walkforward import monthly_splits, purged_kfold  # noqa: E402

SESS = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-02", "2025-12-31")]


def test_monthly_blocks_are_out_of_sample_with_embargo():
    sp = monthly_splits(SESS, "2025-06", embargo=1, min_train=60)
    assert [s.test_label for s in sp] == [f"2025-{m:02d}" for m in range(6, 13)]
    for s in sp:
        assert max(s.train_sessions) < min(s.test_sessions)
        # embargo de 1 sessão: a sessão imediatamente anterior ao teste fica fora do treino
        before = [x for x in SESS if x < s.test_sessions[0]]
        assert before[-1] not in s.train_sessions and before[-2] in s.train_sessions
        assert set(s.test_sessions) == {x for x in SESS if x[:7] == s.test_label}
    # janela expansiva: o treino só cresce
    sizes = [len(s.train_sessions) for s in sp]
    assert sizes == sorted(sizes)


def test_min_train_and_rolling():
    assert monthly_splits(SESS, "2025-02", min_train=60)[0].test_label == "2025-04"
    sp = monthly_splits(SESS, "2025-06", rolling=40)
    assert all(len(s.train_sessions) == 40 for s in sp)


def test_purged_kfold_has_embargo_and_covers_all():
    tr = SESS[:100]
    folds = purged_kfold(tr, k=5, embargo=2)
    assert len(folds) == 5
    vals = [v for _, v in folds]
    assert sorted(x for v in vals for x in v) == tr
    for train, val in folds:
        assert not set(train) & set(val)
        i0, i1 = tr.index(val[0]), tr.index(val[-1])
        gap = set(tr[max(0, i0 - 2):i0]) | set(tr[i1 + 1:i1 + 3])
        assert not gap & set(train)
        assert len(train) == len(tr) - len(val) - len(gap)
