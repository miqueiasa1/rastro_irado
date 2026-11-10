"""Banco sintético para os testes da fase 16 (versionamento de parâmetros / anti-repaint).

Alvo global 'US500' (dia do broker inteiro) com 2 fatores (DXY, VIX), barras M5 em 4 dias,
parâmetros legados gravados como a calibração destrutiva antiga fazia.
"""
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.db import init_db, get_connection  # noqa: E402

TARGET = "US500"
SLUG = "us500"
DAYS = ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"]
LEGACY_FITTED_AT = "2026-11-02T20:00:00Z"  # → vigência da versão adotada: 2026-11-03
LEGACY_PARAMS = {
    "w_dxy": -0.6, "w_vix": -0.3,
    "sigma_dxy": 0.004, "sigma_vix": 0.03,
    "alpha": 1.2, "intercept": 0.05,
}
NEW_PARAMS = {
    "w_dxy": 0.9, "w_vix": 0.4,
    "sigma_dxy": 0.002, "sigma_vix": 0.05,
    "alpha": 2.5, "intercept": -0.2,
}


def build_db(path: str, seed: int = 7) -> str:
    if os.path.exists(path):
        os.remove(path)
    init_db(path)
    conn = get_connection(path)
    conn.execute("""
        INSERT INTO asset_models (target, slug, display_name, factors, factor_labels,
                                  session_start_h, session_end_h, accuracy, r_squared, n_sessions, calibrated_at, active)
        VALUES (?, ?, 'S&P 500', '["DXY", "VIX"]', '{"DXY": "dxy", "VIX": "vix"}', 0, 24, 80.0, 0.5, 252, ?, 1)
    """, (TARGET, SLUG, LEGACY_FITTED_AT))
    conn.executemany(
        "INSERT INTO model_params (param_name, value, effective_from) VALUES (?, ?, ?)",
        [(f"{SLUG}_{k}", v, LEGACY_FITTED_AT) for k, v in LEGACY_PARAMS.items()],
    )
    rnd = random.Random(seed)
    prices = {"US500": 6000.0, "DXY": 100.0, "VIX": 18.0}
    vols = {"US500": 0.0012, "DXY": 0.0004, "VIX": 0.004}
    rows = []
    for day in ["2026-10-30"] + DAYS:  # 30/10 = warm-up
        for i in range(8 * 12, 16 * 12):  # 08:00–16:00 broker, M5
            hh, mm = divmod(i * 5, 60)
            ts = f"{day}T{hh:02d}:{mm:02d}:00Z"
            for sym in ("US500", "DXY", "VIX"):
                o = prices[sym]
                c = o * math.exp(rnd.gauss(0, vols[sym]))
                prices[sym] = c
                rows.append((sym, "tickmill", "M5", ts, o, max(o, c), min(o, c), c, 100.0, 0.0, 0.0))
    conn.executemany("""
        INSERT INTO market_bars (symbol, source, timeframe, timestamp_utc, open, high, low, close, volume, real_volume, delta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()
    return path
