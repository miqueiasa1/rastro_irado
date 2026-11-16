"""
Fase 20 — teste extra: divergência de inclinação rastro (P↑ do snapshot) × preço (ideia do owner, WDO 06/11/2026).

Pré-registro: `CONFIG` é congelado com hash ANTES da execução (`--freeze` grava
`data/eval/fase20/div_config_<hash>.json`; `--run` recusa rodar se o hash não bater).
Banco aberto em `mode=ro`. A série do rastro é a `p_up` gravada em `irai_live_snapshots`
no momento (anti-repaint, fase 15/16): só vale em t se `is_ghost=0` e o snapshot foi gravado
entre a abertura e o FECHAMENTO da barra t (created_at ≤ fechamento) — gravações posteriores
(backfill/reprocesso) ficam NaN.

Uso:
    python scripts/research_divergence.py --db <irai_live.db> --freeze
    python scripts/research_divergence.py --db <irai_live.db> --run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from backend.eval.data import broker_wall_to_brt, connect_ro  # noqa: E402
from backend.eval.divergence import (confirm, divergence_episodes, pullback_episodes,  # noqa: E402
                                     rolling_slope, time_exit_trades)
from backend.eval.events import bh_adjust, cluster_t, p_two_sided  # noqa: E402
from backend.eval.pa_triggers import atr_prev, true_range  # noqa: E402
from backend.eval.trade_sim import SIM_DEFAULT, simulate_session  # noqa: E402
from research_gex_pa import Boot, config_hash, load_bars, max_dd, sha_file  # noqa: E402

CONFIG = {
    "phase": "20-gex-regioes-price-action/divergencia-rastro-preco",
    "idea": "owner 06/11/2026 (WDO): rastro P sobe enquanto o preço corrige -> entrar na direção do rastro",
    "series": "irai_live_snapshots.p_up (P(↑) do nowcast, 0-100; a linha do topo do painel)",
    "series_rule": "usa p_up[t] só se is_ghost=0 e open_t <= created_at <= close_t (UTC real); senão NaN",
    "price": "market_bars M5 close (mesmo ativo)",
    "start": "2026-08-01", "end": "2026-11-10", "design_end": "2026-09-30",
    "targets": ["WIN$N", "WDO$N"],
    "session_min_bars": 60, "session_min_live_p": 60, "exclude_open_gap_abs": 0.02,
    "W_min": [30, 60, 90], "bar_min": 5,
    "k_grid": [0.5, 1.0],
    "sigma": {"what": "desvio-padrão das inclinações (todas as barras) das sessões elegíveis anteriores",
              "sessions": 20, "min_sessions": 5},
    "episode": "início = primeira barra em que vale a divergência (não valia em t-1); direção = rastro",
    "confirm_window_bars": 6,
    "confirm": "primeira barra j em [t0, t0+6] com close_j > high_{j-1} (compra) / close_j < low_{j-1} (venda); entrada open_{j+1}",
    "exits": {"TIME60": "fechamento da barra j+12 (60 min) ou última do pregão",
              "STOPTGT": "simulador da fase 20: stop = min(low_j, low_{j-1}) - 0.1 ATR (venda espelhado), risco em [0.5, 2.5] ATR senão descarta, alvo 1.5R, tempo 60 min, stop primeiro em barra ambígua"},
    "entry_k": list(SIM_DEFAULT["entry_k"]), "one_position": True,
    "costs_pts": {"WIN$N": 10.0, "WDO$N": 1.0}, "cost_sens_mult": 2.0,
    "ticks": {"WIN$N": 5.0, "WDO$N": 0.5},
    "atr": {"n": 14, "min_bars": 5, "fallback_sessions": 20},
    "sim": {**SIM_DEFAULT, "risk_atr": list(SIM_DEFAULT["risk_atr"]), "entry_k": list(SIM_DEFAULT["entry_k"])},
    "family": "2 ativos x 3 W x 2 k x 2 saídas = 24 testes (BH)",
    "controls": {
        "C_random": "entradas aleatórias casadas: para cada operação, sessão elegível sorteada, mesma barra k de entrada e mesmo lado, mesma saída; 200 sorteios",
        "C_pullback": "mesmo recuo do preço (inclinação < -k·σ -> compra) + mesmo gatilho, sem rastro",
        "C_shuffle": "rastro embaralhado em blocos de sessão (P de outra sessão, alinhado por k), σ do original; 200 sorteios",
    },
    "draws": 200, "seed": 2011, "n_boot": 2000, "boot_seed": 0, "fdr_q": 0.05, "min_trades_per_half": 30,
    "verdict": {"GO": "1 IC95 sessão > 0; 2 média > 0 em design e validação com n>=30 cada; 3 q_BH < 0.05; 4 diff vs C_pullback IC > 0 e média >= p95 de C_random e de C_shuffle; 5 média com 2x custo > 0 e o outro k (mesmo W e saída) > 0",
                "INCONCLUSIVO": "média > 0 no total e nas duas metades e acima da média de C_pullback e das medianas de C_random e C_shuffle, sem passar em todos",
                "NO-GO": "demais", "asset": "melhor status entre os 12 testes do ativo"},
}


def frozen_path(h):
    return os.path.join(ROOT, "data", "eval", "fase20", f"div_config_{h}.json")


def freeze():
    h = config_hash(CONFIG)
    os.makedirs(os.path.dirname(frozen_path(h)), exist_ok=True)
    if not os.path.exists(frozen_path(h)):
        with open(frozen_path(h), "w", encoding="utf-8", newline="\n") as f:
            json.dump({"config_hash": h, "frozen_at_utc": pd.Timestamp.utcnow().isoformat(), "config": CONFIG},
                      f, ensure_ascii=False, indent=1)
    return h


def load_p(conn, target, cfg):
    s = pd.read_sql_query(
        "SELECT timestamp_utc, p_up, is_ghost, created_at FROM irai_live_snapshots WHERE target=? AND timeframe='M5' "
        "AND session_date >= ? AND session_date <= ?", conn, params=(target, cfg["start"], cfg["end"]))
    s["ts_brt"] = broker_wall_to_brt(s.timestamp_utc)
    cr = pd.to_datetime(s.created_at, utc=True, format="mixed")
    op = s.ts_brt.dt.tz_convert("UTC")
    cl = op + pd.Timedelta(minutes=cfg["bar_min"])
    ok = (s.is_ghost == 0) & (cr >= op) & (cr <= cl) & s.p_up.notna()
    s["p_live"] = s.p_up.where(ok)
    s["late"] = (s.is_ghost == 0) & ~((cr >= op) & (cr <= cl))
    return s.dropna(subset=["ts_brt"]).drop_duplicates("ts_brt")[["ts_brt", "p_live", "p_up", "late"]]


class S:
    __slots__ = ("d", "o", "h", "l", "c", "k", "p", "atr", "sx", "sp", "sig_x", "sig_p")


def prepare(conn, target, cfg):
    b = load_bars(conn, target, cfg["start"], cfg["end"])
    p = load_p(conn, target, cfg)
    b = b.merge(p, on="ts_brt", how="left")
    sessions = sorted(b.sess.unique())
    out, excl, trs, last_close = [], {"few_live_p": [], "gap": []}, {}, None
    late = int(b.late.fillna(False).sum()); withp = int(b.p_up.notna().sum())
    for s in sessions:
        bb = b[b.sess == s]
        o, h, l, c = (bb[x].to_numpy(float) for x in ("open", "high", "low", "close"))
        tr = true_range(o, h, l, c)
        prev = [x for x in sessions if x < s][-cfg["atr"]["fallback_sessions"]:]
        fb = float(np.median(np.concatenate([trs[x] for x in prev]))) if prev else np.nan
        trs[s] = tr
        gap = (o[0] / last_close - 1) if last_close else 0.0
        last_close = c[-1]
        pl = bb.p_live.to_numpy(float)
        if np.isfinite(pl).sum() < cfg["session_min_live_p"]:
            excl["few_live_p"].append(s); continue
        if abs(gap) > cfg["exclude_open_gap_abs"]:
            excl["gap"].append(s); continue
        x = S()
        x.d, x.o, x.h, x.l, x.c, x.k, x.p = s, o, h, l, c, bb.k.to_numpy(int), pl
        x.atr = atr_prev(tr, cfg["atr"]["n"], cfg["atr"]["min_bars"], fb)
        x.sx, x.sp, x.sig_x, x.sig_p = {}, {}, {}, {}
        out.append(x)
    for W in cfg["W_min"]:
        n = W // cfg["bar_min"]
        for x in out:
            x.sx[W] = rolling_slope(x.c, n)
            x.sp[W] = rolling_slope(x.p, n)
        for i, x in enumerate(out):
            prev = out[max(0, i - cfg["sigma"]["sessions"]):i]
            if len(prev) < cfg["sigma"]["min_sessions"]:
                x.sig_x[W] = x.sig_p[W] = np.nan; continue
            ax = np.concatenate([y.sx[W] for y in prev]); ap = np.concatenate([y.sp[W] for y in prev])
            x.sig_x[W] = float(np.nanstd(ax)); x.sig_p[W] = float(np.nanstd(ap))
    warm = [x.d for x in out if not np.isfinite(x.sig_x[cfg["W_min"][0]])]
    out = [x for x in out if np.isfinite(x.sig_x[cfg["W_min"][0]])]
    return out, {**excl, "warmup_sigma": warm}, {"bars_with_snapshot": withp, "bars_late_snapshot": late}


def trades_for(x, sigs, exit_, target, cfg):
    cost, tick = cfg["costs_pts"][target], cfg["ticks"][target]
    if exit_ == "TIME60":
        tr = time_exit_trades(sigs, x.o, x.c, x.k, cost, cfg["sim"]["hold_bars"], tuple(cfg["entry_k"]))
    else:
        ss = []
        for s in sigs:
            j = s["t"]
            L = min(x.l[j], x.l[j - 1]) if s["side"] == 1 else max(x.h[j], x.h[j - 1])
            ss.append({**s, "L": float(L), "hw": 0.0})
        tr, _ = simulate_session(ss, x.o, x.h, x.l, x.c, x.k, x.atr, [], cost, tick, cfg["sim"])
    for t_ in tr:
        t_["sess"] = x.d
        t_["k_entry"] = int(x.k[t_["entry_i"]])
    return tr


def run_cfg(sess, W, kk, exit_, target, cfg, mode="div", p_override=None):
    out = []
    for i, x in enumerate(sess):
        if mode == "div":
            sp = x.sp[W] if p_override is None else p_override[i]
            ep = divergence_episodes(sp, x.sx[W], x.sig_p[W], x.sig_x[W], kk)
        else:
            ep = pullback_episodes(x.sx[W], x.sig_x[W], kk)
        sigs = confirm(ep, x.h, x.l, x.c, cfg["confirm_window_bars"])
        out += trades_for(x, sigs, exit_, target, cfg)
    return out


def random_matched(sess, trades, exit_, target, cfg, rng):
    """Uma realização: mesma barra k de entrada e lado, sessão sorteada."""
    means = []
    by_k = []
    for x in sess:
        by_k.append({int(kv): i for i, kv in enumerate(x.k)})
    for _ in range(cfg["draws"]):
        net = []
        for t_ in trades:
            for _try in range(20):
                j = int(rng.integers(len(sess)))
                e = by_k[j].get(t_["k_entry"])
                if e is not None and e >= 2:
                    break
            else:
                continue
            x = sess[j]
            tr = trades_for(x, [{"t": e - 1, "side": t_["side"], "t0": e - 1}], exit_, target, cfg)
            if tr:
                net.append(tr[0]["net"])
        means.append(float(np.mean(net)) if net else np.nan)
    return np.array(means, float)


def shuffled(sess, W, kk, exit_, target, cfg, perms):
    means = []
    for perm in perms:
        po = []
        for i, x in enumerate(sess):
            donor = sess[perm[i]]
            m = {int(kv): v for kv, v in zip(donor.k, donor.p)}
            pp = np.array([m.get(int(kv), np.nan) for kv in x.k], float)
            po.append(rolling_slope(pp, W // cfg["bar_min"]))
        tr = run_cfg(sess, W, kk, exit_, target, cfg, p_override=po)
        means.append(float(np.mean([t["net"] for t in tr])) if tr else np.nan)
    return np.array(means, float)


def summarize(tr, boot, cfg, target):
    tr = sorted(tr, key=lambda t: (t["sess"], t["entry_i"]))
    out = {"n": len(tr), "sessions": len({t["sess"] for t in tr})}
    if not tr:
        return out
    net = np.array([t["net"] for t in tr]); sess = np.array([t["sess"] for t in tr])
    tt = cluster_t(net, sess) if len(tr) >= 3 else float("nan")
    des = sess <= cfg["design_end"]
    pos, neg = net[net > 0].sum(), -net[net < 0].sum()
    out.update({"mean_net": float(net.mean()), "median_net": float(np.median(net)),
                "mean_gross": float(np.mean([t["gross"] for t in tr])), "hit": float((net > 0).mean()),
                "pf": float(pos / neg) if neg > 0 else None, "total_net": float(net.sum()), "max_dd": max_dd(net),
                "t": tt, "p": p_two_sided(tt), "ci": boot.ci(tr),
                "mean_net_2xcost": float((net - cfg["costs_pts"][target] * (cfg["cost_sens_mult"] - 1)).mean()),
                "pct_long": float(np.mean([t["side"] == 1 for t in tr])),
                "design": {"n": int(des.sum()), "mean_net": float(net[des].mean()) if des.any() else None},
                "validation": {"n": int((~des).sum()), "mean_net": float(net[~des].mean()) if (~des).any() else None}})
    if "reason" in tr[0]:
        out["pct_stop"] = float(np.mean([t["reason"] == "stop" for t in tr]))
        out["pct_target"] = float(np.mean([t["reason"] == "target" for t in tr]))
    return out


def classify(s, c, other_k_mean, cfg):
    if s["n"] == 0:
        return "NO-GO", {}
    m = s["mean_net"]
    crit = {
        "1_ci_total": s["ci"][0] is not None and s["ci"][0] > 0 and m > 0,
        "2_metades": (s["design"]["mean_net"] or -1) > 0 and (s["validation"]["mean_net"] or -1) > 0
        and s["design"]["n"] >= cfg["min_trades_per_half"] and s["validation"]["n"] >= cfg["min_trades_per_half"],
        "3_bh": s.get("q_bh") is not None and s["q_bh"] < cfg["fdr_q"],
        "4_controles": c["pull_diff_ci"][0] is not None and c["pull_diff_ci"][0] > 0
        and c["rand_p95"] is not None and m >= c["rand_p95"] and c["shuf_p95"] is not None and m >= c["shuf_p95"],
        "5_robustez": s["mean_net_2xcost"] > 0 and other_k_mean is not None and other_k_mean > 0,
    }
    if all(crit.values()):
        return "GO", crit
    soft = m > 0 and (s["design"]["mean_net"] or -1) > 0 and (s["validation"]["mean_net"] or -1) > 0 \
        and c["pull_mean"] is not None and m > c["pull_mean"] \
        and c["rand_median"] is not None and m > c["rand_median"] and c["shuf_median"] is not None and m > c["shuf_median"]
    return ("INCONCLUSIVO" if soft else "NO-GO"), crit


def example(conn, cfg, target="WDO$N", day="2026-11-06"):
    b = load_bars(conn, target, day, day)
    p = load_p(conn, target, cfg)
    b = b.merge(p, on="ts_brt", how="left")
    return [{"brt": t.strftime("%H:%M"), "close": float(c), "high": float(h), "low": float(l),
             "p": (None if not np.isfinite(v) else float(v))}
            for t, c, h, l, v in zip(b.ts_brt, b.close, b.high, b.low, b.p_live.astype(float))]


def run(db, out_json):
    h = config_hash(CONFIG)
    if not os.path.exists(frozen_path(h)):
        raise SystemExit(f"CONFIG {h} não foi congelado; rode --freeze antes.")
    cfg = CONFIG
    conn = connect_ro(db)
    res = {"config_hash": h, "config": cfg, "targets": {}, "started_utc": pd.Timestamp.utcnow().isoformat(),
           "code_sha": {f: sha_file(os.path.join(ROOT, f)) for f in
                        ("backend/eval/divergence.py", "backend/eval/trade_sim.py", "scripts/research_divergence.py")}}
    family = []
    rng = np.random.default_rng(cfg["seed"])
    for target in cfg["targets"]:
        t0 = time.time()
        sess, excl, meta = prepare(conn, target, cfg)
        days = [x.d for x in sess]
        boot = Boot(days, cfg["n_boot"], cfg["boot_seed"])
        perms = [rng.permutation(len(sess)) for _ in range(cfg["draws"])]
        tests, d0611 = {}, {}
        for W in cfg["W_min"]:
            for kk in cfg["k_grid"]:
                for ex in ("TIME60", "STOPTGT"):
                    name = f"W{W}_k{kk}_{ex}"
                    tr = run_cfg(sess, W, kk, ex, target, cfg)
                    pb = run_cfg(sess, W, kk, ex, target, cfg, mode="pull")
                    s = summarize(tr, boot, cfg, target)
                    ps = summarize(pb, boot, cfg, target)
                    rm = random_matched(sess, tr, ex, target, cfg, rng) if tr else np.array([])
                    sh = shuffled(sess, W, kk, ex, target, cfg, perms)
                    rm, sh = rm[np.isfinite(rm)], sh[np.isfinite(sh)]
                    dci, _ = boot.diff_ci(tr, pb)
                    m = s.get("mean_net")
                    ctrl = {"pull_n": ps["n"], "pull_mean": ps.get("mean_net"), "pull_ci": ps.get("ci"), "pull_diff_ci": dci,
                            "rand_median": float(np.median(rm)) if len(rm) else None,
                            "rand_p95": float(np.percentile(rm, 95)) if len(rm) else None,
                            "rand_pct": float(np.mean(rm < m)) if (len(rm) and m is not None) else None,
                            "shuf_median": float(np.median(sh)) if len(sh) else None,
                            "shuf_p95": float(np.percentile(sh, 95)) if len(sh) else None,
                            "shuf_pct": float(np.mean(sh < m)) if (len(sh) and m is not None) else None}
                    eq = np.cumsum([t["net"] for t in sorted(tr, key=lambda t: (t["sess"], t["entry_i"]))]).round(2).tolist()
                    tests[name] = {"W": W, "k": kk, "exit": ex, "summary": s, "controls": ctrl, "equity": eq,
                                   "trades": [{k_: t_[k_] for k_ in ("sess", "entry_i", "exit_i", "side", "entry", "exit", "net", "t0", "t")}
                                              for t_ in tr]}
                    d0611[name] = [t_ for t_ in tests[name]["trades"] if t_["sess"] == "2026-11-06"]
                    family.append((target, name, s.get("p", np.nan)))
        res["targets"][target] = {"sessions": len(sess), "first": days[0], "last": days[-1],
                                  "sessions_design": sum(d <= cfg["design_end"] for d in days),
                                  "sessions_validation": sum(d > cfg["design_end"] for d in days),
                                  "excluded": excl, "meta": meta, "tests": tests, "sig_0611": d0611,
                                  "elapsed_s": round(time.time() - t0, 1)}
        if "2026-11-06" in days:
            x = sess[days.index("2026-11-06")]
            res["targets"][target]["div_0611"] = {
                f"W{W}_k{kk}": [{"t0": int(t), "side": int(d)} for t, d in divergence_episodes(x.sp[W], x.sx[W], x.sig_p[W], x.sig_x[W], kk)]
                for W in cfg["W_min"] for kk in cfg["k_grid"]}
            res["targets"][target]["z_0611"] = {str(W): {"zp": (x.sp[W] / x.sig_p[W]).round(2).tolist(),
                                                         "zx": (x.sx[W] / x.sig_x[W]).round(2).tolist()} for W in cfg["W_min"]}
    q = bh_adjust([f[2] for f in family])
    for (target, name, _), qq in zip(family, q):
        res["targets"][target]["tests"][name]["summary"]["q_bh"] = qq
    rank = {"GO": 2, "INCONCLUSIVO": 1, "NO-GO": 0}
    for target, tt in res["targets"].items():
        best = "NO-GO"
        for name, v in tt["tests"].items():
            ok = [kk for kk in cfg["k_grid"] if kk != v["k"]][0]
            other = tt["tests"][f"W{v['W']}_k{ok}_{v['exit']}"]["summary"].get("mean_net")
            st, cr = classify(v["summary"], v["controls"], other, cfg)
            v["status"], v["criteria"] = st, cr
            best = st if rank[st] > rank[best] else best
        tt["verdict"] = best
    res["example_wdo_0611"] = example(conn, cfg)
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
        out = a.out or os.path.join(ROOT, "data", "eval", "fase20", f"div_{h}.json")
        r = run(a.db, out)
        for t, v in r["targets"].items():
            print(t, v["sessions"], "sessões", v["first"], v["last"], "veredito", v["verdict"], v["elapsed_s"], "s")
        print("salvo:", out)


if __name__ == "__main__":
    main()