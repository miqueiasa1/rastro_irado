import numpy as np


def compute_nwe(data: list[dict], history_closes: list[float] = None) -> list[dict]:
    """
    Computa o Nadaraya-Watson Envelope (NWE) de forma contínua, sem reset diário.
    Usa a sequência ininterrupta de barras históricas (history_closes + barras da sessão),
    para que as bandas fluam do pregão anterior para o pregão atual.

    Gap stitching (AGENTS.md, Regra 4): o salto noturno entre o último preço antes da
    abertura e a abertura de hoje é removido do histórico (history + gap) antes de calcular
    o kernel e o MAE. Sem isso, o gap entra no erro médio e as bandas "estufam como um balão"
    no início da sessão. Os pontos anteriores à abertura recebem as bandas deslocadas de volta
    (−gap), ficando coerentes com os preços que de fato negociaram naquele momento.

    Barras de pré-sessão são identificadas por `is_pre_market` (preenchido pelo engine).
    """
    if not data:
        return data

    raw_history = [float(p) for p in history_closes] if history_closes else []

    pre_prices, pre_indices = [], []        # barras reais do alvo antes da abertura (ex.: after-market de ontem)
    session_prices, session_indices = [], []

    for idx, d in enumerate(data):
        d.setdefault("nwe_center_price", None)
        d.setdefault("nwe_upper_price", None)
        d.setdefault("nwe_lower_price", None)
        d.setdefault("nwe_slope", None)
        d.setdefault("nwe_up_price", None)
        d.setdefault("nwe_down_price", None)

        if d.get("win_current") is not None and not d.get("is_ghost", False):
            if d.get("is_pre_market", False) and not session_indices:
                pre_prices.append(float(d["win_current"]))
                pre_indices.append(idx)
            else:
                session_prices.append(float(d["win_current"]))
                session_indices.append(idx)

    before = raw_history + pre_prices

    # Gap stitching: só quando a sessão já abriu e existe histórico anterior
    gap = 0.0
    if session_indices and before:
        first = data[session_indices[0]]
        session_open = first.get("win_open") or first.get("win_bar_open") or session_prices[0]
        try:
            session_open = float(session_open)
        except (TypeError, ValueError):
            session_open = session_prices[0]
        if session_open and session_open > 0:
            gap = session_open - before[-1]

    stitched_before = [p + gap for p in before]
    all_prices = stitched_before + session_prices
    n_all = len(all_prices)
    n_before = len(before)
    hist_len = len(raw_history)

    # 1) Regressão Kernel Gaussiana Causal (Lookback = 95, BW = 8.0, Mult = 3.0)
    NWE_LOOKBACK = 95
    NWE_BW = 8.0
    NWE_MULT = 3.0
    w = np.exp(-np.arange(NWE_LOOKBACK) ** 2 / (2 * NWE_BW * NWE_BW))

    # Se a quantidade de barras for insuficiente para o filtro, calcular valores estáticos
    if n_all < 3:
        if raw_history:
            last_p = raw_history[-1]
            for idx in pre_indices + session_indices:
                data[idx]["nwe_center_price"] = last_p
                data[idx]["nwe_upper_price"] = last_p
                data[idx]["nwe_lower_price"] = last_p
        return data

    closes = np.array(all_prices, dtype=float)
    center = np.zeros(n_all, dtype=float)

    for t in range(n_all):
        l_idx = min(t, NWE_LOOKBACK - 1)
        w_t = w[:l_idx + 1]
        p_t = closes[t - l_idx: t + 1][::-1]
        center[t] = np.sum(w_t * p_t) / np.sum(w_t)

    # 2) Largura do Envelope com MAE Móvel (lookback = 95)
    errors = np.abs(closes - center)
    upper = np.zeros(n_all, dtype=float)
    lower = np.zeros(n_all, dtype=float)

    for t in range(n_all):
        l_idx = min(t, NWE_LOOKBACK - 1)
        err_t = errors[t - l_idx: t + 1]
        mae = np.mean(err_t)
        width = mae * NWE_MULT
        upper[t] = center[t] + width
        lower[t] = center[t] - width

    def _assign(data_idx, all_idx, shift):
        data[data_idx]["nwe_center_price"] = float(center[all_idx] - shift)
        data[data_idx]["nwe_upper_price"] = float(upper[all_idx] - shift)
        data[data_idx]["nwe_lower_price"] = float(lower[all_idx] - shift)
        data[data_idx]["nwe_slope"] = float(center[all_idx] - center[all_idx - 1]) if all_idx > 0 else 0.0

    # 3) Barras reais de pré-sessão: bandas deslocadas de volta (−gap)
    for k, data_idx in enumerate(pre_indices):
        _assign(data_idx, hist_len + k, gap)

    # 4) Barras da sessão
    for k, data_idx in enumerate(session_indices):
        _assign(data_idx, n_before + k, 0.0)

    # 5) Ghost bars (sem negócio do alvo): repetem a última leitura válida ANTERIOR a elas.
    #    Antes da 1ª barra real usam a última leitura pré-abertura (sem gap).
    last = None
    if n_before > 0:
        last = (float(center[n_before - 1] - gap), float(upper[n_before - 1] - gap), float(lower[n_before - 1] - gap))
    for d in data:
        if d.get("is_ghost", False) or d.get("win_current") is None:
            if last is not None:
                d["nwe_center_price"], d["nwe_upper_price"], d["nwe_lower_price"] = last
                d["nwe_slope"] = 0.0
        elif d.get("nwe_center_price") is not None:
            last = (d["nwe_center_price"], d["nwe_upper_price"], d["nwe_lower_price"])

    return data
