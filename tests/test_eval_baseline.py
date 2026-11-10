"""
Reprodução da baseline da auditoria de 10/11/2026 pelo harness (fase 15, REQ-V04 / REQ-N02).

Usa a fixture reduzida `tests/fixtures/eval_baseline_fixture.db.gz` (snapshots não-ghost e
barras M5 de WIN$N/WDO$N extraídos, somente leitura, da cópia usada na auditoria).
"""

import gzip
import hashlib
import json
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.eval.harness import EvalConfig, metric_rows, run_evaluation  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "eval_baseline_fixture.db.gz")
FROZEN = os.path.join(ROOT, "data", "eval", "baseline", "assertividade_baseline_20261110.json")
AS_OF = "2026-11-10 13:50:00"
TOL = 0.005

# Números medidos na auditoria de 10/11/2026 (PRD §2).
AUDIT = {
    ("WIN$N", "60m"): 0.474,
    ("WDO$N", "60m"): 0.486,
    ("WIN$N", "nowcast"): 0.711,
    ("WDO$N", "nowcast"): 0.754,
    ("WIN$N", "close"): 0.525,
    ("WDO$N", "close"): 0.488,
}


@pytest.fixture(scope="module")
def fixture_db(tmp_path_factory):
    if not os.path.exists(FIXTURE):
        pytest.skip("fixture da baseline ausente")
    out = tmp_path_factory.mktemp("evalfx") / "fixture.db"
    with gzip.open(FIXTURE, "rb") as fi, open(out, "wb") as fo:
        shutil.copyfileobj(fi, fo)
    return str(out)


def _cfg(**kw):
    base = dict(start="2026-08-03", end="2026-11-10", as_of_utc=AS_OF, n_boot=100, seed=0)
    base.update(kw)
    return EvalConfig(**base)


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(scope="module")
def result(fixture_db):
    return run_evaluation(fixture_db, _cfg(), repo_dir=ROOT)


def test_reproduces_audit_baseline(result):
    for (target, horizon), expected in AUDIT.items():
        got = result["targets"][target]["horizons"][horizon]["auc"]
        assert abs(got - expected) <= TOL, f"{target} {horizon}: {got:.4f} vs auditoria {expected}"


def test_brier_skill_negative_as_audited(result):
    # Auditoria: BSS 60 min WIN −0,403 e WDO −0,285 (tolerância de 0,005).
    assert result["targets"]["WIN$N"]["horizons"]["60m"]["bss"] == pytest.approx(-0.403, abs=TOL)
    assert result["targets"]["WDO$N"]["horizons"]["60m"]["bss"] == pytest.approx(-0.285, abs=TOL)


def test_structure_and_roles(result):
    meta = result["meta"]
    assert meta["primary_horizon"] == "60m" and meta["secondary_horizon"] == "close"
    for t in ("WIN$N", "WDO$N"):
        r = result["targets"][t]
        assert set(r["horizons"]) == {"5m", "15m", "30m", "60m", "close", "nowcast"}
        assert r["horizons"]["60m"]["role"] == "primário"
        assert r["horizons"]["close"]["role"] == "secundário"
        for m in r["horizons"].values():
            for k in ("n", "auc", "auc_lo", "auc_hi", "hit", "brier", "bss", "ece", "reliability"):
                assert k in m
        assert set(r["baselines"]) == {"60m", "close"}
        assert {"hour", "month", "vol_tercile"} <= set(r["segments"])
        assert [m["marker"] for m in r["markers"]] == ["ponto_z_rastro", "estrela_dourada"]
    rows = metric_rows(result, eval_date="2026-11-10")
    assert {r["model"] for r in rows} == {"nowcast", "baseline_momentum", "baseline_contrarian"}


def test_two_runs_identical(fixture_db, result):
    again = run_evaluation(fixture_db, _cfg(), repo_dir=ROOT)
    for t in ("WIN$N", "WDO$N"):
        for h, m in result["targets"][t]["horizons"].items():
            m2 = again["targets"][t]["horizons"][h]
            for k in ("auc", "auc_lo", "auc_hi", "bss", "ece", "brier", "hit", "n"):
                assert abs(m[k] - m2[k]) <= 0.001, (t, h, k)
    assert result["meta"]["config_hash"] == again["meta"]["config_hash"]


def test_window_sessions_keeps_last_n_live_sessions(fixture_db):
    r = run_evaluation(fixture_db, _cfg(n_boot=10, window_sessions=20), repo_dir=ROOT)
    for t in ("WIN$N", "WDO$N"):
        assert r["targets"][t]["sessions"] == 20
        assert r["targets"][t]["last_session"] == "2026-11-10"


def test_config_hash_stable_for_optional_window():
    assert _cfg().config_hash() == _cfg(window_sessions=None).config_hash()
    assert _cfg().config_hash() != _cfg(window_sessions=20).config_hash()


def test_source_db_untouched(fixture_db):
    before = _sha(fixture_db)
    run_evaluation(fixture_db, _cfg(n_boot=10), repo_dir=ROOT)
    assert _sha(fixture_db) == before
    assert not os.path.exists(fixture_db + "-wal")


def test_matches_frozen_baseline_if_present(result):
    if not os.path.exists(FROZEN):
        pytest.skip("baseline congelada ainda não gerada")
    with open(FROZEN, encoding="utf-8") as f:
        frozen = json.load(f)
    for t, r in frozen["targets"].items():
        for h, m in r["horizons"].items():
            got = result["targets"][t]["horizons"][h]["auc"]
            assert abs(got - m["auc"]) <= TOL, (t, h, got, m["auc"])


def test_cli_end_to_end(fixture_db, tmp_path):
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import eval_assertividade as cli

    js, md, store = tmp_path / "a.json", tmp_path / "a.md", tmp_path / "s" / "forecast_eval.db"
    rc = cli.main(["--db", fixture_db, "--start", "2026-08-03", "--end", "2026-11-10", "--as-of", AS_OF,
                   "--n-boot", "20", "--json", str(js), "--report", str(md), "--persist", "--store", str(store)])
    assert rc == 0
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["targets"]["WIN$N"]["horizons"]["60m"]["n"] > 0
    raw = md.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r\n" not in raw
    assert "| 60m | primário |" in md.read_text(encoding="utf-8")
    assert store.exists()
