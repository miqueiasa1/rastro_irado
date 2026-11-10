"""
Leitura somente leitura do banco e montagem do painel de avaliação (fase 15).

- O banco é aberto com URI `file:...?mode=ro`; nenhuma escrita é possível por esta conexão.
- `timestamp_utc` (market_bars e irai_live_snapshots) está no relógio do broker
  (Nova York + 7h), conforme `backend/timeconv.py`. `created_at` dos snapshots é UTC real
  (`datetime('now')` do SQLite).
- Pregão B3 para avaliação: barras M5 com abertura em [09:00, 18:25) BRT.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass

import numpy as np
import pandas as pd

BRT = "America/Sao_Paulo"
NY = "America/New_York"


def connect_ro(db_path: str) -> sqlite3.Connection:
    """Conexão estritamente somente leitura (falha se o arquivo não existir)."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(db_path)
    uri = "file:" + os.path.abspath(db_path).replace("\\", "/") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def broker_wall_to_brt(ts: pd.Series) -> pd.Series:
    """Relógio de parede do broker (NY+7, rotulado como UTC) -> datetime tz-aware em BRT.

    Versão vetorizada de `backend.timeconv.broker_wall_to_brt_wall` (equivalência coberta
    por teste). Horários inexistentes/ambíguos da virada do DST americano (domingo de
    madrugada, mercado fechado) viram NaT/deslocados e não afetam o pregão B3.
    """
    t = pd.to_datetime(ts, utc=True, format="mixed").dt.tz_localize(None)
    ny = (t - pd.Timedelta(hours=7)).dt.tz_localize(NY, ambiguous="NaT", nonexistent="shift_forward")
    return ny.dt.tz_convert(BRT)


@dataclass(frozen=True)
class PanelConfig:
    start: str                      # primeira session_date (YYYY-MM-DD)
    end: str                        # última session_date (YYYY-MM-DD)
    as_of_utc: str | None = None    # corte de dados (UTC real); None = tudo
    live_max_lag_min: float = 10.0  # REQ-V02
    session_open_min: int = 9 * 60
    session_end_min: int = 18 * 60 + 25   # exclusivo: última barra abre às 18:20
    horizons: tuple = (("5m", 1), ("15m", 3), ("30m", 6), ("60m", 12))


