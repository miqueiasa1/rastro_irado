"""Banco sintético para os testes das fases 17/18 (valor justo da cesta, features causais).

WIN$N e três fatores (WDO$N, DI1$N, US500) em barras M5 de pregão B3 (09:00–18:20 BRT),
gravadas no relógio do broker (Nova York + 7h), como em `market_bars`.
"""
import os
import sqlite3

import numpy as np
import pandas as pd

TARGET = "WIN$N"
FACTORS = ["WDO$N", "DI1$N", "US500"]
GAMMA = {"WDO$N": -0.8, "DI1$N": -0.3, "US500": 0.6}


def sessions(n=45, start="2026-06-01"):
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start, periods=n)]


def brt_to_broker(ts_brt: pd.DatetimeIndex) -> list[str]:
    ny = ts_brt.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)
    return [t.strftime("%Y-%m-%d %H:%M:%S") for t in ny]


def build_db(path: str, n_sessions: int = 45, seed: int = 3, late_factor: dict | None = None) -> str:
    """`late_factor={'sess': 'AAAA-MM-DD', 'symbol': 'US500', 'first_min': 600}` remove as barras do
    fator antes de `first_min` (minutos desde 00:00 BRT) naquela sessão (fator sem negócio)."""
    if os.path.exists(path):
        os.remove(path)
    rng = np.random.default_rng(seed)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE market_bars (symbol TEXT, source TEXT, timeframe TEXT, timestamp_utc TEXT, "
                 "open REAL, high REAL, low REAL, close REAL, volume REAL, real_volume REAL, delta REAL)")
    px = {"WIN$N": 130000.0, "WDO$N": 5.4, "DI1$N": 14.0, "US500": 6000.0}
    vol = {"WDO$N": 0.0008, "DI1$N": 0.0005, "US500": 0.0009}
    rows = []
    for s in sessions(n_sessions):
        ts = pd.date_range(f"{s} 09:00", f"{s} 18:20", freq="5min", tz="America/Sao_Paulo")
        brk = brt_to_broker(ts)
        for sym in FACTORS + [TARGET]:
            px[sym] *= float(np.exp(rng.normal(0, 0.004)))  # gap noturno
        for i, t in enumerate(ts):
            fr = {f: rng.normal(0, vol[f]) for f in FACTORS}
            rt = sum(GAMMA[f] * fr[f] for f in FACTORS) + rng.normal(0, 0.0006)
            for sym, r in list(fr.items()) + [(TARGET, rt)]:
                if late_factor and sym == late_factor["symbol"] and s == late_factor["sess"] \
                        and t.hour * 60 + t.minute < late_factor["first_min"]:
                    continue
                o = px[sym]
                c = o * float(np.exp(r))
                px[sym] = c
                rows.append((sym, "test", "M5", brk[i], o, max(o, c), min(o, c), c, 1.0, 1.0, 0.0))
    conn.executemany("INSERT INTO market_bars VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return path
