"""
Harness de assertividade do IRAI (milestone v2.0, fase 15).

Avalia o P(↑) atual gravado em `irai_live_snapshots` contra os retornos futuros de
`market_bars` (60 min primário, fechamento secundário, 5/15/30 min e nowcast no relatório).
Abre o banco SOMENTE em modo leitura (`mode=ro`). Não importa nem altera o live.

Exemplos (PowerShell, na raiz do repo):

  # relatório do período inteiro até hoje
  python scripts/eval_assertividade.py --start 2026-08-03

  # últimos 20 pregões com barras ao vivo, grava no store próprio (data/eval/forecast_eval.db)
  python scripts/eval_assertividade.py --window-sessions 20 --persist

  # congelar a baseline (recusa sobrescrever arquivos existentes)
  python scripts/eval_assertividade.py --start 2026-08-03 --end 2026-11-10 \
      --as-of "2026-11-10 13:50:00" --freeze 20261110

  # conferir uma execução contra a baseline congelada (tolerância de AUC ±0,005)
  python scripts/eval_assertividade.py --start 2026-08-03 --end 2026-11-10 \
      --as-of "2026-11-10 13:50:00" --check-baseline data/eval/baseline/assertividade_baseline_20261110.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.eval.harness import DEFAULT_TARGETS, EvalConfig, metric_rows, run_evaluation  # noqa: E402
from backend.eval.report import persist_rows, render_markdown, to_json, write_text  # noqa: E402

DEFAULT_DB = os.path.join(ROOT, "data", "irai_live.db")
EVAL_DIR = os.path.join(ROOT, "data", "eval")
REPORT_DIR = os.path.join(ROOT, "data", "reports")


def brt_today() -> str:
    from backend.timeconv import brt_today as _t
    return _t()


def window_start(end: str, n: int) -> str:
    """Início folgado (3 dias corridos por pregão); o corte exato nos últimos N pregões com
    barras ao vivo é feito pelo harness (EvalConfig.window_sessions)."""
    from datetime import date, timedelta
    return (date.fromisoformat(end) - timedelta(days=3 * n + 7)).isoformat()


def compare_with_baseline(result: dict, baseline_path: str, tol: float) -> list[str]:
    with open(baseline_path, encoding="utf-8") as f:
        base = json.load(f)
    problems = []
    for t, r in base["targets"].items():
        cur = result["targets"].get(t)
        if cur is None:
            problems.append(f"{t}: ausente na execução atual")
            continue
        for h, m in r["horizons"].items():
            a, b = cur["horizons"][h]["auc"], m["auc"]
            if a is None or b is None or abs(a - b) > tol:
                problems.append(f"{t} {h}: AUC {a} vs baseline {b} (tolerância {tol})")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DEFAULT_DB, help="banco fonte (aberto só leitura)")
    ap.add_argument("--start", help="primeira sessão (YYYY-MM-DD)")
    ap.add_argument("--end", help="última sessão (YYYY-MM-DD; padrão: hoje em BRT)")
    ap.add_argument("--window-sessions", type=int, help="usa as últimas N sessões até --end")
    ap.add_argument("--as-of", help="corte de dados em UTC real, ex. '2026-11-10 13:50:00'")
    ap.add_argument("--targets", nargs="+", default=list(DEFAULT_TARGETS))
    ap.add_argument("--live-max-lag", type=float, default=10.0, help="REQ-V02: minutos após a abertura da barra")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", help="caminho do JSON de saída (padrão: data/eval/latest/assertividade.json)")
    ap.add_argument("--report", help="caminho do Markdown (padrão: data/reports/assertividade_<fim>.md)")
    ap.add_argument("--no-report", action="store_true")
    ap.add_argument("--persist", action="store_true", help="grava métricas no store próprio (não no irai_live.db)")
    ap.add_argument("--store", default=os.path.join(EVAL_DIR, "forecast_eval.db"))
    ap.add_argument("--freeze", metavar="TAG", help="congela a baseline com esta tag (arquivos imutáveis)")
    ap.add_argument("--check-baseline", metavar="JSON")
    ap.add_argument("--tol", type=float, default=0.005)
    a = ap.parse_args(argv)

    end = a.end or brt_today()
    if a.window_sessions:
        start = window_start(end, a.window_sessions)
    elif a.start:
        start = a.start
    else:
        ap.error("informe --start ou --window-sessions")

    cfg = EvalConfig(start=start, end=end, targets=tuple(a.targets), as_of_utc=a.as_of,
                     live_max_lag_min=a.live_max_lag, n_boot=a.n_boot, seed=a.seed,
                     window_sessions=a.window_sessions)
    t0 = time.time()
    result = run_evaluation(a.db, cfg, repo_dir=ROOT)
    result["meta"]["elapsed_s"] = round(time.time() - t0, 2)

    for t, r in result["targets"].items():
        h = r["horizons"]
        print(f"{t}: {r['sessions']} pregões, {r['live_bars']} barras ao vivo | "
              f"AUC 60m {h['60m']['auc']:.3f} ({h['60m']['auc_lo']:.3f}-{h['60m']['auc_hi']:.3f}) BSS {h['60m']['bss']:.3f} | "
              f"close {h['close']['auc']:.3f} | nowcast {h['nowcast']['auc']:.3f}")

    tag = end.replace("-", "") + (f"_ultimos{a.window_sessions}" if a.window_sessions else "")
    if a.freeze:
        jpath = os.path.join(EVAL_DIR, "baseline", f"assertividade_baseline_{a.freeze}.json")
        rpath = os.path.join(REPORT_DIR, f"assertividade_baseline_{a.freeze}.md")
        write_text(jpath, to_json(result), overwrite=False)
        write_text(rpath, render_markdown(result, f"Assertividade — baseline congelada {a.freeze} (modelo atual)"), overwrite=False)
        print("baseline congelada:", jpath, rpath)
    else:
        jpath = a.json or os.path.join(EVAL_DIR, "latest", f"assertividade{'_ultimos%d' % a.window_sessions if a.window_sessions else ''}.json")
        write_text(jpath, to_json(result))
        print("json:", jpath)
        if not a.no_report:
            rpath = a.report or os.path.join(REPORT_DIR, f"assertividade_{tag}.md")
            label = f"últimos {a.window_sessions} pregões até {end}" if a.window_sessions else f"{start} a {end}"
            write_text(rpath, render_markdown(result, f"Assertividade do rastro — {label}"))
            print("relatório:", rpath)

    if a.persist:
        n = persist_rows(a.store, metric_rows(result, eval_date=end,
                                              window_label=a.window_sessions))
        print(f"store: {n} linhas em {a.store}")

    if a.check_baseline:
        problems = compare_with_baseline(json.loads(to_json(result)), a.check_baseline, a.tol)
        if problems:
            print("DIVERGE da baseline:\n  " + "\n  ".join(problems))
            return 2
        print(f"OK: todas as AUC dentro de ±{a.tol} da baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
