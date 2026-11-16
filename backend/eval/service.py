"""Fase 19A (v2.0) -- leitura da assertividade fora da amostra para a API (REQ-A02).

So le os artefatos que o harness diario (scripts/eval_assertividade.py, tarefa
"IRAI Daily Assertividade" seg-sex 18:45) ja grava em ``data/eval/latest/``:

- ``assertividade_ultimos20.json``: janela dos ultimos 20 pregoes;
- ``assertividade.json``: periodo inteiro desde 03/08/2026.

Nada e recalculado na requisicao e nada e escrito em banco nenhum. O resultado e
um resumo compacto (< 4 KB por alvo) para o painel (ReliabilityCard) e, quando o
owner aprovar o deploy, para o no ``eval/<target>`` do Firebase.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVAL_LATEST_DIR = os.path.join(ROOT, "data", "eval", "latest")

# D2: so WIN$N e WDO$N fazem parte do v2.0 (REQ-A05).
EVAL_TARGETS = ("WIN$N", "WDO$N")
WINDOWS = {"20": "assertividade_ultimos20.json", "full": "assertividade.json"}
# SPEC §12/§18: BSS abaixo disso = sem habilidade (estado "degradado").
DEGRADED_BSS = -0.02
HORIZONS = ("nowcast", "60m", "close")

_cache_lock = threading.Lock()
_cache: Dict[str, Any] = {}  # path -> (mtime, data)


def _load_json(path: str) -> Optional[dict]:
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    with _cache_lock:
        hit = _cache.get(path)
        if hit and hit[0] == mtime:
            return hit[1]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    with _cache_lock:
        _cache[path] = (mtime, data)
    return data


def _r(x, nd=4):
    if x is None:
        return None
    try:
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def _horizon_summary(h: dict) -> dict:
    rel = []
    for b in h.get("reliability") or []:
        if not isinstance(b, dict):
            continue
        rel.append({
            "bin_lo": _r(b.get("bin_lo", b.get("lo")), 2),
            "bin_hi": _r(b.get("bin_hi", b.get("hi")), 2),
            "n": b.get("n"),
            "p_mean": _r(b.get("p_mean", b.get("mean_p"))),
            "freq_up": _r(b.get("freq_up", b.get("obs_up", b.get("freq")))),
        })
    bss = _r(h.get("bss"))
    return {
        "role": h.get("role"),
        "n": h.get("n"),
        "n_sessions": h.get("n_sessions"),
        "base_rate": _r(h.get("base_up")),
        "auc": _r(h.get("auc")), "auc_lo": _r(h.get("auc_lo")), "auc_hi": _r(h.get("auc_hi")),
        "bss": bss, "bss_lo": _r(h.get("bss_lo")), "bss_hi": _r(h.get("bss_hi")),
        "ece": _r(h.get("ece")),
        "hit": _r(h.get("hit")),
        "degraded": bool(bss is not None and bss < DEGRADED_BSS),
        "reliability": rel,
    }


def summarize_target(data: dict, target: str, window: str) -> dict:
    """Resumo de um alvo a partir do JSON do harness (funcao pura, testavel)."""
    meta = data.get("meta") or {}
    t = (data.get("targets") or {}).get(target)
    if not isinstance(t, dict):
        return {"available": False, "target": target, "window": window,
                "reason": "alvo ausente no relatorio do harness"}
    horizons = t.get("horizons") or {}
    out_h = {k: _horizon_summary(horizons[k]) for k in HORIZONS if isinstance(horizons.get(k), dict)}
    base = {}
    for hz, bl in (t.get("baselines") or {}).items():
        if not isinstance(bl, dict):
            continue
        base[hz] = {name: {"auc": _r((v or {}).get("auc")), "hit": _r((v or {}).get("hit"))}
                    for name, v in bl.items() if isinstance(v, dict)}
    cfg = meta.get("config") or {}
    return {
        "available": True,
        "target": target,
        "window": window,
        "window_sessions": cfg.get("window_sessions"),
        "sessions": t.get("sessions"),
        "first_session": t.get("first_session"),
        "last_session": t.get("last_session"),
        "live_bars": t.get("live_bars"),
        "model": "nowcast",
        "harness_version": meta.get("harness_version"),
        "config_hash": meta.get("config_hash"),
        "code_git_sha": meta.get("code_git_sha"),
        "degraded_60m": bool(out_h.get("60m", {}).get("degraded", False)),
        "degraded_nowcast": bool(out_h.get("nowcast", {}).get("degraded", False)),
        "horizons": out_h,
        "baselines": base,
    }


def load_assertividade(target: str, window: str = "20", eval_dir: str = EVAL_LATEST_DIR) -> dict:
    """Resumo da assertividade de ``target`` na janela ``window`` ('20' ou 'full')."""
    window = str(window)
    if target not in EVAL_TARGETS:
        return {"available": False, "target": target, "window": window,
                "reason": "fora do escopo do v2.0 (so WIN$N e WDO$N)"}
    fname = WINDOWS.get(window)
    if not fname:
        return {"available": False, "target": target, "window": window,
                "reason": "janela invalida (use 20 ou full)"}
    path = os.path.join(eval_dir, fname)
    data = _load_json(path)
    if not data:
        return {"available": False, "target": target, "window": window,
                "reason": "relatorio do harness ainda nao gerado"}
    out = summarize_target(data, target, window)
    try:
        from datetime import datetime, timezone
        out["generated_at"] = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        out["generated_at"] = None
    return out
