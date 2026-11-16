# Phase 20 Summary 01: Regiões de GEX + Gatilho de Price Action (pesquisa W1–W4)

**Executada:** 10/11/2026, ~21:30–22:00 BRT (worktree `rastro_irado_wt_f17_18`, branch local `v2/fase-20-gex-pa` a partir de `751fb43`; sem commit, sem push, sem deploy).
**Escopo:** só pesquisa (W1–W4). W5/W6 (shadow ao vivo, painel, API) **não** foram feitos.
**Config pré-registrada:** `c985f6b2365e`, congelada às 21:37 BRT (`data/eval/fase20/config_c985f6b2365e.json`) antes da execução; resultado `data/eval/fase20/gexpa_c985f6b2365e.json`; relatório `data/reports/fase20_gex_pa_20261110.md`. Duas execuções deram JSON idêntico.

## Veredito
| Ativo | Veredito | Melhor braço | n | Média líquida/op. | IC 95% (sessões) | Bate P1? | P2 (percentil) |
|---|---|---|---|---|---|---|---|
| WIN$N | **INCONCLUSIVO** | C · T3 rompimento/reteste + valor justo (C1) | 147 | +29,4 pts | −49,2 a +113,7 | não (Δ IC −52,1 a +156,3) | 81% (precisava ≥ 95%) |
| WDO$N | **NO-GO** | B · T1 rejeição, sem filtro | 108 | +0,19 pt | −1,80 a +2,15 | não (Δ IC −0,48 a +3,83) | 90% |

- **Nenhum braço passou** nos critérios de GO (§6): nenhum IC acima de 0, nenhum q (BH) < 0,05 com média positiva, nenhum vence o controle P1 com IC, nenhum chega ao percentil 95 do placebo P2.
- WIN: a zona sozinha (T0) perde (−11,3 pts; n 271). Os braços com rastro C1 têm média positiva (T1 +49,1; T2 +39,5; T3 +29,4), mas com IC largo; só T2 e T3 + C1 são positivos nas duas metades (→ INCONCLUSIVO). O T3 + C1 concentra o ganho em outubro (10 operações, média +351,5, ou seja 3.515 dos 4.315 pts do total).
- WDO: todos os braços com rastro e com gatilhos T2/T3 são negativos; três têm média **significativamente negativa** (B·T2 −3,51, q 0,04; C·T3 −2,19, q 0,02; B·T3 −1,17, IC −2,09 a −0,18). O custo de 1 pt domina.
- O filtro do rastro (C − B) não teve IC acima de 0 em nenhum braço (WIN T3: −38,6 a +87,4; T1: −38,4 a +93,4).
- As grades placebo (P2) e o mesmo gatilho fora das zonas (P1) dão médias da mesma ordem: não há evidência de que o nível de GEX seja o que gera o resultado.

## Dados usados
- GEX: CSV oficial do projeto WDO (`mt5/Files/jumba_gex_win_history.csv`, 221 sessões; `..._wdo_history.csv`, 217; 02/01–10/11/2026), lido sem alterar (sha `e61957d4b3f3f4f4` / `6baebff0437a7e06`). Jan–mai valem como as-of (decisão do owner). Fallback `gex_levels` (primeiro run < 09:00): 0 sessões usadas no WIN e no WDO (as 2 datas do WDO sem CSV, 07/09 e 12/10, são feriados sem barras).
- Sessões: WIN 208 (desenho 118, validação 90), WDO 211 (121/90). Excluídas por gap de abertura > 2%: WIN 18/02, 08/04, 15/04, 05/10, 26/10; WDO 05/10, 26/10. Fim de semana fora (23/05, 29/08, 01/11 no CSV).
- Auditoria (W1, `data/eval/fase20/gex_auditoria_20261110.json`): mediana de 34 níveis e 6 níveis primários (N1) por sessão; 1 sessão do WIN (22/05) sem algum nível de gama. CSV × primeiro run < 09:00 do banco nas datas em comum: flip com diferença mediana 0,002 pt (WIN, máx. 0,005) e 0 (WDO, máx. 29,89); conjunto N1 idêntico em 95/118 (WIN) e 104/114 (WDO).
- Contexto do rastro: valor justo da cesta (fase 18) recalculado de forma causal desde 01/09/2025; algum fator stale em 2,7% das barras de 2026 (alerta não sai nos braços C).

## Critérios (20-PLAN-01 §6)
1. IC 95% acima de 0 — **não** (nenhum braço).
2. Média > 0 nas duas metades com n ≥ 30 — só WIN C·T3+C1 (96 / 51 operações; +15,7 / +55,1).
3. q (BH) < 0,05 — nenhum braço com média positiva.
4. Controles (P1 com IC > 0 e P2 ≥ percentil 95) — **não**.
5. Robustez (2× custo, k 0,25 e 1,0) — WIN C·T3+C1, C·T2+C1 e B·T2 mantêm sinal positivo; WDO nenhum.
6. Filtro do rastro adotado — **não** (IC da diferença contém 0).

## Ressalvas
- Poder: com 13–297 operações por braço, o IC do melhor braço do WIN (n 147) tem 163 pts de largura (−49,2 a +113,7); efeitos menores que isso não aparecem.
- Ambiguidade intrabarra (stop e alvo na mesma barra M5): 0% das operações no WIN e ≤ 1% no WDO; checagem com M1 não foi feita.
- Sem stop/alvo (saída fixa em 60 min) o melhor braço do WIN fica negativo (−52,1 pts): o resultado depende do bracket.
- Regime do flip (descritivo): WIN C·T1+C1 +143,5 acima do flip (n 31) e −48,5 abaixo (n 30); não testado como hipótese.
- O histórico de jan–mai foi reconstruído pelo projeto WDO com OI de D−1; tratado como oficial por decisão do owner.

## Testes
- Novos: `tests/test_gex_asof.py` (4), `tests/test_pa_triggers_causal.py` (6, inclui truncamento em 25 séries aleatórias), `tests/test_trade_sim.py` (6).
- Suíte completa numa cópia isolada com cópia do banco (`%TEMP%\irai_p20\suite`): **128 passed**. No worktree sem banco real: 123 passed, 5 falham por falta de dados (`test_api_nwe`, `test_engine`, 3 de `test_engine_session_invariants`); a rodada de base no worktree criou um `data/irai_live.db` vazio (ignorado pelo git), que faz esses 3 testes saírem de "skipped" para "failed".

## Decisões abertas (owner)
1. WIN: manter o braço C·T3+C1 só em acompanhamento offline (reavaliar com mais pregões) ou encerrar? Nada vai para o painel.
2. WDO: encerrar a linha GEX+PA (NO-GO) e manter o GEX só como linha no gráfico.
3. Próximo passo de pesquisa: fluxo (`cum_delta`, fase 20b) ou outra forma de região (força por strike `gex`), com novo pré-registro.

## Key Files
- Novos: `backend/irai/gex_asof.py`, `backend/eval/pa_triggers.py`, `backend/eval/trade_sim.py`, `scripts/research_gex_pa.py`, `scripts/audit_gex_history.py`, `scripts/render_fase20_report.py`, os 3 testes acima, `data/eval/fase20/*.json`, `data/reports/fase20_gex_pa_20261110.md`.
- Sem alteração em código existente.