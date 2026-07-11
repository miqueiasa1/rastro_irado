# System Architecture

**Analysis Date:** 2026-07-11

## Pattern Overview

**Overall:** Modular Multiprocess Service Architecture (FastAPI Backend + SQLite WAL database + React SPA Frontend + Background Workers).

**Key Characteristics:**
- **Local-first with cloud mirror:** Core data capture and heavy calculation run on a local Windows machine. Real-time updates are synced to Firebase Realtime Database to allow zero-cost cloud mirroring (mobile access).
- **Multiprocess execution:** Separated processes for API server, worker collector, and synchronization script, coordinated as Windows Services.
- **SQLite WAL concurrency:** SQLite database serving as a central message queue and data storage, using Write-Ahead Logging (WAL) for conflict-free concurrent reads and writes.
- **Hybrid Static/Dynamic Quantitative Engine:** Incorporates offline batch calibration (V2 Ridge regression) with real-time adaptive parameter adjustment (Kalman Filter) and dynamic cointegration testing (Johansen test).

## Layers

**Data Ingestion Layer (Collector):**
- Purpose: Connects to MetaTrader 5 broker terminals, fetches raw OHLCV and volume tick data, and writes to database.
- Location: `backend/workers/collector.py`
- Contains: MetaTrader 5 connectors, bar delta calculations, and service loop logic.
- Depends on: MetaTrader 5 terminals, SQLite.
- Used by: Ran as a standalone background service.

**Persistence Layer (Database):**
- Purpose: Safe and fast storage for market bars, snapshots, models configurations, and calibration logs.
- Location: `backend/db.py`
- Contains: Table schemas, database initializers, and migration methods.
- Depends on: Standard `sqlite3` library.
- Used by: Collector, API backend, calibration scripts.

**Model/Calculation Layer (IRAI Engine):**
- Purpose: Quant calculations: computes z-scores, runs Kalman filter step updates, verifies cointegration thresholds, and returns prob snapshots.
- Location: `backend/irai/`
- Contains:
  - `engine.py` - Core calculation logic and parameter loaders (`IRAIEngine`).
  - `kalman.py` - Real-time weights adjustment (`KalmanFilterWrapper`).
  - `johansen.py` - Cointegration tests (`check_cointegration`).
- Depends on: Persistence layer, numpy, pandas, statsmodels, scikit-learn.
- Used by: FastAPI backend, calibration scripts, diagnostic scripts.

**Service/API Layer (FastAPI Backend):**
- Purpose: Serves REST endpoints, runs WebSocket push server, and manages calculated metrics cache.
- Location: `backend/api/main.py`
- Contains: FastAPI router, cache dictionary, websocket manager, and update listeners.
- Depends on: Model layer, persistence layer.
- Used by: Frontend dashboard, Firebase Sync worker.

**Sync Layer (Firebase Sync):**
- Purpose: Polls local FastAPI, strips payloads to fit size bounds, and pushes state to Firebase RTDB.
- Location: `scripts/firebase_sync.py`
- Contains: Data polling and payload compression logic.
- Depends on: FastAPI endpoints, Firebase Admin SDK.
- Used by: Ran as a background sync script.

**Presentation Layer (React Frontend):**
- Purpose: Interactive user dashboard rendering curves, tables, cointegration signals, and GEX levels.
- Location: `frontend/src/`
- Contains: React components, chart wrappers, layout grids, and Firebase sync adapters.
- Depends on: Recharts, lightweight-charts, React 19.
- Used by: Web browsers (local and deployed on Firebase Hosting).

## Data Flow

**Real-Time Data Collection and Calculation Loop:**

