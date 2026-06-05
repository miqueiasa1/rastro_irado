# Configuração — IRAI

## Variáveis de Ambiente

### Frontend (`frontend/.env`)

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `VITE_FIREBASE_URL` | URL do Firebase RTDB. Se definido, frontend busca dados do Firebase ao invés da API local | `undefined` (usa API local) |

### Backend

Não utiliza `.env` — configuração é feita diretamente nos arquivos Python e no banco `asset_models`.

## Portas

| Serviço | Porta | Configurável em |
|---------|-------|-----------------|
| FastAPI Backend | **8888** | `backend/api/main.py:502` |
| Frontend Vite | **5175** | `frontend/vite.config.js` (`strictPort: true`) |
| Firebase Sync | N/A (outbound) | `scripts/firebase_sync.py` |
| Collector | N/A (MT5 + SQLite) | `backend/workers/collector.py` |

> ⚠️ **Nunca use porta 5174** — essa pertence ao projeto WDO×WIN pair trading.

## Terminais MetaTrader 5

Configurados em `backend/workers/collector.py`:

```python
TERMINALS = [
    {
        "name": "BR (XP)",
        "paths": [
            r"C:\Program Files\MetaTrader 5 Terminal\terminal64.exe",
            r"C:\Program Files\MetaTrader 5\terminal64.exe",
            r"C:\Program Files\MetaTrader 5 Terminal - milhao - Copia\terminal64.exe",
        ],
        "source": "br",
        "symbols": ["WIN$N", "WDO$N", "DI1$N"],
    },
    {
        "name": "Tickmill",
        "path": r"C:\Program Files\Tickmill MT5 Terminal\terminal64.exe",
        "source": "tickmill",
        "symbols": ["DXY", "BRENT", "CHINA50", "USDMXN", "VIX", "BTCUSD",
                     "US500", "US30", "USTEC", "XAUUSD",
                     "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", ...],
    },
    {
        "name": "Axi",
        "path": r"C:\Program Files\Axi MetaTrader 5 Terminal\terminal64.exe",
        "source": "axi",
        "symbols": ["iSharesBrazil+", "iSharesTreasury20+", ...],
    },
]
```

## Banco de Dados

| Parâmetro | Valor | Definido em |
|-----------|-------|-------------|
| Caminho DB | `data/irai_live.db` | `backend/db.py:7` |
| Journal mode | WAL | `backend/db.py:108` |
| Timeout | 30s | `backend/db.py:107` |

## Configuração por Ativo (`asset_models`)

Cada target é configurado na tabela `asset_models` do SQLite:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `target` | TEXT PK | Símbolo MT5 (e.g., `WIN$N`, `US500`) |
| `slug` | TEXT | Prefixo para model_params (e.g., `win`, `us500`) |
| `display_name` | TEXT | Nome de exibição (e.g., `S&P 500`) |
| `icon` | TEXT | Emoji do ativo |
| `factors` | JSON | Array de fatores usados (e.g., `["DXY","VIX","BTCUSD"]`) |
| `factor_labels` | JSON | Mapa fator → label do model_params |
| `session_start_h` | INT | Hora UTC início da sessão (0-23) |
| `session_end_h` | INT | Hora UTC fim da sessão |
| `data_proxy` | TEXT | Símbolo alternativo para dados (e.g., `DOL$N` para `WDO$N`) |
| `accuracy` | REAL | Última acurácia direcional calibrada |
| `active` | INT | 1=ativo, 0=inativo |

## Parâmetros do Modelo

### Calibração Universal (`scripts/calibrate_universal.py`)

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `--window` | 30 | Dias de lookback para calibração |
| `--targets` | todos | Targets para recalibrar |
| `--min-sessions` | 10 | Sessões mínimas para calibrar |

### Filtro de Kalman

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| Process noise Q | `0.001 × I` | Ruído do processo |
| Measurement noise R | `1.0` | Ruído da medição |
| Estado inicial | Pesos da calibração v1 | Warm start |

### Pair Trading (WIN×WDO)

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| Janela Johansen | 95 barras | 1 sessão completa |
| p-value threshold | 0.05 | Cointegração significativa |
| z-score compra | < -2σ | Sinal de compra |
| z-score venda | > 2σ | Sinal de venda |
| Filtro P(↑) | ≥50 → só compra, ≤50 → só venda | Evita falsos alertas |

## GEX (Gamma Exposure)

Configuração em `frontend/src/gexLevels.js` (auto-gerado):

| Tipo | Cor | Significado |
|------|-----|-------------|
| `wall` | `#00e676` (verde) | Parede de gamma |
| `mid_wall` | `#90a4ae` (cinza) | Ponto médio entre walls |
| `min_gamma` | `#ff1744` (vermelho) | Mínimo de gamma (Piso) |
| `gamma_flip` | `#ffd600` (amarelo) | Pivot de inversão |
| `max_gamma` | `#00b0ff` (azul) | Máximo de gamma (Teto) |

**Atualização:** Os levels GEX são atualizados automaticamente pelo `GEX_DAILY_ALL.bat` do projeto WDO×WIN pair trading, que chama `scripts/sync_gex_to_irai.py`.

## Firebase

| Config | Valor | Arquivo |
|--------|-------|---------|
| Projeto | `rastromacro` | `frontend/.firebaserc` |
| Hosting URL | https://rastromacro.web.app | — |
| RTDB sync interval | 60s | `scripts/firebase_sync.py` |
| Service Account | `serviceAccountKey.json` | (não versionado) |
