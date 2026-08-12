import numpy as np

def compute_nwe(data: list[dict], history_closes: list[float] = None) -> list[dict]:
    """
    Computa o Nadaraya-Watson Envelope (NWE) de forma 100% contínua e sem reseto diário.
    Usa a sequência ininterrupta de barras históricas (history_closes + barras da sessão)
    garantindo que as bandas fluam suavemente do pregão anterior para o pregão atual.
    """
    if not data:
        return data

    raw_history = [float(p) for p in history_closes] if history_closes else []

    current_prices = []
    valid_indices = []

    for idx, d in enumerate(data):
        d.setdefault("nwe_center_price", None)
        d.setdefault("nwe_upper_price", None)
        d.setdefault("nwe_lower_price", None)
        d.setdefault("nwe_slope", None)
        d.setdefault("nwe_up_price", None)
        d.setdefault("nwe_down_price", None)

        if d.get("win_current") is not None and not d.get("is_ghost", False):
            current_prices.append(float(d["win_current"]))
            valid_indices.append(idx)

    # Sequência total ininterrupta: histórico + barras da sessão
    all_prices = raw_history + current_prices
    n_all = len(all_prices)

    # 1) Regressão Kernel Gaussiana Causal (Lookback = 95, BW = 8.0, Mult = 3.0)
    NWE_LOOKBACK = 95
    NWE_BW = 8.0
    NWE_MULT = 3.0
    w = np.exp(-np.arange(NWE_LOOKBACK)**2 / (2 * NWE_BW * NWE_BW))

    # Se a quantidade de barras for insuficiente para o filtro, calcular valores estáticos
    if n_all < 3:
        if raw_history:
            last_p = raw_history[-1]
            for idx in valid_indices:
                data[idx]["nwe_center_price"] = last_p
                data[idx]["nwe_upper_price"] = last_p
                data[idx]["nwe_lower_price"] = last_p
        return data

    closes = np.array(all_prices, dtype=float)
    center = np.zeros(n_all, dtype=float)

    for t in range(n_all):
        l_idx = min(t, NWE_LOOKBACK - 1)
        w_t = w[:l_idx + 1]
        p_t = closes[t - l_idx : t + 1][::-1]
        center[t] = np.sum(w_t * p_t) / np.sum(w_t)

    # 2) Largura do Envelope com MAE Móvel (lookback = 95)
    errors = np.abs(closes - center)
    upper = np.zeros(n_all, dtype=float)
    lower = np.zeros(n_all, dtype=float)

    for t in range(n_all):
        l_idx = min(t, NWE_LOOKBACK - 1)
        err_t = errors[t - l_idx : t + 1]
        mae = np.mean(err_t)
        width = mae * NWE_MULT
        upper[t] = center[t] + width
        lower[t] = center[t] - width

    # 3) Atribuir valores calculados para as barras válidas da sessão
    hist_len = len(raw_history)
    for k, data_idx in enumerate(valid_indices):
        all_idx = hist_len + k
        c_val = float(center[all_idx])
        u_val = float(upper[all_idx])
        l_val = float(lower[all_idx])

        slope = float(center[all_idx] - center[all_idx - 1]) if all_idx > 0 else 0.0

        data[data_idx]["nwe_center_price"] = c_val
        data[data_idx]["nwe_upper_price"] = u_val
        data[data_idx]["nwe_lower_price"] = l_val
        data[data_idx]["nwe_slope"] = slope

    # 4) Ghost bars / Pré-mercado recebem a última leitura histórica contínua
    last_hist_center = float(center[hist_len - 1]) if hist_len > 0 else None
    last_hist_upper = float(upper[hist_len - 1]) if hist_len > 0 else None
    last_hist_lower = float(lower[hist_len - 1]) if hist_len > 0 else None

    for d in data:
        if d.get("is_ghost", False) or d.get("win_current") is None:
            if last_hist_center is not None:
                d["nwe_center_price"] = last_hist_center
                d["nwe_upper_price"] = last_hist_upper
                d["nwe_lower_price"] = last_hist_lower
                d["nwe_slope"] = 0.0

    return data
