"""Gera os relatórios em Markdown (pt-BR) das fases 17/18 a partir dos JSONs dos scripts de pesquisa.

Entradas (geradas por `research_fair_value.py`, `train_forecast.py`, `fase17_unit_fix.py` e
`compare_nowcast_versions.py`); saídas em `data/reports/` e resumos compactos em `data/eval/fase18/`.
Não lê nem escreve banco.

    python scripts/render_fase18_reports.py --in-dir %TEMP%\\irai_p1718\\out --tag 20261110
"""
from __future__ import annotations

import argparse
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def f(v, nd=3, pct=False, sign=False):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "—"
    if pct:
        s = f"{v * 100:.1f}"
    else:
        s = f"{v:+.{nd}f}" if sign else f"{v:.{nd}f}"
    return s.replace(".", ",")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("escrito:", os.path.relpath(path, ROOT))


# ── Fase 18: valor justo da cesta ─────────────────────────────────────────

def render_fair_value(r: dict) -> tuple[str, dict]:
    cfg = r["config"]
    L = ["# Valor justo da cesta — pesquisa da fase 18", ""]
    L.append(f"- **Script:** `scripts/research_fair_value.py` · **config hash:** `{r['config_hash']}` · seed {cfg['seed']} · bootstrap B = {cfg['n_boot']} por pregão")
    L.append(f"- **Período:** {cfg['start']} a {cfg['end']}; **desenho** até {cfg['design_end']}, **validação** depois (2026, nada escolhido nela)")
    L.append(f"- **Custos (ida e volta, por contrato):** " + ", ".join(f"{k} {f(v, 1)} pts" for k, v in cfg["costs_pts"].items()))
    L.append(f"- **Eventos:** primeiro cruzamento de |z| ≥ limiar na janela {cfg['entry_window']}; limiares {', '.join(f(x, 1) for x in cfg['thresholds'])}; direções contrarian (aposta no fechamento do gap) e segue; horizontes {', '.join(str(h * 5) + ' min' for h in cfg['horizons_bars'])} e fechamento")
    L.append(f"- **Testes por parte:** {r['n_tests_per_part']} (correção de Benjamini–Hochberg e Bonferroni dentro de cada parte)")
    L += ["", "Variantes:", ""]
    zdesc = {"perfil": "z = gap ÷ σ do gap no mesmo horário nos 60 pregões anteriores",
             "movel40": "z = gap ÷ desvio móvel de 40 barras (passadas)",
             "atual": "z com a padronização atual do engine (para comparação)"}
    for k, v in cfg["variants"].items():
        kind = "cesta completa" if v["kind"] == "basket" else "só o par WIN↔WDO"
        L.append(f"- `{k}`: {kind}, γ por OLS em {v['window']} pregões anteriores, incrementos de {v['step'] * 5} min; {zdesc.get(v['z'], v['z'])}")
    summary = {"config_hash": r["config_hash"], "targets": {}}
    for tg, t in r["targets"].items():
        L += ["", f"## {tg}", "", f"Pregões: {t['sessions']} ({t['first']} a {t['last']}).", "",
              "| Variante | Parte | Barras | |z| > 2 | desvio do z | AUC −z 15m | 30m | 60m | Eventos z≥2 | Líq. 60m (pts, IC 95%) | t | Fecha em 60m | Fecha no pregão | Parcela do alvo |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        summary["targets"][tg] = {}
        for vn, v in t["variants"].items():
            for part in ("desenho", "validacao"):
                p = v[part]
                ev = next((e for e in p["events"] if e["thr"] == 2.0 and e["direction"] == "contrarian"), {})
                n60 = "—" if ev.get("net_60m") is None else f"{f(ev['net_60m'], 1)} ({f(ev['net_60m_lo'], 1)} a {f(ev['net_60m_hi'], 1)})"
                L.append(f"| {vn} | {part} | {p['bars']} | {f(p['coverage_abs_gt2'], pct=True)}% | {f(p['z_std'], 2)} | "
                         f"{f(p['auc_y15'])} | {f(p['auc_y30'])} | {f(p['auc_y60'])} | {ev.get('events', 0)} | {n60} | {f(ev.get('t_60m'), 2)} | "
                         f"{f(ev.get('gap_closed_60m'), pct=True)}% | {f(ev.get('gap_closed_session'), pct=True)}% | {f(ev.get('gap_close_share_by_target_60m'), 2)} |")
                summary["targets"][tg].setdefault(vn, {})[part] = {
                    k: p[k] for k in ("bars", "sessions", "coverage_abs_gt2", "z_std", "auc_y15", "auc_y30", "auc_y60")}
                summary["targets"][tg][vn][part]["evento_z2_contrarian"] = {
                    k: ev.get(k) for k in ("events", "per_session", "net_15m", "net_60m", "net_60m_lo", "net_60m_hi", "t_60m",
                                           "hit_60m", "gap_closed_60m", "gap_closed_session", "gap_close_share_by_target_60m")}
        b = t["baselines"]
        L += ["", "Baselines (AUC por barra, sinal do retorno do dia): "
              + "; ".join(f"{part}: 60m momentum {f(b[part]['y60']['momentum'])} / contrarian {f(b[part]['y60']['contrarian'])}" for part in ("desenho", "validacao"))]
        summary["targets"][tg]["baselines"] = b
    # Testes que sobrevivem à correção
    L += ["", "## Correção para testes múltiplos", ""]
    for part in ("desenho", "validacao"):
        tests = [x for x in r["tests"] if x["part"] == part]
        sig_bh = [x for x in tests if x.get("q_bh") is not None and x["q_bh"] < 0.05]
        pos = [x for x in sig_bh if x["net"] > 0]
        best = sorted([x for x in tests if x.get("p") is not None], key=lambda x: x["p"])[:5]
        L.append(f"- **{part}:** {len(tests)} testes; {len(sig_bh)} com q (BH) < 0,05, dos quais {len(pos)} com P&L líquido positivo; "
                 f"{sum(1 for x in tests if (x.get('p_bonf') or 1) < 0.05)} passam Bonferroni.")
        for x in best:
            L.append(f"  - menor p: {x['target']} {x['variant']} z≥{f(x['thr'], 1)} {x['direction']} {x['h']}: n {x['n']}, líquido {f(x['net'], 1)} pts, t {f(x['t'], 2)}, p {f(x['p'], 4)}, q {f(x['q_bh'], 3)}")
        summary.setdefault("multiplos", {})[part] = {"testes": len(tests), "bh_q_lt_005": len(sig_bh), "bh_positivos": len(pos)}
    L += ["", "Leitura: um z bem padronizado tem |z| > 2 em ~5% das barras. Os z da cesta e do par com σ causal ficam perto disso; "
          "a construção atual (`par_ols20_z_atual`) dá dezenas de por cento. Nenhum descolamento previu o retorno das barras seguintes (AUC ≈ 0,50) "
          "e nenhum evento teve P&L líquido positivo que sobrevivesse à correção para testes múltiplos.", ""]
    return "\n".join(L) + "\n", summary


# ── Fase 18: p_fwd_60 walk-forward ───────────────────────────────────────

def render_forecast(r: dict) -> tuple[str, dict]:
    cfg = r["config"]
    L = ["# Modelo de 60 minutos (p_fwd_60) — walk-forward da fase 18", ""]
    L.append(f"- **Script:** `scripts/train_forecast.py` · **config hash:** `{r['config_hash']}` (pré-registro em `.config.json`) · seed {cfg['seed']}")
    L.append(f"- **Walk-forward:** blocos mensais a partir de {cfg['first_test_month']}, janela expansiva, embargo de {cfg['outer_embargo']} pregão; "
             f"interno purgado K = {cfg['inner_k']} com embargo de {cfg['inner_embargo']} pregões escolhe C ∈ {cfg['C_grid']} pelo Brier; "
             f"calibração Platt (isotônica só com n ≥ 20 mil e ECE menor); ensemble B = {cfg['n_ensemble']} para a faixa p_lo/p_hi; bootstrap B = {cfg['n_boot']} por pregão")
    L.append("- **Conjuntos de features:** " + "; ".join(f"`{k}` = {v}" for k, v in cfg["feature_sets"].items()))
    L.append("- **Critérios (SPEC §9):** BSS ≥ 0 fora da amostra, ECE ≤ 3 pp, AUC ≥ protótipo (" +
             ", ".join(f"{k} {f(v)}" for k, v in cfg["prototype_auc_60m"].items()) + ") e IC da AUC acima de 0,5")
    summary = {"config_hash": r["config_hash"], "targets": {}}
    for tg, t in r["targets"].items():
        L += ["", f"## {tg}", "", f"{t['rows']} barras de {t['sessions']} pregões ({t['first_session']} a {t['last_session']}); {len(t['splits'])} blocos de teste.", "",
              "| Conjunto | Período | n | AUC (IC 95%) | BSS (IC 95%) | ECE (pp) | Inclinação da confiabilidade | Desvio de p | Barras com p > 55% ou < 45% |",
              "|---|---|---|---|---|---|---|---|---|"]
        summary["targets"][tg] = {"decision": t["decision"], "baselines": t["baselines"], "delta_B_minus_A": t["delta_B_minus_A"], "sets": {}}
        for sn, s in t["sets"].items():
            summary["targets"][tg]["sets"][sn] = {}
            for per in ("oos", "oos_2025", "oos_2026"):
                m = s[per]
                L.append(f"| {sn} | {per.replace('oos', 'fora da amostra').replace('_', ' ')} | {m['n']} | {f(m['auc'])} ({f(m['auc_lo'])} a {f(m['auc_hi'])}) | "
                         f"{f(m['bss'], 4)} ({f(m['bss_lo'], 4)} a {f(m['bss_hi'], 4)}) | {f(m['ece'], pct=True)} | {f(m['rel_slope'], 2)} | {f(m['p_std'], 3)} | {f(m['p_share_gt55_lt45'], pct=True)}% |")
                summary["targets"][tg]["sets"][sn][per] = {k: m[k] for k in ("n", "auc", "auc_lo", "auc_hi", "bss", "bss_lo", "bss_hi", "ece", "rel_slope", "p_std", "p_share_gt55_lt45")}
        b, d, dec = t["baselines"], t["delta_B_minus_A"], t["decision"]
        L += ["", f"- Baselines no mesmo conjunto: momentum AUC {f(b['momentum_auc'])}, contrarian AUC {f(b['contrarian_auc'])}, taxa-base BSS 0.",
              f"- B − A (valor justo acrescentado): ΔBSS {f(d['d_bss'], 5, sign=True)} (IC {f(d['d_bss_ci'][0], 5)} a {f(d['d_bss_ci'][1], 5)}); "
              f"ΔAUC {f(d['d_auc'], 4, sign=True)} (IC {f(d['d_auc_ci'][0], 4)} a {f(d['d_auc_ci'][1], 4)}).",
              f"- Decisão pré-registrada: BSS ≥ 0 {'sim' if dec['bss_ge_0'] else 'não'}; ECE ≤ 3 pp {'sim' if dec['ece_le_3pp'] else 'não'}; "
              f"AUC ≥ protótipo {'sim' if dec['auc_vs_prototype'] else 'não'}; IC da AUC > 0,5 {'sim' if dec['auc_ci_above_05'] else 'não'} → **{dec['status']}**."]
    L += ["", "Leitura: o modelo calibrado aprende a não opinar (p quase sempre entre 45% e 55%), por isso o ECE é baixo e o BSS fica em torno de zero. "
          "Não há vantagem sobre a taxa-base nem sobre momentum/contrarian; o valor justo da cesta não acrescenta nada mensurável.", ""]
    return "\n".join(L) + "\n", summary


# ── Fase 17 ──────────────────────────────────────────────────────────────

def render_fase17(u: dict, cmp: dict) -> tuple[str, dict]:
    L = ["# Correção β/z e ruído do Kalman — fase 17", ""]
    L.append("- **Scripts:** `scripts/fase17_unit_fix.py` (análise e registro shadow) e `scripts/compare_nowcast_versions.py` (recálculo antigo × corrigido nas mesmas barras)")
    L.append("- **Bug:** β estimado com retornos brutos, mas o score somava β·z (z = r/σ). O preditor da regressão é Σ β·r = Σ (β·σ)·z. "
             "Correção: contribuição = β·σ·z ÷ score_scale; α e intercepto refeitos por logística sem o clamp visual.")
    L.append("- **Kalman:** R = variância real do resíduo intradiário (%²); Q = variância por barra da deriva dos β de janelas de 20 pregões.")
    L += ["", "## Janela de calibração (in-sample, 252 pregões)", "",
          "| Alvo | Janela | AUC antigo | AUC corrigido | AUC regressor | Acc antigo | Acc corrigido | Acc regressor | α novo | b novo | score_scale | R antigo → novo | Q antigo → novo |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    summary = {"calibracao": {}, "comparacao": {}}
    for slug, x in u.items():
        c, k, o = x["compare"], x["kalman"], x["old"]
        L.append(f"| {x['target']} | {x['window'][0]} a {x['window'][1]} | {f(c['auc_old'])} | {f(c['auc_fixed'])} | {f(c['auc_regressor'])} | "
                 f"{f(c['acc_old'], pct=True)}% | {f(c['acc_fixed'], pct=True)}% | {f(c['acc_regressor'], pct=True)}% | {f(c['alpha_fixed'], 3)} | {f(c['intercept_fixed'], 3, sign=True)} | "
                 f"{c['score_scale']:.4f} | {o['kalman_obs_cov']:.0e} → {k['kalman_obs_cov']:.3f} | {o['kalman_trans_cov']:.0e} → {k['kalman_trans_cov']:.1e} |".replace(".", ","))
        summary["calibracao"][x["target"]] = {"compare": c, "kalman": k, "old": o, "new_version": x.get("new_version")}
    L += ["", "AUC do score corrigido = AUC do regressor (mesma ordenação, por construção). A acurácia com P > 50% difere da do regressor porque o intercepto da logística "
          "desloca o corte; o regressor usa o intercepto da regressão de retornos.", "",
          "## Recálculo nas mesmas barras (engine v2, versão forçada)", ""]
    for tg, r in cmp.items():
        L += [f"### {tg}: `{r['old_version']}` × `{r['new_version']}`", "",
              f"{r['sessions']} pregões, {r['bars']} barras ({r['start']} a {r['end']}); fora da amostra = sessões ≥ {r['split']} (depois do fim da janela de calibração).", "",
              "| Versão | Parte | Nowcast AUC | Nowcast BSS (IC 95%) | Nowcast ECE (pp) | 60m AUC | 60m BSS | Fechamento AUC | Fechamento BSS | P < 20 ou > 80 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        summary["comparacao"][tg] = {}
        for v in ("old", "new"):
            for part, m in r[v].items():
                n, h, cl = m["nowcast"], m["60m"], m["close"]
                L.append(f"| {'atual' if v == 'old' else 'corrigida'} | {part.replace('_', ' ')} | {f(n['auc'])} | {f(n['bss'])} ({f(n.get('bss_lo'))} a {f(n.get('bss_hi'))}) | {f(n['ece'], pct=True)} | "
                         f"{f(h['auc'])} | {f(h['bss'])} | {f(cl['auc'])} | {f(cl['bss'])} | {f(m['p_extremos_lt20_gt80'], pct=True)}% |")
                summary["comparacao"][tg].setdefault(v, {})[part] = {
                    hz: {kk: m[hz].get(kk) for kk in ("n", "auc", "bss", "bss_lo", "bss_hi", "ece")} for hz in ("nowcast", "60m", "close")}
        L.append("")
    L += ["Nota: nos dois recálculos acima o Kalman começa do zero em cada pregão (cópia sem estado salvo), para comparar as versões "
          "nas mesmas condições. Numa cópia do banco com o estado salvo do live, a versão atual usa esse estado a partir de 29/10 e "
          "fica com nowcast fora da amostra WIN AUC 0,756 / BSS 0,154 e WDO 0,667 / −0,911; a corrigida não tem estado salvo e dá os "
          "mesmos números da tabela. O WDO fora da amostra (9 pregões) está mal calibrado nas duas versões (ECE ~31 pp).", ""]
    L += ["Leitura: a versão corrigida descreve melhor o dia (nowcast) nas mesmas barras. Ela continua sem prever os próximos 60 minutos "
          "(BSS negativo nos dois casos); por isso o painel passa a chamá-la de leitura do dia quando `forecast_ui` for ligado.", ""]
    return "\n".join(L) + "\n", summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--tag", default="20261110")
    a = ap.parse_args()
    rep = os.path.join(ROOT, "data", "reports")
    ev = os.path.join(ROOT, "data", "eval", "fase18")
    fv_md, fv_s = render_fair_value(load(os.path.join(a.in_dir, "fair_value.json")))
    write(os.path.join(rep, f"fase18_valor_justo_{a.tag}.md"), fv_md)
    fc_md, fc_s = render_forecast(load(os.path.join(a.in_dir, "forecast_wf.json")))
    write(os.path.join(rep, f"fase18_p_fwd_60_walkforward_{a.tag}.md"), fc_md)
    u = load(os.path.join(a.in_dir, "fase17_unit_fix.json"))
    cmp = {}
    for slug in ("win", "wdo"):
        p = os.path.join(a.in_dir, f"cmp_{slug}.json")
        if os.path.exists(p):
            c = load(p)
            cmp[c["target"]] = c
    f17_md, f17_s = render_fase17(u, cmp)
    write(os.path.join(rep, f"fase17_correcao_beta_z_{a.tag}.md"), f17_md)
    for name, obj in (("valor_justo", fv_s), ("p_fwd_60", fc_s), ("fase17", f17_s)):
        write(os.path.join(ev, f"{name}_{a.tag}.json"), json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
