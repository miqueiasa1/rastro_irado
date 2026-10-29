# Deploy — IRAI

## Ambientes

| Ambiente | URL | Dados |
|----------|-----|-------|
| **Local** | http://localhost:5175 | API local (127.0.0.1:8888, só loopback) + SQLite |
| **Web** | https://rastromacro.web.app | Firebase RTDB (sync periódico) |

## Deploy Frontend (Firebase Hosting)

### Manual

```bash
cd frontend
npm run build
npx firebase deploy --only hosting
```

### Automático (via script)

```bash
scripts\run_firebase_sync.bat
```

## Serviços Windows (NSSM)

O script `scripts/install_nssm_services.ps1` instala os serviços como Windows Services via NSSM:

```powershell
# Instalar (como administrador)
powershell -ExecutionPolicy Bypass -File scripts\install_nssm_services.ps1
```

Serviços instalados:
| Serviço | Descrição |
|---------|-----------|
| `IRAI-API` | FastAPI na porta 8888 |
| `IRAI-Collector` | Worker de coleta MT5 (60s) |
| `IRAI-FirebaseSync` | Sync dados → Firebase RTDB |

### Gerenciar serviços

```bash
# Verificar status
nssm status IRAI-API

# Reiniciar
nssm restart IRAI-API

# Parar
nssm stop IRAI-API

# Remover
nssm remove IRAI-API confirm
```

## Firebase RTDB Sync

O `scripts/firebase_sync.py` sincroniza dados do SQLite local para o Firebase Realtime Database:

- **Frequência:** A cada 60 segundos
- **Dados sincronizados:** Targets, overview, séries da sessão atual
- **Autenticação:** Service Account (`serviceAccountKey.json`)

## Startup Completo

Para iniciar todo o sistema localmente:

```bash
start_irai.bat
```

Este batch inicia 4 processos em janelas separadas:
1. FastAPI (porta 8888)
2. Collector (intervalo 60s)
3. Frontend Vite (porta 5175)
4. Firebase Sync

## Atualização Diária

### GEX Levels

Os dados de Gamma Exposure são atualizados pelo `scheduled_runner.py` (07:30) ou manualmente pelo `GEX_DAILY_ALL.bat` no projeto WDO×WIN pair trading (15 ativos). O step `[SYNC]` chama `scripts/sync_gex_to_irai.py`, que:

- grava os níveis no SQLite (`gex_levels`) e no Firebase RTDB (`summaries/gex/...`) — o site lê direto do RTDB, **sem redeploy**;
- publica o Pine Script no cofre `pine_vault/<sha256(PINE_SALT:PINE_PASSWORD)>` (senha no `.env` da raiz; nunca em `frontend/public`);
- regenera `frontend/src/gexLevels.js` (fallback estático).

As cadeias de opções brutas (CBOE/Deribit) ficam arquivadas em `wdo win pair trading/gex/data/chain_archive/AAAA-MM-DD/` para recálculo futuro.

## Fuso horário (importante)

`market_bars.timestamp_utc` usa o **relógio do broker** (Nova York + 7h: GMT+3 no verão americano, GMT+2 no inverno). A B3 é convertida de BRT com offset dinâmico (+6h/+5h) — ver `backend/timeconv.py`. O pregão B3 é definido como 09:00–18:30 BRT.

## Manutenção diária

Tarefa agendada **"IRAI Daily Maintenance"** (seg–sex 19:15) roda `scripts/daily_maintenance.py`: backup do SQLite em `D:\irai_backups` (7 cópias), limpeza de logs > 14 dias e retenção de 60 dias no RTDB.

### Recalibração

```bash
python scripts/calibrate_universal.py
```

Recomendado rodar semanalmente ou quando a acurácia cair.

## Troubleshooting

| Problema | Solução |
|----------|---------|
| API não inicia | Verificar porta 8888 livre: `netstat -an \| findstr 8888` |
| Collector não conecta MT5 | Verificar se o terminal MT5 está aberto e logado |
| Frontend porta em uso | Verificar que porta 5174 NÃO está sendo usada (pertence ao pair trading) |
| Firebase deploy falha | Verificar login: `firebase login` |
| GEX não aparece | Verificar target name no `gexLevels.js` (e.g., `USTEC` não `NAS100`) |
