---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Otimização do Cálculo NWE & Estabilização Live
status: executing
last_updated: "2026-08-12T16:30:00.000Z"
last_activity: 2026-08-12
progress:
  total_phases: 13
  completed_phases: 13
  total_plans: 13
  completed_plans: 13
---

## Current Position

Phase: 13
Plan: 13-PLAN-01 complete ✓
Status: Phase complete ✓
Last activity: 2026-08-12

## Accumulated Context

- O cálculo atual do NWE no frontend é realizado em tempo de renderização em Javascript (`computeNWE` no React), com complexidade O(n²), degradando severamente a performance com o aumento das séries temporais.
- A migração deve assegurar paridade matemática e visual com o modelo atual: suavização kernel Gaussiana com bandwidth = 8 e envelope traçado por 3 desvios/MAD (Median Absolute Deviation).
- Fase 4 completou robustez de infraestrutura: guard `_add_column` concorrente, init_db no startup de API e Collector, testes do guard Kalman, auditoria GEX. Engine.py inalterado.
- Fase 5 completou expansão de ativos no rastro (DE40, US2000, JP225, CHINA50).
- Fase 6 completou auditoria de conflitos e alinhamento com o fork.
- Fase 12 completou Motor de Armazenamento de Snapshots Imutáveis em Tempo Real (Zero-Repainting Live Mode): tabela `irai_live_snapshots`, persistência automática no `collector.py`, endpoint API `/api/irai/series?mode=live`, indicador de status no frontend e 20/20 testes unitários passando.
- Fase 13 completou Rastro de Mini Índice (Top 8 Ações IBOV): coleta das 8 ações B3 no `collector.py`, calibração estatística dedicada para `WIN$N_TOP8` em `calibrate_universal.py`, migração em `db.py` e integração completa no Frontend.

### Roadmap Evolution
- Phase 12 added & completed: Motor de Armazenamento de Snapshots Imutáveis em Tempo Real (Zero-Repainting Live Mode)
- Phase 13 added & completed: Rastro de Mini Índice (Top 8 Ações IBOV)
