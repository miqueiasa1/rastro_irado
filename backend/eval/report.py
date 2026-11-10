"""
Saídas do harness (fase 15): relatório Markdown, JSON e store próprio de métricas.

O store `forecast_eval_daily` fica num SQLite SEPARADO (padrão `data/eval/forecast_eval.db`),
nunca no `irai_live.db`: nesta fase o schema do banco de produção não é alterado. A tabela
segue o schema do SPEC §10.6 para poder ser migrada depois sem conversão.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3

FORECAST_EVAL_DAILY_DDL = """
CREATE TABLE IF NOT EXISTS forecast_eval_daily (
    eval_date     TEXT NOT NULL,
    target        TEXT NOT NULL,
    model         TEXT NOT NULL,
    version_id    TEXT,
    horizon       TEXT NOT NULL,
    window_sessions INTEGER NOT NULL,
    n             INTEGER, auc REAL, auc_lo REAL, auc_hi REAL,
    brier REAL, bss REAL, ece REAL, hit REAL,
    config_hash   TEXT, code_git_sha TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (eval_date, target, model, horizon, window_sessions)
)
"""


def _clean(o):
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else round(o, 6)
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "item"):
        return _clean(o.item())
    return o


def to_json(result: dict) -> str:
    return json.dumps(_clean(result), ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def write_text(path: str, text: str, overwrite: bool = True) -> None:
    """Grava UTF-8 sem BOM com LF. Com overwrite=False, recusa sobrescrever (baseline imutável)."""
    if not overwrite and os.path.exists(path):
        raise FileExistsError(f"{path} já existe (baseline congelada é imutável)")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def persist_rows(store_path: str, rows: list[dict]) -> int:
    """Grava as métricas no store próprio. Recusa caminhos do banco de produção."""
    base = os.path.basename(store_path).lower()
    if base in ("irai_live.db", "irai.db", "market_data.db", "irai_data.db"):
        raise ValueError("o store de avaliação não pode ser o banco de produção")
    os.makedirs(os.path.dirname(os.path.abspath(store_path)), exist_ok=True)
    conn = sqlite3.connect(store_path)
    try:
        conn.execute(FORECAST_EVAL_DAILY_DDL)
        cols = ["eval_date", "target", "model", "version_id", "horizon", "window_sessions", "n", "auc",
                "auc_lo", "auc_hi", "brier", "bss", "ece", "hit", "config_hash", "code_git_sha"]
        data = [tuple(_clean(r.get(c)) for c in cols) for r in rows]
        conn.executemany(
            f"INSERT OR REPLACE INTO forecast_eval_daily ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            data,
        )
        conn.commit()
        return len(data)
    finally:
        conn.close()


def _f(v, nd=3, pct=False):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if pct:
        return f"{v * 100:.1f}".replace(".", ",")
    return f"{v:.{nd}f}".replace(".", ",")


def _ci(m, key, nd=3):
    return f"{_f(m[key], nd)} ({_f(m[key + '_lo'], nd)} a {_f(m[key + '_hi'], nd)})"


def render_markdown(result: dict, title: str) -> str:
    meta = result["meta"]
    cfg = meta["config"]
    L = [f"# {title}", ""]
    L.append(f"- **Gerado pelo harness** `scripts/eval_assertividade.py` (versão {meta['harness_version']})")
    L.append(f"- **Modelo avaliado:** P(↑) atual gravado em `irai_live_snapshots` (nowcast), sem recálculo")
    L.append(f"- **Período:** sessões {cfg['start']} a {cfg['end']}" +
             (f" (só os últimos {cfg['window_sessions']} pregões com barras ao vivo)" if cfg.get("window_sessions") else "") +
             (f"; corte de dados (as-of) {cfg['as_of_utc']} UTC" if cfg.get("as_of_utc") else ""))
    L.append(f"- **Fonte:** `{os.path.basename(meta['source_db'])}` aberto em `mode=ro`")
    L.append(f"- **git SHA:** `{meta['code_git_sha']}` · **config hash:** `{meta['config_hash']}` · **seed:** {cfg['seed']} · **bootstrap:** B = {cfg['n_boot']} por pregão")
    L.append(f"- **Horizonte primário:** {meta['primary_horizon']} (decisão D1); **secundário:** fechamento (só avaliação)")
    L.append("")
    L.append("Convenções: " + "; ".join(f"{k}: {v}" for k, v in meta["conventions"].items()) + ".")
    L.append("")
    for t, r in result["targets"].items():
        cov = r["coverage"]
        L += [f"## {t}", ""]
        L.append(f"- Pregões com barras ao vivo: {r['sessions']} ({r['first_session']} a {r['last_session']}); barras ao vivo: {r['live_bars']}")
        L.append(f"- Barras com snapshot que são ao vivo: {_f(cov['live_share_of_snapshots'], pct=True)}% ({cov['live_snapshots']} de {cov['snapshot_bars']}); "
                 f"cobertura sobre todas as barras do pregão: {_f(cov['bar_coverage'], pct=True)}% ({cov['live_snapshots']} de {cov['bars']}, {cov['bar_sessions']} pregões com barras)")
        L.append(f"- Atraso de gravação (created_at − abertura da barra), mediana: {_f(cov['lag_median_min'], 2)} min (todas) / {_f(cov['lag_median_live_min'], 2)} min (ao vivo)")
        pdist = r["p_distribution"]
        L.append(f"- Barras com P < 20 ou P > 80: {_f(pdist['share_extreme_lt20_gt80'], pct=True)}%")
        L += ["", "| Horizonte | Papel | n | Pregões | Taxa de alta | AUC (IC 95%) | BSS (IC 95%) | ECE (pp) | Hit | Empates excl. |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for h, m in r["horizons"].items():
            L.append(f"| {h} | {m['role']} | {m['n']} | {m['n_sessions']} | {_f(m['base_up'], pct=True)}% | {_ci(m, 'auc')} | {_ci(m, 'bss')} | {_f(m['ece'], pct=True)} | {_f(m['hit'], pct=True)}% | {m['ties_excluded']} |")
        L += ["", "**Baselines (REQ-V06), AUC / hit:**", "", "| Horizonte | Taxa-base (alta) | Momentum (retorno do dia) | Contrarian (−retorno do dia) |", "|---|---|---|---|"]
        for h, b in r["baselines"].items():
            L.append(f"| {h} | {_f(b['base_rate']['base_up'], pct=True)}% | {_f(b['momentum']['auc'])} / {_f(b['momentum']['hit'], pct=True)}% | {_f(b['contrarian']['auc'])} / {_f(b['contrarian']['hit'], pct=True)}% |")
        for h in ("60m", "nowcast"):
            L += ["", f"**Confiabilidade — {h}:**", "", "| Bin de P | n | P médio | Freq. de alta |", "|---|---|---|---|"]
            for row in r["horizons"][h]["reliability"]:
                if row["n"]:
                    L.append(f"| {int(row['bin_lo']*100)}–{int(row['bin_hi']*100)} | {row['n']} | {_f(row['p_mean'], pct=True)}% | {_f(row['freq_up'], pct=True)}% |")
        L += ["", "**Marcadores visuais (REQ-V07, parcial), retorno médio em bp (IC 95%) e hit:**", "",
              "| Marcador | n | Por pregão | 60 min bp | 60 min hit | Fechamento bp |", "|---|---|---|---|---|---|"]
        for mk in r["markers"]:
            def bp(lab):
                return "—" if mk.get(f"bp_{lab}") is None else f"{_f(mk[f'bp_{lab}'], 2)} ({_f(mk[f'bp_{lab}_lo'], 2)} a {_f(mk[f'bp_{lab}_hi'], 2)})"
            L.append(f"| {mk['marker']} | {mk['n']} | {_f(mk['per_session'], 1)} | {bp('60m')} | {_f(mk.get('hit_60m'), pct=True)}% | {bp('close')} |")
        ev = r.get("spread_events") or []
        if ev:
            L += ["", f"**Descolamentos gravados ao vivo como eventos (fase 18): cobertura de |z| > 2 e P&L por evento "
                      f"(contrarian, pontos por contrato, líquido de {_f(ev[0].get('cost_pts'), 1)} pts de custo; IC 95% por pregão):**", "",
                  "| z | Barras com |z| > 2 | Eventos | Por pregão | 15 min líq. | 60 min líq. (IC 95%) | Hit 60 min | t 60 min | Fechamento líq. |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for e in ev:
                n60 = "—" if e.get("net_60m") is None else f"{_f(e['net_60m'], 1)} ({_f(e['net_60m_lo'], 1)} a {_f(e['net_60m_hi'], 1)})"
                L.append(f"| {e['z']} | {_f(e.get('coverage_abs_gt2'), pct=True)}% | {e['events']} | {_f(e['per_session'], 2)} | "
                         f"{_f(e.get('net_15m'), 1)} | {n60} | {_f(e.get('hit_60m'), pct=True)}% | {_f(e.get('t_60m'), 2)} | {_f(e.get('net_close'), 1)} |")
            L.append("")
            L.append("Um z bem padronizado tem |z| > 2 em cerca de 5% das barras; muito acima disso, o z não é um z de verdade.")
        for key, lab in (("hour", "hora (BRT)"), ("month", "mês"), ("vol_tercile", "tercil de vol. realizada do pregão")):
            L += ["", f"**Segmentação por {lab} (REQ-V05), AUC / BSS:**", "",
                  f"| {lab} | Barras | Pregões | 60 min | Fechamento | Nowcast |", "|---|---|---|---|---|---|"]
            for row in r["segments"][key]:
                L.append(f"| {row[key]} | {row['n_bars']} | {row['n_sessions']} | {_f(row['auc_60m'])} / {_f(row['bss_60m'])} | {_f(row['auc_close'])} / {_f(row['bss_close'])} | {_f(row['auc_nowcast'])} / {_f(row['bss_nowcast'])} |")
        L.append("")
    return "\n".join(L) + "\n"
