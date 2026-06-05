# IRAI — Intraday Risk Appetite Index

> Dashboard de probabilidade direcional intraday para 11 mercados globais, com indicadores GEX, pair trading e análise de fluxo.

## Visão Geral

O IRAI (Intraday Risk Appetite Index) é um sistema proprietário que calcula em tempo real a **probabilidade direcional (P↑)** de 11 ativos financeiros globais, usando um modelo cross-asset de fatores macroeconômicos com filtro de Kalman adaptativo e teste de cointegração de Johansen.

### Ativos Monitorados

| Ativo | Target | Fonte |
|-------|--------|-------|
| WIN Futures (B3) | `WIN$N` | XP MT5 |
| WDO Dólar Futuro | `WDO$N` | XP MT5 |
| S&P 500 | `US500` | Tickmill MT5 |
| Nasdaq 100 | `USTEC` | Tickmill MT5 |
| Dow Jones | `US30` | Tickmill MT5 |
| Bitcoin | `BTCUSD` | Tickmill MT5 |
| Ouro | `XAUUSD` | Tickmill MT5 |
| EUR/USD | `EURUSD` | Tickmill MT5 |
| GBP/USD | `GBPUSD` | Tickmill MT5 |
| USD/JPY | `USDJPY` | Tickmill MT5 |
| DXY | `DXY` | Tickmill MT5 |

### Funcionalidades Principais

- **Probabilidade Direcional P(↑)** — modelo cross-asset com calibração automática
- **Filtro de Kalman Adaptativo** — pesos dos fatores evoluem dinamicamente por sessão
- **GEX Levels (Gamma Exposure)** — paredes de gamma, pivot e teto/piso para 11 ativos
- **Pair Trading WIN×WDO** — z-score de cointegração Johansen com sinais compra/venda
- **Sessões Forex** — máximas/mínimas das sessões Ásia, Londres e Nova York
- **NWE (Nadaraya-Watson Envelope)** — regressão kernel para tendência de preço
- **Delta Cumulativo** — indicador de fluxo (volume × direção)
- **Firebase Hosting** — dashboard acessível em https://rastromacro.web.app

## Quick Start

```bash
# Iniciar todo o sistema (API + Collector + Frontend + Firebase Sync)
start_irai.bat
```

O dashboard estará disponível em:
- **Local:** http://localhost:5175
- **Web:** https://rastromacro.web.app
- **API Swagger:** http://localhost:8888/docs

## Estrutura do Projeto

```
rastro_irado/
├── backend/
│   ├── api/main.py          # FastAPI — endpoints REST + WebSocket
│   ├── db.py                # Schema SQLite (WAL mode)
│   ├── irai/
│   │   ├── engine.py        # Motor IRAI — compute cross-asset
│   │   ├── kalman.py        # Filtro de Kalman adaptativo
│   │   └── johansen.py      # Teste de cointegração Johansen
│   └── workers/
│       └── collector.py     # Coleta M5 de 3 terminais MT5
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Dashboard principal (React + Recharts)
│   │   ├── Overview.jsx     # Painel multi-ativo
│   │   └── gexLevels.js     # Níveis GEX por ativo (auto-gerado)
│   └── firebase.json        # Config Firebase Hosting
├── scripts/
│   ├── calibrate_universal.py  # Calibração cross-asset
│   ├── firebase_sync.py        # Sync dados → Firebase RTDB
│   ├── sync_gex_to_irai.py     # Parse Pine → gexLevels.js
│   └── install_nssm_services.ps1  # Serviços Windows
├── data/                    # SQLite databases (não versionado)
├── start_irai.bat           # Inicialização completa
└── docs/                    # Documentação
```

## Documentação

- [Arquitetura](docs/ARCHITECTURE.md) — design do sistema e fluxo de dados
- [Primeiros Passos](docs/GETTING-STARTED.md) — instalação e configuração inicial
- [API Reference](docs/API.md) — endpoints REST e WebSocket
- [Configuração](docs/CONFIGURATION.md) — variáveis de ambiente e parâmetros
- [Desenvolvimento](docs/DEVELOPMENT.md) — workflow de desenvolvimento
- [Deploy](docs/DEPLOYMENT.md) — Firebase Hosting e serviços Windows
- [Testes](docs/TESTING.md) — estratégia de testes

## Licença

Proprietário — uso interno.
