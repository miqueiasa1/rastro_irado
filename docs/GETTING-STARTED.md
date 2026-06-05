# Primeiros Passos — IRAI

## Pré-Requisitos

- **Python 3.11+** com pip
- **Node.js 18+** com npm
- **MetaTrader 5** — terminais XP, Tickmill e Axi instalados e logados
- **Firebase CLI** — para deploy do frontend (`npm install -g firebase-tools`)
- **Windows** — o collector depende do módulo `MetaTrader5` (apenas Windows)

## Instalação

### 1. Dependências Python

```bash
pip install fastapi uvicorn MetaTrader5 numpy scipy firebase-admin requests
```

### 2. Dependências Frontend

```bash
cd frontend
npm install
```

### 3. Banco de Dados

O banco é criado automaticamente na primeira execução. Para inicializar manualmente:

```bash
python backend/db.py
```

Isso cria `data/irai_live.db` com o schema completo (market_bars, asset_models, kalman_state, etc.).

### 4. Calibração Inicial

Antes de usar, é necessário coletar dados históricos e calibrar os modelos:

```bash
# Coletar histórico M5 dos terminais MT5
python scripts/collect_history.py

# Calibrar todos os targets
python scripts/calibrate_universal.py
```

A calibração popula `model_params` e atualiza `asset_models` com acurácia e R².

### 5. Firebase (opcional)

Para deploy na web:

```bash
cd frontend
firebase login
firebase deploy --only hosting
```

## Execução

### Tudo de uma vez

```bash
start_irai.bat
```

Isso inicia 4 serviços:
1. **FastAPI** — porta 8888
2. **Collector** — ciclo de 60s
3. **Frontend Vite** — porta 5175
4. **Firebase Sync** — sync periódico

### Serviços individuais

```bash
# API
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8888

# Collector
python backend/workers/collector.py --interval 60

# Frontend
cd frontend && npm run dev

# Firebase Sync
python scripts/firebase_sync.py
```

## Verificação

1. Abrir http://localhost:5175 — deve mostrar o overview multi-ativo
2. Clicar em qualquer ativo — deve carregar a série com gráficos P(↑), Movimento e Heatmap
3. Verificar http://localhost:8888/docs — Swagger com todos os endpoints
4. Verificar http://localhost:8888/api/health — status do sistema

## Atualização Diária do GEX

Os níveis GEX são atualizados automaticamente quando você roda o `GEX_DAILY_ALL.bat` do projeto WDO×WIN pair trading. O script `sync_gex_to_irai.py` é chamado automaticamente ao final do batch.
