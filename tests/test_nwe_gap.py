"""Testes do NWE com gap stitching (AGENTS.md Regra 4)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.irai.nwe import compute_nwe


def _bar(px, pre=False, ghost=False, win_open=None):
    return {"win_current": px, "is_pre_market": pre, "is_ghost": ghost, "win_open": win_open}


def test_gap_does_not_inflate_bands():
    # Histórico estável em 100 e abertura com gap de +10 (110), sessão estável em 110
    history = [100.0 + (0.1 if i % 2 else -0.1) for i in range(150)]
    session = [_bar(110.0 + (0.1 if i % 2 else -0.1), win_open=110.0) for i in range(10)]
    out = compute_nwe(session, history)
    width = out[0]["nwe_upper_price"] - out[0]["nwe_lower_price"]
    # Sem stitching, o MAE absorveria o gap de 10 pontos (largura ~ dezenas). Com stitching fica < 2.
    assert width < 2.0, width
    assert abs(out[0]["nwe_center_price"] - 110.0) < 0.5


def test_pre_market_bars_keep_their_price_level():
    history = [100.0] * 150
    data = [_bar(100.2, pre=True), _bar(100.1, pre=True), _bar(110.0, win_open=110.0), _bar(110.0, win_open=110.0)]
    out = compute_nwe(data, history)
    # Barras pré-abertura recebem bandas no nível de 100 (deslocadas de volta), não de 110
    assert abs(out[0]["nwe_center_price"] - 100.0) < 0.5
    assert abs(out[2]["nwe_center_price"] - 110.0) < 0.5


def test_ghost_in_session_forward_fills_last_session_value():
    history = [100.0] * 150
    data = [_bar(110.0, win_open=110.0), _bar(110.0, win_open=110.0), _bar(None, ghost=True)]
    out = compute_nwe(data, history)
    assert out[2]["nwe_center_price"] == out[1]["nwe_center_price"]


def test_no_session_yet_no_stitching():
    history = [100.0] * 150
    data = [_bar(None, ghost=True, pre=True)]
    out = compute_nwe(data, history)
    assert abs(out[0]["nwe_center_price"] - 100.0) < 1e-9

