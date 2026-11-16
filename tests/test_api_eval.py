"""Fase 19A: contrato de /api/eval/assertividade, guarda REQ-A05 e sync sem p_fwd_close* (REQ-S01)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.eval import service  # noqa: E402
from backend.irai.engine import sanitize_forecast_flags  # noqa: E402


def _horizon(auc, bss, role):
    return {"n": 100, "n_sessions": 20, "base_up": 0.5, "auc": auc, "auc_lo": auc - 0.05,
            "auc_hi": auc + 0.05, "hit": 0.5, "brier": 0.25, "bss": bss, "bss_lo": bss - 0.1,
            "bss_hi": bss + 0.1, "ece": 0.1, "role": role, "ties_excluded": 0,
            "reliability": [{"bin_lo": i / 10, "bin_hi": (i + 1) / 10, "n": 10,
                             "p_mean": i / 10 + 0.05, "freq_up": 0.5} for i in range(10)]}


def _fixture(tmp_path):
    data = {
        "meta": {"harness_version": "18.0", "config_hash": "abc", "code_git_sha": "deadbee",
                 "config": {"window_sessions": 20}},
        "targets": {"WIN$N": {
            "target": "WIN$N", "sessions": 20, "first_session": "2026-10-16",
            "last_session": "2026-11-13", "live_bars": 2140,
            "horizons": {"60m": _horizon(0.45, -0.33, "primário"),
                         "nowcast": _horizon(0.88, 0.37, "nowcast"),
                         "close": _horizon(0.53, -0.18, "secundário"),
                         "5m": _horizon(0.47, -0.3, "relatório")},
            "baselines": {"60m": {"momentum": {"auc": 0.44, "hit": 0.45},
                                  "contrarian": {"auc": 0.56, "hit": 0.55}}},
        }},
    }
    (tmp_path / "assertividade_ultimos20.json").write_text(json.dumps(data), encoding="utf-8")
    return str(tmp_path)


def test_eval_contract(tmp_path):
    d = _fixture(tmp_path)
    out = service.load_assertividade("WIN$N", "20", eval_dir=d)
    assert out["available"] is True
    assert out["last_session"] == "2026-11-13"
    assert set(out["horizons"]) == {"60m", "nowcast", "close"}
    h60 = out["horizons"]["60m"]
    for k in ("auc", "auc_lo", "auc_hi", "bss", "ece", "hit", "n", "reliability", "degraded"):
        assert k in h60
    assert len(h60["reliability"]) == 10
    assert out["degraded_60m"] is True
    assert out["degraded_nowcast"] is False
    assert out["baselines"]["60m"]["contrarian"]["auc"] == 0.56
    assert len(json.dumps(out)) < 8000


def test_eval_rejects_out_of_scope(tmp_path):
    d = _fixture(tmp_path)
    assert service.load_assertividade("US500", "20", eval_dir=d)["available"] is False
    assert service.load_assertividade("WIN$N", "99", eval_dir=d)["available"] is False
    assert service.load_assertividade("WDO$N", "20", eval_dir=d)["available"] is False
    assert service.load_assertividade("WIN$N", "full", eval_dir=d)["available"] is False


def test_eval_does_not_write(tmp_path):
    d = _fixture(tmp_path)
    before = {p.name: p.stat().st_mtime for p in tmp_path.iterdir()}
    service.load_assertividade("WIN$N", "20", eval_dir=d)
    after = {p.name: p.stat().st_mtime for p in tmp_path.iterdir()}
    assert before == after


def test_req_a05_scope_guard():
    assert sanitize_forecast_flags("US500", "shadow", "nowcast_only") == ("off", "off")
    assert sanitize_forecast_flags("WIN$N", "off", "nowcast_only") == ("off", "nowcast_only")
    assert sanitize_forecast_flags("WDO$N", "bogus", None) == ("off", "off")
    assert sanitize_forecast_flags("WDO$N", "shadow", "on") == ("shadow", "on")


def test_firebase_sync_strips_pfwd_close():
    from backend import public_payload as fs
    bars = [
        {"time": "09:00", "p_up": 55, "factors": [1], "p_fwd_60": 0.5, "p_fwd_close": 0.6,
         "p_fwd_close_lo": 0.5, "p_fwd_close_hi": 0.7},
        {"time": "09:05", "p_up": 56},
        {"time": "09:10", "p_up": 57, "factors": [2], "p_fwd_close": 0.6},
    ]
    lean = fs.build_lean_series(bars)
    assert len(lean) == 3
    for b in lean:
        assert not any(k.startswith("p_fwd_close") for k in b)
    assert "factors" not in lean[0] and lean[0]["p_fwd_60"] == 0.5
    assert lean[1] == {"time": "09:05", "p_up": 56}
    assert lean[2]["factors"] == [2]
    assert fs.build_lean_series(None) == []
