"""Testes de robustez para backend/db.py.

Validam:
- Guard monotônico de save_kalman_state (INFRA-02)
- Helper _add_column para migrações concorrentes (INFRA-01)
- Idempotência de migrate_gex_levels (INFRA-03)
- init_db paralelo sem crash (INFRA-01)
"""
import os
import json
import tempfile
import multiprocessing
import numpy as np
import pytest

from backend.db import (
    get_connection, init_db, _add_column,
    save_kalman_state, load_kalman_state,
    migrate_gex_levels,
)


@pytest.fixture
def tmp_db():
    """Cria banco temporário inicializado para testes."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


# ── INFRA-02: Guard monotônico do Kalman ──────────────────

class TestKalmanGuard:
    """save_kalman_state deve respeitar monotonicidade de timestamp."""

    def test_rejects_older_timestamp(self, tmp_db):
        """Replay com timestamp antigo NÃO sobrescreve estado mais recente."""
        conn = get_connection(tmp_db)
        slug, tf, sd = "win-test", "M5", "2026-07-18"

        # Gravar estado "recente" (17:30)
        save_kalman_state(conn, slug, tf, sd,
                          np.array([0.1, 0.2, 0.3]), np.eye(3) * 0.01,
                          0.05, True, "2026-07-18T17:30:00Z")

        # Tentar replay "antigo" (10:00) — deve ser rejeitado
        save_kalman_state(conn, slug, tf, sd,
                          np.array([9.9, 9.9, 9.9]), np.eye(3) * 9.9,
                          0.99, False, "2026-07-18T10:00:00Z")

        # Verificar que o estado persistido é o RECENTE
        row = conn.execute(
            "SELECT state_mean, timestamp_utc FROM kalman_state "
            "WHERE slug=? AND timeframe=? AND session_date=?",
            (slug, tf, sd)).fetchone()

        assert row["timestamp_utc"] == "2026-07-18T17:30:00Z"
        persisted = json.loads(row["state_mean"])
        assert abs(persisted[0] - 0.1) < 1e-9, f"Guard falhou: {persisted}"
        conn.close()

    def test_allows_newer_timestamp(self, tmp_db):
        """Atualização com timestamp mais recente SOBRESCREVE anterior."""
        conn = get_connection(tmp_db)
        slug, tf, sd = "win-test", "M5", "2026-07-18"

        save_kalman_state(conn, slug, tf, sd,
                          np.array([0.1, 0.2]), np.eye(2) * 0.01,
                          0.05, True, "2026-07-18T10:00:00Z")

        save_kalman_state(conn, slug, tf, sd,
                          np.array([0.5, 0.6]), np.eye(2) * 0.02,
                          0.03, True, "2026-07-18T17:30:00Z")

        row = conn.execute(
            "SELECT timestamp_utc FROM kalman_state "
            "WHERE slug=? AND timeframe=? AND session_date=?",
            (slug, tf, sd)).fetchone()

        assert row["timestamp_utc"] == "2026-07-18T17:30:00Z"
        conn.close()

    def test_rejects_equal_timestamp(self, tmp_db):
        """Mesmo timestamp NÃO sobrescreve (guard usa <=)."""
        conn = get_connection(tmp_db)
        slug, tf, sd = "win-test", "M5", "2026-07-18"
        ts = "2026-07-18T15:00:00Z"

        save_kalman_state(conn, slug, tf, sd,
                          np.array([1.0, 2.0]), np.eye(2), 0.05, True, ts)
        save_kalman_state(conn, slug, tf, sd,
                          np.array([9.9, 9.9]), np.eye(2) * 9.9, 0.99, False, ts)

        row = conn.execute(
            "SELECT state_mean FROM kalman_state "
            "WHERE slug=? AND timeframe=? AND session_date=?",
            (slug, tf, sd)).fetchone()

        persisted = json.loads(row["state_mean"])
        assert abs(persisted[0] - 1.0) < 1e-9
        conn.close()

    def test_load_returns_previous_session(self, tmp_db):
        """load_kalman_state retorna estado da sessão ANTERIOR, não da atual."""
        conn = get_connection(tmp_db)
        slug, tf = "win-test", "M5"

        # Gravar sessão de ontem
        save_kalman_state(conn, slug, tf, "2026-07-17",
                          np.array([0.3, 0.4]), np.eye(2) * 0.02,
                          0.02, True, "2026-07-17T17:50:00Z")

        # Carregar para a sessão de hoje — deve retornar o de ontem
        state = load_kalman_state(conn, slug, tf, "2026-07-18")
        assert state is not None
        assert abs(state["state_mean"][0] - 0.3) < 1e-9
        assert state["timestamp_utc"] == "2026-07-17T17:50:00Z"

        # Carregar para a sessão de ontem — não há sessão anterior
        state_prev = load_kalman_state(conn, slug, tf, "2026-07-17")
        assert state_prev is None
        conn.close()

    def test_load_filters_dimension_mismatch(self, tmp_db):
        """load_kalman_state retorna None se expected_dim for diferente da dimensao salva."""
        conn = get_connection(tmp_db)
        slug, tf = "win-test", "M5"

        # Gravar sessão com dimensão 3
        save_kalman_state(conn, slug, tf, "2026-07-17",
                          np.array([0.1, 0.2, 0.3]), np.eye(3) * 0.01,
                          0.02, True, "2026-07-17T17:50:00Z")

        # Carregar com expected_dim=2 -> deve retornar None
        state_wrong_dim = load_kalman_state(conn, slug, tf, "2026-07-18", expected_dim=2)
        assert state_wrong_dim is None

        # Carregar com expected_dim=3 -> deve carregar com sucesso
        state_correct_dim = load_kalman_state(conn, slug, tf, "2026-07-18", expected_dim=3)
        assert state_correct_dim is not None
        assert len(state_correct_dim["state_mean"]) == 3
        conn.close()


# ── INFRA-01: Helper _add_column ──────────────────────────

class TestAddColumn:
    """_add_column deve ser idempotente e silenciar duplicatas."""

    def test_adds_new_column(self, tmp_db):
        """Adiciona coluna nova com sucesso."""
        conn = get_connection(tmp_db)
        result = _add_column(conn, "ALTER TABLE market_bars ADD COLUMN test_col REAL DEFAULT 0")
        assert result is True
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(market_bars)")}
        assert "test_col" in cols
        conn.close()

    def test_silences_duplicate(self, tmp_db):
        """Duplicata retorna False sem crashar."""
        conn = get_connection(tmp_db)
        _add_column(conn, "ALTER TABLE market_bars ADD COLUMN test_col2 REAL DEFAULT 0")
        result = _add_column(conn, "ALTER TABLE market_bars ADD COLUMN test_col2 REAL DEFAULT 0")
        assert result is False  # Já existe, sem erro
        conn.close()

    def test_propagates_real_errors(self, tmp_db):
        """Erros legítimos (tabela inexistente) são propagados."""
        conn = get_connection(tmp_db)
        with pytest.raises(Exception):
            _add_column(conn, "ALTER TABLE tabela_que_nao_existe ADD COLUMN x REAL")
        conn.close()


# ── INFRA-03: Idempotência de migrate_gex_levels ─────────

class TestGexMigration:
    """migrate_gex_levels deve ser idempotente."""

    def test_idempotent(self, tmp_db):
        """Rodar 3 vezes não causa erro."""
        migrate_gex_levels(tmp_db)
        migrate_gex_levels(tmp_db)
        migrate_gex_levels(tmp_db)

        conn = get_connection(tmp_db)
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(gex_levels)")}
        assert "run_name" in cols
        assert "session_date" in cols
        assert "target" in cols
        assert "levels_json" in cols
        conn.close()


# ── INFRA-01: init_db paralelo ────────────────────────────

def _init_worker(db_path):
    """Worker para teste de init_db paralelo."""
    init_db(db_path)


class TestParallelInit:
    """init_db em paralelo não deve crashar."""

    def test_concurrent_init(self, tmp_db):
        """2 processos chamando init_db simultaneamente → ambos exitcode 0."""
        p1 = multiprocessing.Process(target=_init_worker, args=(tmp_db,))
        p2 = multiprocessing.Process(target=_init_worker, args=(tmp_db,))
        p1.start()
        p2.start()
        p1.join(timeout=30)
        p2.join(timeout=30)
        assert p1.exitcode == 0, f"p1 crashou com exitcode={p1.exitcode}"
        assert p2.exitcode == 0, f"p2 crashou com exitcode={p2.exitcode}"
