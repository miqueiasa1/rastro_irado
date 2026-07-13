---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Otimização do Cálculo NWE
status: planning
last_updated: "2026-07-13T12:58:12.664Z"
last_activity: 2026-07-13
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
---

## Current Position

Phase: 3
Plan: Not started
Status: Ready to plan
Last activity: 2026-07-13

## Accumulated Context

- O cálculo atual do NWE no frontend é realizado em tempo de renderização em Javascript (`computeNWE` no React), com complexidade O(n²), degradando severamente a performance com o aumento das séries temporais.
- A migração deve assegurar paridade matemática e visual com o modelo atual: suavização kernel Gaussiana com bandwidth = 8 e envelope traçado por 3 desvios/MAD (Median Absolute Deviation).
