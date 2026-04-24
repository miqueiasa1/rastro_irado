"""
IRAI — Implied Volatility ATM Calculator.

Calcula IV ATM de opções BOVA11 via MT5:
1. Descobre a option chain (calls do front-month)
2. Seleciona strike ATM (mais próximo do spot)
3. Calcula IV via Black-Scholes bisection

Requer: MT5 já inicializado no terminal BR (XP).
"""

import math
import logging
from datetime import datetime, date

log = logging.getLogger("iv_calc")

# ── B3 Options Calendar ──────────────────────────────────
# Call series letters: A=Jan, B=Feb, ..., L=Dec
CALL_SERIES = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "F",
               7: "G", 8: "H", 9: "I", 10: "J", 11: "K", 12: "L"}


def _norm_cdf(x):
    """Standard normal CDF (Abramowitz & Stegun approximation)."""
    a1, a2, a3, a4, a5 = (
        0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    )
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x / 2)
    return 0.5 * (1.0 + sign * y)


def bs_call_price(S, K, T, r, sigma):
    """Black-Scholes call price (European)."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)


def bs_put_price(S, K, T, r, sigma):
    """Black-Scholes put price (European)."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def implied_vol_bisection(market_price, S, K, T, r, is_call=True, tol=1e-5, max_iter=100):
    """
    Calcula IV via bisection method.
    Retorna IV como decimal (ex: 0.25 = 25%).
    """
    if market_price <= 0 or T <= 0:
        return None

    price_fn = bs_call_price if is_call else bs_put_price

    # Limites da busca
    lo, hi = 0.01, 3.0  # 1% a 300%

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        price = price_fn(S, K, T, r, mid)

        if abs(price - market_price) < tol:
            return mid

        if price > market_price:
            hi = mid
        else:
            lo = mid

    return (lo + hi) / 2  # best estimate


def find_atm_option(mt5_module, underlying="BOVA11"):
    """
    Descobre a opção ATM call do front-month para o ativo subjacente.

    Returns:
        dict com {symbol, strike, spot, mid_price, days_to_expiry, series_letter}
        ou None se não encontrar.
    """
    mt5 = mt5_module

    # 1. Preço spot do subjacente
    tick = mt5.symbol_info_tick(underlying)
    if tick is None or tick.bid <= 0:
        log.warning(f"Sem tick para {underlying}")
        return None
    spot = (tick.bid + tick.ask) / 2 if tick.ask > 0 else tick.bid

    # 2. Determinar série (letra) do mês corrente e próximo
    today = date.today()
    current_month = today.month
    next_month = current_month + 1 if current_month < 12 else 1
    current_letter = CALL_SERIES[current_month]
    next_letter = CALL_SERIES[next_month]

    # 3. Listar opções disponíveis
    # Pattern: BOVA + letter + strike (ex: BOVAE115, BOVAF120)
    prefix = underlying.replace("11", "")  # "BOVA"

    # Tentar mês corrente primeiro, depois próximo
    for series_letter in [current_letter, next_letter]:
        pattern = f"{prefix}{series_letter}*"
        symbols = mt5.symbols_get(pattern)

        if symbols is None or len(symbols) == 0:
            log.debug(f"Nenhum symbol para pattern {pattern}")
            continue

        # 4. Filtrar symbols válidos e encontrar ATM
        candidates = []
        for sym_info in symbols:
            name = sym_info.name
            # Extrair strike do nome (números após a letra de série)
            strike_str = name[len(prefix) + 1:]  # Remove "BOVA" + letter
            try:
                strike = float(strike_str)
                # Alguns tickers podem ter formato com decimais
                if strike > 1000:
                    strike = strike / 100  # ex: 11500 -> 115.00
                elif strike > 200:
                    strike = strike / 10   # ex: 1150 -> 115.0
            except ValueError:
                continue

            # Pegar preço da opção
            opt_tick = mt5.symbol_info_tick(name)
            if opt_tick is None:
                continue

            bid = opt_tick.bid if opt_tick.bid > 0 else 0
            ask = opt_tick.ask if opt_tick.ask > 0 else 0

            # Pular opções sem preço
            if bid <= 0 and ask <= 0:
                continue

            mid = (bid + ask) / 2 if ask > 0 and bid > 0 else max(bid, ask)

            candidates.append({
                "symbol": name,
                "strike": strike,
                "mid_price": mid,
                "bid": bid,
                "ask": ask,
                "distance": abs(strike - spot),
                "series_letter": series_letter,
            })

        if not candidates:
            continue

        # 5. Selecionar ATM (menor distância do spot)
        atm = min(candidates, key=lambda x: x["distance"])

        # 6. Calcular dias até vencimento (3ª sexta-feira do mês)
        expiry_month = current_month if series_letter == current_letter else next_month
        expiry_year = today.year if expiry_month >= current_month else today.year + 1
        days = _days_to_expiry(today, expiry_year, expiry_month)

        if days <= 0:
            # Expiração já passou, pular para próximo mês
            continue

        return {
            "symbol": atm["symbol"],
            "strike": atm["strike"],
            "spot": spot,
            "mid_price": atm["mid_price"],
            "bid": atm["bid"],
            "ask": atm["ask"],
            "days_to_expiry": days,
            "series_letter": atm["series_letter"],
        }

    log.warning(f"Nenhuma opção ATM encontrada para {underlying}")
    return None


