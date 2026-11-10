"""Fase 18 — features causais e valor justo da cesta (SPEC §4, R1).

Critério: nenhuma feature usa dado posterior à barra. Verificado por invariância à truncagem
(calcular com o histórico cortado numa sessão dá exatamente o mesmo valor para as sessões até ela)
e por propriedades da padronização (σ do gap só com sessões anteriores).
"""
import os
import sqlite3
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import f18_fixtures as fx  # noqa: E402
from backend.irai.features import (FairValueConfig, build_panel, fair_value, fit_gamma,  # noqa: E402
                                   forecast_features, forward_targets)

CFG = FairValueConfig(window_sessions=20, sigma_sessions=20, min_sessions=10)
SESS = fx.sessions(45)
CUT = SESS[30]


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    return fx.build_db(str(tmp_path_factory.mktemp("f18") / "bars.db"))


def _panel(db, end, start=SESS[0]):
    conn = sqlite3.connect(db)
    try:
        return build_panel(conn, fx.TARGET, fx.FACTORS, start, end)
    finally:
        conn.close()


def test_panel_shape_and_anchor(db):
    p = _panel(db, SESS[-1])
    df = p.df
    assert df.sess.nunique() == 45
    assert df.groupby("sess").size().eq(113).all()          # 09:00–18:20 = 113 barras M5
    first = df.groupby("sess").head(1)
    # âncora na abertura: r da 1ª barra = log(close/open) da própria barra
    assert np.allclose(first.rT, np.log(first.close / first.o0))
    assert (df.k.min(), df.k.max()) == (0, 112)


def test_fit_gamma_recovers_known_betas(db):
    p = _panel(db, SESS[-1])
    fv = fair_value(p, CFG)
    g = np.array(list(fv.attrs["gammas"].values()))
    expect = np.array([fx.GAMMA[f] for f in fx.FACTORS])
    assert np.allclose(np.median(g, axis=0), expect, atol=0.12)
    X = np.random.default_rng(0).normal(size=(500, 2))
    y = X @ np.array([0.5, -1.0])
    assert np.allclose(fit_gamma(X, y, ridge=1e-9), [0.5, -1.0], atol=1e-6)


def test_fair_value_is_truncation_invariant(db):
    full = fair_value(_panel(db, SESS[-1]), CFG)
    cut = fair_value(_panel(db, CUT), CFG)
    a = full[full.sess <= CUT].reset_index(drop=True)
    b = cut.reset_index(drop=True)
    assert len(a) == len(b)
    for c in ("fv", "gap", "gap_sigma", "z"):
        assert np.allclose(a[c], b[c], equal_nan=True, rtol=0, atol=1e-12), c


def test_gap_sigma_uses_only_previous_sessions(db):
    fv = fair_value(_panel(db, SESS[-1]), CFG)
    s = fv.groupby("sess").z.apply(lambda x: x.notna().any())
    # sem z nas primeiras sessões: precisa de min_sessions de γ e depois min_sessions de gaps passados
    assert not s.iloc[:CFG.min_sessions].any()
    assert s.iloc[-5:].all()
    # mudar o gap de uma sessão não muda o σ dela mesma (nem das anteriores)
    p = _panel(db, SESS[-1])
    p2 = _panel(db, SESS[-1])
    last = SESS[-1]
    p2.df.loc[p2.df.sess == last, "rT"] += 0.05
    a, b = fair_value(p, CFG), fair_value(p2, CFG)
    m = a.sess == last
    assert np.allclose(a.gap_sigma[m], b.gap_sigma[m], equal_nan=True)
    assert not np.allclose(a.gap[m], b.gap[m])


def test_z_is_roughly_standardized(db):
    fv = fair_value(_panel(db, SESS[-1]), CFG)
    z = fv.z.dropna()
    assert 0.7 < z.std() < 1.4
    assert (z.abs() > 2).mean() < 0.12   # o z atual do engine fica em ~31–36%


def test_pair_only_uses_the_pair(db):
    fv = fair_value(_panel(db, SESS[-1]), CFG, pair_only=True)
    assert fv.attrs["factors"] == ["WDO$N"]
    g = np.array(list(fv.attrs["gammas"].values()))
    assert g.shape[1] == 1


def test_forecast_features_are_truncation_invariant(db):
    full_p, cut_p = _panel(db, SESS[-1]), _panel(db, CUT)
    F_full = forecast_features(full_p, fair_value(full_p, CFG), fair_value(full_p, CFG, pair_only=True), sigma_window=20)
    F_cut = forecast_features(cut_p, fair_value(cut_p, CFG), fair_value(cut_p, CFG, pair_only=True), sigma_window=20)
    a = F_full[F_full.sess <= CUT].reset_index(drop=True)
    b = F_cut.reset_index(drop=True)
    assert list(a.columns) == list(b.columns)
    for c in a.columns:
        if c == "sess":
            continue
        assert np.allclose(a[c].astype(float), b[c].astype(float), equal_nan=True, atol=1e-10), c


def test_forecast_features_ignore_future_bars_of_same_session(db):
    """Cortar a sessão no meio (barras até 13:00) não muda nenhuma feature até 13:00."""
    full_p = _panel(db, CUT)
    cut_p = _panel(db, CUT)
    keep = ~((cut_p.df.sess == CUT) & (cut_p.df.k > 48))
    cut_p.df = cut_p.df[keep].reset_index(drop=True)
    Fa = forecast_features(full_p, sigma_window=20)
    Fb = forecast_features(cut_p, sigma_window=20)
    a = Fa[keep.to_numpy()].reset_index(drop=True)
    for c in Fa.columns:
        if c == "sess":
            continue
        assert np.allclose(a[c].astype(float), Fb[c].astype(float), equal_nan=True, atol=1e-10), c


def test_untraded_factor_contributes_zero(tmp_path):
    late = {"sess": SESS[5], "symbol": "US500", "first_min": 10 * 60}
    db = fx.build_db(str(tmp_path / "late.db"), n_sessions=10, late_factor=late)
    conn = sqlite3.connect(db)
    p = build_panel(conn, fx.TARGET, fx.FACTORS, SESS[0], SESS[9])
    conn.close()
    d = p.df[p.df.sess == SESS[5]]
    col = p.factor_cols["US500"]
    assert (d.loc[d.k < 12, col] == 0).all()           # antes do 1º negócio (10:00): 0
    assert d.loc[d.k >= 13, col].abs().gt(0).any()      # depois ancora no 1º negócio do dia
    other = p.df[p.df.sess == SESS[4]]
    assert other.loc[other.k < 12, col].abs().gt(0).any()  # sessão normal: contribui desde 09:00


def test_forward_targets_stay_in_session(db):
    p = _panel(db, SESS[3])
    y = forward_targets(p)
    last = p.df.groupby("sess").cumcount(ascending=False)
    assert y.loc[last < 3, "y15"].isna().all()
    assert y.loc[last == 0, "yclose"].isna().all()
    assert y.loc[last >= 12, "y60"].notna().all()
