"""
IRAI — Forex Currency Basket & Spread Engine.

Implementa a matemática de decomposição cambial a partir dos 28 pares de Forex
das 8 principais moedas mundiais (USD, EUR, GBP, CHF, JPY, AUD, CAD, NZD),
calculando a força sintética de cada moeda e o Z-Score de Resíduo de Cesta (Basket Spread)
para o par alvo.
"""

from typing import Optional, Tuple, Dict, List
import numpy as np


# As 8 principais moedas globais do Forex
MAJOR_CURRENCIES = {"USD", "EUR", "GBP", "CHF", "JPY", "AUD", "CAD", "NZD"}

# Todos os 28 pares padrão formados pelas 8 moedas principais
FOREX_28_PAIRS = [
    # USD pairs (7)
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    # EUR crosses (6)
    "EURGBP", "EURCHF", "EURJPY", "EURAUD", "EURCAD", "EURNZD",
    # GBP crosses (5)
    "GBPJPY", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD",
    # AUD crosses (4)
    "AUDNZD", "AUDCAD", "AUDCHF", "AUDJPY",
    # NZD crosses (3)
    "NZDCAD", "NZDCHF", "NZDJPY",
    # CAD crosses (2)
    "CADCHF", "CADJPY",
    # CHF cross (1)
    "CHFJPY",
]


def parse_forex_pair(symbol: str) -> Optional[Tuple[str, str]]:
    """
    Identifica se o símbolo é um par cambial de 6 caracteres composto
    por moedas conhecidas (ex: EURUSD -> ('EUR', 'USD')).
    """
    if not symbol or len(symbol) != 6:
        return None
    
    sym = symbol.upper()
    base = sym[:3]
    quote = sym[3:]
    
    if base in MAJOR_CURRENCIES and quote in MAJOR_CURRENCIES and base != quote:
        return base, quote
        
    return None


def is_forex_pair(symbol: str) -> bool:
    """Verifica se o símbolo é um par cambial Forex reconhecido."""
    return parse_forex_pair(symbol) is not None


def compute_currency_basket_spread(
    target: str,
    target_return: float,
    current_pair_returns: Dict[str, float],
    recent_spread_history: List[float],
    min_sigma: float = 0.0010,
    threshold: float = 2.0
) -> Dict:
    """
    Calcula o Resíduo e o Z-Score de Cesta Cambial para o par alvo.

    Args:
        target: Símbolo do par alvo (ex: 'EURUSD')
        target_return: Retorno acumulado do par alvo na barra atual (desde a abertura)
        current_pair_returns: Dicionário { 'SYMBOL': return } com retornos de todos os pares na barra
        recent_spread_history: Histórico de spreads (resíduos) anteriores da sessão para cálculo de sigma
        min_sigma: Piso mínimo de volatilidade do spread (0.10% / 0.0010) para evitar divisão por zero
        threshold: Limiar para emissão de sinal de arbitragem / reversão (default: 2.0)

    Returns:
        Dict com:
            - pair_z: float | None
            - pair_factor: str (ex: "CESTA (12 PARES)")
            - pair_beta: float (1.0)
            - pair_signal: "buy" | "sell" | None
            - residuo: float
            - basket_return: float
            - base_power: float
            - quote_power: float
            - active_pairs_count: int
    """
    parsed = parse_forex_pair(target)
    if not parsed:
        return {
            "pair_z": None,
            "pair_factor": None,
            "pair_beta": None,
            "pair_signal": None,
            "residuo": 0.0,
            "basket_return": 0.0,
            "base_power": 0.0,
            "quote_power": 0.0,
            "active_pairs_count": 0,
        }

    base_curr, quote_curr = parsed
    target_clean = target.upper()

    base_contributions = []
    quote_contributions = []
    active_pairs = set()

    for pair_sym, ret in current_pair_returns.items():
        if not ret or not isinstance(ret, (int, float)) or np.isnan(ret):
            continue

        pair_clean = pair_sym.upper()
        if pair_clean == target_clean:
            # Exclui o próprio par alvo para evitar autocorrelação / tautologia
            continue

        p_parsed = parse_forex_pair(pair_clean)
        if not p_parsed:
            continue

        p_base, p_quote = p_parsed

        # Contribuição para a moeda Base
        if p_base == base_curr:
            base_contributions.append(+ret)
            active_pairs.add(pair_clean)
        elif p_quote == base_curr:
            base_contributions.append(-ret)
            active_pairs.add(pair_clean)

        # Contribuição para a moeda Cotada (Quote)
        if p_base == quote_curr:
            quote_contributions.append(+ret)
            active_pairs.add(pair_clean)
        elif p_quote == quote_curr:
            quote_contributions.append(-ret)
            active_pairs.add(pair_clean)

    # Força média isolada da Moeda Base e da Moeda Cotada
    base_power = float(np.mean(base_contributions)) if base_contributions else 0.0
    quote_power = float(np.mean(quote_contributions)) if quote_contributions else 0.0

    # Retorno Teórico Sintético da Cesta para o par Base/Quote
    basket_return = base_power - quote_power

    # Resíduo do Spread (Retorno Real do Par - Retorno Teórico da Cesta)
    residuo = target_return - basket_return

    # Atualiza lista de histórico de spreads
    recent_spread_history.append(residuo)
    if len(recent_spread_history) > 100:
        recent_spread_history.pop(0)

    pair_z = None
    pair_signal = None

    if len(recent_spread_history) >= 6 and len(active_pairs) >= 2:
        past_spreads = recent_spread_history[:-1]
        spread_sigma = float(np.std(past_spreads))
        if spread_sigma < min_sigma:
            spread_sigma = min_sigma

        z_val = (residuo - 0.0) / spread_sigma
        pair_z = round(float(z_val), 2)

        if pair_z < -threshold:
            pair_signal = "buy"
        elif pair_z > threshold:
            pair_signal = "sell"

    factor_label = f"CESTA ({len(active_pairs)} PARES)" if active_pairs else "CESTA CAMBIAL"

    return {
        "pair_z": pair_z,
        "pair_factor": factor_label,
        "pair_beta": 1.0,
        "pair_signal": pair_signal,
        "residuo": residuo,
        "basket_return": basket_return,
        "base_power": base_power,
        "quote_power": quote_power,
        "active_pairs_count": len(active_pairs),
    }
