"""
Fase 16 (v2.0) — registro imutável de versões de modelo.

REQ-P01 (calibrar nunca apaga), REQ-P06 (promoção explícita e auditável), REQ-N06 (imutabilidade),
migração aditiva e idempotente (SPEC §10), REQ-A03 (listagem sem artefato).
Tudo em bancos temporários sintéticos — nunca toca o banco de produção.
"""
import importlib.util
import os
import sqlite3
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fase16_fixtures as fx  # noqa: E402
from backend.db import get_connection, DB_PATH  # noqa: E402
from backend.irai import model_registry as mr  # noqa: E402

MIGRATE = os.path.join(ROOT, "scripts", "migrate_fase16_model_versions.py")


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def db(tmp_path):
    return fx.build_db(str(tmp_path / "f16_registry.db"))


@pytest.fixture
def migrated(db):
    mig = _load_script("migrate_fase16_model_versions")
    mig.migrate(db)
    return db


def _fake_result(weights=None):
    w = weights or {"dxy": 0.7, "vix": 0.2}
    return {
        "factors": ["DXY", "VIX"], "labels": ["dxy", "vix"],
        "factor_labels": {"DXY": "dxy", "VIX": "vix"},
        "weights": w, "sigmas": {"dxy": 0.003, "vix": 0.02},
        "alpha": 1.5, "intercept": 0.1, "r2": 0.4, "accuracy": 70.0, "logistic_acc": 69.0,
        "n_sessions": 252, "train_start": "2025-11-01", "train_end": "2026-11-09",
        "min_factors": 2, "max_factors": 2,
    }


# ── Migração ──────────────────────────────────────────────────────────────

def test_migration_is_additive_and_idempotent(db):
    mig = _load_script("migrate_fase16_model_versions")
    conn = get_connection(db)
    objs_before = {(r[0], r[1]) for r in conn.execute("SELECT type, name FROM sqlite_master")}
    params_before = conn.execute("SELECT param_name, value, effective_from FROM model_params ORDER BY 1").fetchall()
    bars_before = conn.execute("SELECT COUNT(*) FROM market_bars").fetchone()[0]
    conn.close()

    r1 = mig.migrate(db)
    assert "+ model_versions" in r1["schema_changes"]
    assert "+ model_params.version_id" in r1["schema_changes"]
    assert "+ irai_live_snapshots.model_version" in r1["schema_changes"]
    assert "+ kalman_state.model_version" in r1["schema_changes"]
    assert any(b.get("version_id") for b in r1["bootstrap"])

    r2 = mig.migrate(db)
    assert r2["schema_changes"] == []
    assert all("skipped" in b for b in r2["bootstrap"])

    conn = get_connection(db)
    objs_after = {(r[0], r[1]) for r in conn.execute("SELECT type, name FROM sqlite_master")}
    assert objs_before <= objs_after, "a migração não pode remover objetos"
    params_after = conn.execute("SELECT param_name, value, effective_from FROM model_params ORDER BY 1").fetchall()
    assert [tuple(r) for r in params_after] == [tuple(r) for r in params_before]
    assert conn.execute("SELECT COUNT(*) FROM market_bars").fetchone()[0] == bars_before
    assert conn.execute("SELECT COUNT(*) FROM model_versions").fetchone()[0] == 1
    cols = {r[1] for r in conn.execute("PRAGMA table_info(asset_models)")}
    assert {"forecast_mode", "forecast_ui"} <= cols
    assert tuple(conn.execute("SELECT forecast_mode, forecast_ui FROM asset_models").fetchone()) == ("off", "off")
    conn.close()


def test_dry_run_writes_nothing(db):
    mig = _load_script("migrate_fase16_model_versions")
    rep = mig.migrate(db, dry_run=True)
    assert rep["schema_changes"]
    conn = get_connection(db)
    assert not mr.has_registry(conn)
    assert not mr.column_exists(conn, "model_params", "version_id")
    conn.close()


def test_migration_cli_refuses_production_db_without_confirmation():
    out = subprocess.run([sys.executable, MIGRATE, "--db", DB_PATH, "--dry-run"],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 2
    assert "--confirm-live" in out.stdout


def test_bootstrap_adopts_exact_legacy_params(migrated):
    conn = get_connection(migrated)
    v = mr.current_active(conn, fx.SLUG)
    assert v is not None and v["status"] == "active"
    assert v["version_id"] == "us500-nowcast-20261102T200000Z"
    assert v["effective_from"] == "2026-11-03"
    assert v["artifact"]["params"] == fx.LEGACY_PARAMS
    assert v["artifact"]["factors"] == ["DXY", "VIX"]
    assert v["config"]["adopted_from_legacy"] is True
    ev = mr.list_events(conn, v["version_id"])
    assert [e["event"] for e in ev] == ["registered"]
    conn.close()


def test_first_full_session_rule():
    # Calibração de 28/10 às 19:05 UTC (16:05 BRT, pregão em andamento) → sessão mista → vale a partir de 29/10
    assert mr.first_full_session_after("2026-10-28T19:05:10Z", is_b3=True) == "2026-10-29"
    # Antes das 09:00 BRT → o próprio dia já é inteiro
    assert mr.first_full_session_after("2026-10-28T11:00:00Z", is_b3=True) == "2026-10-28"
    # Globais: sempre o dia seguinte do broker (formato legado com microssegundos/offset)
    assert mr.first_full_session_after("2026-07-23T16:58:11.779347+00:00", is_b3=False) == "2026-07-24"


# ── Imutabilidade (REQ-N06) ───────────────────────────────────────────────

def test_params_and_versions_cannot_be_deleted_or_rewritten(migrated):
    conn = get_connection(migrated)
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM model_params WHERE param_name LIKE 'us500%'")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE model_params SET value = 0")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM model_versions")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE model_versions SET artifact_json = '{}'")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE model_versions SET config_json = '{}'")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM model_version_events")
    # status/vigência continuam alteráveis (única exceção permitida)
    conn.execute("UPDATE model_versions SET effective_to = '2030-01-01'")
    conn.rollback()
    conn.close()


