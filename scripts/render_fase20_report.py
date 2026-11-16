"""Relatório markdown da fase 20 a partir do JSON de `research_gex_pa.py` (somente leitura)."""
from __future__ import annotations

import argparse
import json

NAMES = {"A_T0_C0": "A · zona sozinha (T0)", "B_T1_C0": "B · zona + rejeição (T1)", "B_T2_C0": "B · zona + falso rompimento (T2)",
         "B_T3_C0": "B · zona + rompimento/reteste (T3)", "C_T1_C1": "C · T1 + valor justo (C1)", "C_T2_C1": "C · T2 + valor justo (C1)",
         "C_T3_C1": "C · T3 + valor justo (C1)", "Cp_T1_C2": "C' · T1 + direção da cesta (C2)", "Cp_T2_C2": "C' · T2 + direção da cesta (C2)",
         "Cp_T3_C2": "C' · T3 + direção da cesta (C2)"}


def f(x, d=1):
    return "—" if x is None else f"{x:.{d}f}".replace(".", ",")


def render(r: dict) -> str:
    L = [f"# Fase 20 — regiões de GEX + gatilho de price action (config `{r['config_hash']}`)", "",
         f"Família de decisão: {r['n_family']} testes (BH q < {r['config']['fdr_q']}). Desenho até {r['config']['design_end']}; validação depois. "
         "P&L líquido por operação em pontos (custo WIN 10, WDO 1). IC 95% por bootstrap de sessões (2.000).", ""]
    for t, v in r["targets"].items():
        L += [f"## {t}: veredito **{v['verdict']}**", "",
              f"{v['sessions']} sessões ({v['first']} a {v['last']}; desenho {v['sessions_design']}, validação {v['sessions_validation']}); "
              f"fonte do GEX: {v['gex_source_counts']}; excluídas por gap > 2%: {', '.join(v['excluded']['gap']) or 'nenhuma'}.", "",
              "| Braço | n | Média líq. | IC 95% | Desenho (n; média) | Validação (n; média) | Acerto | q BH | P1 média | Δ vs P1 IC | P2 pct | Status |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for a, s in v["arms"].items():
            c = v["controls"][a]
            if s["n"] == 0:
                L.append(f"| {NAMES[a]} | 0 | — | — | — | — | — | — | — | — | — | {s['status']} |"); continue
            L.append(f"| {NAMES[a]} | {s['n']} | {f(s['mean_net'])} | [{f(s['ci'][0])}; {f(s['ci'][1])}] | "
                     f"{s['design']['n']}; {f(s['design']['mean_net'])} | {s['validation']['n']}; {f(s['validation']['mean_net'])} | "
                     f"{f(100 * s['hit'], 0)}% | {f(s['q_bh'], 2)} | {f(c['p1_mean'])} | [{f(c['p1_diff_ci'][0])}; {f(c['p1_diff_ci'][1])}] | "
                     f"{f(100 * c['p2_pct'], 0) if c['p2_pct'] is not None else '—'}% | {s['status']} |")
        L += ["", "Sensibilidade (média líquida): k=0,25 / k=1,0 / 2× custo / sem stop (60 min fixo) / N0 (todas as walls)", ""]
        for a, s in v["arms"].items():
            if s["n"] == 0:
                continue
            c = v["controls"][a]
            L.append(f"- {NAMES[a]}: {f(c['k_sens'].get('0.25'))} / {f(c['k_sens'].get('1.0'))} / {f(s['mean_net_2xcost'])} / "
                     f"{f(s['fixed60_mean'])} / {f(v['n0'][a].get('mean_net'))} (n={v['n0'][a]['n']})")
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.json, encoding="utf-8") as fh:
        r = json.load(fh)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render(r))


if __name__ == "__main__":
    main()