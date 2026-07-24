---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Otimização do Cálculo NWE
status: executing
last_updated: "2026-07-18T23:05:00.000Z"
last_activity: 2026-07-18
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 5
  completed_plans: 5
---

## Current Position

Phase: 5
Plan: All complete (2/2)
Status: Phase complete ✓
Last activity: 2026-07-23

## Accumulated Context

- O cálculo atual do NWE no frontend é realizado em tempo de renderização em Javascript (`computeNWE` no React), com complexidade O(n²), degradando severamente a performance com o aumento das séries temporais.
- A migração deve assegurar paridade matemática e visual com o modelo atual: suavização kernel Gaussiana com bandwidth = 8 e envelope traçado por 3 desvios/MAD (Median Absolute Deviation).
- Fase 4 completou robustez de infraestrutura: guard `_add_column` concorrente, init_db no startup de API e Collector, testes do guard Kalman, auditoria GEX. Engine.py inalterado.
- Fase 5 adicionada: Expansão de Ativos no Rastro (Índices Globais: DE40, US2000, JP225, +1).

### Roadmap Evolution
- Phase 5 added: Expansão de Ativos no Rastro (Índices Globais: DE40, US2000, JP225, etc.)
