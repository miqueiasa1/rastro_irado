"""
Fase 16 (v2.0) — anti-repaint por versão vigente na data.

Critérios da fase 16 (PHASES.md):
  2. Recalcular um pregão com versão registrada reproduz o snapshot (|ΔP| ≤ 0,1 pp, 0% troca de lado).
  3. Comportamento ao vivo idêntico antes e depois da migração (ΔP ≤ 0,01 pp).
  4. Datas anteriores à primeira versão: snapshot ou erro explícito, nunca série com params atuais.
REQ-P03 (snapshot grava model_version), REQ-P05 (Kalman por versão), REQ-N04 (compatibilidade).
"""
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fase16_fixtures as fx  # noqa: E402
from backend.db import get_connection, save_live_snapshots, get_live_snapshots, save_kalman_state, load_kalman_state  # noqa: E402
from backend.irai import model_registry as mr  # noqa: E402
from backend.irai.engine import IRAIEngine  # noqa: E402
from backend.irai.model_registry import ModelVersionUnavailable  # noqa: E402

D_BOOT = "2026-11-03"   # 1ª sessão da versão adotada do legado
D_MID = "2026-11-04"
D_NEW = "2026-11-05"    # vigência da versão nova
D_PRE = "2026-11-02"    # anterior à primeira versão registrada


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _p(snaps):
    return [s.p_up for s in snaps]


def _compute(db, day, version="v2"):
    return IRAIEngine(db).compute_from_db(day, target=fx.TARGET, version=version, timeframe="M5", persist_state=False)


@pytest.fixture
def db(tmp_path):
    return fx.build_db(str(tmp_path / "f16_repaint.db"))


def _migrate(db):
    _load_script("migrate_fase16_model_versions").migrate(db)


def _register_new_and_promote(db):
    conn = get_connection(db)
    vid = mr.register_version(conn, slug=fx.SLUG, param_map=fx.NEW_PARAMS, factors=["DXY", "VIX"],
                              factor_labels={"DXY": "dxy", "VIX": "vix"}, fitted_at="2026-11-04T22:00:00Z",
                              config={"teste": True}, actor="teste")
    conn.commit()
    conn.close()
    return vid


def _promote(db, vid):
    conn = get_connection(db)
    mr.promote(conn, vid, D_NEW, actor="teste", today="2026-11-04")
    conn.commit()
    conn.close()


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_live_identical_before_and_after_migration(db, version):
    before = {d: _p(_compute(db, d, version)) for d in (D_PRE, D_BOOT, D_MID)}
    assert all(before.values())
    _migrate(db)
    for d in (D_BOOT, D_MID):
        after = _p(_compute(db, d, version))
        assert len(after) == len(before[d])
        assert max(abs(a - b) for a, b in zip(after, before[d])) <= 0.01
    snaps = _compute(db, D_MID, version)
    assert {s.model_version for s in snaps} == {"us500-nowcast-20261102T200000Z"}


def test_legacy_path_tags_legacy_and_is_not_blocked(db):
    snaps = _compute(db, D_PRE)
    assert snaps and {s.model_version for s in snaps} == {"legacy"}


def test_shadow_version_does_not_change_live(db):
    _migrate(db)
    ref = _p(_compute(db, D_NEW))
    _register_new_and_promote(db)  # registrada, ainda shadow
    assert _p(_compute(db, D_NEW)) == ref


def test_recalc_uses_version_valid_at_date_and_matches_snapshot(db):
    _migrate(db)
    from backend.api.main import _snap_to_dict
    # "Ao vivo" em D_MID com a versão adotada: grava snapshots
    live = _compute(db, D_MID)
    save_live_snapshots(db, fx.TARGET, D_MID, [_snap_to_dict(s) for s in live], timeframe="M5", is_live_captured=1)
    ref_new_day_old_params = _p(_compute(db, D_NEW))

    vid = _register_new_and_promote(db)
    _promote(db, vid)

    # Recalcular D_MID depois da recalibração → versão vigente em D_MID (a antiga), igual ao snapshot
    recalc = _compute(db, D_MID)
    stored = get_live_snapshots(db, fx.TARGET, D_MID)
    stored_by_ts = {r["timestamp_utc"]: r for r in stored}
    pairs = [(s.p_up, stored_by_ts[s.timestamp]["p_up"]) for s in recalc if s.timestamp in stored_by_ts]
    assert len(pairs) == len(stored) > 0
    deltas = [abs(a - b) for a, b in pairs]
    within = sum(d <= 0.1 for d in deltas) / len(deltas)
    flips = sum((a > 50) != (b > 50) for a, b in pairs)
    assert within >= 0.99 and flips == 0
    assert {r["model_version"] for r in stored} == {"us500-nowcast-20261102T200000Z"}
    assert {s.model_version for s in recalc} == {"us500-nowcast-20261102T200000Z"}

    # D_NEW passa a usar a versão nova (e muda de fato)
    new_day = _compute(db, D_NEW)
    assert {s.model_version for s in new_day} == {vid}
    assert _p(new_day) != ref_new_day_old_params


