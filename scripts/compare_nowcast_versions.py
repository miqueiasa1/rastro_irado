"""
Fase 17: compara duas versões do nowcast nas MESMAS barras (recalculadas pelo engine, v2 Kalman).

Somente leitura: o engine roda com `model_version_id` forçado, o que desliga a gravação do estado
do Kalman. Use um banco CÓPIA por segurança (o engine abre conexões normais).

    python scripts/compare_nowcast_versions.py --db <copia.db> --target WDO$N \
        --old wdo-nowcast-20261028T190512Z --new wdo-nowcast-2026... --start 2026-08-03 --end 2026-11-10
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.eval.metrics import evaluate_probability
from backend.eval.data import broker_wall_to_brt
from backend.irai.engine import IRAIEngine


def series(engine, target, vid, sessions):
    rows = []
    for s in sessions:
        try:
            snaps = engine.compute_from_db(s, target, version="v2", model_version_id=vid, persist_state=False)
        except Exception as e:  # sessão sem dados etc.
            print(f"  {s}: {e}")
            continue
        for sn in snaps:
            if getattr(sn, "is_ghost", False) or getattr(sn, "is_pre_market", False):
                continue
            rows.append({"sess": s, "ts": sn.timestamp, "p": sn.p_up / 100.0, "close": sn.win_current,
                         "open": sn.win_open})
    df = pd.DataFrame(rows)
    df["ts_brt"] = broker_wall_to_brt(df.ts.str.replace("+00:00", "Z", regex=False))
    m = df.ts_brt.dt.hour * 60 + df.ts_brt.dt.minute
    return df[(m >= 9 * 60) & (m < 18 * 60 + 25)].reset_index(drop=True)


def evaluate(df, n_boot, seed):
    g = df.groupby("sess")
    df = df.copy()
    df["rtd"] = df.close / df.open - 1
    df["fwd_60m"] = g.close.shift(-12) / df.close - 1
    df["fwd_close"] = g.close.transform("last") / df.close - 1
    out = {}
    for lab, col in (("nowcast", "rtd"), ("60m", "fwd_60m"), ("close", "fwd_close")):
        d = df[df[col].notna() & (df[col] != 0)]
        r = evaluate_probability(d.p.to_numpy(), (d[col] > 0).astype(int).to_numpy(), d.sess.to_numpy(), n_boot, seed)
        r.pop("reliability", None)
        out[lab] = r
    p = df.p
    out["p_extremos_lt20_gt80"] = float(((p < 0.2) | (p > 0.8)).mean())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--split", default=None, help="1ª sessão fora da amostra da calibração (ex.: 2026-10-29)")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    eng = IRAIEngine(a.db)
    import sqlite3
    c = sqlite3.connect(a.db)
    sessions = [r[0] for r in c.execute(
        "SELECT DISTINCT session_date FROM irai_live_snapshots WHERE target=? AND session_date BETWEEN ? AND ? ORDER BY 1",
        (a.target, a.start, a.end))] or None
    c.close()
    if not sessions:
        sessions = [d.strftime("%Y-%m-%d") for d in pd.bdate_range(a.start, a.end)]
    res = {"target": a.target, "old_version": a.old, "new_version": a.new, "start": a.start, "end": a.end,
           "split": a.split, "n_boot": a.n_boot}
    S = {k: series(eng, a.target, v, sessions) for k, v in (("old", a.old), ("new", a.new))}
    keys = S["old"].merge(S["new"], on=["sess", "ts"], suffixes=("_o", "_n"))
    for k in ("old", "new"):
        d = keys.rename(columns={f"p_{k[0]}": "p", f"close_{k[0]}": "close", f"open_{k[0]}": "open"})
        parts = {"todas": d}
        if a.split:
            parts["in_sample"] = d[d.sess < a.split]
            parts["fora_da_amostra"] = d[d.sess >= a.split]
        res[k] = {name: evaluate(dd, a.n_boot, 0) for name, dd in parts.items() if len(dd) > 200}
    res["bars"] = int(len(keys))
    res["sessions"] = int(keys.sess.nunique())
    print(json.dumps({k: (v if not isinstance(v, dict) else {p: {h: {m: round(x, 4) for m, x in hv.items() if m in ("auc", "bss", "ece", "n")} if isinstance(hv, dict) else hv for h, hv in pv.items()} for p, pv in v.items()}) for k, v in res.items()}, ensure_ascii=False, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    main()
