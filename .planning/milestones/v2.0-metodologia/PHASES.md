# Fases GSD — Milestone v2.0 Metodologia Preditiva Calibrada

**Status:** todas não iniciadas · **Data:** 2026-11-10 · **Revisão:** decisões D1–D4 de 10/11/2026 aplicadas (PRD §12.1)

**Decisões que valem para todas as fases:** D1 horizonte de produto = 60 min (fechamento só avaliação) · D2 só WIN$N e WDO$N · D3 no-go → sem rótulos direcionais, P atual como "Leitura do dia (nowcast)" · D4 `p_fwd_60` e card de assertividade também no site público; **todo deploy do Firebase exige aprovação explícita do usuário** · Q5 (GEX as-of e backfill) em aberto, pendente do projeto WDO.
**Referências:** [`PRD.md`](./PRD.md) (requisitos REQ-*) · [`SPEC.md`](./SPEC.md) (seções §)

Ordem e dependências:

```
15 ──▶ 16 ──▶ 17
 │      └────▶ 18 ──▶ 19 ──▶ 20
 │                    └────▶ 21 ──▶ 22
 └──────────────────────────────────▶ 22 (relatório contínuo é insumo do corte)
```

Cada fase, ao ser iniciada, ganha a pasta `.planning/phases/NN-<slug>/` com `NN-CONTEXT.md`, `NN-PLAN-XX.md` e `NN-SUMMARY-XX.md`, no padrão das fases 12–13.

---

### Phase 15: Harness de Avaliação e Baseline Congelada
* **Slug sugerido:** `15-harness-de-avaliacao-e-baseline`
* **Goal:** Medir a assertividade de forma reprodutível e contínua a partir dos snapshots imutáveis, antes de mudar qualquer modelo.
* **Escopo:** `backend/eval/metrics.py`, `scripts/eval_assertividade.py`, tabela `forecast_eval_daily`, relatório diário em `data/reports/`, `GET /api/eval/assertividade` (leitura), agendamento pós-fechamento. Sem mudança no cálculo do P.
* **Requirements:** REQ-V01, REQ-V02, REQ-V03, REQ-V04, REQ-V05, REQ-V06, REQ-V07, REQ-A02, REQ-O03, REQ-N02
* **Entregáveis:** harness + testes `test_eval_metrics.py` e `test_eval_baseline.py`; relatório baseline `data/reports/assertividade_baseline_20261110.md`.
* **Success Criteria:**
  1. O harness reproduz a baseline da auditoria com tolerância de ±0,005 de AUC (WIN 60 min 0,474; WDO 60 min 0,486; WIN nowcast 0,711).
  2. Duas execuções com a mesma entrada produzem métricas idênticas (diferença ≤ 0,001).
  3. O relatório diário é gerado automaticamente por 5 pregões seguidos sem intervenção.
  4. Nenhuma escrita no banco além de `forecast_eval_daily` (verificado por teste).
* **Depende de:** fases 12 e 14 (concluídas).

### Phase 16: Versionamento Imutável de Parâmetros e Anti-Repaint
* **Slug sugerido:** `16-versionamento-imutavel-de-parametros`
* **Goal:** Nunca mais apagar calibrações e fazer qualquer recálculo usar a versão vigente na data.
* **Escopo:** migrações aditivas (§10.1, 10.2, 10.3 `model_version`, 10.4, 10.5), `backend/irai/model_registry.py`, remoção do `DELETE` em `scripts/calibrate_universal.py::save_to_db`, resolução por data em `IRAIEngine._load_params`, Kalman por versão, `GET /api/model/versions`, Regra 5 no `.agents/AGENTS.md`.
* **Requirements:** REQ-P01, REQ-P02, REQ-P03, REQ-P04, REQ-P05, REQ-P06, REQ-A03, REQ-N04, REQ-N05, REQ-N06
* **Entregáveis:** migração idempotente; registro da versão atual (calibração de 28/10) como primeira versão `active`; testes `test_model_registry.py` e `test_repaint_versioned.py`.
* **Success Criteria:**
  1. Rodar `calibrate_universal.py` duas vezes não remove nenhuma linha de `model_params`/`model_versions`.
  2. Para pregões com versão registrada: recálculo vs. snapshot com |ΔP| ≤ 0,1 pp em ≥ 99% das barras e 0% de troca de lado **[META]**.
  3. O comportamento ao vivo fica idêntico antes e depois da migração (P do mesmo pregão com diferença ≤ 0,01 pp) **[META]**.
  4. Recalcular datas anteriores à primeira versão registrada retorna o snapshot ou um erro explícito, nunca uma série com parâmetros atuais.
* **Depende de:** 15.

