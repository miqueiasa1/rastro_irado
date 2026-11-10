---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Otimização do Cálculo NWE & Estabilização Live
status: executing
last_updated: "2026-11-10T13:42:00.000Z"
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
- Status: planejada; nenhuma fase iniciada. A milestone v1.0 segue como registro histórico (fases 1–14).
- Fases 15–22 adicionadas ao `ROADMAP.md` como "Não iniciada": 15 harness de avaliação, 16 versionamento imutável/anti-repaint, 17 correção β/z e honestidade do painel, 18 features causais + walk-forward, 19 shadow mode ao vivo, 20 GEX e fluxo como features, 21 UI com incerteza, 22 go/no-go.
- Documentos: `.planning/milestones/v2.0-metodologia/PRD.md`, `SPEC.md` e `PHASES.md`.
- Motivação (auditoria de 10/11/2026, 65 pregões ao vivo de 03/08 a 10/11): AUC do P(↑) de 0,47–0,50 para 5–60 min, nowcast de 0,71 (WIN) e 0,75 (WDO), Brier skill de −0,27 a −0,40.
- Decisões do owner em 10/11/2026 (PRD §12.1), já propagadas em PRD, SPEC, PHASES e ROADMAP:
  - D1: horizonte de produto = 60 min para WIN e WDO; fechamento só como horizonte secundário de avaliação. O go/no-go passa a ser por ativo, em 60 min.
  - D2: só WIN$N e WDO$N no v2.0; demais alvos ficam como não-objetivo/futuro.
  - D3: se o go/no-go falhar, remover os rótulos direcionais e mostrar o P atual só como "Leitura do dia (nowcast)" (`forecast_ui='nowcast_only'`).
  - D4: publicar `p_fwd_60` e o card de assertividade no site público (nó `eval/<target>`, regra de leitura no RTDB). Todo deploy do Firebase continua exigindo aprovação explícita do usuário.
- Em aberto: Q5 (o projeto WDO garante GEX publicado antes de 09:00 e marca o backfill?), pendente de consulta ao projeto WDO; afeta só a Phase 20. Q6 e Q7 têm padrão proposto no PRD.
- Próximo passo: iniciar a Phase 15 (`/gsd-discuss-phase 15`); em paralelo, consultar o projeto WDO sobre Q5.
