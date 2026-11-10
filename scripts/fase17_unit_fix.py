"""
Fase 17: cria versões NOWCAST corrigidas (β/z + Kalman R/Q) em SHADOW a partir das versões active.

Mantém fatores e β da versão vigente (mesma calibração de 28/10) e só corrige o que é bug:
  - score no espaço z certo (Σ βᵢ·σᵢ·zᵢ ÷ score_scale), α/intercepto reestimados SEM clamp;
  - R e Q do Kalman estimados nas barras intradiárias da janela de calibração.
Nada muda ao vivo: a versão nasce 'shadow'. Promover é explícito (scripts/model_versions.py promote).

    # só calcula e mostra (somente leitura):
    python scripts/fase17_unit_fix.py --db data/irai_live.db --out data/reports/fase17_unit_fix
    # registra as versões shadow num banco (use uma CÓPIA; o ao vivo só com aprovação):
    python scripts/fase17_unit_fix.py --db <copia.db> --register-db <copia.db>
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.eval.data import connect_ro
from backend.irai import model_registry as R
from backend.irai import nowcast_calib as NC
from backend.irai import features as F
from scripts.calibrate_universal import load_daily_returns

TARGETS = {"win": "WIN$N", "wdo": "WDO$N"}


def window_returns(conn, target, factors, end, n=252):
    daily = load_daily_returns(conn, 9, 18, symbols=[target] + list(factors))
    df = pd.DataFrame({"target": daily[target]})
    for f in factors:
        df[f] = daily.get(f)
    df = df.dropna()
    df = df[[getattr(d, "weekday", lambda: 0)() < 5 for d in df.index]]
    df = df[[str(d) <= end for d in df.index]]
    return df.iloc[-n:]


def analyse(conn, slug, window_end, n=252):
    target = TARGETS[slug]
    v = R.current_active(conn, slug, with_artifact=True)
    if v is None:
        raise RuntimeError(f"sem versão active para {slug}")
    art = v["artifact"]
    params = art["params"]
    factors = art["factors"]
    labels = art["factor_labels"]
    lab = [labels.get(f, f) for f in factors]
    beta = np.array([params[f"w_{l}"] for l in lab])
    sig = np.array([params.get(f"sigma_{l}", params.get(f"sigma_{l}_session", np.nan)) for l in lab])
    win = window_returns(conn, target, factors, window_end, n)
    Rm = win[factors].to_numpy(float)
    y = win["target"].to_numpy(float)
    c_ols = float(np.mean(y - Rm @ beta))
    cmp = NC.compare_scores(Rm, y, beta, sig, c_ols, params.get("alpha"), params.get("intercept"))
    p = F.build_panel(conn, target, factors, str(win.index.min()), str(win.index.max()))
    cum_t = (np.exp(p.df.rT.to_numpy()) - 1) * 100
    cum_f = (np.exp(p.df[[p.factor_cols[f] for f in factors]].to_numpy()) - 1) * 100
    kal = NC.estimate_kalman_noise(cum_t, cum_f, p.df.sess.to_numpy(), p.df.k.to_numpy(), beta)
    new_params = dict(params)
    new_params.update({"alpha": cmp["alpha_fixed"], "intercept": cmp["intercept_fixed"], "unit_fix": 1.0,
                       "score_scale": cmp["score_scale"]})
    if np.isfinite(kal["kalman_obs_cov"]) and kal["kalman_obs_cov"] > 0:
        new_params["kalman_obs_cov"] = kal["kalman_obs_cov"]
    if np.isfinite(kal["kalman_trans_cov"]) and kal["kalman_trans_cov"] > 0:
        new_params["kalman_trans_cov"] = kal["kalman_trans_cov"]
    return {"slug": slug, "target": target, "base_version": v["version_id"], "factors": factors,
            "factor_labels": labels, "window": [str(win.index.min()), str(win.index.max())],
            "compare": cmp, "kalman": kal, "params": new_params,
            "old": {"alpha": params.get("alpha"), "intercept": params.get("intercept"),
                    "kalman_obs_cov": 1e-3, "kalman_trans_cov": 1e-5}}


def register(db, res):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    ids = {}
    for slug, r in res.items():
        vid = R.register_version(
            conn, slug=slug, kind="nowcast", param_map=r["params"], factors=r["factors"],
            factor_labels=r["factor_labels"], status="shadow", train_start=r["window"][0], train_end=r["window"][1],
            config={"method": "fase 17: unit-fix β/z (correção A) + logística sem clamp + Kalman R/Q estimados",
                    "base_version": r["base_version"], "window_sessions": r["compare"]["n_sessions"]},
            metrics={"in_sample": True, "unit_fix_compare": r["compare"], "kalman_noise": r["kalman"]},
            git_sha=R.code_git_sha(), actor="fase17_unit_fix",
            notes=f"correção da fase 17 sobre {r['base_version']} (mesmos fatores e β)")
        ids[slug] = vid
    conn.commit()
    conn.close()
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--window-end", default="2026-10-28")
    ap.add_argument("--out", default=None)
    ap.add_argument("--register-db", default=None, help="banco onde registrar as versões shadow (use uma cópia)")
    a = ap.parse_args()
    conn = connect_ro(a.db)
    conn.row_factory = sqlite3.Row
    res = {slug: analyse(conn, slug, a.window_end) for slug in TARGETS}
    conn.close()
    for slug, r in res.items():
        c, k = r["compare"], r["kalman"]
        print(f"{r['target']}: acc regressor {c['acc_regressor']:.1%} | antigo {c['acc_old']:.1%} | corrigido {c['acc_fixed']:.1%}"
              f" | AUC {c['auc_old']:.3f} -> {c['auc_fixed']:.3f} | α {c['alpha_fixed']:.3f} b {c['intercept_fixed']:+.3f}"
              f" | R {k['kalman_obs_cov']:.4g} %² Q {k['kalman_trans_cov']:.3g}")
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out + ".json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    if a.register_db:
        print("registradas (shadow):", register(a.register_db, res))


if __name__ == "__main__":
    main()
