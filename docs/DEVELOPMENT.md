# Desenvolvimento — IRAI

## Estrutura de Código

```
backend/
├── api/main.py         # FastAPI — endpoints, WebSocket, cache
├── db.py               # Schema SQLite, conexão, migrações
├── irai/
│   ├── engine.py       # Motor principal (IRAIEngine, IRAISnapshot)
│   ├── kalman.py       # Filtro de Kalman adaptativo
│   └── johansen.py     # Teste de cointegração Johansen
└── workers/
    └── collector.py    # Worker de coleta MT5

frontend/
├── src/
│   ├── App.jsx         # Dashboard (1700+ linhas — monólito React)
│   ├── Overview.jsx    # Grid multi-ativo
│   └── gexLevels.js    # Dados GEX (auto-gerado, não editar)
├── index.html
├── vite.config.js
└── firebase.json

scripts/
├── calibrate_universal.py    # Calibração cross-asset
├── firebase_sync.py          # Sync SQLite → Firebase RTDB
├── sync_gex_to_irai.py       # Parse Pine → gexLevels.js
├── collect_history.py        # Backfill histórico
├── backfill_tickmill.py      # Backfill específico Tickmill
├── backfill_axi.py           # Backfill específico Axi
└── install_nssm_services.ps1 # Instalar serviços Windows
```

## Workflow de Desenvolvimento

### Backend

1. Editar `backend/irai/engine.py` para mudanças no modelo
2. Testar localmente: `python -m uvicorn backend.api.main:app --reload --port 8888`
3. O `--reload` detecta mudanças automaticamente

### Frontend

1. Editar `frontend/src/App.jsx`
2. O Vite HMR atualiza automaticamente no browser
3. Para build: `cd frontend && npm run build`
4. Para deploy: `cd frontend && npx firebase deploy --only hosting`

### Calibração

```bash
# Recalibrar todos os targets
python scripts/calibrate_universal.py

# Recalibrar um target específico
python scripts/calibrate_universal.py --targets US500
```

### GEX Levels

O arquivo `frontend/src/gexLevels.js` é **auto-gerado** — nunca editar manualmente.

Para atualizar:
```bash
python scripts/sync_gex_to_irai.py
```

Ou automaticamente via `GEX_DAILY_ALL.bat` do projeto WDO×WIN pair trading.

## Convenções

### Backend
- Python puro (sem frameworks além do FastAPI)
- SQLite com WAL mode para concorrência
- Timestamps sempre em UTC (ISO 8601)
- Nomenclatura: `snake_case` para tudo

### Frontend
- React funcional com hooks
- Recharts para gráficos
- CSS inline (sem framework CSS)
- Sem TypeScript (JSX puro)

## Adicionando um Novo Ativo

1. **Collector:** Adicionar símbolo no array `TERMINALS` em `collector.py`
2. **Banco:** Inserir na tabela `asset_models` com fatores e configuração de sessão
3. **Calibração:** Rodar `calibrate_universal.py` para gerar pesos
4. **GEX (opcional):** Adicionar no Pine Script e rodar `sync_gex_to_irai.py`

## Debugging

### Verificar dados no banco
```bash
python -c "
from backend.db import get_connection
conn = get_connection()
for r in conn.execute('SELECT symbol, COUNT(*) as n FROM market_bars GROUP BY symbol').fetchall():
    print(f'{r[0]}: {r[1]} barras')
conn.close()
"
```

### Verificar calibração
```bash
python -c "
from backend.irai.engine import IRAIEngine
e = IRAIEngine()
for t in e.registered_targets:
    print(f'{t[\"target\"]}: acc={t.get(\"accuracy\")}, R²={t.get(\"r_squared\")}')
"
```

### API local
```bash
curl http://localhost:8888/api/health
curl http://localhost:8888/api/irai/targets
```
