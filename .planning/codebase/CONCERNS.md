# Codebase Concerns

**Analysis Date:** 2026-07-11

## Tech Debt

**Monolithic React Dashboard:**
- Issue: The frontend dashboard is built as a single monolithic component file containing 1700+ lines of code. It handles UI state, layout, sub-panel logic, REST API polling, and WebSocket connection listeners in one place.
- Files: `frontend/src/App.jsx`
- Why: Rapid prototyping and deployment of features without intermediate modular planning.
- Impact: High complexity, making refactoring or adding new UI panels highly error-prone and hard to trace.
- Fix approach: Extract panels (e.g. CardGrid, Sidebar, ChartSection, SettingsPanel) into separate files inside `frontend/src/components/`.

**Hardcoded MetaTrader 5 Paths:**
- Issue: Paths to MetaTrader 5 executables for XP, Tickmill, and Axi brokers are hardcoded as raw string lists.
- Files: `backend/workers/collector.py` (lines ~31-62)
- Why: Simplicity of local path resolutions during development setup.
- Impact: If the installation folder changes or if the code is run on another workstation, the collector script must be modified.
- Fix approach: Move path strings to a backend configuration file or load them from environment variables.

**Duplicate test setups in scratch scripts:**
- Issue: 45+ files in the `scratch/` folder contain duplicate SQLite setup logic and database paths resolutions.
- Files: `scratch/*.py`
- Why: Created ad-hoc to test specific bug fixes or verify calibration performance inline.
- Impact: Maintenance overhead; changes to database schema or paths require updating multiple scratch scripts.
- Fix approach: Consolidate testing code in a centralized `/tests` package and configure a standard test suite with `pytest`.

## Known Bugs

**Single-Connection limit in MetaTrader 5 Python Library:**
- Symptoms: If one broker terminal hangs or experiences a connection timeout, it delays the entire collection sequence, which can cause other targets to miss data updates and be marked as "stale".
- Trigger: Sequentially calling `mt5.initialize(path=...)` for each broker in the collector process.
- Files: `backend/workers/collector.py` (lines ~150-188)
- Workaround: The collector implements fallbacks and timeouts (5s to 15s) but still operates sequentially.
- Root cause: The `MetaTrader5` python library restriction of only permitting a single terminal connection per process.
- Fix: Spawn separate background subprocesses for each broker collector (one process for XP, one for Tickmill, one for Axi) that write to the WAL-enabled SQLite database in parallel.

## Security Considerations

**Firebase Service Account Key in Project Root:**
- Risk: Exposing the Firebase service account certificate (`serviceAccountKey.json`), which grants administrative write access to the Firebase Realtime Database.
- Files: `serviceAccountKey.json` (placed in root)
- Current mitigation: Added to `.gitignore` to prevent commits to public repositories.
- Recommendations: Load Firebase credentials from a secure environment variable (e.g., as base64-encoded strings) in production.

## Performance Bottlenecks

**On-Demand calculations block API requests:**
- Problem: Math operations (Kalman updates, Johansen cointegration) are computed synchronously when API or WebSocket requests are made.
- Files: `backend/api/main.py` (`_get_series_data_sync` / `_get_overview_data_sync`) and `backend/irai/engine.py`.
- Measurement: High response latency on initial loads when calculating historical series (up to 500ms per series).
- Cause: Complex calculations are performed inside the FastAPI server's request threads instead of being pre-cached.
- Improvement path: Compute risk index snapshots inside the collector worker immediately after new bar ingestions, store computed metrics in `irai_snapshots` SQLite table, and serve read-only queries from the database.

## Fragile Areas

**Timezone offset shifts:**
- Why fragile: Brazilian B3 contracts (`WIN$N`, `WDO$N`) open at 09:00 BRT. The system translates Tickmill server time (EEST) to BRT using hardcoded hour differences. Changes in Daylight Saving Time (DST) on the broker side shift the hour alignments, which can break the pre-market ghost bar filters.
- Common failures: Return data showing returns in pre-market or ghost filters blocking initial regular session bars.
- Safe modification: Retrieve time offsets programmatically from the MT5 broker terminal status or use timezone-aware datetime objects (`pytz` or standard `zoneinfo`).
- Test coverage: Partially verified in `scratch/verify_continuity_fixes.py` but relies on static test dates.

## Scaling Limits

**Local Windows environment dependency:**
- Current capacity: Single-user execution on a local workstation.
- Limit: MetaTrader 5 Python library does not run natively on Linux, which prevents standard cloud container deployment (e.g. Docker, AWS ECS).
- Symptoms at limit: High infrastructure overhead for trading rooms requiring centralized servers.
- Scaling path: Run MT5 terminals inside Windows Server VM instances or configure Wine-emulated environments in Linux containers.

## Test Coverage Gaps

**Quantitative equations validation:**
- What's not tested: Correctness of Kalman filter updating matrices and Johansen cointegration eigenvectors calculation.
- Risk: Code changes to math equations could introduce silent errors (e.g., incorrect Kalman gain coefficients) that degrade model predictions without throwing errors.
- Priority: High.
- Difficulty to test: Requires Mock datasets with known statistical spreads to check for expected convergence outputs.

---

*Concerns audit: 2026-07-11*
*Update as issues are fixed or new ones discovered*
