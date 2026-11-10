"""
Harness de assertividade (fase 15): avalia o P(↑) atual gravado nos snapshots ao vivo.

Saída é um dicionário serializável em JSON (ver `run_evaluation`). Não escreve em banco.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from . import HARNESS_VERSION
from .data import PanelConfig, build_panel, coverage, connect_ro, load_bars
from .events import COST_PTS, live_spread_events
from .metrics import auc, brier_skill, evaluate_probability, hit_rate, mean_ci_by_session

PRIMARY_HORIZON = "60m"      # decisão D1 (PRD §12.1)
SECONDARY_HORIZON = "close"  # só avaliação
DEFAULT_TARGETS = ("WIN$N", "WDO$N")  # decisão D2


@dataclass(frozen=True)
class EvalConfig:
    start: str
    end: str
    targets: tuple = DEFAULT_TARGETS
    as_of_utc: str | None = None
    live_max_lag_min: float = 10.0
    n_boot: int = 1000
    seed: int = 0
    segment_boot: int = 0          # segmentações sem IC (custo); >0 liga IC
    marker_z: float = 2.0
    window_sessions: int | None = None   # mantém só os últimos N pregões com barras ao vivo

    def panel_config(self) -> PanelConfig:
        return PanelConfig(start=self.start, end=self.end, as_of_utc=self.as_of_utc,
                           live_max_lag_min=self.live_max_lag_min)

    def config_hash(self) -> str:
        d = asdict(self)
        if d.get("window_sessions") is None:  # campo opcional: não muda o hash de configs antigas
            d.pop("window_sessions")
        payload = json.dumps({**d, "harness": HARNESS_VERSION}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def git_sha(repo_dir: str | None = None) -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_dir,
                             capture_output=True, text=True, timeout=10)
        sha = out.stdout.strip() or "unknown"
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo_dir,
                               capture_output=True, text=True, timeout=20).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def _valid(df: pd.DataFrame, fwd_col: str) -> pd.DataFrame:
    """Remove alvos indefinidos e empates (retorno exatamente zero), conforme SPEC §3."""
    f = df[fwd_col]
    return df[f.notna() & (f != 0)]


def _prob_block(df: pd.DataFrame, fwd_col: str, cfg: EvalConfig, seed_offset: int, n_boot: int) -> dict:
    d = _valid(df, fwd_col)
    y = (d[fwd_col] > 0).astype(int).to_numpy()
    p = (d.p_up.to_numpy() / 100.0)
    res = evaluate_probability(p, y, d.sess.to_numpy(), n_boot=n_boot, seed=cfg.seed + seed_offset)
    res["ties_excluded"] = int(((df[fwd_col] == 0)).sum())
    return res


def _baselines(df: pd.DataFrame, fwd_col: str) -> dict:
    """REQ-V06: taxa-base, momentum (retorno do dia) e contrarian (−retorno do dia)."""
    d = _valid(df, fwd_col)
    y = (d[fwd_col] > 0).astype(int).to_numpy()
    rtd = d.rtd.to_numpy()
    base = float(y.mean()) if len(y) else float("nan")
    return {
        "base_rate": {"base_up": base, "auc": 0.5, "bss": 0.0,
                      "hit": float(max(base, 1 - base)) if len(y) else float("nan")},
        "momentum": {"auc": auc(rtd, y), "hit": hit_rate((rtd > 0).astype(float), y)},
        "contrarian": {"auc": auc(-rtd, y), "hit": hit_rate((rtd < 0).astype(float), y)},
    }


def _segments(df: pd.DataFrame, cfg: EvalConfig) -> dict:
    """REQ-V05: AUC/BSS por hora, mês e tercil de vol, para 60 min e nowcast."""
    out = {}
    for key in ("hour", "month", "vol_tercile"):
        rows = []
        for val, g in df.groupby(key):
            row = {key: str(val), "n_bars": int(len(g)), "n_sessions": int(g.sess.nunique())}
            for lab, col in (("60m", "fwd_60m"), ("close", "fwd_close"), ("nowcast", "rtd")):
                d = _valid(g, col)
                y = (d[col] > 0).astype(int).to_numpy()
                p = d.p_up.to_numpy() / 100.0
                row[f"auc_{lab}"] = auc(p, y)
                row[f"bss_{lab}"] = brier_skill(p, y)
            rows.append(row)
        out[key] = rows
    return out


def _markers(df: pd.DataFrame, cfg: EvalConfig) -> list[dict]:
    """REQ-V07 (parcial): pontos |Z rastro| ≥ 2 (contrarian) e estrela dourada (Z rastro + pair Z + P).

    Retorno do marcador = sinal × retorno futuro, em bp. IC 95% da média por bootstrap de pregões.
    """
    z, pz, p = df.price_diverge_z, df.pair_z, df.p_up
    sig = np.where(z <= -cfg.marker_z, 1, np.where(z >= cfg.marker_z, -1, 0))
    gold = ((z <= -cfg.marker_z) & (pz <= -cfg.marker_z) & (p > 50)) | \
           ((z >= cfg.marker_z) & (pz >= cfg.marker_z) & (p < 50))
    out = []
    n_sess = max(1, df.sess.nunique())
    for name, sel in (("ponto_z_rastro", sig != 0), ("estrela_dourada", gold.to_numpy())):
        d = df[sel]
        s = sig[sel]
        row = {"marker": name, "n": int(len(d)), "per_session": float(len(d) / n_sess)}
        for lab, col in (("15m", "fwd_15m"), ("30m", "fwd_30m"), ("60m", "fwd_60m"), ("close", "fwd_close")):
            x = s * d[col].to_numpy()
            ok = np.isfinite(x) & (d[col].to_numpy() != 0)
            xs, ss = x[ok] * 1e4, d.sess.to_numpy()[ok]
            if len(xs):
                m, lo, hi = mean_ci_by_session(xs, ss, n_boot=cfg.n_boot, seed=cfg.seed + 1)
                row[f"bp_{lab}"], row[f"bp_{lab}_lo"], row[f"bp_{lab}_hi"] = m, lo, hi
                row[f"hit_{lab}"] = float((xs > 0).mean())
            else:
                row[f"bp_{lab}"] = row[f"bp_{lab}_lo"] = row[f"bp_{lab}_hi"] = row[f"hit_{lab}"] = None
        out.append(row)
    return out


SPREAD_Z_COLS = ("pair_fixed_z", "pair_z", "price_diverge_z")


def _spread_events(conn, target: str, pcfg: PanelConfig, live: pd.DataFrame, cfg: EvalConfig) -> list[dict]:
    """Fase 18: cobertura do z (% |z| > 2) e P&L por evento (pontos, líquido de custo) dos z
    gravados ao vivo. Os z entram na grade completa de barras M5 do pregão (barra sem snapshot ao
    vivo = z ausente), para que os horizontes sejam contados em barras reais."""
    cols = [c for c in SPREAD_Z_COLS if c in live]
    if not cols or not len(live):
        return []
    b = load_bars(conn, target, pcfg)
    b = b[b.sess.isin(set(live.sess))].copy()
    b["k"] = ((b.ts_brt.dt.hour * 60 + b.ts_brt.dt.minute) - pcfg.session_open_min) // 5
    z = live[["ts_brt"] + cols].drop_duplicates("ts_brt")
    m = b.merge(z, on="ts_brt", how="left").sort_values("ts_brt").reset_index(drop=True)
    rows = live_spread_events(m, z_cols=tuple(cols), target=target, thr=cfg.marker_z,
                              n_boot=max(100, min(cfg.n_boot, 1000)), seed=cfg.seed + 7)
    for r in rows:
        r["cost_pts"] = COST_PTS.get(target, 0.0)
    return rows


def evaluate_target(conn, target: str, cfg: EvalConfig) -> dict:
    pcfg = cfg.panel_config()
    panel = build_panel(conn, target, pcfg)
    live = panel[panel.live].copy()
    if cfg.window_sessions:
        keep = sorted(live.sess.unique())[-cfg.window_sessions:]
        live = live[live.sess.isin(keep)].copy()
    horizons = {}
    for i, (lab, _) in enumerate(pcfg.horizons):
        horizons[lab] = _prob_block(live, "fwd_" + lab, cfg, i, cfg.n_boot)
    horizons["close"] = _prob_block(live, "fwd_close", cfg, 10, cfg.n_boot)
    horizons["nowcast"] = _prob_block(live, "rtd", cfg, 20, cfg.n_boot)
    for lab in horizons:
        horizons[lab]["role"] = ("primário" if lab == PRIMARY_HORIZON else
                                 "secundário" if lab == SECONDARY_HORIZON else
                                 "nowcast" if lab == "nowcast" else "relatório")
    # Para o nowcast o momentum é o próprio alvo (AUC trivial = 1), então não entra.
    baselines = {lab: _baselines(live, col) for lab, col in (("60m", "fwd_60m"), ("close", "fwd_close"))}
    ext = live.p_up
    return {
        "target": target,
        "sessions": int(live.sess.nunique()),
        "first_session": str(live.sess.min()) if len(live) else None,
        "last_session": str(live.sess.max()) if len(live) else None,
        "live_bars": int(len(live)),
        "coverage": coverage(conn, target, pcfg),
        "p_distribution": {
            "share_extreme_lt20_gt80": float(((ext < 20) | (ext > 80)).mean()) if len(ext) else None,
            "mean_abs_dev_from_50": float((ext - 50).abs().mean()) if len(ext) else None,
        },
        "horizons": horizons,
        "baselines": baselines,
        "segments": _segments(live, cfg),
        "markers": _markers(live, cfg),
        "spread_events": _spread_events(conn, target, pcfg, live, cfg),
    }


def run_evaluation(db_path: str, cfg: EvalConfig, repo_dir: str | None = None) -> dict:
    conn = connect_ro(db_path)
    try:
        results = {t: evaluate_target(conn, t, cfg) for t in cfg.targets}
    finally:
        conn.close()
    return {
        "meta": {
            "harness_version": HARNESS_VERSION,
            "config": asdict(cfg),
            "config_hash": cfg.config_hash(),
            "code_git_sha": git_sha(repo_dir),
            "source_db": db_path,
            "model": "nowcast_atual",
            "primary_horizon": PRIMARY_HORIZON,
            "secondary_horizon": SECONDARY_HORIZON,
            "conventions": {
                "live_bar": f"is_ghost=0 e created_at − abertura da barra (BRT) em [0, {cfg.live_max_lag_min}] min",
                "session": "barras M5 com abertura em [09:00, 18:25) BRT",
                "target": "sinal do retorno do fechamento da barra até h barras à frente no mesmo pregão; retorno zero excluído",
                "nowcast": "sinal do retorno do dia (fechamento da barra / abertura do pregão − 1)",
                "bss": "contra a taxa-base do próprio conjunto avaliado",
                "ece": "10 bins de largura igual",
                "ci": f"bootstrap de pregões, B={cfg.n_boot}, seed={cfg.seed}",
            },
        },
        "targets": results,
    }


def metric_rows(result: dict, eval_date: str, window_label: int | None = None) -> list[dict]:
    """Linhas no formato de `forecast_eval_daily` (SPEC §10.6)."""
    meta = result["meta"]
    rows = []
    for t, r in result["targets"].items():
        ws = window_label if window_label is not None else r["sessions"]
        for h, m in r["horizons"].items():
            rows.append(dict(eval_date=eval_date, target=t, model="nowcast", version_id=None,
                             horizon=h, window_sessions=ws, n=m["n"], auc=m["auc"],
                             auc_lo=m["auc_lo"], auc_hi=m["auc_hi"], brier=m["brier"], bss=m["bss"],
                             ece=m["ece"], hit=m["hit"], config_hash=meta["config_hash"],
                             code_git_sha=meta["code_git_sha"]))
        for h, bl in r["baselines"].items():
            for name in ("momentum", "contrarian"):
                rows.append(dict(eval_date=eval_date, target=t, model=f"baseline_{name}", version_id=None,
                                 horizon=h, window_sessions=ws, n=r["horizons"][h]["n"],
                                 auc=bl[name]["auc"], auc_lo=None, auc_hi=None, brier=None, bss=None,
                                 ece=None, hit=bl[name]["hit"], config_hash=meta["config_hash"],
                                 code_git_sha=meta["code_git_sha"]))
    return rows
