"""
Testes de Unidade e Integração para o Motor de Snapshots Imutáveis em Tempo Real (Zero-Repainting Live Mode).
"""

import os
import sys
import pytest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import (
    get_connection,
    init_db,
    migrate_live_snapshots,
    save_live_snapshots,
    get_live_snapshots,
)
from backend.api.main import _get_series_data_sync

TEST_DB = "test_live_snapshots.db"

@pytest.fixture(autouse=True)
def setup_teardown_db():
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass


def test_migrate_live_snapshots_idempotent():
    conn = get_connection(TEST_DB)
    # Deve rodar sem erros múltiplas vezes
    migrate_live_snapshots(TEST_DB)
    migrate_live_snapshots(TEST_DB)
    
    rows = conn.execute("PRAGMA table_info(irai_live_snapshots)").fetchall()
    cols = {r["name"] for r in rows}
    assert "target" in cols
    assert "p_up" in cols
    assert "price_diverge_z" in cols
    assert "is_live_captured" in cols
    conn.close()


def test_save_and_get_live_snapshots():
    today = date.today().isoformat()
    mock_snapshots = [
        {
            "timestamp": f"{today}T10:00:00Z",
            "timestamp_utc": f"{today}T10:00:00Z",
            "bar_idx": 0,
            "p_up": 55.5,
            "score": 0.42,
            "verdict": "levemente comprador",
            "verdict_color": "#6FB38A",
            "price_diverge_z": 1.25,
            "price_diverges": False,
            "pair_z": -0.8,
            "pair_factor": "US500",
            "pair_beta": 0.85,
            "pair_signal": None,
            "win_return": 0.15,
            "win_current": 130000.0,
            "win_open": 129800.0,
            "cum_delta": 1500.0,
            "cum_delta_norm": 0.5,
            "nwe_center_price": 129900.0,
            "nwe_upper_price": 130500.0,
            "nwe_lower_price": 129300.0,
            "nwe_slope": 10.0,
            "nwe_up_price": 129900.0,
            "nwe_down_price": None,
            "is_ghost": False,
        },
        {
            "timestamp": f"{today}T10:05:00Z",
            "timestamp_utc": f"{today}T10:05:00Z",
            "bar_idx": 1,
            "p_up": 62.0,
            "score": 0.85,
            "verdict": "RISK-ON",
            "verdict_color": "#6FB38A",
            "price_diverge_z": 2.10,
            "price_diverges": True,
            "pair_z": -2.1,
            "pair_factor": "US500",
            "pair_beta": 0.85,
            "pair_signal": "buy",
            "win_return": 0.35,
            "win_current": 130250.0,
            "win_open": 129800.0,
            "cum_delta": 3200.0,
            "cum_delta_norm": 1.1,
            "nwe_center_price": 130100.0,
            "nwe_upper_price": 130700.0,
            "nwe_lower_price": 129500.0,
            "nwe_slope": 15.0,
            "nwe_up_price": 130100.0,
            "nwe_down_price": None,
            "is_ghost": False,
        }
    ]

    saved_count = save_live_snapshots(TEST_DB, "WIN$N", today, mock_snapshots, timeframe="M5", is_live_captured=1)
    assert saved_count == 2

    retrieved = get_live_snapshots(TEST_DB, "WIN$N", today, timeframe="M5")
    assert len(retrieved) == 2
    assert retrieved[0]["p_up"] == 55.5
    assert retrieved[0]["price_diverge_z"] == 1.25
    assert retrieved[1]["price_diverges"] == 1
    assert retrieved[1]["pair_signal"] == "buy"
    assert retrieved[1]["is_live_captured"] == 1


def test_api_series_live_mode_retrieval():
    today = date.today().isoformat()
    mock_snapshots = [
        {
            "timestamp": f"{today}T11:00:00Z",
            "timestamp_utc": f"{today}T11:00:00Z",
            "bar_idx": 0,
            "p_up": 50.0,
            "score": 0.0,
            "verdict": "indeciso",
            "verdict_color": "#7A7F8A",
            "price_diverge_z": 0.0,
            "win_return": 0.0,
            "win_current": 5000.0,
            "win_open": 5000.0,
        }
    ]
    save_live_snapshots(TEST_DB, "WDO$N", today, mock_snapshots, timeframe="M5", is_live_captured=1)

    conn = get_connection(TEST_DB)
    live_snaps = get_live_snapshots(conn, "WDO$N", today, timeframe="M5")
    conn.close()

    assert len(live_snaps) == 1
    assert live_snaps[0]["target"] == "WDO$N"
    assert live_snaps[0]["p_up"] == 50.0
