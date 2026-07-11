# Codebase Structure

**Analysis Date:** 2026-07-11

## Directory Layout

```
rastro_irado/
├── .agent/                  # GSD agent definitions and workflows
├── .planning/               # GSD project plans, roadmaps, and codebase maps
│   └── codebase/            # [New] This directory containing codebase documents
├── backend/                 # Backend FastAPI and MT5 ingestion workers
│   ├── api/                 # API endpoint handlers
│   ├── irai/                # Quant models, Kalman filters, and cointegration calculations
│   └── workers/             # MT5 data collectors
├── data/                    # Local SQLite databases (gitignored)
├── docs/                    # Architecture, deployment, and testing documents
├── frontend/                # React dashboard web application
│   └── src/                 # React source code
│       └── components/      # Charting and detail sub-components
├── logs/                    # Operational logs (gitignored)
├── scratch/                 # Ad-hoc diagnostic and testing scripts
├── scripts/                 # Core calibration, sync, and backfilling utility scripts
├── SessionOpenHigh.mq5      # MT5 Indicator script
├── start_irai.bat           # Master windows start script
└── README.md                # General project overview
```

## Directory Purposes

**.agent/**
- Purpose: Contains GSD workspace configuration, workflow definitions, and agent instructions.
- Contains: `agents/` instructions, `get-shit-done/` templates and workflows, `skills/` custom scripts.
- Key files: `.agent/get-shit-done/workflows/map-codebase.md` - workflow for mapping the codebase.

**.planning/**
- Purpose: Tracks the status, decisions, backlog, and architecture maps of the project.
- Contains: `PROJECT.md` (active requirements), `ROADMAP.md` (milestones phases), and `codebase/` maps.

**backend/api/**
- Purpose: Handles REST and WebSocket routing, client connections, and server-side cache.
- Contains: Python ASGI routers and endpoints.
- Key files: `backend/api/main.py` - FastAPI server file.

**backend/irai/**
- Purpose: Quantitative calculation engine for probabilities, Kalman weights, and Johansen spreads.
- Contains: Time-series calculation scripts, Kalman filters, and math functions.
- Key files:
  - `backend/irai/engine.py` - Main engine orchestration (`IRAIEngine`).
  - `backend/irai/kalman.py` - Dynamic Kalman weighting implementation.
  - `backend/irai/johansen.py` - Cointegration tests.

**backend/workers/**
- Purpose: Background ingestion processes.
- Contains: MetaTrader 5 API polling workers.
- Key files: `backend/workers/collector.py` - data collector from MT5 terminal instances.

**data/**
- Purpose: Directory holding databases (not versioned in Git).
- Key files: `data/irai_live.db` - primary SQLite database in WAL mode.

**docs/**
- Purpose: Contains developer guides and system documentation.
- Contains: ARCHITECTURE.md, CONFIGURATION.md, DEPLOYMENT.md, DEVELOPMENT.md, TESTING.md, API.md.

**frontend/src/**
- Purpose: Frontend dashboard dashboard UI source files.
- Contains: Main React components, stylesheets, and assets.
- Key files:
  - `frontend/src/App.jsx` - Monolithic dashboard containing layouts, data handlers, and panels (1700+ lines).
  - `frontend/src/Overview.jsx` - Grid of cards displaying overview stats for all 20 assets.
  - `frontend/src/gexLevels.js` - Auto-generated GEX boundaries.
- Subdirectories: `frontend/src/components/` - Chart wrappers (TVNweChart.jsx, TVProbabilityChart.jsx, etc.).

**scratch/**
- Purpose: Contains throwaway tests, speed diagnostics, and verification scripts.
- Key files:
  - `scratch/verify_continuity_fixes.py` - Verifies Kalman state timestamp guards.
  - `scratch/diagnose_overview.py` - Verifies compute output structures.

**scripts/**
- Purpose: Operations, calibration, and synchronization scripts.
- Key files:
  - `scripts/calibrate_universal.py` - Calibrates factors and stores Ridge weights in SQLite.
  - `scripts/firebase_sync.py` - Uploads local SQLite data to Firebase Realtime Database.
  - `scripts/sync_gex_to_irai.py` - Parses GEX levels from Pine script exports.

## Key File Locations

**Entry Points:**
- `backend/api/main.py` - FastAPI server ASGI entry point.
- `backend/workers/collector.py` - Raw bar collector process.
- `frontend/src/main.jsx` - React dashboard web app mount.
- `start_irai.bat` - CLI launcher for local execution of the full application stack.

**Configuration:**
- `frontend/vite.config.js` - Vite development server port and asset rules config.
- `backend/db.py` - SQLite schema configurations.
- `.env` (Root) - Cloud database endpoint settings.
- `frontend/package.json` - Frontend dev package configurations.

**Core Logic:**
- `backend/irai/engine.py` - Risk index calculations orchestrations.
- `scripts/calibrate_universal.py` - Quantitative Ridge parameters solver.

**Testing:**
- `scratch/verify_continuity_fixes.py` - Dynamic state tests.
- `scratch/diagnose_overview.py` - Endpoint responses check.

**Documentation:**
- `README.md` - Setup and run commands.
- `docs/ARCHITECTURE.md` - Core system architectural documentation.
- `docs/CONFIGURATION.md` - Environment and active targets configuration parameters.

## Naming Conventions

**Files:**
- `snake_case.py` - Python modules and script utilities.
- `PascalCase.jsx` - React components (`Overview.jsx`, `TVNweChart.jsx`).
- `UPPERCASE.md` - Planning documents and main project readmes.
- `test_*.py` / `verify_*.py` - Test and validation scripts in `scratch/`.

**Directories:**
- `snake_case` or `flat-case` - For python packages and directories (`api`, `irai`, `workers`).
- `kebab-case` - Feature folders (`get-shit-done`).

## Where to Add New Code

**New Asset Target:**
- Ingest rules: Add to `TERMINALS` in `backend/workers/collector.py`.
- Asset Model settings: Register target in `asset_models` SQLite table.
- Weights: Execute `scripts/calibrate_universal.py` to calculate active Ridge coefficients.

**New Chart or Dashboard Element:**
- Chart component: Create in `frontend/src/components/TV[ElementName]Chart.jsx`.
- Layout integration: Embed in `frontend/src/App.jsx`.

**New Quantitative Predictor:**
- Math logic: Code in `backend/irai/kalman.py` or create helper module under `backend/irai/`.
- Integration: Call predictor from `backend/irai/engine.py:IRAIEngine.compute_from_db`.

**Utilities:**
- Operations or backfill scripts: Write in `scripts/`.
- Throwaway diagnostic tests: Write in `scratch/`.

## Special Directories

**data/**
- Purpose: Holds SQLite database files.
- Generated: Dynamically initialized by `backend/db.py:init_db`.
- Committed: No (specifically ignored in `.gitignore`).

**logs/**
- Purpose: Holds runtime crash logs and console streams.
- Generated: Initialized by processes or NSSM wrappers.
- Committed: No (specifically ignored in `.gitignore`).

---

*Structure analysis: 2026-07-11*
*Update when directory structure changes*
