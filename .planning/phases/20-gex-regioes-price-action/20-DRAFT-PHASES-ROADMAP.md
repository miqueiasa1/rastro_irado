# Rascunho: atualização de PHASES.md e ROADMAP.md para a fase 20

**Status:** rascunho para aprovação; PHASES.md e ROADMAP.md **não** foram alterados. Aplicar só depois do "ok" do owner (D20‑1).

## Substituir em `.planning/milestones/v2.0-metodologia/PHASES.md`, seção "Phase 20"

### Phase 20: Regiões de GEX + Gatilho de Price Action, com o Rastro como Contexto
* **Slug:** `20-gex-regioes-price-action` (antes: `20-gex-e-fluxo-como-features`)
* **Goal:** Testar se alertas "zona de GEX as-of + gatilho de price action + direção do rastro" têm P&L líquido de custos positivo e estável em 60 min, por ativo (WIN$N, WDO$N), e mostrá-los como apoio à decisão se passarem.
* **Princípio do owner (10/11/2026):** o rastro dá o contexto, o GEX dá a região e o price action dá o gatilho.
* **Escopo:** seleção as-of do GEX e flag `gex_asof_ok` (§16); zonas por ATR; filtros C1 (valor justo) e C2 (direção da cesta); gatilhos T0–T3; simulador com stop/alvo/tempo e custos; ablação zona × zona+gatilho × zona+gatilho+rastro com placebos; BH em família fixa de 20 testes; se aprovado, versão `gexpa` em shadow, tabelas append-only e UI atrás de `gexpa_ui`.
* **Requirements:** REQ-G01, REQ-G02, REQ-G04 (adaptado a eventos); REQ-G03 (fluxo) passa para a 20b.
* **Entregáveis:** `20-CONTEXT.md`, `20-PLAN-01.md`; auditoria do histórico de `gex_levels`; `data/reports/fase20_gex_pa_<data>.md`; `20-SUMMARY-01.md` com a decisão.
* **Success Criteria:**
  1. Nenhuma sessão sem `gex_asof_ok = 1` na amostra principal (teste).
  2. Teste de causalidade dos gatilhos verde (truncar em t não muda sinais ≤ t).
  3. Decisão por ativo GO / INCONCLUSIVO / NO-GO com os números dos critérios da §6 do plano, em ≥ 40 pregões elegíveis **[META]**.
  4. Se GO: 40 pregões de shadow ao vivo com média líquida > 0 e IC acima de 0 antes de tirar o selo "em avaliação" **[META]**.
* **Depende de:** 15 (harness), 16 (registro), 18 (valor justo causal). A 19 deixa de ser pré-requisito (p_fwd_60 rejeitado).
* **Medido em 10/11/2026:** com o CSV oficial, 208 (WIN) / 211 (WDO) sessões de 2026 (antes: 115 / 113 só com o banco); ~1,3 entrada por pregão nas walls fortes; a grade completa de walls cobre ~49% das barras do WIN com ±0,5 ATR (não seletiva); `/api/gex` mostra run posterior ao pregão em 75 sessões.
* **Status:** Pesquisa W1–W4 concluída em 10/11/2026 (config `c985f6b2365e`): **WIN$N INCONCLUSIVO** (melhor braço T3 + valor justo: +29,4 pts/op., n 147, IC −49,2 a +113,7; não bate os controles), **WDO$N NO-GO** (melhor braço +0,19 pt/op., n 108, IC −1,80 a +2,15). Nada ligado ao vivo; GEX segue só como linha no gráfico. Ver `phases/20-gex-regioes-price-action/20-SUMMARY-01.md`.

### Phase 20b (nova, opcional): Fluxo (delta acumulado) como contexto
* **Goal:** Avaliar `cum_delta_norm` como filtro adicional dos alertas da fase 20, pelo mesmo protocolo.
* **Observação:** delta M5 do WDO só existe desde abr–mai/2026.
* **Status:** Não iniciada · **Depende de:** 20.

## Substituir em `.planning/ROADMAP.md`, bloco "Phase 20"

### Phase 20: Regiões de GEX + Gatilho de Price Action (rastro como contexto)
* **Goal:** Alertas de apoio à decisão "zona de GEX as-of + gatilho de price action + direção do rastro", aceitos só com P&L líquido > 0, estável fora da amostra e melhor que zona sozinha e placebos.
* **Status:** Pesquisa concluída (10/11/2026): WIN INCONCLUSIVO, WDO NO-GO; sem shadow nem UI (ver `phases/20-gex-regioes-price-action/20-SUMMARY-01.md`) · **Depende de:** 15, 16, 18
* **Success Criteria:** só sessões com GEX as-of; gatilhos sem lookahead; decisão por ativo em ≥ 40 pregões; shadow de 40 pregões antes de tirar o selo.

## Ajustes relacionados
- PHASES.md, diagrama de dependências: `18 ──► 20` direto (sem passar pela 19); 22 depende de 20 só se houver versão `gexpa` em shadow.
- STATE.md: "Phase 20 (pesquisa W1–W4) concluída em 10/11/2026 na branch local `v2/fase-20-gex-pa`, sem commit: WIN INCONCLUSIVO, WDO NO-GO. Q5 resolvida pelo owner: CSV oficial do projeto WDO; fallback = primeiro run < 09:00."