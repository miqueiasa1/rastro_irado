"""
Auditoria do histórico de GEX usado na fase 20 (W1). Somente leitura (CSV oficial + banco mode=ro).

Uso: python scripts/audit_gex_history.py --db <irai_live.db> --out data/eval/fase20/gex_auditoria.json
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.eval.data import connect_ro  # noqa: E402
from backend.irai import gex_asof as G  # noqa: E402
from scripts.research_gex_pa import CONFIG, GEX_DIR, load_bars, sha_file  # noqa: E402


def audit(db: str) -> dict:
    conn = connect_ro(db)
    out = {}
    for target in CONFIG["targets"]:
        path = os.path.join(GEX_DIR, CONFIG["gex_csv"][target])
        csvl = G.load_gex_csv(path)
        dbl = G.load_gex_db_preopen(conn, target)
        hist = G.build_gex_history(csvl, dbl, exclude=tuple(CONFIG["exclude_sessions"]))
        bars = load_bars(conn, target, CONFIG["start"], CONFIG["end"])
        bsess = sorted(bars.sess.unique())
        per = []
        for d, lv in sorted(csvl.items()):
            c = collections.Counter(x["type"] for x in lv)
            wc = collections.Counter(x["width"] for x in lv if x["type"] == "wall")
            per.append({"d": d, "n": len(lv), "types": dict(c), "walls_by_width": dict(wc),
                        "n_primary": len(G.primary_levels(lv))})
        miss_gamma = [p["d"] for p in per if any(p["types"].get(t, 0) == 0 for t in G.GAMMA_TYPES)]
        # CSV × banco (primeiro run < 09:00) nas datas em comum
        flipd, same_prim = [], 0
        common = sorted(set(csvl) & set(dbl))
        for d in common:
            a = {round(x["price"], 1) for x in G.primary_levels(csvl[d])}
            b = {round(x["price"], 1) for x in G.primary_levels(dbl[d]["levels"])}
            same_prim += int(a == b)
            fa = [x["price"] for x in csvl[d] if x["type"] == "gamma_flip"]
            fb = [x["price"] for x in dbl[d]["levels"] if x["type"] == "gamma_flip"]
            if fa and fb:
                flipd.append(abs(fa[0] - fb[0]))
        out[target] = {
            "csv_path": path, "csv_sha": sha_file(path), "csv_sessions": len(csvl),
            "csv_first": min(csvl), "csv_last": max(csvl),
            "csv_weekend_dates": [d for d in csvl if G.is_weekend(d)],
            "csv_sessions_by_month": dict(sorted(collections.Counter(d[:7] for d in csvl).items())),
            "levels_per_session_median": float(np.median([p["n"] for p in per])),
            "primary_per_session_median": float(np.median([p["n_primary"] for p in per])),
            "primary_per_session_min": int(min(p["n_primary"] for p in per)),
            "csv_sessions_missing_a_gamma_level": miss_gamma,
            "db_preopen_sessions": len(dbl),
            "db_fallback_used": [d for d, v in hist.items() if v["source"] == "db"],
            "bar_sessions": len(bsess),
            "bar_sessions_without_gex": [d for d in bsess if d not in hist],
            "gex_sessions_without_bars": [d for d in hist if d not in set(bsess)],
            "csv_vs_db_common": len(common), "csv_vs_db_same_primary_set": same_prim,
            "csv_vs_db_flip_absdiff_median": float(np.median(flipd)) if flipd else None,
            "csv_vs_db_flip_absdiff_max": float(np.max(flipd)) if flipd else None,
        }
    conn.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r = audit(a.db)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    for t, v in r.items():
        print(t, {k: (v[k] if not isinstance(v[k], list) or len(v[k]) < 12 else f"{len(v[k])} itens") for k in v if k != "csv_sessions_by_month"})


if __name__ == "__main__":
    main()