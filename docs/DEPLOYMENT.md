# Deploy — IRAI

## Ambientes

| Ambiente | URL | Dados |
|----------|-----|-------|
| **Local** | http://localhost:5175 | API local (porta 8888) + SQLite |
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

Os dados de Gamma Exposure são atualizados automaticamente quando o `GEX_DAILY_ALL.bat` é executado no projeto WDO×WIN pair trading. O step `[SYNC]` no final do batch chama `scripts/sync_gex_to_irai.py`.

Fluxo:
```
GEX_DAILY_ALL.bat
    ├── [1-11/11] Engines GEX (11 ativos)
    ├── Git commit do .pine
    └── [SYNC] sync_gex_to_irai.py → frontend/src/gexLevels.js
```

Após a atualização do `gexLevels.js`:
- **Local:** O Vite HMR aplica automaticamente
- **Web:** Requer rebuild + deploy: `cd frontend && npm run build && npx firebase deploy --only hosting`

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
