"""Fase 19A (REQ-S01, SPEC §15): montagem do payload publico do Firebase, sem efeitos colaterais.

Modulo puro (nao inicializa o Firebase) para que o filtro possa ser testado.
"""

# p_fwd_close* e so para avaliacao e nunca vai ao RTDB publico.
PUBLIC_STRIP_ALWAYS = ("p_fwd_close", "p_fwd_close_lo", "p_fwd_close_hi")
# Barras fechadas tambem perdem os fatores (so a ultima barra os leva, para o card do painel).
PUBLIC_STRIP_CLOSED = ("factors", "stale_factors")


def build_lean_series(raw_series):
    """Serie enxuta para o Firebase: tira p_fwd_close* de todas as barras e fatores das fechadas."""
    raw_series = raw_series or []
    last = len(raw_series) - 1
    lean = []
    for i, bar in enumerate(raw_series):
        if not isinstance(bar, dict):
            continue
        drop = PUBLIC_STRIP_ALWAYS if i == last else PUBLIC_STRIP_ALWAYS + PUBLIC_STRIP_CLOSED
        lean.append({k: v for k, v in bar.items() if k not in drop})
    return lean