def test_calibrate_save_twice_never_removes_rows(migrated):
    cal = _load_script("calibrate_universal")
    conn = sqlite3.connect(migrated)
    conn.row_factory = sqlite3.Row
    n_params0 = conn.execute("SELECT COUNT(*) FROM model_params").fetchone()[0]
    legacy0 = conn.execute("SELECT * FROM model_params ORDER BY param_name").fetchall()
    v1 = cal.save_to_db(conn, fx.TARGET, fx.SLUG, _fake_result())
    v2 = cal.save_to_db(conn, fx.TARGET, fx.SLUG, _fake_result({"dxy": 0.1, "vix": 0.9}))
    assert v1 and v2 and v1 != v2
    n_params = conn.execute("SELECT COUNT(*) FROM model_params").fetchone()[0]
    assert n_params == n_params0 + 2 * 6
    # linhas legadas intactas
    legacy = conn.execute("SELECT param_name, value, effective_from FROM model_params WHERE version_id IS NULL ORDER BY param_name").fetchall()
    assert [tuple(r) for r in legacy] == [(r["param_name"], r["value"], r["effective_from"]) for r in legacy0]
    assert conn.execute("SELECT COUNT(*) FROM model_versions").fetchone()[0] == 3
    st = dict(conn.execute("SELECT version_id, status FROM model_versions").fetchall())
    assert st[v1] == "shadow" and st[v2] == "shadow"
    v = mr.get_version(conn, v1)
    assert v["train_start"] == "2025-11-01" and v["train_end"] == "2026-11-09"
    assert v["metrics"]["in_sample"] is True
    # asset_models só muda na promoção
    assert conn.execute("SELECT calibrated_at FROM asset_models WHERE slug=?", (fx.SLUG,)).fetchone()[0] == fx.LEGACY_FITTED_AT
    # caminho legado ignora linhas versionadas (shadow não vira "a mais recente")
    assert mr.legacy_param_map(conn, fx.SLUG) == fx.LEGACY_PARAMS
    conn.close()


def test_calibrate_save_aborts_without_registry(db):
    cal = _load_script("calibrate_universal")
    conn = sqlite3.connect(db)
    before = conn.execute("SELECT * FROM model_params ORDER BY 1").fetchall()
    assert cal.save_to_db(conn, fx.TARGET, fx.SLUG, _fake_result()) is None
    assert conn.execute("SELECT * FROM model_params ORDER BY 1").fetchall() == before
    conn.close()


# ── Promoção (REQ-P06) ────────────────────────────────────────────────────

def test_promote_is_explicit_future_and_audited(migrated):
    cal = _load_script("calibrate_universal")
    conn = get_connection(migrated)
    boot = mr.current_active(conn, fx.SLUG)["version_id"]
    vid = cal.save_to_db(conn, fx.TARGET, fx.SLUG, _fake_result())
    with pytest.raises(ValueError):
        mr.promote(conn, vid, "2026-11-05", actor="teste", today="2026-11-10")  # retroativo = repaint
    with pytest.raises(ValueError):
        mr.promote(conn, vid, "2026-11-10", actor="teste", today="2026-11-10")  # hoje sem allow_today
    with pytest.raises(ValueError):
        mr.promote(conn, boot, "2026-11-11", actor="teste", today="2026-11-10")  # não é shadow
    res = mr.promote(conn, vid, "2026-11-11", actor="teste", today="2026-11-10", notes="ok")
    conn.commit()
    assert res == {"promoted": vid, "retired": boot, "effective_from": "2026-11-11"}
    old = mr.get_version(conn, boot, with_artifact=False)
    assert old["status"] == "retired" and old["effective_to"] == "2026-11-11"
    assert mr.resolve_version(conn, fx.SLUG, "2026-11-10")["version_id"] == boot
    assert mr.resolve_version(conn, fx.SLUG, "2026-11-11")["version_id"] == vid
    assert mr.resolve_version(conn, fx.SLUG, "2026-11-02") is None
    events = [(e["version_id"], e["event"]) for e in mr.list_events(conn)]
    assert (boot, "retired") in events and (vid, "promoted") in events
    am = conn.execute("SELECT accuracy, calibrated_at FROM asset_models WHERE slug=?", (fx.SLUG,)).fetchone()
    assert am["accuracy"] == 70.0
    conn.close()


def test_reject_only_shadow(migrated):
    cal = _load_script("calibrate_universal")
    conn = get_connection(migrated)
    vid = cal.save_to_db(conn, fx.TARGET, fx.SLUG, _fake_result())
    mr.reject(conn, vid, actor="teste")
    conn.commit()
    assert mr.get_version(conn, vid)["status"] == "rejected"
    with pytest.raises(ValueError):
        mr.promote(conn, vid, "2030-01-01", actor="teste")
    conn.close()


def test_list_versions_has_no_artifact(migrated):
    conn = get_connection(migrated)
    vs = mr.list_versions(conn, slug=fx.SLUG)
    assert len(vs) == 1
    assert "artifact" not in vs[0] and "artifact_json" not in vs[0]
    assert vs[0]["config"]["adopted_from_legacy"] is True
    conn.close()
