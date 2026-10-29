"""
Testes de invariantes do engine sobre o banco real (cópia), sem gravar estado.
Pulam automaticamente se o banco não estiver disponível.

Invariantes (AGENTS.md Regra 4 + auditoria 28/10/2026):
  - Alvo B3: abertura = 1ª barra a partir das 09:00 BRT (nunca o after-market de ontem).
  - Pré-sessão: retorno do alvo = 0, contribuições/z dos fatores = 0, cum_delta = 0.
  - bar_idx/t_frac contam a partir da abertura (não do warm-up).
  - Recalcular o mesmo dia é determinístico para as barras pré-sessão (zero repainting).
"""
import os
import sys
from datetime import datetime, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DB = os.path.join(ROOT, "data", "irai_live.db")

pytestmark = pytest.mark.skipif(not os.path.exists(DB), reason="banco não disponível")

DAY = "2026-10-27"


@pytest.fixture(scope="module")
def win_snaps():
    from backend.irai.engine import IRAIEngine
    e = IRAIEngine(DB)
    return e.compute_from_db(DAY, target="WIN$N", version="v2", timeframe="M5", persist_state=False)


def _ts(s):
    return datetime.fromisoformat(s.timestamp)


def test_b3_open_is_0900_brt(win_snaps):
    from backend.timeconv import b3_session_open_broker
    open_ts = b3_session_open_broker(DAY)
    first_session = next(s for s in win_snaps if _ts(s) >= open_ts and not s.is_ghost)
    assert first_session.win_open == first_session.win_bar_open or first_session.win_open > 0
    assert all(s.win_open == first_session.win_open for s in win_snaps)
    # O after-market de ontem (00:00–00:30 broker) não pode ser a abertura
    after_market = [s for s in win_snaps if _ts(s) < open_ts and not s.is_ghost]
    assert after_market, "esperava barras de after-market antes da abertura"
    assert first_session.win_open != after_market[0].win_bar_open


def test_pre_session_is_flat(win_snaps):
    pre = [s for s in win_snaps if s.is_pre_market]
    assert pre
    for s in pre:
        assert s.win_return == 0.0
        assert s.cum_delta == 0.0
        assert s.bar_idx == 0
        for f in s.factors.values():
            assert f["ret"] == 0.0 and f["z_score"] == 0.0
    assert len({s.p_up for s in pre}) == 1, "P(↑) deve ser constante antes da abertura"


def test_session_index_starts_at_open(win_snaps):
    session = [s for s in win_snaps if not s.is_pre_market]
    assert session[0].bar_idx == 0
    assert session[-1].bar_idx >= 100  # pregão completo ~114 barras M5


def test_recompute_is_deterministic():
    from backend.irai.engine import IRAIEngine
    a = IRAIEngine(DB).compute_from_db(DAY, target="WIN$N", version="v2", timeframe="M5", persist_state=False)
    b = IRAIEngine(DB).compute_from_db(DAY, target="WIN$N", version="v2", timeframe="M5", persist_state=False)
    assert [(s.timestamp, s.p_up) for s in a] == [(s.timestamp, s.p_up) for s in b]

