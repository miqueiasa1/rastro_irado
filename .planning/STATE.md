---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Otimização do Cálculo NWE
status: executing
last_updated: "2026-07-18T23:05:00.000Z"
last_activity: 2026-07-18
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 3
  completed_plans: 3
---

## Current Position

Phase: 4
Plan: All complete (3/3)
Status: Phase complete ✓
Last activity: 2026-07-18

## Accumulated Context

- O cálculo atual do NWE no frontend é realizado em tempo de renderização em Javascript (`computeNWE` no React), com complexidade O(n²), degradando severamente a performance com o aumento das séries temporais.
- A migração deve assegurar paridade matemática e visual com o modelo atual: suavização kernel Gaussiana com bandwidth = 8 e envelope traçado por 3 desvios/MAD (Median Absolute Deviation).
- Fase 4 completou robustez de infraestrutura: guard `_add_column` concorrente, init_db no startup de API e Collector, testes do guard Kalman, auditoria GEX. Engine.py inalterado.
