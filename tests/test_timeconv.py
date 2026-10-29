"""Testes das conversões de fuso (backend/timeconv.py)."""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import timeconv as tc


def _epoch(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp()


def test_broker_offset_summer_winter():
    assert tc.broker_offset_hours(datetime(2026, 10, 28, 14, tzinfo=timezone.utc)) == 3
    assert tc.broker_offset_hours(datetime(2026, 11, 3, 14, tzinfo=timezone.utc)) == 2
    assert tc.broker_offset_hours(datetime(2026, 1, 15, 14, tzinfo=timezone.utc)) == 2


def test_brt_bar_to_broker_summer():
    # 09:00 BRT em 28/10/2026 (EUA em horário de verão) → 15:00 broker (+6h)
    out = tc.brt_epoch_to_broker_epoch(_epoch(2026, 10, 28, 9, 0))
    assert datetime.fromtimestamp(out, tz=timezone.utc) == datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)


def test_brt_bar_to_broker_winter():
    # 09:00 BRT em 03/11/2026 (EUA em horário padrão) → 14:00 broker (+5h)
    out = tc.brt_epoch_to_broker_epoch(_epoch(2026, 11, 3, 9, 0))
    assert datetime.fromtimestamp(out, tz=timezone.utc) == datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)


def test_after_market_crosses_broker_midnight_in_summer():
    out = tc.brt_epoch_to_broker_epoch(_epoch(2026, 10, 27, 18, 15))
    assert datetime.fromtimestamp(out, tz=timezone.utc) == datetime(2026, 10, 28, 0, 15, tzinfo=timezone.utc)


def test_session_open_broker():
    assert tc.b3_session_open_broker("2026-10-28") == datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)
    assert tc.b3_session_open_broker("2026-11-03") == datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)


def test_broker_to_brt_roundtrip():
    b = datetime(2026, 10, 28, 15, 5, tzinfo=timezone.utc)
    assert tc.broker_wall_to_brt_wall(b) == datetime(2026, 10, 28, 9, 5, tzinfo=timezone.utc)
    w = datetime(2026, 12, 1, 20, 0)
    assert tc.broker_wall_to_brt_wall(w) == datetime(2026, 12, 1, 15, 0)


def test_display_offset():
    assert tc.broker_to_brt_offset_hours("2026-10-28") == -6
    assert tc.broker_to_brt_offset_hours("2026-11-03") == -5


def test_bars_per_session():
    assert tc.b3_bars_per_session("M5") == 114
    assert tc.b3_bars_per_session("M1") == 570