### Phase 17: Correção β/z e Honestidade do Painel
* **Slug sugerido:** `17-correcao-beta-z-e-honestidade-do-painel`
* **Goal:** Corrigir o bug de unidade do score, recalibrar α/intercepto sem clamp visual e tirar da UI toda métrica in-sample.
* **Escopo:** §8 em `scripts/calibrate_universal.py` e `backend/irai/engine.py` (inclusive o Kalman); nova versão `nowcast` em shadow; `Overview.jsx` sem "acc"; `signalAnalyzer.js` sem convicção por accuracy; rótulo "Leitura do dia (nowcast)" em `SignalGauge.jsx`; `/api/irai/targets` com `calibrated`; filtro do overview independente de `accuracy`.
* **Requirements:** REQ-M01, REQ-M02, REQ-M03, REQ-M04, REQ-U04, REQ-A04
* **Entregáveis:** versão `nowcast` corrigida em shadow; `test_unit_fix.py`; comparação no harness: versão antiga vs. corrigida.
* **Success Criteria:**
  1. Na janela de calibração, o score corrigido reproduz a acurácia do próprio regressor (WDO 73,0%, ±0,5 pp) em vez de 64,7%.
  2. O nowcast corrigido tem BSS ≥ BSS do atual no harness (mesmas barras) **[META]**.
  3. Nenhuma ocorrência de "acc" ou de acurácia in-sample na UI local nem no site público (o deploy do site exige aprovação explícita).
  4. Todos os alvos continuam listados no overview.
* **Depende de:** 16 (para gravar a versão nova sem apagar a antiga).

### Phase 18: Features Causais e Treino Walk-Forward com Calibração
* **Slug sugerido:** `18-features-causais-e-treino-walk-forward`
* **Goal:** Construir offline o modelo preditivo de 60 min (produto, D1) para WIN e WDO com validação honesta; o fechamento é treinado e medido só como horizonte secundário.
* **Escopo:** `backend/irai/features.py` (§4.1–4.2), `scripts/train_forecast.py` (§5–7: L2, CV purgado interno, walk-forward externo com embargo, Platt/isotônica, ensemble bootstrap, limiares §5.4 só para 60 min), pré-registro de config, relatório walk-forward, registro como `forecast` em `rejected` ou `shadow`.
* **Requirements:** REQ-F01, REQ-F02, REQ-F03, REQ-F04, REQ-F05, REQ-F06, REQ-F08, REQ-N01
* **Entregáveis:** `test_features_causal.py`, `test_walkforward_split.py`; `data/reports/forecast_wf_<version>.md` com todas as configurações tentadas.
* **Success Criteria:**
  1. Testes de causalidade e de split verdes.
  2. Walk-forward em ago–nov/2026, 60 min: BSS ≥ 0 por ativo **[META]**; ECE ≤ 3 pp **[META]**. Fechamento: só reportado.
  3. AUC de 60 min ao menos igual à do protótipo dentro do IC (WIN 0,540; WDO 0,503, que não teve sinal), ou justificativa documentada da diferença. Relatório explicita, por ativo, se 60 min tem chance de passar no corte.
  4. Versão registrada com config, artefato, métricas e git SHA.
* **Depende de:** 15 (métricas), 16 (registro).

### Phase 19: Shadow Mode ao Vivo (Inferência, Snapshots, API, Firebase)
* **Slug sugerido:** `19-shadow-mode-ao-vivo`
* **Goal:** Rodar o novo modelo (WIN$N e WDO$N) a cada ciclo do collector e gravar `p_fwd_60` (e `p_fwd_close` só para avaliação) nos snapshots, sem exibir.
* **Escopo:** `backend/irai/forecast.py`; colunas §10.3; `save_live_snapshots` estendido; `persist_live_snapshots_cycle` com `forecast_mode`; campos em `/api/irai/series`; `/api/health.forecast`; checagem no `health_watchdog.py`; `firebase_sync.py` aceitando os campos novos e removendo `p_fwd_close*` do payload público (SPEC §15); bloqueio de `forecast_mode` para alvos fora de WIN/WDO.
* **Requirements:** REQ-F07, REQ-F09, REQ-A01, REQ-A05, REQ-S01, REQ-O01, REQ-O02, REQ-N03, REQ-N04, REQ-N07
* **Entregáveis:** `test_forecast_snapshot.py`, `test_api_eval.py`; `forecast_mode='shadow'` para WIN$N e WDO$N.
* **Success Criteria:**
  1. `p_fwd_60` presente em ≥ 98% das barras de pregão de WIN e WDO por 10 pregões seguidos **[META]**.
  2. Inferência com p95 ≤ 1 s por alvo por ciclo **[META]**; nenhum ciclo do collector derrubado por erro do forecast.
  3. O site público continua funcionando com os campos novos e com snapshots antigos; o payload sincronizado não contém `p_fwd_close*` (teste do sync). Se for preciso deploy, só com aprovação explícita.
  4. O harness passa a avaliar `forecast` junto do `nowcast` no relatório diário.
* **Depende de:** 18.