def test_dates_before_first_version_are_blocked(db):
    _migrate(db)
    with pytest.raises(ModelVersionUnavailable) as exc:
        _compute(db, D_PRE)
    assert exc.value.first_effective == D_BOOT


def test_api_returns_snapshot_or_explicit_error_before_first_version(db, monkeypatch):
    import backend.db as bdb
    import backend.api.main as api
    from backend.api.main import _snap_to_dict
    # snapshot "ao vivo" de D_PRE gravado ANTES da migração (como os pregões até 28/10)
    pre_live = _compute(db, D_PRE)
    save_live_snapshots(db, fx.TARGET, D_PRE, [_snap_to_dict(s) for s in pre_live], timeframe="M5")
    _migrate(db)
    monkeypatch.setattr(bdb, "DB_PATH", db)
    monkeypatch.setattr(api, "DB_PATH", db)
    monkeypatch.setattr(api, "engine", IRAIEngine(db))

    res = api._get_series_data_sync(fx.TARGET, D_PRE, "v2", timeframe="M5", mode="recalculated")
    assert res["recalc_blocked"] is True and res["is_live_mode"] is True
    assert [s["p_up"] for s in res["series"]] == [s.p_up for s in pre_live]
    # REQ-N04: snapshot antigo (sem versão) continua legível
    assert all(s.get("model_version") is None for s in res["series"])

    # Sem snapshot: erro explícito, nunca série com params atuais
    conn = get_connection(db)
    conn.execute("DELETE FROM irai_live_snapshots WHERE session_date = ?", (D_PRE,))
    conn.commit()
    conn.close()
    res2 = api._get_series_data_sync(fx.TARGET, D_PRE, "v2", timeframe="M5", mode="recalculated")
    assert res2["error_code"] == "model_version_unavailable"
    assert res2["first_effective_from"] == D_BOOT

    vers = api._get_model_versions_sync(fx.TARGET)
    assert vers["registry"] is True and len(vers["versions"]) == 1
    assert "artifact" not in vers["versions"][0]


def test_model_versions_endpoint_without_registry(db, monkeypatch):
    import backend.db as bdb
    import backend.api.main as api
    monkeypatch.setattr(bdb, "DB_PATH", db)
    monkeypatch.setattr(api, "engine", IRAIEngine(db))
    res = api._get_model_versions_sync(None)
    assert res["registry"] is False and res["versions"] == []


def test_snapshot_payload_unchanged_before_migration(db):
    from backend.api.main import _snap_to_dict
    snaps = _compute(db, D_MID)
    assert "model_version" not in _snap_to_dict(snaps[-1])


def test_kalman_state_bound_to_version(db):
    _migrate(db)
    conn = get_connection(db)
    save_kalman_state(conn, fx.SLUG, "M5", D_BOOT, [0.1, 0.2, 0.3], [[1, 0, 0], [0, 1, 0], [0, 0, 1]], 0.01, True,
                      f"{D_BOOT}T16:00:00Z", model_version="vA")
    assert load_kalman_state(conn, fx.SLUG, "M5", D_MID, expected_dim=3, model_version="vA") is not None
    # troca de versão → estado reinicializado explicitamente
    assert load_kalman_state(conn, fx.SLUG, "M5", D_MID, expected_dim=3, model_version="vB") is None
    # estado antigo sem versão (anterior à migração): só a versão adotada do legado aceita
    save_kalman_state(conn, fx.SLUG, "M5", D_MID, [0.1, 0.2, 0.3], [[1, 0, 0], [0, 1, 0], [0, 0, 1]], 0.01, True,
                      f"{D_MID}T16:00:00Z")
    assert load_kalman_state(conn, fx.SLUG, "M5", D_NEW, expected_dim=3, model_version="vB") is None
    assert load_kalman_state(conn, fx.SLUG, "M5", D_NEW, expected_dim=3, model_version="vB", accept_untagged=True) is not None
    # sem versão pedida → comportamento antigo
    assert load_kalman_state(conn, fx.SLUG, "M5", D_NEW, expected_dim=3) is not None
    conn.close()


def test_engine_persists_kalman_with_version(db):
    _migrate(db)
    e = IRAIEngine(db)
    e.compute_from_db(D_MID, target=fx.TARGET, version="v2", timeframe="M5", persist_state=True)
    conn = get_connection(db)
    row = conn.execute("SELECT model_version FROM kalman_state WHERE slug=? AND session_date=?", (fx.SLUG, D_MID)).fetchone()
    conn.close()
    assert row["model_version"] == "us500-nowcast-20261102T200000Z"
