"""
GEX as-of para a pesquisa da fase 20 (regiões de GEX + gatilho de price action).

Fonte dos níveis por sessão (decisão do owner em 10/11/2026):
1. Histórico oficial do projeto WDO (`mt5/Files/jumba_gex_<win|wdo>_history.csv`, `;`,
   colunas `session_date;type;price;width`). Os níveis de jan–mai/2026 foram calculados com a
   posição em aberto do pregão anterior e são OFICIAIS: valem como conhecidos na abertura.
2. Para sessões ausentes do CSV: `gex_levels` do IRAI, o PRIMEIRO run com `run_name` < 09:00
   (horário de Brasília). Sem run antes de 09:00 → a sessão sai da amostra.
3. Sábados/domingos (ex.: 23/05/2026) são excluídos.

Este módulo só LÊ arquivos e o banco (conexão somente leitura). Nunca escreve.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date

TYPE_MAP = {
    "wall": "wall", "midwall": "mid_wall", "mid_wall": "mid_wall",
    "maxgamma": "max_gamma", "max_gamma": "max_gamma",
    "mingamma": "min_gamma", "min_gamma": "min_gamma",
    "gammaflip": "gamma_flip", "gamma_flip": "gamma_flip",
}
GAMMA_TYPES = ("min_gamma", "max_gamma", "gamma_flip")
RUN_RE = re.compile(r"^\d{2}:\d{2}$")
OPEN_HHMM = "09:00"


def norm_type(t: str) -> str:
    k = str(t).strip().lower()
    if k not in TYPE_MAP:
        raise ValueError(f"tipo de nível desconhecido: {t!r}")
    return TYPE_MAP[k]


def is_weekend(d: str) -> bool:
    return date.fromisoformat(d).weekday() >= 5


def load_gex_csv(path: str) -> dict[str, list[dict]]:
    """{session_date: [{'type','price','width'}...]} a partir do CSV oficial (somente leitura)."""
    out: dict[str, list[dict]] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            d = (r.get("session_date") or "").strip()
            if not d:
                continue
            out.setdefault(d, []).append({
                "type": norm_type(r["type"]),
                "price": float(r["price"]),
                "width": int(float(r.get("width") or 1)),
            })
    return out


def first_preopen_run(runs: list[tuple[str, str]]) -> tuple[str, str] | None:
    """Entre (run_name, levels_json), o primeiro com run_name HH:MM < 09:00; senão None."""
    ok = sorted((rn, lj) for rn, lj in runs if RUN_RE.match(str(rn)) and str(rn) < OPEN_HHMM)
    return ok[0] if ok else None


def load_gex_db_preopen(conn, target: str) -> dict[str, dict]:
    """{session_date: {'run_name','updated_at','levels'}} com o primeiro run antes de 09:00."""
    rows = conn.execute(
        "SELECT session_date, run_name, levels_json, updated_at FROM gex_levels WHERE target = ?",
        (target,)).fetchall()
    by: dict[str, list] = {}
    upd: dict[tuple, str] = {}
    for d, rn, lj, up in rows:
        by.setdefault(d, []).append((rn, lj))
        upd[(d, rn)] = up
    out = {}
    for d, runs in by.items():
        pick = first_preopen_run(runs)
        if pick is None:
            continue
        rn, lj = pick
        levels = [{"type": norm_type(x.get("type", "wall")), "price": float(x["price"]),
                   "width": int(x.get("width", 1) or 1)} for x in json.loads(lj)]
        out[d] = {"run_name": rn, "updated_at": upd[(d, rn)], "levels": levels}
    return out


def build_gex_history(csv_levels: dict, db_levels: dict, exclude: tuple = ()) -> dict[str, dict]:
    """Une as fontes: CSV oficial primeiro; `gex_levels` (run < 09:00) só onde o CSV não tem a data."""
    out = {}
    for d, lv in csv_levels.items():
        if is_weekend(d) or d in exclude:
            continue
        out[d] = {"source": "csv", "levels": lv}
    for d, info in db_levels.items():
        if d in out or is_weekend(d) or d in exclude:
            continue
        out[d] = {"source": "db", "levels": info["levels"], "run_name": info["run_name"]}
    return dict(sorted(out.items()))


def primary_levels(levels: list[dict], min_width: int = 2) -> list[dict]:
    """N1: walls com width ≥ min_width ∪ min/max/flip (preços duplicados → um só, maior width)."""
    sel = [x for x in levels if (x["type"] == "wall" and x["width"] >= min_width) or x["type"] in GAMMA_TYPES]
    best: dict[float, dict] = {}
    for x in sel:
        p = round(x["price"], 4)
        if p not in best or x["width"] > best[p]["width"]:
            best[p] = x
    return sorted(best.values(), key=lambda x: x["price"])


def all_walls(levels: list[dict]) -> list[dict]:
    """N0 (controle): todas as walls (grade de strikes)."""
    return sorted([x for x in levels if x["type"] == "wall"], key=lambda x: x["price"])


def grid_spacing(levels: list[dict]) -> float | None:
    """Espaçamento mediano da grade wall + mid_wall da sessão."""
    import numpy as np
    p = sorted({round(x["price"], 4) for x in levels if x["type"] in ("wall", "mid_wall")})
    if len(p) < 3:
        return None
    return float(np.median(np.diff(p)))


def merge_levels(levels: list[dict], h_ref: float, open_price: float) -> list[dict]:
    """Funde níveis a menos de 2·h_ref; representante = maior width (empate: mais perto da abertura)."""
    lv = sorted(levels, key=lambda x: x["price"])
    groups: list[list[dict]] = []
    for x in lv:
        if groups and x["price"] - groups[-1][-1]["price"] <= 2 * h_ref:
            groups[-1].append(x)
        else:
            groups.append([x])
    out = []
    for g in groups:
        rep = sorted(g, key=lambda x: (-x["width"], abs(x["price"] - open_price)))[0]
        out.append({**rep, "merged": len(g)})
    return out