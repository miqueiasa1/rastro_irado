import numpy as np

def compute_nwe(data: list[dict], history_closes: list[float] = None) -> list[dict]:
    """
    Computa o Nadaraya-Watson Envelope (NWE) no backend de forma vetorizada com NumPy.
    Retorna a lista de dicionários enriquecida com os preços absolutos do NWE.
    """
    # Inicializar os campos preventivamente como None para todos os elementos
    for d in data:
        d.setdefault("nwe_center_price", None)
        d.setdefault("nwe_upper_price", None)
        d.setdefault("nwe_lower_price", None)
        d.setdefault("nwe_slope", None)
        d.setdefault("nwe_up_price", None)
        d.setdefault("nwe_down_price", None)

    if not data:
        return data

    history_prices = list(history_closes) if history_closes else []
    
    # Filtrar barras válidas (não ghost e não futuras/pad)
    valid_data = [d for d in data if d.get("win_current") is not None and not d.get("is_ghost", False)]
    current_prices = [d["win_current"] for d in valid_data]

    # Stitching de gap noturno
    if history_prices and current_prices:
        gap = current_prices[0] - history_prices[-1]
        history_prices = [p + gap for p in history_prices]

    all_prices = history_prices + current_prices
    n_all = len(all_prices)
    if n_all < 3:
        return data

    all_prices_arr = np.array(all_prices, dtype=float)

    # 1) Regressão Kernel Gaussiana Causal (Lookback = 95, BW = 8)
    NWE_LOOKBACK = 95
    NWE_BW = 8.0
    NWE_MULT = 3.0

    w = np.exp(-np.arange(NWE_LOOKBACK)**2 / (2 * NWE_BW * NWE_BW))
    center = np.zeros(n_all, dtype=float)
    
    for t in range(n_all):
        limit = min(t, NWE_LOOKBACK - 1)
        w_t = w[:limit+1]
        p_t = all_prices_arr[t - limit : t + 1][::-1]
        center[t] = np.sum(w_t * p_t) / np.sum(w_t)

    # 2) Largura do Envelope com MAE Móvel (lookback = 95)
    errors = np.abs(all_prices_arr - center)
    env_width = np.zeros(n_all, dtype=float)
    
    for t in range(n_all):
        limit = min(t, NWE_LOOKBACK - 1)
        err_t = errors[t - limit : t + 1]
        mae = np.mean(err_t)
        env_width[t] = mae * NWE_MULT

    # Fatiar curvas de volta para a sessão atual (removendo histórico)
    current_center = center[len(history_prices):]
    current_env_width = env_width[len(history_prices):]

    last_slope = 0.0
    valid_idx = 0
    enriched_data = []

    # Inicializar os valores anteriores com base no histórico para evitar colapsar na abertura do dia
    if len(history_prices) > 0:
        last_center = float(center[len(history_prices) - 1])
        last_upper = float(center[len(history_prices) - 1] + env_width[len(history_prices) - 1])
        last_lower = float(center[len(history_prices) - 1] - env_width[len(history_prices) - 1])
    else:
        last_center = None
        last_upper = None
        last_lower = None

    for d in data:
        # Futuras barras vazias na grade horária (padding)
        if d.get("win_current") is None:
            enriched_data.append(d)
            continue

        # Tratamento de Ghost Bars (B3 overnight flat)
        if d.get("is_ghost", False):
            val = d["win_current"]
            enriched_data.append({
                **d,
                "nwe_center_price": last_center if last_center is not None else val,
                "nwe_upper_price": last_upper if last_upper is not None else val,
                "nwe_lower_price": last_lower if last_lower is not None else val,
                "nwe_slope": last_slope,
                "nwe_up_price": None,
                "nwe_down_price": None
            })
            continue

        # Barras reais
        i = valid_idx
        valid_idx += 1

        nwe_center_price = float(current_center[i])
        nwe_upper_price = float(current_center[i] + current_env_width[i])
        nwe_lower_price = float(current_center[i] - current_env_width[i])

        # Atualizar carry-forward para as próximas ghost bars
        last_center = nwe_center_price
        last_upper = nwe_upper_price
        last_lower = nwe_lower_price

        # Inclinação (Slope)
        if i > 0:
            prev_c = float(current_center[i - 1])
        elif history_prices:
            prev_c = float(center[len(history_prices) - 1])
        else:
            prev_c = float(current_center[0])

        nwe_slope_price = float(nwe_center_price - prev_c)
        is_up = nwe_slope_price >= 0.0

        # Transição posterior (próxima barra muda de direção?)
        if i < len(valid_data) - 1:
            next_c = float(current_center[i + 1])
            next_slope = float(next_c - nwe_center_price)
        else:
            next_slope = nwe_slope_price
        is_transition = (nwe_slope_price >= 0.0) != (next_slope >= 0.0)

        # Transição anterior (barra anterior era direção diferente?)
        if i > 1:
            prev_prev_c = float(current_center[i - 2])
        elif len(history_prices) > 1:
            prev_prev_c = float(center[len(history_prices) - 2])
        else:
            prev_prev_c = prev_c

        prev_slope_price = float(prev_c - prev_prev_c)
        was_transition = (prev_slope_price >= 0.0) != (nwe_slope_price >= 0.0)

        # Preencher series para plotagem dinâmica de cor
        nwe_up_price = nwe_center_price if (is_up or is_transition or was_transition) else None
        nwe_down_price = nwe_center_price if (not is_up or is_transition or was_transition) else None

        last_slope = nwe_slope_price

        enriched_data.append({
            **d,
            "nwe_center_price": nwe_center_price,
            "nwe_upper_price": nwe_upper_price,
            "nwe_lower_price": nwe_lower_price,
            "nwe_slope": nwe_slope_price,
            "nwe_up_price": nwe_up_price,
            "nwe_down_price": nwe_down_price
        })

    return enriched_data