1. **Ingest:** Background collector (`collector.py`) wakes up every 60s -> Connects sequentially to B3 (XP), Tickmill, and Axi terminals -> Fetches M5 bars.
2. **Transform & Persist:** Collector calculates bar delta and writes bars to `market_bars` table using `INSERT OR REPLACE` for the current bar and `INSERT OR IGNORE` for historical bars.
3. **Notify:** Collector sends a HTTP POST request to `/api/internal/notify_update` on FastAPI.
4. **Invalidate Cache:** FastAPI handler reloads latest parameters, clears in-memory `series_cache` and `overview_cache_data`, and calls `data_updated_event.set()`.
5. **Calculate (On-Demand):** When API receives requests or WebSocket updates, FastAPI invokes `engine.compute_from_db()`:
   - Fetches historical closes for target and factors.
   - Computes z-scores based on calibrated variances (`sigmas`).
   - Version `v1`: applies static Ridge weights (`model_params`).
   - Version `v2`: loads previous Kalman mean/covariance (`kalman_state`), runs Kalman update step sequentially, and updates weights dynamically.
   - Pair targets: runs `check_cointegration()` over a 95-bar window to calculate the spread z-score.
   - Calculates directional probability: $P(up) = \text{sigmoid}(\text{score})$.
6. **Push:** FastAPI WS handler streams computed JSON payload to all connected WebSocket clients.
7. **Cloud Mirroring:** The Firebase Sync script (`firebase_sync.py`) queries the local API every 60s -> Formats lean snapshots -> Uploads JSON objects directly to Firebase RTDB -> Cloud dashboard renders data directly from Firebase RTDB.

**State Management:**
- **Market Data:** Persistent in single-file SQLite database `data/irai_live.db`.
- **Dynamic Filter State:** Kalman filter state (mean and covariance) persisted in the `kalman_state` SQLite table after each session.
- **Server Cache:** In-memory dictionary in `backend/api/main.py`, matching `(target, session_date, version, timeframe)`.

## Key Abstractions

**`IRAIEngine` (`backend/irai/engine.py`):**
- Purpose: Central singleton coordinating active targets, parameters reloading, and calculations loop.
- Pattern: Singleton.

**`KalmanFilterWrapper` (`backend/irai/kalman.py`):**
- Purpose: Class wrapping state transition matrices, measurement noise parameters, and the Kalman equations update step.
- Pattern: Strategy/State wrapper.

**`IRAISnapshot` (`backend/irai/engine.py`):**
- Purpose: Structured data class storing all probability metrics, verdicts, factor contributions, and spread z-scores at a single point in time.
- Pattern: Data Transfer Object (DTO).

## Entry Points

**FastAPI server:**
- Location: `backend/api/main.py`
- Command: `python -m uvicorn backend.api.main:app` (Port 8888 or 8889)
- Responsibility: REST router and WebSocket server.

**Collector Service:**
- Location: `backend/workers/collector.py`
- Command: `python backend/workers/collector.py`
- Responsibility: MetaTrader 5 connectors pool and raw data feed.

**Firebase Sync Service:**
- Location: `scripts/firebase_sync.py`
- Command: `python scripts/firebase_sync.py`
- Responsibility: Local API polling and Firebase RTDB updating.

**Frontend Development Server:**
- Location: `frontend/`
- Command: `npm run dev` (Port 5175)
- Responsibility: Local web server hosting dashboard assets.

## Error Handling

**Strategy:** Fail-safe design with stale flags and fallback parameters to prevent dashboard white-screens.

**Patterns:**
- **Broker Offline:** If a terminal falls offline (XP or Tickmill), the collector logs a warning, skips collection for those assets, and continues. Calculated metrics will flag affected factors as "stale" (using `stale_flags` column in SQLite).
- **FastAPI Crash Guard:** Uncaught exceptions are handled at the router boundary and printed to `api_crash.log`, returning a standard JSON error response instead of dropping the server.
- **Empty Data Fallback:** If `compute_from_db` has no bars, it returns an empty list, and the API returns a `404 Sem dados` message gracefully.
- **State Guard:** Kalman filter loading checks timestamps. If a save request is older than the current database state, it is rejected to prevent database corruption.

---

*Architecture analysis: 2026-07-11*
*Update when major patterns change*
