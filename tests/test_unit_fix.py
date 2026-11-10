"""Fase 17 — correção da unidade β/z, ruído do Kalman calibrado e honestidade da API.

Critérios (PHASES.md, fase 17):
  1. Score corrigido = preditor linear da regressão (Σ β·r), na escala de "desvios".
  3. Versões legado/adotadas calculam exatamente como antes (opções padrão); a correção só vale
     para versões novas que gravam `unit_fix=1` (shadow até promoção explícita).
  REQ-A04: `calibrated` não depende da acurácia; `forecast_ui` padrão 'off'.
"""
import importlib.util
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fase16_fixtures as fx  # noqa: E402
from backend.db import get_connection  # noqa: E402
from backend.irai import model_registry as mr  # noqa: E402
from backend.irai.engine import IRAIEngine  # noqa: E402
from backend.irai.nowcast_calib import (compare_scores, estimate_kalman_noise, fit_logistic,  # noqa: E402
                                        score_fixed, score_old)

D_MID = "2026-11-04"
D_NEW = "2026-11-05"


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def db(tmp_path):
    p = fx.build_db(str(tmp_path / "f17.db"))
    _load_script("migrate_fase16_model_versions").migrate(p)
    return p


def _register(db, extra):
    conn = get_connection(db)
    params = dict(fx.NEW_PARAMS, **extra)
    vid = mr.register_version(conn, slug=fx.SLUG, param_map=params, factors=["DXY", "VIX"],
                              factor_labels={"DXY": "dxy", "VIX": "vix"}, fitted_at="2026-11-04T22:00:00Z",
                              config={"teste": "fase17"}, actor="teste")
    conn.commit()
    conn.close()
    return vid


# ── Matemática ────────────────────────────────────────────────────────────

def _synthetic(n=400, seed=1):
    rng = np.random.default_rng(seed)
    sigma = np.array([0.002, 0.03])          # fatores com σ muito diferentes (bug pesa aqui)
    R = rng.normal(size=(n, 2)) * sigma
    beta = np.array([2.0, -0.05])
    y = R @ beta + rng.normal(0, 0.003, n)
    return R, y, beta, sigma


def test_fixed_score_is_the_regression_predictor():
    R, y, beta, sigma = _synthetic()
    s, scale = score_fixed(R, beta, sigma)
    assert np.allclose(s * scale, R @ beta)
    assert np.std(s) == pytest.approx(1.0)
    # o score antigo pondera z pelo β cru (errado quando σ difere): não é proporcional a Σβr
    old = score_old(R, beta, sigma)
    assert abs(np.corrcoef(old, R @ beta)[0, 1]) < 0.99


def test_compare_scores_auc_fixed_equals_regressor_and_beats_old():
    R, y, beta, sigma = _synthetic()
    c = compare_scores(R, y, beta, sigma)
    assert c["auc_fixed"] == pytest.approx(c["auc_regressor"], abs=1e-12)
    assert c["auc_fixed"] > c["auc_old"]


def test_logistic_has_no_clamp():
    rng = np.random.default_rng(0)
    s = rng.normal(size=4000)
    y = (rng.random(4000) < 1 / (1 + np.exp(-(5.0 * s - 0.6)))).astype(int)
    a, b = fit_logistic(s, y)
    assert a > 3.5 and b < -0.25      # fora do antigo clamp [1; 3,5] e [±0,25]


def test_kalman_noise_from_residual():
    rng = np.random.default_rng(2)
    sess = np.repeat(np.arange(40), 113)
    k = np.tile(np.arange(113), 40)
    X = np.cumsum(rng.normal(0, 0.05, (len(k), 2)), axis=0)
    X = X - np.repeat(X[k == 0], 113, axis=0)
    beta = np.array([0.7, -0.2])
    resid = rng.normal(0, 0.3, len(k))
    y = X @ beta + resid
    r = estimate_kalman_noise(y, X, sess, k, beta)
    assert r["kalman_obs_cov"] == pytest.approx(0.09, rel=0.1)
    assert np.isfinite(r["kalman_trans_cov"]) and r["kalman_trans_cov"] > 0


# ── Engine: compatibilidade e versões novas ───────────────────────────────

