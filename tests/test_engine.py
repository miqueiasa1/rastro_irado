import os
import sys
import math
import pytest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_connection, init_db, save_kalman_state, load_kalman_state
from backend.irai.engine import IRAIEngine


def test_engine_initialization():
    """Verifica se o IRAIEngine carrega modelos e targets cadastrados no banco."""
    engine = IRAIEngine()
    assert engine is not None
    assert len(engine.models) > 0
    assert len(engine.registered_targets) > 0


def test_engine_compute_ustec():
    """Testa a geração de snapshots para o Nasdaq (USTEC) com a fórmula Rolling Window."""
    engine = IRAIEngine()
    snaps = engine.compute_from_db("2026-07-20", "USTEC", "both", "M5", persist_state=False)
    assert isinstance(snaps, list)
    if len(snaps) > 0:
        for s in snaps:
            assert hasattr(s, "price_diverge_z")
            assert hasattr(s, "price_diverges")
            if s.price_diverge_z is not None:
                assert isinstance(s.price_diverge_z, float)
                # O Z-Score rolling não deve conter NaN nem valores infinitos
                assert not math.isnan(s.price_diverge_z)
                assert not math.isinf(s.price_diverge_z)
                assert -10.0 <= s.price_diverge_z <= 10.0


def test_engine_multi_factor_basket_spread():
    """Valida o calculo do Z-Score da Cesta Completa de Fatores (Multi-Factor Basket Spread)."""
    engine = IRAIEngine()
    snaps = engine.compute_from_db("2026-07-20", "WIN$N", "both", "M5", persist_state=False)
    assert isinstance(snaps, list)
    if len(snaps) > 10:
        valid_z = [s.price_diverge_z for s in snaps if s.price_diverge_z is not None]
        assert len(valid_z) > 0
        for z in valid_z:
            assert -10.0 <= z <= 10.0


def test_kalman_state_monotonicity():
    """Garante que salva/carrega do estado Kalman respeita a ordem monotônica de timestamps."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_file = tmp.name

    try:
        init_db(db_file)
        conn = get_connection(db_file)
        
        slug = "test_asset"
        tf = "M5"
        date = "2026-07-21"
        
        # Salvar estado inicial (10:00:00)
        save_kalman_state(
            conn, slug, tf, date,
            state_mean=[0.5, 0.1],
            state_covariance=[[1.0, 0.0], [0.0, 1.0]],
            p_value=0.01,
            is_cointegrated=True,
            timestamp_utc="2026-07-21T10:00:00Z"
        )
        
        # Tentativa de salvar com timestamp MAIS ANTIGO (09:00:00) — deve ser IGNORADO
        save_kalman_state(
            conn, slug, tf, date,
            state_mean=[9.9, 9.9],
            state_covariance=[[9.0, 0.0], [0.0, 9.0]],
            p_value=0.99,
            is_cointegrated=False,
            timestamp_utc="2026-07-21T09:00:00Z"
        )
        
        # Carregar estado e verificar se manteve o estado de 10:00:00
        st = load_kalman_state(conn, slug, tf, "2026-07-22", expected_dim=2)
        assert st is not None
        assert st["timestamp_utc"] == "2026-07-21T10:00:00Z"
        assert st["state_mean"][0] == 0.5
        
        conn.close()
    finally:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass
