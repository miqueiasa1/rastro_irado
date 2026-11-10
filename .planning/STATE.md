---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Otimização do Cálculo NWE & Estabilização Live
status: executing
last_updated: "2026-11-10T19:30:00.000Z"
last_activity: 2026-11-10
progress:
  total_phases: 14
  completed_phases: 14
  total_plans: 13
  completed_plans: 13
---

## Current Position

Phase: 14
Plan: sem 14-PLAN formal; entregue no commit f2b6d0d ✓
Status: Phase complete ✓
Last activity: 2026-11-10

## Accumulated Context

- O cálculo atual do NWE no frontend é realizado em tempo de renderização em Javascript (`computeNWE` no React), com complexidade O(n²), degradando severamente a performance com o aumento das séries temporais.
- A migração deve assegurar paridade matemática e visual com o modelo atual: suavização kernel Gaussiana com bandwidth = 8 e envelope traçado por 3 desvios/MAD (Median Absolute Deviation).
- Fase 4 completou robustez de infraestrutura: guard `_add_column` concorrente, init_db no startup de API e Collector, testes do guard Kalman, auditoria GEX. Engine.py inalterado.
- Fase 5 completou expansão de ativos no rastro (DE40, US2000, JP225, CHINA50).
- Fase 6 completou auditoria de conflitos e alinhamento com o fork.
- Fase 12 completou Motor de Armazenamento de Snapshots Imutáveis em Tempo Real (Zero-Repainting Live Mode): tabela `irai_live_snapshots`, persistência automática no `collector.py`, endpoint API `/api/irai/series?mode=live`, indicador de status no frontend e 20/20 testes unitários passando.
- Fase 13 completou Rastro de Mini Índice (Top 8 Ações IBOV): coleta das 8 ações B3 no `collector.py`, calibração estatística dedicada para `WIN$N_TOP8` em `calibrate_universal.py`, migração em `db.py` e integração completa no Frontend.
- Fase 14 completou a auditoria waves 0-5 no commit `f2b6d0d` (29/10/2026, 08:55 horário de Brasília / America/Sao_Paulo): cofre do Pine e endurecimento da API, normalização do fuso do broker, sessão B3 09:00 e gap stitching do NWE, sincronização estrita dos gráficos, endurecimento histórico do GEX e manutenção diária. A numeração das waves segue a ordem da mensagem do commit; as ondas 1 e 2 também estão nomeadas em `scripts/deploy_onda1_2.ps1` (fuso/sessão B3 + Regra 4). O mesmo commit ainda inclui o motor de cesta cambial (`backend/irai/forex_basket.py` e UI associada) — atribuição a uma wave específica: a confirmar.

### Roadmap Evolution
- Phase 12 added & completed: Motor de Armazenamento de Snapshots Imutáveis em Tempo Real (Zero-Repainting Live Mode)
- Phase 13 added & completed: Rastro de Mini Índice (Top 8 Ações IBOV)
- Phase 14 added & completed: Auditoria Waves 0-5 (commit f2b6d0d, 2026-10-29)

### Working tree (2026-11-10)
- Diff local não commitado: 229 arquivos de tooling GSD em `.agent/` (atualização da ferramenta; não é código da aplicação).
- `frontend/src/gexLevels.js` modificado em 10/11/2026 07:32 (horário de Brasília / America/Sao_Paulo); provável sync diário de GEX, ainda não revisado.

### Próxima milestone: v2.0 Metodologia Preditiva Calibrada (planejada em 2026-11-10)
- Status: em andamento. Phase 15 **em revisão** (implementada e commitada em 2026-11-10 na branch local `v2/fase-15-harness`, sem push; critério 3 em andamento). Phase 16 **em produção desde 10/11/2026** (commit `deb199f` na branch local `v2/fase-16-versionamento`, sem push). Phases 17 e 18 **implementadas, aguardando aprovação** (10/11/2026, worktree `rastro_irado_wt_f17_18`, branch local `v2/fase-17-18` criada de `v2/fase-16-versionamento`, sem commit). Fases 19–22 não iniciadas. A milestone v1.0 segue como registro histórico (fases 1–14).
- Fases 15–22 adicionadas ao `ROADMAP.md` como "Não iniciada": 15 harness de avaliação, 16 versionamento imutável/anti-repaint, 17 correção β/z e honestidade do painel, 18 features causais + walk-forward, 19 shadow mode ao vivo, 20 GEX e fluxo como features, 21 UI com incerteza, 22 go/no-go.
- Documentos: `.planning/milestones/v2.0-metodologia/PRD.md`, `SPEC.md` e `PHASES.md`.
- Motivação (auditoria de 10/11/2026, 65 pregões ao vivo de 03/08 a 10/11): AUC do P(↑) de 0,47–0,50 para 5–60 min, nowcast de 0,71 (WIN) e 0,75 (WDO), Brier skill de −0,27 a −0,40.
- Decisões do owner em 10/11/2026 (PRD §12.1), já propagadas em PRD, SPEC, PHASES e ROADMAP:
  - D1: horizonte de produto = 60 min para WIN e WDO; fechamento só como horizonte secundário de avaliação. O go/no-go passa a ser por ativo, em 60 min.
  - D2: só WIN$N e WDO$N no v2.0; demais alvos ficam como não-objetivo/futuro.
  - D3: se o go/no-go falhar, remover os rótulos direcionais e mostrar o P atual só como "Leitura do dia (nowcast)" (`forecast_ui='nowcast_only'`).
  - D4: publicar `p_fwd_60` e o card de assertividade no site público (nó `eval/<target>`, regra de leitura no RTDB). Todo deploy do Firebase continua exigindo aprovação explícita do usuário.
- Em aberto: Q5 (o projeto WDO garante GEX publicado antes de 09:00 e marca o backfill?), pendente de consulta ao projeto WDO; afeta só a Phase 20. Q6 e Q7 têm padrão proposto no PRD.
- Phase 15: harness `scripts/eval_assertividade.py` + pacote isolado `backend/eval/`; baseline congelada em `data/eval/baseline/assertividade_baseline_20261110.json` (WIN 60 min AUC 0,474, WDO 0,486; nowcast 0,710 / 0,754). Decisões do owner (10/11/2026): (1) tarefa "IRAI Daily Assertividade" seg–sex 18:45 via `scripts/run_eval_assertividade.bat`, log em `logs/eval_assertividade.log`; (2) `forecast_eval_daily` em `data/eval/forecast_eval.db` até a fase 16; (3) endpoint `/api/eval/assertividade` na fase 19; (4) fixture de ~600 KB versionada; (5) baseline aceita com `5904ef5-dirty`. Critério 3 fecha após 5 pregões seguidos de relatório automático.
- Phase 16 (10/11/2026): registro imutável `model_versions` + `model_version_events` (`backend/irai/model_registry.py`), calibração sem `DELETE` (versão nova `shadow`), engine resolvendo a versão vigente na data, `model_version` em snapshots e no Kalman, `GET /api/model/versions`, Regra 5 no `.agents/AGENTS.md`. Migração `scripts/migrate_fase16_model_versions.py` validada numa cópia (`%TEMP%\irai_p16`) e aplicada ao `irai_live.db` em 10/11/2026 às 13:46 BRT (backup `data/backups/irai_live_pre_fase16_20261110.db`, 14 versões ativas, contagens preservadas): idempotente, ΔP legado × migrado = 0 em 14 alvos × 5 pregões; suíte 87/87 com e sem migração. Não ligada ao `init_db()`. Repaint residual não ligado a parâmetros (mediana 0,5 pp WIN / 0,35 pp WDO, ~1,5% troca de lado) fica em aberto (critério 2 [META]).
- Phase 17 (10/11/2026): score corrigido (β·σ·z ÷ score_scale), α/b sem clamp e R/Q do Kalman medidos, como opções de versão (`unit_fix`, `score_scale`, `kalman_obs_cov`, `kalman_trans_cov`); versões legado/adotadas inalteradas. Versões corrigidas de WIN/WDO registradas só numa cópia (shadow). Nowcast recalculado nas mesmas barras (03/08–10/11): AUC 0,774 → 0,828 (WIN) e 0,757 → 0,869 (WDO), BSS 0,165 → 0,266 e 0,147 → 0,261; 60 min continua com BSS negativo. Painel honesto atrás de `forecast_ui` (padrão `off`); `/api/irai/targets` com `calibrated` independente de `accuracy`.
- Phase 18 (10/11/2026): valor justo da cesta com γ walk-forward e z causal (|z| > 2 em 4–8% das barras, contra 54–58% da construção atual); nenhum descolamento previu 15/30/60 min de forma útil (AUC 0,49–0,52) nem teve P&L líquido que sobrevivesse a BH/Bonferroni; p_fwd_60 walk-forward (361 pregões fora da amostra) com AUC 0,48–0,50 e BSS ≤ 0 nos conjuntos A/B/C → não passou. Harness diário com cobertura do z e P&L por evento (`HARNESS_VERSION` 18.0).
- Próximo passo: owner decide commit/ativação das fases 17/18 (ver SUMMARYs). Acompanhar a Phase 16 em produção (snapshots com `model_version`, P estável); seguir acompanhando os 5 pregões da Phase 15. Em paralelo, consultar o projeto WDO sobre Q5.