### Phase 20: GEX e Fluxo como Features Testáveis
* **Slug sugerido:** `20-gex-e-fluxo-como-features`
* **Goal:** Testar, com o protocolo da fase 18, se GEX (projeto WDO) e delta acumulado melhoram a previsão.
* **Escopo:** regra as-of do GEX e flag `gex_asof_ok` (§16); features §4.3; ablação com e sem; decisão registrada; nova versão em shadow se aprovada.
* **Requirements:** REQ-G01, REQ-G02, REQ-G03, REQ-G04
* **Entregáveis:** relatório de ablação; auditoria de causalidade do histórico de `gex_levels` (sessões com e sem garantia).
* **Success Criteria:**
  1. Cada feature candidata tem decisão aceita/rejeitada com ΔBSS e IC em ≥ 40 pregões elegíveis **[META]**.
  2. Nenhuma sessão sem `gex_asof_ok=1` entra no treino das features de GEX.
* **Depende de:** 18 (protocolo) e 19 (para shadow de uma versão nova); dados do projeto WDO.

### Phase 21: UI de Probabilidade com Incerteza e Limiares Calibrados
* **Slug sugerido:** `21-ui-probabilidade-com-incerteza`
* **Goal:** Mostrar P(↑ 60 min) com faixa e rótulos calibrados, além do card de assertividade, atrás de feature flag, no painel local **e no site público** (D4).
* **Escopo:** §12: `SignalGauge.jsx`, `TVProbabilityChart.jsx`, `ReliabilityCard.jsx` (novo), `App.jsx`, `signalProcessor.js`, `TVNweChart.jsx` (marcadores experimentais desligados por padrão), `useIraiData.js`; `forecast_ui` ∈ {off, on, nowcast_only} por alvo; modo sem previsão (D3); nó `eval/<target>` no `firebase_sync.py`; campos novos em `targets`; regra `eval/$target` em `frontend/database.rules.json` (SPEC §15); selo "em avaliação" antes do corte.
* **Requirements:** REQ-U01, REQ-U02, REQ-U03, REQ-U05, REQ-U06, REQ-U07, REQ-S02, REQ-S03, REQ-S04, REQ-S05, REQ-S06
* **Entregáveis:** UI local e pública atrás de flag; diff das regras do RTDB e teste de regras (leitura anônima de `eval` permitida, escrita negada); checklist de deploy para aprovação do usuário; checklist de UAT (sync, zoom, pair spread visível, zero-repaint, flag em off/on/nowcast_only).
* **Success Criteria:**
  1. Com a flag desligada, a UI fica idêntica à atual, exceto pelas mudanças da fase 17.
  2. Com a flag ligada, os rótulos vêm dos limiares da versão e o card mostra AUC/BSS/ECE dos últimos 20 pregões.
  3. As regras 1–4 do `.agents/AGENTS.md` são verificadas no UAT.
  4. Com `nowcast_only`, nenhum rótulo direcional (COMPRA/VENDA, veredito, setas) aparece, local nem público; o P atual aparece como "Leitura do dia (nowcast)".
  5. O site público mostra `p_fwd_60` (com selo "em avaliação") e o card lendo `eval/<target>`; nenhum `p_fwd_close*` no RTDB.
  6. Regras e hosting só publicados depois da aprovação explícita do usuário, registrada no SUMMARY.
* **Depende de:** 19 (dados), 15 (métricas).

### Phase 22: Avaliação Go/No-Go e Corte
* **Slug sugerido:** `22-go-no-go-e-corte`
* **Goal:** Decidir por ativo (WIN$N, WDO$N), com critério objetivo em 60 min, se o novo modelo vira o sinal principal.
* **Escopo:** relatório de ≥ 40 pregões em shadow; aplicação dos critérios do PRD §8; promoção `shadow → active` (ou permanência em pesquisa); atualização do Firebase (`targets.forecast_ui`, `eval`) conforme D4, com deploy aprovado; deprecar `accuracy`; atualizar `docs/API.md`, `docs/ARCHITECTURE.md` e o PRD v3.0 histórico com uma nota de remissão.
* **Requirements:** critérios do PRD §8 (consolidação de REQ-V*, REQ-F*, REQ-N05, REQ-U*)
* **Entregáveis:** `22-SUMMARY-01.md` com a decisão e os números; plano de reversão testado (desligar a flag e voltar a versão).
* **Success Criteria:**
  1. Decisão registrada por ativo com os números medidos dos 6 critérios do PRD §8 (60 min); fechamento reportado à parte.
  2. Ativo com "go": `forecast_mode=active` e `forecast_ui=on`, local e público (sem o selo "em avaliação"). Ativo com "no-go": `forecast_ui=nowcast_only` (D3), local e público, e plano de pesquisa seguinte. Mudanças no site público só após aprovação explícita do usuário.
  3. Reversão executada em teste em menos de 5 minutos, sem perda de dados **[META]**.
* **Depende de:** 15, 19, 21 (e 20, se houver versão com GEX em shadow).