def _days_to_expiry(today, year, month):
    """Calcula dias úteis até a 3ª sexta-feira do mês de vencimento."""
    import calendar
    # 3ª sexta-feira: achar o primeiro dia do mês, localizar a 3ª sexta
    c = calendar.Calendar(firstweekday=0)
    fridays = [d for d in c.itermonthdays2(year, month)
               if d[0] != 0 and d[1] == 4]  # (day, weekday) where Friday=4

    if len(fridays) < 3:
        return 0
    third_friday = date(year, month, fridays[2][0])
    delta = (third_friday - today).days
    return max(delta, 0)


def compute_iv_atm(mt5_module, underlying="BOVA11", risk_free_rate=None):
    """
    Calcula IV ATM completa.

    Args:
        mt5_module: módulo MetaTrader5 já inicializado
        underlying: ativo subjacente (default: BOVA11)
        risk_free_rate: taxa livre de risco anual (default: estima do DI1)

    Returns:
        dict com {iv, spot, strike, option_symbol, days_to_expiry, mid_price}
        ou None se falhar.
    """
    atm = find_atm_option(mt5_module, underlying)
    if atm is None:
        return None

    # Taxa de juros: usar ~13% (SELIC atual) se não fornecida
    if risk_free_rate is None:
        # Tentar pegar do DI1
        di_tick = mt5_module.symbol_info_tick("DI1$N")
        if di_tick and di_tick.bid > 0:
            risk_free_rate = di_tick.bid / 100  # DI1 vem em % (ex: 13.5 -> 0.135)
        else:
            risk_free_rate = 0.135  # fallback SELIC

    S = atm["spot"]
    K = atm["strike"]
    T = atm["days_to_expiry"] / 252  # dias úteis
    r = risk_free_rate
    C = atm["mid_price"]

    if T <= 0:
        log.warning("Days to expiry <= 0, skipping IV")
        return None

    iv = implied_vol_bisection(C, S, K, T, r, is_call=True)

    if iv is None or iv < 0.01 or iv > 2.0:
        log.warning(f"IV fora dos limites: {iv}")
        return None

    log.info(f"IV ATM: {iv*100:.1f}% | {atm['symbol']} K={K:.0f} "
             f"S={S:.2f} T={atm['days_to_expiry']}d C={C:.2f}")

    return {
        "iv": iv,
        "spot": S,
        "strike": K,
        "option_symbol": atm["symbol"],
        "days_to_expiry": atm["days_to_expiry"],
        "mid_price": C,
        "risk_free_rate": r,
        "series_letter": atm["series_letter"],
    }
