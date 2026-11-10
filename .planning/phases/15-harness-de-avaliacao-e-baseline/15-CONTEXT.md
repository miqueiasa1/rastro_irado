# Phase 15: Harness de Avaliação e Baseline Congelada - Context

**Gathered:** 2026-11-10
**Status:** Implementada, em revisão
**Source:** `.planning/milestones/v2.0-metodologia/PHASES.md` (Phase 15), `SPEC.md` §13 e §17, `PRD.md` REQ-V01–V07, REQ-A02, REQ-O03, REQ-N02

<domain>
## Phase Boundary

Medir a assertividade do P(↑) atual de forma reprodutível a partir dos snapshots imutáveis
(`irai_live_snapshots`), antes de mudar qualquer modelo. A fase entrega um harness isolado,
testes e a baseline congelada do modelo atual para WIN$N e WDO$N (60 min primário, fechamento
secundário, decisões D1/D2 de 10/11/2026).
</domain>

<decisions>
## Implementation Decisions

### Isolamento do live (restrição do owner para esta fase)
- Os serviços NSSM (IRAI_API, IRAI_Collector, IRAI_FirebaseSync, IRAI_Frontend) rodam desta pasta.
  Nenhum módulo importado pelo live foi alterado (`backend/irai/engine.py`, `backend/workers/collector.py`,
  `backend/db.py`, `backend/api/*`, `scripts/firebase_sync.py`, `frontend/src/*`). Nenhum serviço foi reiniciado.
- Código novo e isolado: pacote `backend/eval/` (não importado pelo live), `scripts/eval_assertividade.py`
  e testes novos. O harness só importa `backend/timeconv.py` (em teste) sem modificá-lo.
- Banco: aberto exclusivamente com URI `mode=ro` + `PRAGMA query_only=ON`. Schema do `irai_live.db` intocado.

### Desvios do SPEC (por causa do isolamento)
- `forecast_eval_daily` (SPEC §10.6) é criada num SQLite próprio, `data/eval/forecast_eval.db`, com o mesmo
  schema, em vez de no `irai_live.db`. Migrar para o banco principal fica para decisão do owner (fase 16).
- `GET /api/eval/assertividade` (REQ-A02) não foi criado: exigiria editar `backend/api/main.py`. O contrato
  JSON já é gerado em `data/eval/latest/assertividade*.json` para o endpoint ler depois.
- Agendamento diário (REQ-O03, SPEC §13.7) não foi ligado: exigiria editar `scripts/daily_maintenance.py`
  ou criar tarefa no Agendador do Windows. Comando pronto; decisão do owner.

### Convenções de medição (iguais às da auditoria de 10/11/2026)
- Barra ao vivo: `is_ghost=0` e `created_at` (UTC real) − abertura da barra (BRT) em [0, 10] min (`--live-max-lag`).
- Pregão: barras M5 com abertura em [09:00, 18:25) BRT; conversão do relógio do broker (NY+7) equivalente a
  `backend.timeconv.broker_wall_to_brt_wall` (teste de equivalência).
- Alvo: sinal do retorno do fechamento da barra até h barras à frente no mesmo pregão (5/15/30/60 min) e até o
  último fechamento do pregão; retorno zero excluído. Nowcast: sinal do retorno do dia.
- BSS contra a taxa-base do próprio conjunto; ECE com 10 bins; IC por bootstrap de pregões (B = 1000, seed 0).
- Baseline congelada com corte `as-of` 2026-11-10 13:50:00 UTC (10:50 BRT), o mesmo instante da extração da auditoria.
</decisions>

<canonical_refs>
## Canonical References

- `.planning/milestones/v2.0-metodologia/SPEC.md` — §13 (harness), §10.6 (forecast_eval_daily), §17 (testes)
- `.planning/milestones/v2.0-metodologia/PRD.md` — §5.1 (REQ-V), §7 (métricas)
- `backend/timeconv.py` — convenção do relógio do broker
- `backend/db.py` — schema de `irai_live_snapshots` e `market_bars` (somente leitura)
</canonical_refs>
