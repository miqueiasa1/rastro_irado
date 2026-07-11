# Coding Conventions

**Analysis Date:** 2026-07-11

## Naming Patterns

**Files:**
- `snake_case.py` - For all Python modules and scripts (e.g., `collector.py`, `firebase_sync.py`).
- `PascalCase.jsx` - For all React component files (e.g., `Overview.jsx`, `TVNweChart.jsx`).
- `camelCase.js` - For frontend utility or static data modules (e.g., `gexLevels.js`).
- `UPPERCASE.md` - For primary documentation, roadmap tracking, and codebase maps (e.g., `PROJECT.md`, `STACK.md`).
- `kebab-case.md` - For general system documentation files under `docs/` (e.g., `getting-started.md`).

**Functions:**
- `snake_case` - For all Python functions (e.g., `get_connection`, `compute_from_db`).
- `_prefix_snake_case` - For private/internal Python methods or helpers (e.g., `_load_params`, `_get_series_data_sync`).
- `camelCase` - For JavaScript/React functions (e.g., `fetchData`, `handleZoom`).
- `PascalCase` - For React functional components definitions.

**Variables:**
- `snake_case` - For all Python local variables and parameters.
- `camelCase` - For JavaScript local variables and state hooks.
- `UPPER_SNAKE_CASE` - For global constants in both languages (e.g., `DB_PATH`, `BARS_PER_SESSION`, `TERMINALS`).
- `_` prefix - For unused variables (e.g., `for _ in range(3)`).

**Types/Classes:**
- `PascalCase` - For Python classes and dataclasses (e.g., `IRAIEngine`, `IRAISnapshot`, `FactorState`).
- Interfaces are not used (no TypeScript in frontend).

## Code Style

**Formatting:**
- **Python:** Standard PEP 8 coding style with 4-space indentation.
- **JavaScript/React:** JSX with 2-space indentation. Formatting rules verified via ESLint.
- **Styling:** Vanilla CSS class styling defined in `App.css` and applied via `className`, or inline style objects. Utility libraries (like TailwindCSS) are avoided.

**Linting:**
- Frontend: ESLint configured in `frontend/eslint.config.js`. Run with `npm run lint`.
- Backend: Manual style check (no static analysis tool configured).

## Import Organization

**Python Order:**
1. Standard library imports (e.g., `os`, `sys`, `sqlite3`, `math`).
2. Third-party packages (e.g., `numpy`, `pandas`, `fastapi`).
3. Local application imports (e.g., `from backend.db import get_connection`).

**JavaScript/React Order:**
1. React core modules (`react`, `createRoot`).
2. Style dependencies (`./index.css`, `./App.css`).
3. Component imports.
4. Static config/data files (`./gexLevels`).

**Grouping:**
- Blank lines must separate core import blocks.
- Relative paths are preferred for frontend imports (no compiler aliases configured).

## Error Handling

**Strategy:** Fail-safe execution with graceful degradation. Stale data or network offline flags should prevent system crashes.

**Patterns:**
- **Database transaction safety:** Migrations are wrapped in explicit database transactions (`BEGIN TRANSACTION`, `COMMIT`, `ROLLBACK` on except).
- **Graceful parameter reloading:** Parameter updates check for integrity. If parameters load fails, the system logs the error and continues running on previously loaded weights.
- **Stale factor markers:** When a terminal fails to retrieve data, the factors are logged as stale (via `stale_factors` arrays) rather than returning null snapshots.
- **React state safety:** REST/WebSocket fetch methods check status flags. If a connection is lost, state transitions to offline displays instead of raising runtime exceptions.

## Logging

**Framework:**
- Python standard `logging` library configured in worker processes (`backend/workers/collector.py`).
- Output redirected to logs: `api_crash.log` for FastAPI errors and `collector_start.log` for ingestion metrics.

**Patterns:**
- Ingestion steps log successfully completed cycles or specific terminal errors.
- Raw print statements are avoided in production code; structured logging or explicit print logging to log files is used.

## Comments

**When to Comment:**
- **Mathematical explanation:** Docstrings and comments must explain quantitative formula steps (e.g., Kalman process noise matrices initialization, Johansen spread calculation windows).
- **Sessões forex/Time offsets:** Document timezone shifts and pre-market alignment strategies (e.g., XP vs. Tickmill GMT translations).
- **Service definitions:** All modules start with a summary docstring explaining active endpoints or responsibilities.

**JSDoc/Docstrings:**
- Standard Python triple-quote docstrings (`"""`) on every class, public function, and API router.
- Brief inline comments for complex React hooks.

---

*Convention analysis: 2026-07-11*
*Update when patterns change*
