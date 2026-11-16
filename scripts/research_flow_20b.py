"""
Fase 20b: fluxo (delta acumulado do pregao) como filtro do melhor braco da fase 20 no WIN$N.

Teste UNICO pre-registrado (ver .planning/phases/20b-fluxo-como-contexto/20b-PREREG.md):
braco primario F_T3_C1 = gatilho T3 (rompimento/reteste) em zona de GEX as-of + rastro C1
(valor justo) + filtro de fluxo  side * cdn(t-1) > 0, onde cdn = soma(delta)/soma(|delta|)
acumulados desde a abertura do pregao ate a barra anterior.

Pre-registro: CONFIG congelado com hash ANTES da execucao (--freeze grava
data/eval/fase20b/config_<hash>.json; --run recusa rodar se o hash nao bater).
Somente leitura: banco aberto com mode=ro, CSVs do projeto WDO so lidos. Pesquisa, nada vai ao vivo.

Uso:
    python scripts/research_flow_20b.py --db data/irai_live.db --freeze
    python scripts/research_flow_20b.py --db data/irai_live.db --run
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import research_gex_pa as R  # noqa: E402
from backend.eval.data import connect_ro  # noqa: E402
from backend.eval.pa_triggers import detect_level, detect_session, rolling_levels  # noqa: E402
from backend.eval.trade_sim import simulate_session  # noqa: E402

TARGET = "WIN$N"
BASE = {k: copy.deepcopy(v) for k, v in R.CONFIG.items() if k not in ("arms", "targets", "verdict", "phase", "fdr_q")}
CONFIG = {
    **BASE,
    "phase": "20b-fluxo-como-contexto",
    "base_config_hash": "c985f6b2365e",
    "targets": [TARGET],
    "flow": {
        "definition": "cdn(t) = cumsum(delta)/cumsum(|delta|) desde a abertura do pregao (09:00 BRT) ate a barra t; usado cdn(t-1)",
        "rule": "compra cdn(t-1) > 0; venda cdn(t-1) < 0; cdn indefinido (sem delta) -> sem alerta",
        "delta_source": "market_bars.delta (M5)",
    },
    "primary_arm": "F_T3_C1",
    "base_arm": "C_T3_C1",
    "descriptive_arms": ["F_T2_C1", "F_T3_C0"],
    "family_size": 1,
    "verdict": {
        "GO": "1 IC95 da media liquida > 0; 2 media > 0 nas duas metades com n >= 30 cada; "
              "3 IC95 de (F - base C_T3_C1) > 0; 4 IC95 de (F - P1_T3_C1F) > 0 e media >= p95 do placebo P2; "
              "5 media > 0 com 2x custo e com k 0,25 e 1,0",
        "INCONCLUSIVO": "media > 0 no total e nas duas metades, acima da media do braco base, da media do P1 e da mediana do P2, sem passar em todos os criterios do GO",
        "NO-GO": "demais casos",
    },
}
OUT_DIR = os.path.join(ROOT, "data", "eval", "fase20b")


def frozen_path(h):
    return os.path.join(OUT_DIR, f"config_{h}.json")


def freeze():
    h = R.config_hash(CONFIG)
    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.exists(frozen_path(h)):
        with open(frozen_path(h), "w", encoding="utf-8", newline="\n") as f:
            json.dump({"config_hash": h, "frozen_at_utc": pd.Timestamp.utcnow().isoformat(), "config": CONFIG},
                      f, ensure_ascii=False, indent=1)
    return frozen_path(h)


# ---------------------------------------------------------------- fluxo (causal)

def flow_map(conn, bars: pd.DataFrame) -> dict:
    """{sessao: cdn(t-1) alinhado as barras de `bars` daquela sessao}."""
    d = pd.read_sql_query(
        "SELECT timestamp_utc, delta FROM market_bars WHERE symbol=? AND timeframe='M5' "
        "AND timestamp_utc >= ? AND timestamp_utc < ? ORDER BY timestamp_utc", conn,
        params=(TARGET, bars.timestamp_utc.min(), bars.timestamp_utc.max() + "z"))
    d = d.drop_duplicates("timestamp_utc")
    b = bars[["timestamp_utc", "sess"]].merge(d, on="timestamp_utc", how="left")
    out = {}
    for s, g in b.groupby("sess", sort=False):
        x = g.delta.to_numpy(float)
        x = np.where(np.isfinite(x), x, 0.0)
        cs, ca = np.cumsum(x), np.cumsum(np.abs(x))
        with np.errstate(invalid="ignore", divide="ignore"):
            cdn = np.where(ca > 0, cs / ca, np.nan)
        out[s] = np.r_[np.nan, cdn[:-1]]           # so informacao ate a barra anterior
    return out


def flow_ok(fm: dict, x, sig) -> bool:
    v = fm[x.d][sig["t"]]
    return bool(np.isfinite(v) and sig["side"] * v > 0)


def parse(arm):
    kind, trig, ctx = arm.split("_")
    return trig, ctx, kind == "F"


def run_arms(S, cfg, k_mult, fm, arms, shifts=None):
    res = {a: [] for a in arms}
    cost, tick = cfg["costs_pts"][TARGET], cfg["ticks"][TARGET]
    for i, x in enumerate(S):
        sh = shifts[i] if shifts is not None else 0.0
        levels = R.session_levels(x, cfg, TARGET, k_mult, "N1", sh)
        sigs = detect_session(x.o, x.h, x.l, x.c, levels, x.hw, x.atr, cfg["triggers"])
        for a in arms:
            trig, ctx, fl = parse(a)
            ss = [s for s in sigs if s["trigger"] == trig and R.ctx_ok(x, s, ctx) and (not fl or flow_ok(fm, x, s))]
            tr, _ = simulate_session(ss, x.o, x.h, x.l, x.c, x.k, x.atr, levels, cost, tick, cfg["sim"])
            for t_ in tr:
                t_["sess"] = x.d
            res[a] += tr
    return res


def run_p1(S, cfg, k_mult, fm):
    """Controle P1: mesmo gatilho T3 + C1 + fluxo em minimos/maximos de 12 barras FORA das zonas de GEX."""
    out = []
    cost, tick = cfg["costs_pts"][TARGET], cfg["ticks"][TARGET]
    for x in S:
        levels = R.session_levels(x, cfg, TARGET, k_mult)
        lo, hi = rolling_levels(x.h, x.l, cfg["p1"]["lookback"])
        sigs = detect_level(x.o, x.h, x.l, x.c, lo, x.hw, x.atr, roles=("sup",), p=cfg["triggers"]) + \
            detect_level(x.o, x.h, x.l, x.c, hi, x.hw, x.atr, roles=("res",), p=cfg["triggers"])
        if levels:
            lv = np.array(levels)
            sigs = [s for s in sigs if not np.any((x.l[s["t"]] <= lv + x.hw[s["t"]]) & (x.h[s["t"]] >= lv - x.hw[s["t"]]))]
        ss = sorted([s for s in sigs if s["trigger"] == "T3" and R.ctx_ok(x, s, "C1") and flow_ok(fm, x, s)],
                    key=lambda s: s["t"])
        tr, _ = simulate_session(ss, x.o, x.h, x.l, x.c, x.k, x.atr, levels, cost, tick, cfg["sim"])
        for t_ in tr:
            t_["sess"] = x.d
        out += tr
    return out


def classify(s, base, ctrl, cfg):
    if s["n"] == 0:
        return "NO-GO", {}
    c = {
        "1_ci_total": s["ci"][0] is not None and s["ci"][0] > 0 and s["mean_net"] > 0,
        "2_metades": (s["design"]["mean_net"] or -1) > 0 and (s["validation"]["mean_net"] or -1) > 0
        and s["design"]["n"] >= cfg["min_trades_per_half"] and s["validation"]["n"] >= cfg["min_trades_per_half"],
        "3_incremento_fluxo": ctrl["vs_base_ci"][0] is not None and ctrl["vs_base_ci"][0] > 0,
        "4_controles": ctrl["p1_diff_ci"][0] is not None and ctrl["p1_diff_ci"][0] > 0
        and ctrl["p2_pct"] is not None and ctrl["p2_pct"] >= 0.95,
        "5_robustez": s["mean_net_2xcost"] > 0 and all(v is not None and v > 0 for v in ctrl["k_sens"].values()),
    }
    if all(c.values()):
        return "GO", c
    soft = s["mean_net"] > 0 and (s["design"]["mean_net"] or -1) > 0 and (s["validation"]["mean_net"] or -1) > 0 \
        and s["mean_net"] > (base.get("mean_net") or -1e9) \
        and ctrl["p1_mean"] is not None and s["mean_net"] > ctrl["p1_mean"] \
        and ctrl["p2_median"] is not None and s["mean_net"] > ctrl["p2_median"]
    return ("INCONCLUSIVO" if soft else "NO-GO"), c


def run(db, out_json):
    h = R.config_hash(CONFIG)
    if not os.path.exists(frozen_path(h)):
        raise SystemExit(f"CONFIG {h} nao foi congelado; rode --freeze antes.")
    cfg = CONFIG
    t0 = time.time()
    conn = connect_ro(db)
    hist, meta = R.gex_history(conn, TARGET, cfg)
    bars = R.load_bars(conn, TARGET, cfg["panel_start"], cfg["end"])
    fm_all = flow_map(conn, bars)
    ctx = R.context_frame(conn, TARGET, cfg)
    S, excl = R.prepare(bars, ctx, hist, TARGET, cfg, cfg["k"])
    for x in S:
        assert len(fm_all[x.d]) == len(x.o), f"fluxo desalinhado em {x.d}"
    sessions = [x.d for x in S]
    boot = R.Boot(sessions, cfg["n_boot"], cfg["seed"])
    arms_all = [cfg["primary_arm"], cfg["base_arm"]] + cfg["descriptive_arms"]
    arms = run_arms(S, cfg, cfg["k"], fm_all, arms_all)
    p1 = run_p1(S, cfg, cfg["k"], fm_all)
    ksens = {}
    for km in cfg["k_sens"]:
        Sk, _ = R.prepare(bars, ctx, hist, TARGET, cfg, km)
        r = run_arms(Sk, cfg, km, fm_all, [cfg["primary_arm"]])
        ksens[str(km)] = R.summarize(r[cfg["primary_arm"]], boot, cfg, TARGET)
    rng = np.random.default_rng(cfg["p2"]["seed"])
    med_sp = float(np.nanmedian([x.spacing for x in S if x.spacing]))
    p2 = []
    for _ in range(cfg["p2"]["draws"]):
        u = rng.uniform(*cfg["p2"]["shift_frac"], size=len(S))
        sg = rng.choice([-1.0, 1.0], size=len(S)) if cfg["p2"]["random_sign"] else np.ones(len(S))
        shifts = [float(sg[i] * u[i] * (x.spacing or med_sp)) for i, x in enumerate(S)]
        v = run_arms(S, cfg, cfg["k"], fm_all, [cfg["primary_arm"]], shifts=shifts)[cfg["primary_arm"]]
        p2.append(float(np.mean([t["net"] for t in v])) if v else np.nan)
    summ = {a: R.summarize(v, boot, cfg, TARGET) for a, v in arms.items()}
    p1s = R.summarize(p1, boot, cfg, TARGET)
    pa, ba = cfg["primary_arm"], cfg["base_arm"]
    m = summ[pa].get("mean_net")
    d2 = np.array(p2, float); d2 = d2[np.isfinite(d2)]
    dci, pgt = boot.diff_ci(arms[pa], p1)
    vb, vbp = boot.diff_ci(arms[pa], arms[ba])
    ctrl = {"p1_mean": p1s.get("mean_net"), "p1_n": p1s["n"], "p1_diff_ci": dci, "p1_diff_prob_pos": pgt,
            "vs_base_ci": vb, "vs_base_prob_pos": vbp,
            "p2_draws": int(len(d2)), "p2_median": float(np.median(d2)) if len(d2) else None,
            "p2_p95": float(np.percentile(d2, 95)) if len(d2) else None,
            "p2_pct": float(np.mean(d2 < m)) if (len(d2) and m is not None) else None,
            "k_sens": {k: v.get("mean_net") for k, v in ksens.items()}}
    status, crit = classify(summ[pa], summ[ba], ctrl, cfg)
    cov = np.concatenate([fm_all[s] for s in sessions])
    res = {"config_hash": h, "config": cfg, "target": TARGET, "sessions": len(S),
           "first": sessions[0], "last": sessions[-1],
           "sessions_design": sum(1 for s in sessions if s <= cfg["design_end"]),
           "sessions_validation": sum(1 for s in sessions if s > cfg["design_end"]),
           "excluded": excl, "gex_meta": {k: v for k, v in meta.items() if k not in ("csv", "db")},
           "flow_coverage": float(np.mean(np.isfinite(cov))),
           "arms": summ, "controls": ctrl, "p1": p1s, "k_sens": ksens,
           "monthly": {a: R.monthly(v) for a, v in arms.items()},
           "status": status, "criteria": crit, "elapsed_s": round(time.time() - t0, 1),
           "code_sha": {f: R.sha_file(os.path.join(ROOT, f)) for f in (
               "scripts/research_flow_20b.py", "scripts/research_gex_pa.py", "backend/eval/pa_triggers.py",
               "backend/eval/trade_sim.py", "backend/irai/gex_asof.py")}}
    conn.close()
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    h = R.config_hash(CONFIG)
    if a.freeze:
        print("config congelado:", freeze())
    if a.run:
        out = os.path.join(OUT_DIR, f"flow20b_{h}.json")
        r = run(a.db, out)
        s = r["arms"][CONFIG["primary_arm"]]
        print(f"{TARGET}: {r['sessions']} sessoes; {CONFIG['primary_arm']} n={s['n']} media={s.get('mean_net')} IC={s.get('ci')}; veredito {r['status']}")
        print("salvo:", out)


if __name__ == "__main__":
    main()
