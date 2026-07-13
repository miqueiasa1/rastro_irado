## Current Position

Phase: Phase 1 — Implementação e Testes Unitários de NWE no Backend
Plan: —
Status: Discussing phase
Last activity: 2026-07-13 — Milestone v1.0 started

## Accumulated Context

- O cálculo atual do NWE no frontend é realizado em tempo de renderização em Javascript (`computeNWE` no React), com complexidade O(n²), degradando severamente a performance com o aumento das séries temporais.
- A migração deve assegurar paridade matemática e visual com o modelo atual: suavização kernel Gaussiana com bandwidth = 8 e envelope traçado por 3 desvios/MAD (Median Absolute Deviation).