def load_bars(conn, symbol: str, cfg: PanelConfig) -> pd.DataFrame:
    lo = (pd.Timestamp(cfg.start) - pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    hi = (pd.Timestamp(cfg.end) + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    b = pd.read_sql_query(
        "SELECT timestamp_utc, open, close FROM market_bars "
        "WHERE symbol = ? AND timeframe = 'M5' AND timestamp_utc >= ? AND timestamp_utc < ? "
        "ORDER BY timestamp_utc",
        conn, params=(symbol, lo, hi),
    )
    b["ts_brt"] = broker_wall_to_brt(b["timestamp_utc"])
    b = b.dropna(subset=["ts_brt"])
    mins = b.ts_brt.dt.hour * 60 + b.ts_brt.dt.minute
    b = b[(mins >= cfg.session_open_min) & (mins < cfg.session_end_min)].copy()
    if cfg.as_of_utc:
        cut = pd.Timestamp(cfg.as_of_utc, tz="UTC")
        b = b[(b.ts_brt + pd.Timedelta(minutes=5)) <= cut]
    b["sess"] = b.ts_brt.dt.strftime("%Y-%m-%d")
    b = b[(b.sess >= cfg.start) & (b.sess <= cfg.end)]
    b = b.drop_duplicates("ts_brt").sort_values("ts_brt").reset_index(drop=True)
    return b


def _snapshot_extra_cols(conn) -> str:
    """Fase 18: `pair_fixed_z` entra no painel quando a coluna existe (bancos antigos/fixtures não têm)."""
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(irai_live_snapshots)")}
    except Exception:
        cols = set()
    return ", pair_fixed_z" if "pair_fixed_z" in cols else ""


def load_snapshots(conn, target: str, cfg: PanelConfig) -> pd.DataFrame:
    s = pd.read_sql_query(
        "SELECT target, session_date, timestamp_utc, p_up, is_ghost, created_at, "
        "price_diverge_z, pair_z" + _snapshot_extra_cols(conn) + " FROM irai_live_snapshots "
        "WHERE target = ? AND timeframe = 'M5' AND session_date >= ? AND session_date <= ? "
        "ORDER BY session_date, timestamp_utc",
        conn, params=(target, cfg.start, cfg.end),
    )
    s["ts_brt"] = broker_wall_to_brt(s["timestamp_utc"])
    s["created_utc"] = pd.to_datetime(s["created_at"], utc=True, format="mixed")
    if cfg.as_of_utc:
        s = s[s.created_utc <= pd.Timestamp(cfg.as_of_utc, tz="UTC")]
    s["lag_min"] = (s.created_utc - s.ts_brt).dt.total_seconds() / 60.0
    return s


def build_panel(conn, target: str, cfg: PanelConfig, bar_symbol: str | None = None) -> pd.DataFrame:
    """Uma linha por snapshot ao vivo, com retornos futuros e retorno do dia (nowcast)."""
    b = load_bars(conn, bar_symbol or target, cfg)
    g = b.groupby("sess")
    for name, h in cfg.horizons:
        b["fwd_" + name] = g.close.shift(-h) / b.close - 1.0
    b["fwd_close"] = g.close.transform("last") / b.close - 1.0
    b["rtd"] = b.close / g.open.transform("first") - 1.0
    keep = ["ts_brt", "sess", "close", "rtd", "fwd_close"] + ["fwd_" + n for n, _ in cfg.horizons]
    s = load_snapshots(conn, target, cfg)
    m = s.merge(b[keep], on="ts_brt", how="inner")
    m = m[m.is_ghost == 0]
    m["live"] = (m.lag_min >= 0) & (m.lag_min <= cfg.live_max_lag_min)
    m["hour"] = m.ts_brt.dt.hour
    m["month"] = m.ts_brt.dt.strftime("%Y-%m")
    # Tercil de volatilidade realizada do pregão (segmentação de relatório, não é feature).
    rv = b.assign(r=g.close.pct_change()).groupby("sess").r.std()
    terc = pd.qcut(rv.rank(method="first"), 3, labels=["baixa", "media", "alta"]) if len(rv) >= 3 else None
    m["vol_tercile"] = m.sess.map(terc.astype(str)) if terc is not None else "n/a"
    return m.reset_index(drop=True)


def coverage(conn, target: str, cfg: PanelConfig, bar_symbol: str | None = None) -> dict:
    """Cobertura de snapshots ao vivo (PRD §7).

    - `live_share_of_snapshots`: barras com snapshot (não-ghost) que são "ao vivo" — definição
      usada na auditoria de 10/11/2026 (87,6% = 6.637 de 7.579 no WIN).
    - `bar_coverage`: barras ao vivo / todas as barras M5 do pregão no período (inclui pregões
      sem nenhum snapshot) — definição da meta "≥ 95% das barras do pregão".
    """
    b = load_bars(conn, bar_symbol or target, cfg)
    m = build_panel(conn, target, cfg, bar_symbol)
    live = m[m.live]
    n_live = int(live.ts_brt.nunique())
    return {
        "bars": int(len(b)),
        "bar_sessions": int(b.sess.nunique()),
        "snapshot_bars": int(m.ts_brt.nunique()),
        "live_snapshots": n_live,
        "live_share_of_snapshots": float(n_live / m.ts_brt.nunique()) if len(m) else float("nan"),
        "bar_coverage": float(n_live / len(b)) if len(b) else float("nan"),
        "lag_median_min": float(m.lag_min.median()) if len(m) else float("nan"),
        "lag_median_live_min": float(live.lag_min.median()) if len(live) else float("nan"),
    }
