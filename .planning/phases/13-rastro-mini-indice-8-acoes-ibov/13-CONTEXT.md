# Phase 13: Rastro de Mini Índice (Top 8 Ações IBOV) - Context

**Gathered:** 2026-08-12
**Status:** Ready for planning
**Source:** User request

<domain>
## Phase Boundary

Esta fase constrói um novo modelo estatístico e rastro em tempo real para o Mini Índice (`WIN$N`) baseado nas 8 ações de maior peso na carteira teórica do Ibovespa (ex: VALE3, PETR4, ITUB4, BBDC4, ELET3, WEGE3, ABEV3, B3SA3).
O objetivo é criar uma proxy sintética de alta fidelidade intraday do comportamento corporativo/equity brasileiro, permitindo medir a divergência do Mini Índice em relação ao peso real das suas principais constituintes em tempo real.
</domain>

<decisions>
## Implementation Decisions

### 1. Cesta de Ativos (Top 8 IBOV)
- Selecionar e parametrizar as 8 ações mais pesadas da B3: VALE3, PETR4, ITUB4, BBDC4, ELET3, WEGE3, ABEV3, B3SA3.
- Incluir estes tickers no ciclo de coleta do `collector.py` (ou resolução de contrato/ações a partir do MT5 B3).

### 2. Motor de Calibração (`calibrate_universal.py` / `engine.py`)
- Rodar o motor estatístico (Regressão Ridge, Filtro Kalman para Hedge Ratio dinâmico e teste de Cointegração de Johansen) para mapear o vetor de pesos $\beta$ das 8 ações contra o `WIN$N`.
- Persistir modelo em `asset_models` e `model_params`.

### 3. API & Processamento Backend (`backend/irai/engine.py` & `backend/api/main.py`)
- Calcular em tempo real o Z-Score dinâmico do Pair Spread, o sinal de convicção $P_{up}$ e as curvas NWE do Mini Índice ancorado na cesta Top 8.
- Garantir que a regra de Zero-Repainting no pré-mercado (abertura fixada no fechamento da sessão anterior até que a 1ª barra do dia seja negociada nas ações) seja mantida rigorosamente.

### 4. Interface Web Frontend (`frontend/src/`)
- Adicionar/Habilitar a exibição do rastro do Mini Índice (Top 8 Ações IBOV) no Dashboard e Tela de Detalhes.
- Assegurar a renderização incondicional do gráfico de Pair Spread (`TVPairwiseZScoreChart`), sincronização de eixos e travamento de zoom horizontal do usuário.
</decisions>

<canonical_refs>
## Canonical References

- `backend/workers/collector.py` — Coleta de barras M1/M5 via MT5
- `backend/calibrate_universal.py` — Engine de calibração estatística Ridge / Johansen / Kalman
- `backend/irai/engine.py` — Engine de cálculo intraday
- `backend/api/main.py` — API FastAPI de séries e snapshots
- `frontend/src/App.jsx` e `frontend/src/components/TVPairwiseZScoreChart.jsx` — Frontend React e gráficos
</canonical_refs>
