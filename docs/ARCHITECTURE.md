# Arquitetura — IRAI

## Visão de Alto Nível

O IRAI é um sistema de 4 serviços que operam em conjunto para calcular e exibir a probabilidade direcional de 11 mercados em tempo real.

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────────┐
│  MT5 Terminals   │────▶│  Collector    │────▶│  SQLite (WAL)    │
│  (XP, Tickmill,  │     │  (60s cycle)  │     │  market_bars     │
│   Axi)           │     └──────┬───────┘     │  asset_models    │
└─────────────────┘            │              │  kalman_state    │
                               │ notify       └────────┬─────────┘
                               ▼                       │
                        ┌──────────────┐               │
                        │  FastAPI     │◀──────────────┘
                        │  (port 8888) │    compute_from_db()
                        │  REST + WS   │
                        └──────┬───────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
             ┌──────────┐ ┌────────┐ ┌────────────────┐
             │ Frontend  │ │Firebase│ │ Firebase RTDB  │
             │ Vite:5175 │ │Hosting │ │ (Sync Service) │
             └──────────┘ └────────┘ └────────────────┘
```

## Componentes

### 1. Collector (`backend/workers/collector.py`)

Worker cíclico que coleta barras M5 de 3 terminais MetaTrader 5:

| Terminal | Fonte | Símbolos |
|----------|-------|----------|
| XP (BR) | `br` | WIN$N, WDO$N, DI1$N |
| Tickmill | `tickmill` | US500, USTEC, US30, BTCUSD, XAUUSD, DXY, BRENT, VIX, EURUSD, GBPUSD, USDJPY, ... |
| Axi | `axi` | iSharesBrazil+, iSharesTreasury20+, ... (fatores de calibração) |

- **Ciclo:** 60 segundos
- **Horário B3:** 09:55–18:10 BRT (apenas internacional fora deste horário)
- **Delta:** Calculado como `real_volume × (2 × close_pct - 1)`
- **Notificação:** POST `/api/internal/notify_update` após cada ciclo

### 2. IRAI Engine (`backend/irai/engine.py`)

Motor principal de cálculo probabilístico:

- **Modelo por ativo:** Cada target tem fatores próprios (definidos em `asset_models`)
- **Calibração:** Regressão logística cross-asset com janela de 30 sessões
- **Dois modos:**
  - **v1 (estático):** Pesos fixos da última calibração
  - **v2 (dinâmico):** Filtro de Kalman atualiza pesos em tempo real
- **Output:** `IRAISnapshot` com P(↑), score, verdict, fatores z-score, delta, pair z-score

#### Filtro de Kalman (`backend/irai/kalman.py`)

Adaptação online dos pesos do modelo:
- Estado: vetor de pesos β dos fatores
- Observação: retorno real vs predição
- Atualização: Kalman gain com process noise calibrado por volatilidade

#### Cointegração Johansen (`backend/irai/johansen.py`)

Teste de cointegração para pair trading WIN×WDO:
- Janela de 95 barras (1 sessão completa)
- p-value < 0.05 → par cointegrado → z-score do spread
- Sinais: z > 2σ → venda, z < -2σ → compra

### 3. FastAPI Backend (`backend/api/main.py`)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/irai/targets` | GET | Lista targets com status de calibração |
| `/api/irai/overview` | GET | Snapshot de todos os targets calibrados |
| `/api/irai/series` | GET | Série completa de uma sessão + target |
| `/api/irai/dates` | GET | Datas com dados disponíveis |
| `/api/irai/current` | GET | Snapshot mais recente |
| `/api/model/params` | GET | Parâmetros do modelo por target |
| `/api/health` | GET | Status do sistema |
| `/ws/irai` | WS | Push real-time (target configurável) |
| `/api/internal/notify_update` | POST | Notificação do collector |

- **Cache:** `series_cache` e `overview_cache_data` invalidados em cada ciclo do collector
- **WebSocket:** Broadcast automático para todos os clients conectados

### 4. Frontend (`frontend/src/`)

Dashboard React (Vite) com Recharts:

- **Overview:** Grid multi-ativo com sparklines, P(↑), verdicts
- **Série detalhada:** 3 gráficos sincronizados:
  1. **RASTRO MACRO** — P(↑) ao longo do dia com zonas coloridas
  2. **MOVIMENTO** — Preço do ativo + NWE + sessões forex + GEX levels + pair signals
  3. **HEATMAP** — Delta, P(↑), Z-score, Entropy por barra
- **GEX Levels:** Dados extraídos de `gexLevels.js` (gerado automaticamente do Pine Script)
- **Firebase:** Se `VITE_FIREBASE_URL` está configurado, busca dados do Firebase RTDB

## Banco de Dados

SQLite com WAL mode para leitura concorrente:

| Tabela | Propósito |
|--------|-----------|
| `market_bars` | Barras M5 brutas (OHLCV + delta) |
| `asset_models` | Configuração de targets (fatores, sessão, calibração) |
| `model_params` | Pesos calibrados por target (versionados) |
| `session_opens` | Preço de abertura por sessão |
| `calibration_log` | Histórico de calibrações |
| `kalman_state` | Estado do filtro Kalman por sessão |

## Fluxo de Dados

```
MT5 Bars (M5)
    │
    ▼
market_bars (SQLite)
    │
    ├── compute_from_db() ──▶ z-scores por fator
    │                              │
    │                              ├── v1: pesos estáticos (model_params)
    │                              └── v2: pesos dinâmicos (Kalman)
    │                                     │
    │                                     ▼
    │                              P(↑) = sigmoid(score)
    │                                     │
    │                              IRAISnapshot
    │                                     │
    ├── REST API ◀─────────────────────────┤
    ├── WebSocket ◀────────────────────────┤
    └── Firebase RTDB ◀────────────────────┘
```
