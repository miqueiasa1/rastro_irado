"""
Pesquisa do valor justo da cesta (fase 18): o descolamento do alvo frente à cesta prevê retorno?

Pré-registro: a grade de variantes, limiares, horizontes, custos e o split desenho/validação são
fixados em `CONFIG` abaixo e gravados (com hash) no relatório. Todas as configurações tentadas
aparecem no relatório (REQ-N01, SPEC §6.4). Controle de teste múltiplo: Benjamini–Hochberg e
Bonferroni sobre todos os testes de cada parte (desenho e validação).

Uso (somente leitura; nunca escreve no banco):
    python scripts/research_fair_value.py --db data/irai_live.db --out data/reports/fair_value_20261110
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.eval.data import connect_ro
from backend.eval.events import bar_predictive, bh_adjust, event_table
from backend.eval.metrics import auc
from backend.irai import features as F

CONFIG = {
    "start": "2024-12-01",
    "end": "2026-11-10",
    "design_end": "2025-12-31",       # desenho: até 31/12/2025; validação: 2026
    "targets": ["WIN$N", "WDO$N"],
    "variants": {
        "cesta_w60":         {"kind": "basket", "window": 60, "step": 6, "z": "perfil"},
        "cesta_w20":         {"kind": "basket", "window": 20, "step": 6, "z": "perfil"},
        "cesta_w60_5min":    {"kind": "basket", "window": 60, "step": 1, "z": "perfil"},
        "cesta_w60_movel40": {"kind": "basket", "window": 60, "step": 6, "z": "movel40"},
        "par_ols20":         {"kind": "pair", "window": 20, "step": 6, "z": "perfil"},
        "par_ols60":         {"kind": "pair", "window": 60, "step": 6, "z": "perfil"},
        "par_ols20_z_atual": {"kind": "pair", "window": 20, "step": 6, "z": "atual"},
    },
    "thresholds": [1.5, 2.0, 2.5],
    "directions": [-1, 1],             # −1 = contrarian (hipótese principal), +1 = segue
    "horizons_bars": [3, 6, 12],       # 15, 30, 60 min (+ fechamento)
    "costs_pts": {"WIN$N": 10.0, "WDO$N": 1.0},
    "entry_window": "09:30–17:00 BRT",
    "n_boot": 300,
    "seed": 0,
}


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]


def build(conn, target: str, cfg: dict):
    p = F.build_panel(conn, target, F.BASKETS[target], cfg["start"], cfg["end"])
    ys = F.forward_targets(p, horizons=(3, 6, 12))
    base = pd.concat([p.df[["sess", "k", "close", "rT"]].copy(), ys], axis=1)
    zs = {}
    for name, v in cfg["variants"].items():
        fcfg = F.FairValueConfig(window_sessions=v["window"], step_bars=v["step"])
        fv = F.fair_value(p, fcfg, pair_only=(v["kind"] == "pair"))
        if v["z"] == "perfil":
            z = fv.z.to_numpy()
        elif v["z"] == "movel40":
            z = F.rolling_z(fv.gap.to_numpy(), fv.sess.to_numpy(), 40)
        else:
            z = F.legacy_like_z(fv.gap.to_numpy() * 100, fv.sess.to_numpy(), floor=0.01)
        zs[name] = (z, fv.gap.to_numpy())
    return p, base, zs


def _logit_partial(dd: pd.DataFrame) -> list | None:
    """Coeficientes padronizados de y60 ~ retorno do dia + z: o z traz algo além do contrarian?"""
    ok = dd.y60.notna() & (dd.y60 != 0)
    if ok.sum() <= 200:
        return None
    from sklearn.linear_model import LogisticRegression
    X = np.column_stack([dd.loc[ok, "rT"].to_numpy() / dd.rT.std(), dd.loc[ok, "zz"].to_numpy()])
    yy = (dd.loc[ok, "y60"] > 0).astype(int).to_numpy()
    lr = LogisticRegression(C=1.0).fit(X, yy)
    return [float(c) for c in lr.coef_[0]]


def run(db: str, out: str, cfg: dict = CONFIG) -> dict:
    conn = connect_ro(db)
    res = {"config": cfg, "config_hash": config_hash(cfg), "targets": {}}
    rows = []
    parts = lambda d: (("desenho", d.sess <= cfg["design_end"]), ("validacao", d.sess > cfg["design_end"]))
    for target in cfg["targets"]:
        p, base, zs = build(conn, target, cfg)
        tr = {"sessions": int(base.sess.nunique()), "first": base.sess.min(), "last": base.sess.max(),
              "variants": {}, "baselines": {}}
        for part, sel in parts(base):
            d = base[sel]
            bl = {"sessions": int(d.sess.nunique())}
            for yc in ("y15", "y30", "y60"):
                ok = d[yc].notna() & (d[yc] != 0)
                yy = (d.loc[ok, yc] > 0).astype(int).to_numpy()
                r = d.loc[ok, "rT"].to_numpy()
                bl[yc] = {"momentum": auc(r, yy), "contrarian": auc(-r, yy)}
            tr["baselines"][part] = bl
        for name, (z, gap) in zs.items():
            d = base.copy()
            d["zz"] = z
            d["gap"] = gap
            vr = {}
            for part, sel in parts(d):
                dd = d[sel & d.zz.notna()]
                pr = {"bars": int(len(dd)), "sessions": int(dd.sess.nunique()),
                      "coverage_abs_gt2": float((dd.zz.abs() > 2).mean()) if len(dd) else None,
                      "z_std": float(dd.zz.std()) if len(dd) else None, **bar_predictive(dd, "zz"),
                      "logit_coef_rT_z": _logit_partial(dd)}
                evs = []
                for thr in cfg["thresholds"]:
                    for dr in cfg["directions"]:
                        e = event_table(dd, "zz", thr, target, horizons=tuple(cfg["horizons_bars"]),
                                        cost=cfg["costs_pts"][target], direction=dr,
                                        n_boot=cfg["n_boot"], seed=cfg["seed"])
                        e["variant"] = name
                        evs.append(e)
                        for lab in ("15m", "30m", "60m", "close"):
                            if f"p_{lab}" in e:
                                rows.append({"target": target, "part": part, "variant": name, "thr": thr,
                                             "direction": e["direction"], "h": lab, "n": e[f"n_{lab}"],
                                             "gross": e[f"gross_{lab}"], "net": e[f"net_{lab}"],
                                             "t": e[f"t_{lab}"], "p": e[f"p_{lab}"], "hit": e[f"hit_{lab}"]})
                pr["events"] = evs
                vr[part] = pr
            tr["variants"][name] = vr
        res["targets"][target] = tr
    conn.close()
    tab = pd.DataFrame(rows)
    for part in ("desenho", "validacao"):
        m = tab.part == part
        tab.loc[m, "q_bh"] = bh_adjust(tab.loc[m, "p"].tolist())
        tab.loc[m, "p_bonf"] = np.minimum(1.0, tab.loc[m, "p"] * m.sum())
    res["tests"] = tab.to_dict(orient="records")
    res["n_tests_per_part"] = int((tab.part == "desenho").sum())
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out + ".json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True, help="prefixo do arquivo de saída (sem extensão)")
    a = ap.parse_args()
    r = run(a.db, a.out)
    print(json.dumps({"config_hash": r["config_hash"], "n_tests_per_part": r["n_tests_per_part"]}))


if __name__ == "__main__":
    main()