def test_engine_options_defaults_are_old_behavior():
    o = mr.engine_options({})
    assert o == {"unit_fix": 0.0, "score_scale": 1.0, "kalman_obs_cov": 1e-3, "kalman_trans_cov": 1e-5}
    assert mr.engine_options({"score_scale": 0})["score_scale"] == 1.0


def test_adopted_version_unchanged_and_shadow_unit_fix_isolated(db):
    eng = IRAIEngine(db)
    ref = [s.p_up for s in eng.compute_from_db(D_NEW, target=fx.TARGET, version="v2", persist_state=False)]
    vid = _register(db, {"unit_fix": 1, "score_scale": 0.004, "kalman_obs_cov": 0.2, "kalman_trans_cov": 3e-5})
    eng2 = IRAIEngine(db)
    live = [s.p_up for s in eng2.compute_from_db(D_NEW, target=fx.TARGET, version="v2", persist_state=False)]
    assert live == ref                              # shadow não muda o live
    m = eng2.model_for_version(fx.TARGET, vid)
    assert m["options"]["unit_fix"] == 1.0 and m["options"]["kalman_obs_cov"] == 0.2
    assert eng2.models[fx.SLUG]["options"] == mr.engine_options({})
    shadow = eng2.compute_from_db(D_NEW, target=fx.TARGET, version="v2", persist_state=True, model_version_id=vid)
    assert {s.model_version for s in shadow} == {vid}
    assert [s.p_up for s in shadow] != ref
    # recálculo com versão forçada não grava estado do Kalman
    conn = get_connection(db)
    n = conn.execute("SELECT COUNT(*) FROM kalman_state WHERE model_version = ?", (vid,)).fetchone()[0] \
        if mr.column_exists(conn, "kalman_state", "model_version") else 0
    conn.close()
    assert n == 0


def test_compute_unit_fix_contribution_is_beta_sigma_z(db):
    from backend.irai.engine import FactorState
    eng = IRAIEngine(db)

    def states():
        return {
            "a": FactorState(symbol="A", label="a", open_price=100.0, current_price=100.2, weight=2.0, sigma=0.002),
            "b": FactorState(symbol="B", label="b", open_price=10.0, current_price=10.3, weight=-0.05, sigma=0.03),
        }
    old = eng.compute(112, 100.0, 100.0, factor_states=states(), alpha=1.0, intercept=0.0, session_date=D_MID)
    new = eng.compute(112, 100.0, 100.0, factor_states=states(), alpha=1.0, intercept=0.0, session_date=D_MID,
                      unit_fix=True, score_scale=0.004)
    ra, rb = 0.2 / 100.0, 0.3 / 10.0
    assert old.score == pytest.approx(2.0 * ra / 0.002 - 0.05 * rb / 0.03, rel=1e-6)
    assert new.score == pytest.approx((2.0 * ra - 0.05 * rb) / 0.004, rel=1e-6)


# ── API / painel ──────────────────────────────────────────────────────────

def test_targets_expose_calibrated_and_forecast_flags(db, monkeypatch):
    import backend.db as bdb
    import backend.api.main as api
    conn = get_connection(db)
    conn.execute("UPDATE asset_models SET accuracy = NULL")
    conn.commit()
    conn.close()
    monkeypatch.setattr(bdb, "DB_PATH", db)
    monkeypatch.setattr(api, "engine", IRAIEngine(db))
    import asyncio
    res = asyncio.run(api.irai_targets())
    t = next(x for x in res["targets"] if x["target"] == fx.TARGET)
    assert t["calibrated"] is True                 # tem parâmetros, mesmo sem acurácia
    assert t["forecast_ui"] == "off" and t["forecast_mode"] == "off"
    assert t["model_version"] == "us500-nowcast-20261102T200000Z"
    conn = get_connection(db)
    conn.execute("UPDATE asset_models SET forecast_ui = 'nowcast_only' WHERE target = ?", (fx.TARGET,))
    conn.commit()
    conn.close()
    res = asyncio.run(api.irai_targets())
    assert next(x for x in res["targets"] if x["target"] == fx.TARGET)["forecast_ui"] == "nowcast_only"
    s = api._get_series_data_sync(fx.TARGET, D_MID, "v2", timeframe="M5", mode="recalculated")
    assert s["summary"]["forecast_ui"] == "nowcast_only"
