"""
Testes unitários para o motor de Cesta Cambial (Forex Basket Spread).
"""

import math
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.irai.forex_basket import (
    parse_forex_pair,
    is_forex_pair,
    compute_currency_basket_spread,
    MAJOR_CURRENCIES,
    FOREX_28_PAIRS,
)


def test_parse_forex_pair():
    """Valida o parser de pares cambiais."""
    assert parse_forex_pair("EURUSD") == ("EUR", "USD")
    assert parse_forex_pair("eurusd") == ("EUR", "USD")
    assert parse_forex_pair("GBPJPY") == ("GBP", "JPY")
    assert parse_forex_pair("CADCHF") == ("CAD", "CHF")
    assert parse_forex_pair("AUDNZD") == ("AUD", "NZD")
    
    # Não-forex
    assert parse_forex_pair("WIN$N") is None
    assert parse_forex_pair("US500") is None
    assert parse_forex_pair("BTCUSD") is None
    assert parse_forex_pair("EUREUR") is None
    assert parse_forex_pair("EUR") is None


def test_is_forex_pair():
    """Valida o validador booleano."""
    assert is_forex_pair("EURUSD") is True
    assert is_forex_pair("USDJPY") is True
    assert is_forex_pair("WIN$N") is False
    assert is_forex_pair("XAUUSD") is False


def test_28_pairs_structure():
    """Garante que a lista oficial possui 28 pares únicos formados pelas 8 moedas."""
    assert len(FOREX_28_PAIRS) == 28
    assert len(set(FOREX_28_PAIRS)) == 28
    for p in FOREX_28_PAIRS:
        res = parse_forex_pair(p)
        assert res is not None
        b, q = res
        assert b in MAJOR_CURRENCIES
        assert q in MAJOR_CURRENCIES


def test_compute_currency_basket_spread_basic():
    """Testa o cálculo sintético do spread de cesta para EURUSD."""
    # Cenário: EUR subindo 1% no mundo, USD caindo 0.5% no mundo.
    # Retorno esperado para EURUSD na cesta = +1.0% - (-0.5%) = +1.5%
    # Se EURUSD real subiu apenas +0.8%, EURUSD está atrasado (residuo = -0.7%).
    
    pair_returns = {
        # Pares com EUR (Base) -> EUR subindo
        "EURGBP": 0.010,
        "EURJPY": 0.012,
        "EURCHF": 0.008,
        "EURAUD": 0.011,
        "EURCAD": 0.009,
        # Pares com USD (Quote) -> USD caindo (se USD é quote, par sobe; se USD é base, par cai)
        "GBPUSD": 0.005,   # USD quote -> USD caindo
        "USDJPY": -0.005,  # USD base -> USD caindo
        "USDCHF": -0.004,  # USD base -> USD caindo
        "USDCAD": -0.006,  # USD base -> USD caindo
        # EURUSD atual
        "EURUSD": 0.008,
    }

    history = [0.0, 0.001, -0.002, 0.001, -0.001]
    res = compute_currency_basket_spread(
        target="EURUSD",
        target_return=0.008,
        current_pair_returns=pair_returns,
        recent_spread_history=history,
        min_sigma=0.001,
        threshold=2.0
    )

    assert res["active_pairs_count"] == 9  # 5 de EUR + 4 de USD (excluindo EURUSD)
    assert res["base_power"] > 0           # EUR forte
    assert res["quote_power"] < 0          # USD fraco
    assert res["basket_return"] > 0        # Cesta apontando alta forte para EURUSD
    assert res["residuo"] < 0              # EURUSD atrasado em relação à cesta
    assert res["pair_factor"] == "CESTA (9 PARES)"
    assert res["pair_beta"] == 1.0
    assert res["pair_z"] is not None
    assert res["pair_z"] < 0               # Z-Score negativo (sinal de compra / oversold)


def test_compute_currency_basket_warmup():
    """Garante que durante as primeiras 5 barras, pair_z é None até ter amostra suficiente."""
    pair_returns = {"EURGBP": 0.005, "GBPUSD": 0.005}
    history = [0.001, 0.002]
    res = compute_currency_basket_spread(
        target="EURUSD",
        target_return=0.005,
        current_pair_returns=pair_returns,
        recent_spread_history=history,
    )
    assert res["pair_z"] is None
    assert res["pair_signal"] is None
