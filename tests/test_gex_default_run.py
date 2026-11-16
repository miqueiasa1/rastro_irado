"""/api/gex: run padrao as-of (antes de 09:00) para pregoes passados (16/11/2026)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.main import default_gex_run  # noqa: E402


def test_past_session_uses_last_preopen_run():
    runs = ["18:40", "12:14", "08:15", "07:32", "07:26_CBOE"]
    assert default_gex_run(runs, "2026-11-06", "2026-11-16") == ("08:15", "asof_preopen", True)


def test_past_session_never_picks_post_open_run():
    run, rule, asof = default_gex_run(["09:05", "17:00", "08:59"], "2026-10-01", "2026-11-16")
    assert run == "08:59" and asof is True


def test_past_session_without_preopen_falls_back_and_flags():
    assert default_gex_run(["12:14", "18:00"], "2026-11-01", "2026-11-16") == ("12:14", "earliest_no_preopen", False)
    assert default_gex_run(["default"], "2026-05-01", "2026-11-16") == ("default", "earliest_no_preopen", False)


def test_today_uses_latest_run():
    assert default_gex_run(["07:32", "12:00"], "2026-11-16", "2026-11-16") == ("12:00", "latest_today", True)


def test_empty():
    assert default_gex_run([], "2026-11-06", "2026-11-16") == (None, None, False)
