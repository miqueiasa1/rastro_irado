"""
Treino walk-forward do modelo de 60 min (fase 18, SPEC §5–7) com o valor justo da cesta.

- Features causais de `backend/irai/features.py` (SPEC §4.2 + gap do valor justo e do par).
- Logística L2 (StandardScaler → LogisticRegression), C escolhido por Brier em CV purgado interno
  (K=5, embargo 2 sessões); calibração Platt nas previsões out-of-fold do treino (isotônica só se
  n ≥ 20.000 e reduzir o ECE em validação cruzada); faixa p_lo/p_hi = percentis 10/90 de um
  ensemble bootstrap por pregão.
- Externo: blocos mensais, treino expansivo, embargo de 1 sessão.
- Todas as configurações (conjuntos de features) são pré-registradas em CONFIG e reportadas.

Somente leitura no banco de dados de mercado. `--register-db` grava a versão `forecast` num banco
(use uma CÓPIA; o banco ao vivo só com aprovação explícita) como `shadow` se passar nos critérios
da fase 18, senão como `rejected`.

    python scripts/train_forecast.py --db data/irai_live.db --out data/reports/forecast_wf_20261110
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.eval.data import connect_ro
from backend.eval.events import cluster_t, detect_events, COST_PTS
from backend.eval.metrics import auc, brier, brier_skill, ece, hit_rate, bootstrap_by_session, session_groups
from backend.eval.walkforward import monthly_splits, purged_kfold
from backend.irai import features as F

warnings.filterwarnings("ignore", category=RuntimeWarning)

BASE_FEATURES = ["own_rtd_z", "own_r1", "own_r3", "own_r6", "own_r12", "nwe_pos", "rvol", "tod", "tod2", "gap_z"]

CONFIG = {
    "start": "2024-12-01",
    "end": "2026-11-10",
    "first_test_month": "2025-04",
    "targets": ["WIN$N", "WDO$N"],
    "horizon_bars": 12,
    "feature_sets": {
        "A_base": "SPEC §4.2 sem valor justo (próprio ativo + retornos da cesta)",
        "B_base_valor_justo": "A + gap do valor justo da cesta (z) + gap do par (β OLS 20 pregões)",
        "C_so_valor_justo": "gap da cesta + gap do par + retorno do dia + horário",
    },
    "C_grid": [0.01, 0.03, 0.05, 0.1, 0.3],
    "inner_k": 5, "inner_embargo": 2, "outer_embargo": 1,
    "n_ensemble": 50, "n_boot": 1000, "seed": 0,
    "fair_value": {"window_sessions": 60, "step_bars": 6, "sigma_sessions": 60},
    "pair": {"window_sessions": 20, "step_bars": 6},
    "signal_thresholds": [0.55, 0.60],
    "prototype_auc_60m": {"WIN$N": 0.540, "WDO$N": 0.503},
}


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]


def feature_columns(X: pd.DataFrame, fset: str) -> list[str]:
    fac = [c for c in X.columns if c.startswith("f_rtd_z_") or c.startswith("f_r3_")]
    if fset == "A_base":
        return BASE_FEATURES + fac
    if fset == "B_base_valor_justo":
        return BASE_FEATURES + fac + ["fv_gap_z", "pair_gap_z"]
    if fset == "C_so_valor_justo":
        return ["fv_gap_z", "pair_gap_z", "own_rtd_z", "tod"]
    raise ValueError(fset)


def _fit(X, y, C, seed=0):
    sc = StandardScaler().fit(X)
    lr = LogisticRegression(C=C, max_iter=500).fit(sc.transform(X), y)
    return sc, lr


def _logit(sc, lr, X):
    return lr.decision_function(sc.transform(X))


def _rows(sess_arr, wanted):
    w = set(wanted)
    return np.fromiter((s in w for s in sess_arr), bool, len(sess_arr))


class Calibrator:
    def __init__(self, kind, model):
        self.kind, self.model = kind, model

    def __call__(self, logits):
        if self.kind == "platt":
            return self.model.predict_proba(logits.reshape(-1, 1))[:, 1]
        return np.clip(self.model.predict(logits), 1e-4, 1 - 1e-4)

    def to_json(self):
        if self.kind == "platt":
            return {"kind": "platt", "a": float(self.model.coef_[0, 0]), "b": float(self.model.intercept_[0])}
        return {"kind": "isotonic", "x": self.model.X_thresholds_.tolist(), "y": self.model.y_thresholds_.tolist()}


def fit_calibrator(oof_logit, y, sess):
    platt = LogisticRegression(C=1e6, max_iter=500).fit(oof_logit.reshape(-1, 1), y)
    if len(y) < 20000:
        return Calibrator("platt", platt)
    # validação cruzada em duas metades de sessões: isotônica só se reduzir o ECE
    us = np.array(sorted(set(sess)))
    half = set(us[: len(us) // 2])
    m = np.fromiter((s in half for s in sess), bool, len(sess))
    e_p, e_i = 0.0, 0.0
    for a, b in ((m, ~m), (~m, m)):
        pl = LogisticRegression(C=1e6, max_iter=500).fit(oof_logit[a].reshape(-1, 1), y[a])
        iso = IsotonicRegression(out_of_bounds="clip").fit(oof_logit[a], y[a])
        e_p += ece(pl.predict_proba(oof_logit[b].reshape(-1, 1))[:, 1], y[b])
        e_i += ece(np.clip(iso.predict(oof_logit[b]), 1e-4, 1 - 1e-4), y[b])
    if e_i < e_p:
        return Calibrator("isotonic", IsotonicRegression(out_of_bounds="clip").fit(oof_logit, y))
    return Calibrator("platt", platt)


def thresholds_from_oof(p, y, n_min=200):
    """SPEC §5.4 (aproximação: usa p calibrado OOF em vez de p_lo)."""
    up = down = None
    for u in np.round(np.arange(0.50, 0.71, 0.01), 2):
        m = p > u
        if m.sum() >= n_min and y[m].mean() >= u:
            up = float(u)
            break
    for d in np.round(np.arange(0.50, 0.29, -0.01), 2):
        m = p < d
        if m.sum() >= n_min and (1 - y[m]).mean() >= 1 - d:
            down = float(d)
            break
    return up, down


def train_block(Xtr, ytr, str_, cfg, rng):
    """Seleciona C (Brier no CV purgado), calibra no OOF e treina o ensemble."""
    tr_sessions = sorted(set(str_))
    folds = purged_kfold(tr_sessions, cfg["inner_k"], cfg["inner_embargo"])
    best = None
    oof_by_c = {}
    for C in cfg["C_grid"]:
        oof = np.full(len(ytr), np.nan)
        for tr_s, va_s in folds:
            a, b = _rows(str_, tr_s), _rows(str_, va_s)
            if a.sum() < 500 or b.sum() == 0:
                continue
            sc, lr = _fit(Xtr[a], ytr[a], C)
            oof[b] = _logit(sc, lr, Xtr[b])
        ok = np.isfinite(oof)
        b_score = brier(1 / (1 + np.exp(-oof[ok])), ytr[ok])
        oof_by_c[C] = oof
        if best is None or b_score < best[1]:
            best = (C, b_score)
    C = best[0]
    oof = oof_by_c[C]
    ok = np.isfinite(oof)
    cal = fit_calibrator(oof[ok], ytr[ok], np.asarray(str_)[ok])
    p_oof = cal(oof[ok])
    thr_up, thr_down = thresholds_from_oof(p_oof, ytr[ok])
    sc, lr = _fit(Xtr, ytr, C)
    ens = []
    groups = session_groups(np.asarray(str_))
    for _ in range(cfg["n_ensemble"]):
        pick = rng.integers(0, len(groups), len(groups))
        idx = np.concatenate([groups[i] for i in pick])
        if len(np.unique(ytr[idx])) < 2:
            continue
        ens.append(_fit(Xtr[idx], ytr[idx], C))
    return {"C": C, "inner_brier": best[1], "cal": cal, "model": (sc, lr), "ens": ens,
            "thr_up": thr_up, "thr_down": thr_down, "base_rate_train": float(ytr.mean()),
            "oof_auc": auc(p_oof, ytr[ok]), "oof_ece": ece(p_oof, ytr[ok])}


def predict(block, X):
    sc, lr = block["model"]
    p = block["cal"](_logit(sc, lr, X))
    if block["ens"]:
        E = np.column_stack([block["cal"](_logit(s, l, X)) for s, l in block["ens"]])
        lo, hi = np.percentile(E, [10, 90], axis=1)
    else:
        lo = hi = p
    return p, lo, hi


def reliability_slope(p, y):
    lg = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    m = LogisticRegression(C=1e6, max_iter=500).fit(lg.reshape(-1, 1), y)
    return float(m.coef_[0, 0]), float(m.intercept_[0])


def metrics_block(p, y, sess, base_train, n_boot, seed):
    groups = session_groups(sess)
    ci = bootstrap_by_session({
        "auc": lambda i: auc(p[i], y[i]),
        "bss": lambda i: brier_skill(p[i], y[i]),
        "bss_train": lambda i: brier_skill(p[i], y[i], base_train[i].mean() if np.ndim(base_train) else base_train),
    }, groups, n_boot, seed)
    slope, icpt = reliability_slope(p, y)
    bt = float(np.mean(base_train)) if np.ndim(base_train) else base_train
    return {"n": int(len(y)), "sessions": int(len(groups)), "base_up": float(y.mean()),
            "auc": auc(p, y), "auc_lo": ci["auc"][0], "auc_hi": ci["auc"][1],
            "brier": brier(p, y), "bss": brier_skill(p, y), "bss_lo": ci["bss"][0], "bss_hi": ci["bss"][1],
            "bss_train_base": float(1 - brier(p, y) / np.mean((base_train - y) ** 2)),
            "bss_train_lo": ci["bss_train"][0], "bss_train_hi": ci["bss_train"][1],
            "ece": ece(p, y), "hit": hit_rate(p, y), "rel_slope": slope, "rel_intercept": icpt,
            "p_std": float(np.std(p)), "p_share_gt55_lt45": float(((p > 0.55) | (p < 0.45)).mean())}


def signal_events(p, close, sess, k, target, thr):
    """Evento = primeiro cruzamento de p acima de thr (compra) ou abaixo de 1−thr (venda)."""
    z = np.where(p > 0.5, (p - 0.5), -(0.5 - p))  # distância com sinal
    ev = detect_events(z, sess, k, thr - 0.5)
    if len(ev) == 0:
        return {"thr": thr, "events": 0}
    last_of = pd.Series(np.arange(len(sess))).groupby(sess).transform("max").to_numpy()
    j = np.minimum(ev + 12, last_of[ev])
    ok = j > ev
    sgn = np.sign(z[ev])
    net = sgn * (close[j] - close[ev]) - COST_PTS[target]
    net, es = net[ok], sess[ev][ok]
    return {"thr": thr, "events": int(len(net)), "per_session": float(len(net) / len(np.unique(sess))),
            "hit_60m": float((net > 0).mean()), "net_60m": float(net.mean()), "t_60m": cluster_t(net, es)}


def run_target(conn, target, cfg, log):
    t0 = time.time()
    p = F.build_panel(conn, target, F.BASKETS[target], cfg["start"], cfg["end"])
    fv = F.fair_value(p, F.FairValueConfig(**cfg["fair_value"]))
    pf = F.fair_value(p, F.FairValueConfig(**cfg["pair"]), pair_only=True)
    X = F.forecast_features(p, fv, pf)
    Y = F.forward_targets(p, horizons=(3, 6, 12))
    ycol = f"y{cfg['horizon_bars'] * 5}"
    allcols = sorted(set(sum((feature_columns(X, s) for s in cfg["feature_sets"]), [])))
    valid = X[allcols].notna().all(axis=1) & Y[ycol].notna() & (Y[ycol] != 0)
    d = X[valid].reset_index(drop=True)
    y = (Y.loc[valid, ycol] > 0).astype(int).to_numpy()
    yclose = Y.loc[valid, "yclose"].to_numpy()
    close = p.df.loc[valid, "close"].to_numpy()
    rT = p.df.loc[valid, "rT"].to_numpy()
    sess = d.sess.to_numpy()
    kk = d.k.to_numpy()
    log(f"{target}: painel {len(p.df)} barras, válidas {len(d)} em {len(set(sess))} pregões ({time.time() - t0:.0f}s)")
    splits = monthly_splits(sess, cfg["first_test_month"], cfg["outer_embargo"])
    out = {"target": target, "rows": int(len(d)), "sessions": int(len(set(sess))),
           "first_session": str(min(sess)), "last_session": str(max(sess)),
           "splits": [{"test": s.test_label, "train_sessions": len(s.train_sessions), "train_first": s.train_sessions[0],
                       "train_last": s.train_sessions[-1], "test_sessions": len(s.test_sessions)} for s in splits],
           "sets": {}}
    preds = {}
    for si, fset in enumerate(cfg["feature_sets"]):
        cols = feature_columns(d, fset)
        Xm = d[cols].to_numpy(float)
        P = np.full(len(d), np.nan); LO = P.copy(); HI = P.copy(); BT = P.copy()
        blocks = []

        def _one(bi, s):
            a = _rows(sess, s.train_sessions)
            rng = np.random.default_rng([cfg["seed"], si, bi])  # determinístico por bloco
            return train_block(Xm[a], y[a], sess[a], cfg, rng)

        trained = Parallel(n_jobs=cfg.get("n_jobs", -1))(delayed(_one)(bi, s) for bi, s in enumerate(splits))
        for s, blk in zip(splits, trained):
            b = _rows(sess, s.test_sessions)
            P[b], LO[b], HI[b] = predict(blk, Xm[b])
            BT[b] = blk["base_rate_train"]
            blocks.append({"test": s.test_label, "C": blk["C"], "cal": blk["cal"].kind, "thr_up": blk["thr_up"],
                           "thr_down": blk["thr_down"], "oof_auc": blk["oof_auc"], "oof_ece": blk["oof_ece"]})
            last_blk, last_cols = blk, cols
        m = np.isfinite(P)
        res = {"features": cols, "blocks": blocks,
               "oos": metrics_block(P[m], y[m], sess[m], BT[m], cfg["n_boot"], cfg["seed"])}
        for lab, sel in (("2025", np.char.startswith(sess.astype(str), "2025")),
                         ("2026", np.char.startswith(sess.astype(str), "2026"))):
            mm = m & sel
            if mm.sum() > 500:
                res[f"oos_{lab}"] = metrics_block(P[mm], y[mm], sess[mm], BT[mm], 300, cfg["seed"])
        yc = yclose[m]
        okc = np.isfinite(yc) & (yc != 0)
        res["close_secondary_auc"] = auc(P[m][okc], (yc[okc] > 0).astype(int))
        res["band_width_median"] = float(np.median(HI[m] - LO[m]))
        res["signals"] = [signal_events(P[m], close[m], sess[m], kk[m], target, thr) for thr in cfg["signal_thresholds"]]
        sc, lr = last_blk["model"]
        res["last_model"] = {"C": last_blk["C"], "coef": dict(zip(last_cols, map(float, lr.coef_[0]))),
                             "intercept": float(lr.intercept_[0]), "scaler_mean": sc.mean_.tolist(),
                             "scaler_scale": sc.scale_.tolist(), "calibrator": last_blk["cal"].to_json(),
                             "thr_up": last_blk["thr_up"], "thr_down": last_blk["thr_down"],
                             "ensemble": [{"coef": l.coef_[0].tolist(), "intercept": float(l.intercept_[0]),
                                           "mean": s.mean_.tolist(), "scale": s.scale_.tolist()} for s, l in last_blk["ens"]],
                             "train_end": splits[-1].train_sessions[-1]}
        out["sets"][fset] = res
        preds[fset] = P
        log(f"  {fset}: AUC {res['oos']['auc']:.3f} [{res['oos']['auc_lo']:.3f}; {res['oos']['auc_hi']:.3f}] "
            f"BSS {res['oos']['bss']:+.4f} ECE {res['oos']['ece']:.3f} ({time.time() - t0:.0f}s)")
    m = np.isfinite(preds["A_base"])
    groups = session_groups(sess[m])
    out["baselines"] = {
        "momentum_auc": auc(rT[m], y[m]), "contrarian_auc": auc(-rT[m], y[m]),
        "base_rate_bss_train": float(1 - brier(np.full(m.sum(), y[m].mean()), y[m]) / np.mean((y[m].mean() - y[m]) ** 2)),
        "prototype_auc_60m": cfg["prototype_auc_60m"][target],
    }
    pa, pb = preds["A_base"][m], preds["B_base_valor_justo"][m]
    yy = y[m]
    ci = bootstrap_by_session({"d_bss": lambda i: brier_skill(pb[i], yy[i]) - brier_skill(pa[i], yy[i]),
                               "d_auc": lambda i: auc(pb[i], yy[i]) - auc(pa[i], yy[i])},
                              groups, cfg["n_boot"], cfg["seed"] + 7)
    out["delta_B_minus_A"] = {"d_bss": brier_skill(pb, yy) - brier_skill(pa, yy), "d_bss_ci": ci["d_bss"],
                              "d_auc": auc(pb, yy) - auc(pa, yy), "d_auc_ci": ci["d_auc"]}
    return out


def decide(res_t: dict, fset: str = "B_base_valor_justo") -> dict:
    """Critérios da fase 18 (SPEC/PHASES): BSS OOS ≥ 0, ECE ≤ 3 pp, AUC ≥ protótipo dentro do IC."""
    o = res_t["sets"][fset]["oos"]
    proto = res_t["baselines"]["prototype_auc_60m"]
    c = {"bss_ge_0": o["bss_train_base"] >= 0, "ece_le_3pp": o["ece"] <= 0.03,
         "auc_vs_prototype": o["auc_hi"] >= proto, "auc_ci_above_05": o["auc_lo"] > 0.5}
    c["status"] = "shadow" if (c["bss_ge_0"] and c["ece_le_3pp"] and c["auc_ci_above_05"]) else "rejected"
    return c


def register(db_path: str, res: dict, cfg: dict, fset: str = "B_base_valor_justo"):
    import sqlite3
    from backend.irai import model_registry as R
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ids = {}
    for t, r in res["targets"].items():
        dec = decide(r, fset)
        slug = t.split("$")[0].lower()
        lm = r["sets"][fset]["last_model"]
        vid = R.register_version(
            conn, slug=slug, kind="forecast", param_map={}, factors=F.BASKETS[t], factor_labels={},
            status="shadow", train_start=r["first_session"], train_end=lm["train_end"],
            config={**{k: v for k, v in cfg.items() if k != "targets"}, "feature_set": fset,
                    "features": r["sets"][fset]["features"], "config_hash": res["config_hash"]},
            metrics={"oos": r["sets"][fset]["oos"], "decision": dec, "delta_B_minus_A": r["delta_B_minus_A"]},
            git_sha=R.code_git_sha(), actor="train_forecast", write_params=False,
            notes=f"walk-forward fase 18 ({fset}); decisão automática: {dec['status']}")
        # artefato completo do modelo vai no config (o artifact da versão guarda fatores; params vazio)
        if dec["status"] == "rejected":
            R.reject(conn, vid, actor="train_forecast", notes="critérios da fase 18 não atendidos")
        ids[t] = (vid, dec["status"])
    conn.commit()
    conn.close()
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="banco com market_bars (aberto em modo somente leitura)")
    ap.add_argument("--out", required=True, help="prefixo dos arquivos de saída")
    ap.add_argument("--register-db", default=None, help="banco onde registrar a versão forecast (use uma cópia)")
    ap.add_argument("--n-ensemble", type=int, default=None)
    ap.add_argument("--n-boot", type=int, default=None)
    a = ap.parse_args()
    cfg = dict(CONFIG)
    if a.n_ensemble is not None:
        cfg["n_ensemble"] = a.n_ensemble
    if a.n_boot is not None:
        cfg["n_boot"] = a.n_boot
    res = {"config": cfg, "config_hash": config_hash(cfg), "targets": {}}
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out + ".config.json", "w", encoding="utf-8", newline="\n") as f:  # pré-registro
        json.dump({"config": cfg, "config_hash": res["config_hash"]}, f, ensure_ascii=False, indent=1)
    conn = connect_ro(a.db)
    for t in cfg["targets"]:
        res["targets"][t] = run_target(conn, t, cfg, print)
        res["targets"][t]["decision"] = decide(res["targets"][t])
    conn.close()
    with open(a.out + ".json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    if a.register_db:
        print("registrado:", register(a.register_db, res, cfg))


if __name__ == "__main__":
    main()
