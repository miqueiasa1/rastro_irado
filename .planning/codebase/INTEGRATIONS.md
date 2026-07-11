# External Integrations

**Analysis Date:** 2026-07-11

## APIs & External Services

**Broker Data Feed (MetaTrader 5):**
- MetaTrader 5 Terminal Integration - Colets M5 (and other timeframes M1, M2, M15, M30, H1) bar data.
  - SDK/Client: `MetaTrader5` python package
  - Connection Method: IPC native library connection to local terminal processes
  - Terminals used:
    - XP: `C:\Program Files\MetaTrader 5 Terminal\terminal64.exe` (or fallbacks) for Brazilian B3 contracts (`WIN$N`, `WDO$N`, `DI1$N`)
    - Tickmill: `C:\Program Files\Tickmill MT5 Terminal\terminal64.exe` for international cross pairs, indices, and crypto
    - Axi: `C:\Program Files\Axi MetaTrader 5 Terminal\terminal64.exe` for iShares macro ETF factors
  - Auth: Local application permissions (must have terminal running and authenticated to broker)

**Realtime Cloud Database Sync (Firebase):**
- Firebase Realtime Database (RTDB) - Sincroniza dados computados do SQLite local para exibição no dashboard web hospedado.
  - SDK/Client: `firebase_admin` (Python)
  - Auth: Service account credential file `serviceAccountKey.json` placed in project root
  - Connection: REST/WebSocket via admin SDK to `FIREBASE_URL` env variable
  - Endpoint targets in Firebase RTDB:
    - `/session_date`
    - `/overview` (real-time card stats)
    - `/targets` (available monitor list)
    - `/series` (full intraday curves)
    - `/history_closes` (previous session prices)
    - `/last_updated` (timestamp of sync)

## Data Storage

**Databases:**
- SQLite (Local Single-File DB) - Armazena barras de mercado brutas, snapshots do IRAI, estados do filtro de Kalman e configurações de ativos.
  - Connection: via standard python module `sqlite3`
  - Mode: WAL (Write-Ahead Logging) enabled for safe concurrent writes from collector and reads from API/Engine
  - Path: `backend/data/irai_live.db` (configured as `DB_PATH` in `backend/db.py`)
  - Connection Timeout: 30 seconds

**File Storage:**
- None (Local filesystem only)

**Caching:**
- Server-side In-memory Cache - FastAPI backend stores calculated results.
  - Location: Dicts `series_cache` and `overview_cache_data` in `backend/api/main.py`
  - Invalidation: Programmatically cleared upon POST requests to `/api/internal/notify_update` triggered by the collector at the end of each cycle.

## Authentication & Identity

**Auth Provider:**
- Firebase Admin SDK (Cloud Sync)
  - Implementation: Python `credentials.Certificate` loading `serviceAccountKey.json`
- Local Access Dashboard
  - No authentication (designed as a private local-first tool)

## Monitoring & Observability

**Logs:**
- Local Filesystem Logs:
  - `api_crash.log` - Captures critical exceptions from the FastAPI server
  - `collector_start.log` - Captures logging outputs from the background collector worker
  - Python standard `logging` library configured in `backend/workers/collector.py` using format `%(asctime)s [%(levelname)s] %(message)s`

## CI/CD & Deployment

**Hosting:**
- Firebase Hosting - Public static web server hosting the dashboard UI.
  - Platform: Firebase CDN
  - Address: https://rastromacro.web.app
  - Command: `cd frontend && npm run build && npx firebase deploy --only hosting`
- Windows Services (Local Host) - Persistent background execution of API, Collector, and Firebase Sync.
  - Wrapper: NSSM (Non-Sucking Service Manager)
  - Automation: `scripts/install_nssm_services.ps1` sets up standard windows services:
    - `IRAI-API` (FastAPI)
    - `IRAI-Collector` (collector.py)
    - `IRAI-FirebaseSync` (firebase_sync.py)

## Environment Configuration

**Development:**
- Required env vars:
  - `FIREBASE_URL` - Database endpoint URL in `.env` (backend)
  - `VITE_FIREBASE_URL` - Firebase RTDB url in `frontend/.env` (optional; if missing, frontend defaults to localhost polling)
- Secrets location:
  - `.env` (gitignored)
  - `serviceAccountKey.json` (gitignored, contains Firebase service account certificate)

**Production (Windows Service host):**
- System-level path mappings handled via scripts/NSSM parameters.
- Secrets retrieved locally from environment and local filesystem (`serviceAccountKey.json`).

## Webhooks & Callbacks

**Incoming:**
- Internal FastAPI Update Hook - `/api/internal/notify_update` (POST)
  - Caller: `backend/workers/collector.py` at the end of a successful cycle
  - Action: Triggers cache clear on backend (`series_cache.clear()`, `overview_cache_data.clear()`) and triggers `data_updated_event.set()` to alert websocket listeners.

**Outgoing:**
- None

---

*Integration audit: 2026-07-11*
*Update when adding/removing external services*
