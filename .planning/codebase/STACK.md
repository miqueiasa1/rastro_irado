# Technology Stack

**Analysis Date:** 2026-07-11

## Languages

**Primary:**
- Python 3.11+ - Backend API, collector worker, calibration and synchronization scripts
- JavaScript (JSX/ESM) - React-based dashboard frontend logic and Vite configurations

**Secondary:**
- CSS - Vanilla CSS styling for the frontend (`App.css`, `index.css`)
- PowerShell - Windows services orchestration installer script (`scripts/install_nssm_services.ps1`)
- Batch (cmd.exe) - Startup and utility command scripts (`start_irai.bat`, `scripts/run_api.bat`, `scripts/run_firebase_sync.bat`)
- MQL5 - MetaTrader 5 expert advisor code (`SessionOpenHigh.mq5`)

## Runtime

**Environment:**
- Python 3.11+ (Windows environment) - Executor for data collectors, API server, and utilities
- Node.js 18.x/20.x + npm - Frontend development server and build runner
- MetaTrader 5 Terminal (64-bit Windows) - Three terminal instances (XP, Tickmill, Axi) running locally as data providers

**Package Manager:**
- npm 10.x (Frontend)
  - Lockfile: `package-lock.json` present
- pip (Backend)
  - Lockfile: None (packages installed directly in the python environment)

## Frameworks

**Core:**
- FastAPI 0.x - Python web framework for REST API and WebSocket endpoints
- React 19.2.5 - Single-page application frontend UI framework

**Testing:**
- None - No automated test runner or testing framework is configured. Verification is performed using ad-hoc python scripts in `scratch/`.

**Build/Dev:**
- Vite 8.0.10 - Frontend bundling, hot module reloading (HMR), and server runner
- Uvicorn 0.x - ASGI server implementation for running FastAPI backend
- NSSM (Non-Sucking Service Manager) - Wrapper to daemonize backend tasks as Windows Services

## Key Dependencies

**Critical:**
- MetaTrader5 5.0.5640 - Python library for integration with MetaTrader 5 terminals
- sqlite3 (Standard Library) - Single-file relational database storage running in Write-Ahead Logging (WAL) mode
- firebase-admin - Python SDK for Firebase Realtime Database and Cloud synchronization
- lightweight-charts 5.2.0 - TradingView lightweight charts library for financial charts
- recharts 3.8.1 - Redesigned chart library built with React and D3
- numpy & pandas - For linear algebra, time-series operations, and Kalman filter calculations
- statsmodels & scikit-learn - Ridge regression and Johansen cointegration analysis for multi-asset models calibration

**Infrastructure:**
- contextlib (Standard Library) - Lifespan events handling in FastAPI
- asyncio (Standard Library) - Async event loops, websocket broadcasts, and update events handling
- urllib (Standard Library) - Lightweight HTTP requester in sync scripts
- react-swipeable 7.0.2 - Swipe interactions helper on mobile devices

## Configuration

**Environment:**
- `.env` in root folder - Backend environment variables (manually parsed by `scripts/firebase_sync.py`), containing:
  - `FIREBASE_URL` - Target Firebase database URL
- `frontend/.env`, `frontend/.env.local`, `frontend/.env.production` - Frontend configurations containing:
  - `VITE_FIREBASE_URL` - Endpoint for remote Firebase RTDB data loading (fallback to local API if undefined)
- `.firebaserc` - Firebase project identifier (`rastromacro`)
- `firebase.json` - Firebase Hosting rewrite rules and folder configs

**Build:**
- `frontend/vite.config.js` - Vite configuration (defines React plugin, strictPort: 5175, process.env mapping)
- `frontend/eslint.config.js` - ESLint linter configuration

## Platform Requirements

**Development:**
- Windows OS (due to MetaTrader 5 Python library requiring native Windows MT5 terminal instances)
- Multi-terminal setup: XP, Tickmill, Axi MT5 installations

**Production:**
- Host: Windows (running MT5 terminals, API, Collector, and Sync via NSSM services)
- Cloud Hosting: Firebase Hosting (for public static hosting at https://rastromacro.web.app)
- Cloud Database: Firebase Realtime Database (RTDB) for real-time mobile sync

---

*Stack analysis: 2026-07-11*
*Update after major dependency changes*
