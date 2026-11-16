"""
Pesquisa da fase 20: regiões de GEX + gatilho de price action + rastro como filtro de direção.

Pré-registro: `CONFIG` abaixo é congelado e gravado com hash ANTES da execução
(`--freeze` grava `data/eval/fase20/config_<hash>.json`; a execução recusa rodar se o hash do
CONFIG não bater com um arquivo congelado). Somente leitura: o banco é aberto com `mode=ro` e os
CSVs do projeto WDO são só lidos.

Uso:
    python scripts/research_gex_pa.py --db <irai_live.db> --freeze
    python scripts/research_gex_pa.py --db <irai_live.db> --run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.eval.data import broker_wall_to_brt, connect_ro  # noqa: E402
from backend.eval.events import bh_adjust, cluster_t, p_two_sided  # noqa: E402
from backend.eval.pa_triggers import DEFAULT as TRIG_DEFAULT  # noqa: E402
from backend.eval.pa_triggers import atr_prev, detect_level, detect_session, rolling_levels, true_range  # noqa: E402
from backend.eval.trade_sim import SIM_DEFAULT, simulate_session  # noqa: E402
from backend.irai import features as F  # noqa: E402
from backend.irai import gex_asof as G  # noqa: E402

GEX_DIR = os.path.normpath(os.path.join(ROOT, "..", "wdo win pair trading", "mt5", "Files"))

CONFIG = {
    "phase": "20-gex-regioes-price-action",
    "panel_start": "2025-09-01", "start": "2026-01-02", "end": "2026-11-10",
    "design_end": "2026-06-30",
    "targets": ["WIN$N", "WDO$N"],
    "gex_csv": {"WIN$N": "jumba_gex_win_history.csv", "WDO$N": "jumba_gex_wdo_history.csv"},
    "gex_fallback": "gex_levels: primeiro run com run_name < 09:00; senão exclui",
    "exclude_sessions": ["2026-05-23"],
    "exclude_open_gap_abs": 0.02,
    "levels_primary": {"wall_min_width": 2, "gamma": ["min_gamma", "max_gamma", "gamma_flip"]},
    "k": 0.5, "k_sens": [0.25, 1.0], "floor_cost_mult": 2.0,
    "costs_pts": {"WIN$N": 10.0, "WDO$N": 1.0}, "cost_sens_mult": 2.0,
    "ticks": {"WIN$N": 5.0, "WDO$N": 0.5},
    "atr": {"n": 14, "min_bars": 5, "fallback_sessions": 20},
    "triggers": TRIG_DEFAULT, "sim": {**SIM_DEFAULT, "risk_atr": list(SIM_DEFAULT["risk_atr"]),
                                      "entry_k": list(SIM_DEFAULT["entry_k"])},
    "context": {"C1": {"WIN$N": "cesta_w60 z (perfil)", "WDO$N": "cesta_w60_movel40 z", "rule": "compra z(t-1)<=0; venda z(t-1)>=0"},
                "C2": {"rule": "compra fv(t-1)-fv(t-13)>0; venda <0 (fv da cesta_w60; antes da abertura fv=0)"},
                "unavailable": "z/fv NaN ou algum fator stale em t-1 → sem alerta nos braços C"},
    "arms": ["A_T0_C0", "B_T1_C0", "B_T2_C0", "B_T3_C0", "C_T1_C1", "C_T2_C1", "C_T3_C1",
             "Cp_T1_C2", "Cp_T2_C2", "Cp_T3_C2"],
    "p1": {"lookback": 12, "exclude_gex_zones": True, "triggers": ["T0", "T1", "T2", "T3"]},
    "p2": {"draws": 200, "shift_frac": [0.25, 0.75], "random_sign": True, "seed": 20},
    "n_boot": 2000, "seed": 0, "fdr_q": 0.05, "min_trades_per_half": 30,
    "verdict": {"GO": "criterios 1-5 do 20-PLAN-01 §6",
                "INCONCLUSIVO": "media>0 no total e nas duas metades e media acima de P1 e da mediana de P2, sem passar em todos os criterios",
                "NO-GO": "demais casos", "asset": "melhor status entre os 10 bracos"},
}
TRIG_ORDER = ("T0", "T1", "T2", "T3")


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]


def sha_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


# ── dados ──────────────────────────────────────────────────────────────────

def load_bars(conn, target: str, start: str, end: str) -> pd.DataFrame:
    b = pd.read_sql_query(
        "SELECT timestamp_utc, open, high, low, close FROM market_bars WHERE symbol=? AND timeframe='M5' "
        "AND timestamp_utc >= ? AND timestamp_utc < ? ORDER BY timestamp_utc", conn,
        params=(target, (pd.Timestamp(start) - pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
                (pd.Timestamp(end) + pd.Timedelta(days=2)).strftime("%Y-%m-%d")))
    b["ts_brt"] = broker_wall_to_brt(b.timestamp_utc)
    b = b.dropna(subset=["ts_brt"]).drop_duplicates("ts_brt").sort_values("ts_brt").reset_index(drop=True)
    m = b.ts_brt.dt.hour * 60 + b.ts_brt.dt.minute
    b = b[(m >= F.SESSION_OPEN_MIN) & (m < F.SESSION_END_MIN)].copy()
    b["sess"] = b.ts_brt.dt.strftime("%Y-%m-%d")
    b = b[(b.sess >= start) & (b.sess <= end)]
    b = b[b.groupby("sess").close.transform("size") >= 60].copy()
    b["k"] = ((b.ts_brt.dt.hour * 60 + b.ts_brt.dt.minute - F.SESSION_OPEN_MIN) // F.BAR_MIN).astype(int)
    return b.reset_index(drop=True)


def context_frame(conn, target: str, cfg: dict) -> pd.DataFrame:
    p = F.build_panel(conn, target, F.BASKETS[target], cfg["panel_start"], cfg["end"])
    fv = F.fair_value(p, F.FairValueConfig(window_sessions=60, step_bars=6))
    df = p.df[["ts_brt", "sess", "k"]].copy()
    df["fv"] = fv.fv.to_numpy()
    df["z"] = fv.z.to_numpy() if target == "WIN$N" else F.rolling_z(fv.gap.to_numpy(), fv.sess.to_numpy(), 40)
    st = [c for c in p.df.columns if c.startswith("stale_")]
    df["stale"] = (p.df[st].sum(axis=1) > 0).astype(int).to_numpy() if st else 0
    g = df.groupby("sess")
    df["z_prev"] = g.z.shift(1)
    df["stale_prev"] = g.stale.shift(1)
    fvp = g.fv.shift(1)
    fv13 = g.fv.shift(13)
    fv13 = fv13.where(g.cumcount() >= 13, 0.0)       # antes da abertura: fv = 0
    df["dfv_prev"] = fvp - fv13
    return df[["ts_brt", "z_prev", "dfv_prev", "stale_prev"]]


def gex_history(conn, target: str, cfg: dict) -> tuple[dict, dict]:
    path = os.path.join(GEX_DIR, cfg["gex_csv"][target])
    csvl = G.load_gex_csv(path)
    dbl = G.load_gex_db_preopen(conn, target)
    hist = G.build_gex_history(csvl, dbl, exclude=tuple(cfg["exclude_sessions"]))
    return hist, {"csv_path": path, "csv_sha": sha_file(path), "csv_sessions": len(csvl),
                  "csv_first": min(csvl), "csv_last": max(csvl), "db_preopen_sessions": len(dbl), "csv": csvl, "db": dbl}


# ── por sessão ─────────────────────────────────────────────────────────────

class Sess:
    __slots__ = ("d", "o", "h", "l", "c", "k", "atr", "hw", "fallback", "levels_raw", "z", "dfv", "stale", "spacing", "gex_src")


def prepare(b: pd.DataFrame, ctx: pd.DataFrame, hist: dict, target: str, cfg: dict, k_mult: float):
    b = b.merge(ctx, on="ts_brt", how="left")
    sessions = sorted(b.sess.unique())
    floor = cfg["floor_cost_mult"] * cfg["costs_pts"][target]
    trs = {}
    out, excl = [], {"no_gex": [], "gap": []}
    last_close = None
    for s in sessions:
        bb = b[b.sess == s]
        o, h, l, c = (bb[x].to_numpy(float) for x in ("open", "high", "low", "close"))
        tr = true_range(o, h, l, c)
        prev = [x for x in sessions if x < s][-cfg["atr"]["fallback_sessions"]:]
        fb = float(np.median(np.concatenate([trs[x] for x in prev]))) if prev else np.nan
        trs[s] = tr
        gap = (o[0] / last_close - 1) if last_close else 0.0
        last_close = c[-1]
        if s < cfg["start"]:
            continue
        if s not in hist:
            excl["no_gex"].append(s); continue
        if abs(gap) > cfg["exclude_open_gap_abs"]:
            excl["gap"].append(s); continue
        x = Sess()
        x.d, x.o, x.h, x.l, x.c, x.k = s, o, h, l, c, bb.k.to_numpy(int)
        x.atr = atr_prev(tr, cfg["atr"]["n"], cfg["atr"]["min_bars"], fb)
        x.fallback = fb
        x.hw = np.maximum(k_mult * x.atr, floor)
        x.levels_raw = hist[s]["levels"]
        x.gex_src = hist[s]["source"]
        x.spacing = G.grid_spacing(x.levels_raw)
        x.z, x.dfv, x.stale = bb.z_prev.to_numpy(float), bb.dfv_prev.to_numpy(float), bb.stale_prev.to_numpy(float)
        out.append(x)
    return out, excl


def session_levels(x: Sess, cfg, target, k_mult, kind="N1", shift=0.0):
    floor = cfg["floor_cost_mult"] * cfg["costs_pts"][target]
    h_ref = max(k_mult * x.fallback, floor)
    lv = G.primary_levels(x.levels_raw, cfg["levels_primary"]["wall_min_width"]) if kind == "N1" else G.all_walls(x.levels_raw)
    if shift:
        lv = [{**y, "price": y["price"] + shift} for y in lv]
    m = G.merge_levels(lv, h_ref, x.o[0])
    return [y["price"] for y in m]


def ctx_ok(x: Sess, sig: dict, rule: str) -> bool:
    t, sd = sig["t"], sig["side"]
    if rule == "C0":
        return True
    if x.stale[t] != 0 or not np.isfinite(x.stale[t]):
        return False
    if rule == "C1":
        z = x.z[t]
        return bool(np.isfinite(z) and ((sd == 1 and z <= 0) or (sd == -1 and z >= 0)))
    v = x.dfv[t]
    return bool(np.isfinite(v) and sd * v > 0)


def arm_parts(arm: str):
    _, trig, ctx = arm.split("_")
    return trig, ctx


def run_arms(sess_list, cfg, target, k_mult, kind="N1", shifts=None, arms=None):
    """{arm: [trades]} para um conjunto de sessões."""
    arms = arms or cfg["arms"]
    res = {a: [] for a in arms}
    cost, tick = cfg["costs_pts"][target], cfg["ticks"][target]
    for i, x in enumerate(sess_list):
        sh = shifts[i] if shifts is not None else 0.0
        levels = session_levels(x, cfg, target, k_mult, kind, sh)
        sigs = detect_session(x.o, x.h, x.l, x.c, levels, x.hw, x.atr, cfg["triggers"])
        for a in arms:
            trig, ctx = arm_parts(a)
            ss = [s for s in sigs if s["trigger"] == trig and ctx_ok(x, s, ctx)]
            tr, _ = simulate_session(ss, x.o, x.h, x.l, x.c, x.k, x.atr, levels, cost, tick, cfg["sim"])
            for t_ in tr:
                t_["sess"] = x.d
            res[a] += tr
    return res


def run_p1(sess_list, cfg, target, k_mult):
    """Controle P1: o mesmo gatilho em mínimos/máximos de 12 barras, FORA das zonas de GEX."""
    out = {}
    cost, tick = cfg["costs_pts"][target], cfg["ticks"][target]
    for ctx in ("C0", "C1", "C2"):
        for trig in cfg["p1"]["triggers"]:
            out[f"P1_{trig}_{ctx}"] = []
    for x in sess_list:
        levels = session_levels(x, cfg, target, k_mult)
        lo, hi = rolling_levels(x.h, x.l, cfg["p1"]["lookback"])
        sigs = detect_level(x.o, x.h, x.l, x.c, lo, x.hw, x.atr, roles=("sup",), p=cfg["triggers"]) + \
            detect_level(x.o, x.h, x.l, x.c, hi, x.hw, x.atr, roles=("res",), p=cfg["triggers"])
        if cfg["p1"]["exclude_gex_zones"] and levels:
            lv = np.array(levels)
            sigs = [s for s in sigs if not np.any((x.l[s["t"]] <= lv + x.hw[s["t"]]) & (x.h[s["t"]] >= lv - x.hw[s["t"]]))]
        for ctx in ("C0", "C1", "C2"):
            for trig in cfg["p1"]["triggers"]:
                ss = sorted([s for s in sigs if s["trigger"] == trig and ctx_ok(x, s, ctx)], key=lambda s: s["t"])
                tr, _ = simulate_session(ss, x.o, x.h, x.l, x.c, x.k, x.atr, levels, cost, tick, cfg["sim"])
                for t_ in tr:
                    t_["sess"] = x.d
                out[f"P1_{trig}_{ctx}"] += tr
    return out


# ── estatística ────────────────────────────────────────────────────────────

class Boot:
    def __init__(self, sessions, n_boot, seed):
        self.sessions = list(sessions)
        self.pos = {s: i for i, s in enumerate(self.sessions)}
        rng = np.random.default_rng(seed)
        self.idx = rng.integers(0, len(self.sessions), size=(n_boot, len(self.sessions)))

    def sums(self, trades, field="net", mult_cost=0.0, cost=0.0):
        S = np.zeros(len(self.sessions)); N = np.zeros(len(self.sessions))
        for t in trades:
            j = self.pos[t["sess"]]
            S[j] += t[field] - mult_cost * cost
            N[j] += 1
        return S, N

    def mean_dist(self, S, N):
        ss = S[self.idx].sum(axis=1); nn = N[self.idx].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            return ss / nn

    def ci(self, trades, field="net"):
        S, N = self.sums(trades, field)
        if N.sum() < 3:
            return [None, None]
        m = self.mean_dist(S, N)
        m = m[np.isfinite(m)]
        return [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]

    def diff_ci(self, a, b):
        Sa, Na = self.sums(a); Sb, Nb = self.sums(b)
        if Na.sum() < 3 or Nb.sum() < 3:
            return [None, None], None
        d = self.mean_dist(Sa, Na) - self.mean_dist(Sb, Nb)
        d = d[np.isfinite(d)]
        return [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))], float(np.mean(d > 0))


def max_dd(x):
    if len(x) == 0:
        return 0.0
    eq = np.cumsum(x)
    return float((np.maximum.accumulate(np.r_[0.0, eq])[1:] - eq).max())


def summarize(trades, boot: Boot, cfg, target):
    cost = cfg["costs_pts"][target]
    tr = sorted(trades, key=lambda t: (t["sess"], t["entry_i"]))
    net = np.array([t["net"] for t in tr], float)
    out = {"n": int(len(tr)), "sessions": int(len({t["sess"] for t in tr}))}
    if len(tr) == 0:
        return out
    sess = np.array([t["sess"] for t in tr])
    gross = np.array([t["gross"] for t in tr])
    tt = cluster_t(net, sess) if len(tr) >= 3 else float("nan")
    pos, neg = net[net > 0].sum(), -net[net < 0].sum()
    des = np.array([s <= cfg["design_end"] for s in sess])
    out.update({
        "mean_net": float(net.mean()), "median_net": float(np.median(net)), "mean_gross": float(gross.mean()),
        "hit": float((net > 0).mean()), "pf": float(pos / neg) if neg > 0 else None,
        "mean_R": float(np.mean([t["net_R"] for t in tr])), "max_dd": max_dd(net), "total_net": float(net.sum()),
        "t": tt, "p": p_two_sided(tt), "ci": boot.ci(tr),
        "mean_net_2xcost": float((net - cost * (cfg["cost_sens_mult"] - 1)).mean()),
        "fixed60_mean": float(np.mean([t["fixed60_net"] for t in tr])),
        "pct_stop": float(np.mean([t["reason"] == "stop" for t in tr])),
        "pct_target": float(np.mean([t["reason"] == "target" for t in tr])),
        "pct_time": float(np.mean([t["reason"] in ("time", "eod") for t in tr])),
        "pct_ambiguous": float(np.mean([t["ambiguous"] for t in tr])),
        "pct_long": float(np.mean([t["side"] == 1 for t in tr])),
        "design": {"n": int(des.sum()), "mean_net": float(net[des].mean()) if des.any() else None},
        "validation": {"n": int((~des).sum()), "mean_net": float(net[~des].mean()) if (~des).any() else None},
    })
    return out


def equity(trades):
    tr = sorted(trades, key=lambda t: (t["sess"], t["entry_i"]))
    eq = np.cumsum([t["net"] for t in tr]) if tr else []
    return [{"sess": t["sess"], "net": round(t["net"], 2), "eq": round(float(e), 2)} for t, e in zip(tr, eq)]


def monthly(trades):
    df = pd.DataFrame([{"m": t["sess"][:7], "net": t["net"]} for t in trades])
    if df.empty:
        return {}
    g = df.groupby("m").net
    return {m: {"n": int(n), "mean": float(v)} for m, n, v in zip(g.size().index, g.size().values, g.mean().values)}


def classify(s, ctrl, cfg):
    """Status do braço pelos critérios pré-registrados."""
    if s["n"] == 0:
        return "NO-GO", {}
    c = {
        "1_ci_total": s["ci"][0] is not None and s["ci"][0] > 0 and s["mean_net"] > 0,
        "2_metades": (s["design"]["mean_net"] or -1) > 0 and (s["validation"]["mean_net"] or -1) > 0
        and s["design"]["n"] >= cfg["min_trades_per_half"] and s["validation"]["n"] >= cfg["min_trades_per_half"],
        "3_bh": s.get("q_bh") is not None and s["q_bh"] < cfg["fdr_q"],
        "4_controles": ctrl["p1_diff_ci"][0] is not None and ctrl["p1_diff_ci"][0] > 0 and ctrl["p2_pct"] is not None
        and ctrl["p2_pct"] >= 0.95,
        "5_robustez": s["mean_net_2xcost"] > 0 and all(v is not None and v > 0 for v in ctrl["k_sens"].values()),
    }
    if all(c.values()):
        return "GO", c
    soft = s["mean_net"] > 0 and (s["design"]["mean_net"] or -1) > 0 and (s["validation"]["mean_net"] or -1) > 0 \
        and ctrl["p1_mean"] is not None and s["mean_net"] > ctrl["p1_mean"] \
        and ctrl["p2_median"] is not None and s["mean_net"] > ctrl["p2_median"]
    return ("INCONCLUSIVO" if soft else "NO-GO"), c


# ── execução ───────────────────────────────────────────────────────────────

def frozen_path(h):
    return os.path.join(ROOT, "data", "eval", "fase20", f"config_{h}.json")


def freeze():
    h = config_hash(CONFIG)
    os.makedirs(os.path.dirname(frozen_path(h)), exist_ok=True)
    if not os.path.exists(frozen_path(h)):
        with open(frozen_path(h), "w", encoding="utf-8", newline="\n") as f:
            json.dump({"config_hash": h, "frozen_at_utc": pd.Timestamp.utcnow().isoformat(), "config": CONFIG},
                      f, ensure_ascii=False, indent=1)
    return h


def run(db: str, out_json: str):
    h = config_hash(CONFIG)
    if not os.path.exists(frozen_path(h)):
        raise SystemExit(f"CONFIG {h} não foi congelado; rode --freeze antes.")
    cfg = CONFIG
    conn = connect_ro(db)
    res = {"config_hash": h, "config": cfg, "targets": {}, "started_utc": pd.Timestamp.utcnow().isoformat(),
           "code_sha": {f: sha_file(os.path.join(ROOT, f)) for f in ("backend/irai/gex_asof.py", "backend/eval/pa_triggers.py", "backend/eval/trade_sim.py", "scripts/research_gex_pa.py")}}
    family = []
    for target in cfg["targets"]:
        t0 = time.time()
        hist, meta = gex_history(conn, target, cfg)
        bars = load_bars(conn, target, cfg["panel_start"], cfg["end"])
        ctx = context_frame(conn, target, cfg)
        S, excl = prepare(bars, ctx, hist, target, cfg, cfg["k"])
        sessions = [x.d for x in S]
        boot = Boot(sessions, cfg["n_boot"], cfg["seed"])
        arms = run_arms(S, cfg, target, cfg["k"])
        p1 = run_p1(S, cfg, target, cfg["k"])
        # sensibilidade k
        ksens = {}
        for km in cfg["k_sens"]:
            Sk, _ = prepare(bars, ctx, hist, target, cfg, km)
            ksens[str(km)] = {a: summarize(v, boot, cfg, target) for a, v in run_arms(Sk, cfg, target, km).items()}
        n0 = {a: summarize(v, boot, cfg, target) for a, v in run_arms(S, cfg, target, cfg["k"], kind="N0").items()}
        # placebo P2
        rng = np.random.default_rng(cfg["p2"]["seed"])
        med_sp = float(np.nanmedian([x.spacing for x in S if x.spacing]))
        p2 = {a: [] for a in cfg["arms"]}
        for _ in range(cfg["p2"]["draws"]):
            u = rng.uniform(*cfg["p2"]["shift_frac"], size=len(S))
            sg = rng.choice([-1.0, 1.0], size=len(S)) if cfg["p2"]["random_sign"] else np.ones(len(S))
            shifts = [float(sg[i] * u[i] * (x.spacing or med_sp)) for i, x in enumerate(S)]
            r = run_arms(S, cfg, target, cfg["k"], shifts=shifts)
            for a, v in r.items():
                p2[a].append(float(np.mean([t["net"] for t in v])) if v else np.nan)
        summ = {a: summarize(v, boot, cfg, target) for a, v in arms.items()}
        p1s = {a: summarize(v, boot, cfg, target) for a, v in p1.items()}
        ctrl = {}
        for a in cfg["arms"]:
            trig, cx = arm_parts(a)
            pk = f"P1_{trig}_{cx}"
            dci, pgt = boot.diff_ci(arms[a], p1[pk])
            d2 = np.array(p2[a], float); d2 = d2[np.isfinite(d2)]
            m = summ[a].get("mean_net")
            fil = None
            if cx in ("C1", "C2"):
                fil = boot.diff_ci(arms[a], arms[f"B_{trig}_C0"])[0]
            ctrl[a] = {"p1_key": pk, "p1_mean": p1s[pk].get("mean_net"), "p1_n": p1s[pk]["n"],
                       "p1_diff_ci": dci, "p1_diff_prob_pos": pgt,
                       "p2_draws": int(len(d2)), "p2_median": float(np.median(d2)) if len(d2) else None,
                       "p2_p95": float(np.percentile(d2, 95)) if len(d2) else None,
                       "p2_pct": float(np.mean(d2 < m)) if (len(d2) and m is not None) else None,
                       "k_sens": {k: ksens[k][a].get("mean_net") for k in ksens},
                       "filter_vs_B_ci": fil}
            family.append((target, a, summ[a].get("p", np.nan)))
        # regime (lado do flip na abertura), descritivo
        reg = {}
        for a in cfg["arms"]:
            rr = {"acima": [], "abaixo": []}
            for t_ in arms[a]:
                x = next(y for y in S if y.d == t_["sess"])
                fl = [y["price"] for y in x.levels_raw if y["type"] == "gamma_flip"]
                if fl:
                    rr["acima" if x.o[0] > fl[0] else "abaixo"].append(t_["net"])
            reg[a] = {k: {"n": len(v), "mean": float(np.mean(v)) if v else None} for k, v in rr.items()}
        res["targets"][target] = {
            "sessions": len(S), "first": sessions[0], "last": sessions[-1],
            "sessions_design": sum(1 for s in sessions if s <= cfg["design_end"]),
            "sessions_validation": sum(1 for s in sessions if s > cfg["design_end"]),
            "gex_source_counts": {k: sum(1 for x in S if x.gex_src == k) for k in ("csv", "db")},
            "excluded": excl, "gex_meta": {k: v for k, v in meta.items() if k not in ("csv", "db")},
            "arms": summ, "controls": ctrl, "p1": p1s, "k_sens": ksens, "n0": n0, "regime_flip": reg,
            "equity": {a: equity(v) for a, v in arms.items()}, "monthly": {a: monthly(v) for a, v in arms.items()},
            "p2_means": p2, "elapsed_s": round(time.time() - t0, 1),
        }
    q = bh_adjust([f[2] for f in family])
    for (target, a, p), qq in zip(family, q):
        s = res["targets"][target]["arms"][a]
        s["q_bh"] = qq
        s["p_bonf"] = float(min(1.0, p * len(family))) if np.isfinite(p) else None
    rank = {"GO": 2, "INCONCLUSIVO": 1, "NO-GO": 0}
    for target, tr in res["targets"].items():
        best = "NO-GO"
        for a in cfg["arms"]:
            st, crit = classify(tr["arms"][a], tr["controls"][a], cfg)
            tr["arms"][a]["status"] = st
            tr["arms"][a]["criteria"] = crit
            if rank[st] > rank[best]:
                best = st
        tr["verdict"] = best
    res["n_family"] = len(family)
    res["finished_utc"] = pd.Timestamp.utcnow().isoformat()
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
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    h = config_hash(CONFIG)
    if a.freeze:
        print("config congelado:", freeze())
    if a.run:
        out = a.out or os.path.join(ROOT, "data", "eval", "fase20", f"gexpa_{h}.json")
        r = run(a.db, out)
        for t, v in r["targets"].items():
            print(t, v["sessions"], "sessões; veredito", v["verdict"])
        print("salvo:", out)


if __name__ == "__main__":
    main()