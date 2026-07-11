# Testing Patterns

**Analysis Date:** 2026-07-11

## Test Framework

**Runner:**
- No formal test runner (such as `pytest` or `unittest`) is integrated into the build pipeline or configured in package manifests.
- Validation is performed by running ad-hoc diagnostic scripts in the `scratch/` directory.

**Assertion Library:**
- Built-in Python `assert` statement (used in scripts like `scratch/verify_continuity_fixes.py`).
- Print-based verification (scripts print progress and log `[SUCCESS]` or print outputs for human verification).

**Run Commands:**
```bash
# Verify database query performance and content
python test_db.py

# Verify engine snapshot calculation calculations
python scripts/_test_engine.py

# Run Kalman state and pre-market alignment tests
python scratch/verify_continuity_fixes.py

# Run API overview endpoint diagnostics
python scratch/diagnose_overview.py

# Test API health endpoint
curl http://localhost:8888/api/health
```

## Test File Organization

**Location:**
- Utility verification scripts: `/scratch/` (contains 45+ check, test, and profile modules).
- Engine verification scripts: `/scripts/` (e.g., `scripts/_test_engine.py`).
- Root-level tests: `test.py`, `test_db.py`.
- No collocated tests in production directories (`backend/` or `frontend/`).

**Naming:**
- `test_*.py` - For unit-like check scripts (e.g., `scratch/test_state_loading.py`).
- `verify_*.py` - For behavioral checks (e.g., `scratch/verify_continuity_fixes.py`).
- `diagnose_*.py` - For exception tracing (e.g., `scratch/diagnose_overview.py`).
- `check_*.py` - For listing database records or stats (e.g., `scratch/check_db.py`).

**Structure:**
```
scratch/
  verify_continuity_fixes.py   # State and time alignments assertions
  diagnose_overview.py         # Endpoint integrity logs
  test_mt5.py                  # MT5 API connection logs
  ...
```

## Test Structure

**Suite Organization:**
Tests are structured as standalone functions executed under the main guard:
```python
def test_timestamp_guard():
    # 1. Arrange/Clean state
    conn = get_connection()
    # 2. Act
    save_kalman_state(conn, ...)
    # 3. Assert
    state = conn.execute(...).fetchone()
    assert state["timestamp_utc"] == "expected_time"
    # 4. Clean up
    conn.close()

if __name__ == "__main__":
    test_timestamp_guard()
```

## Mocking

- **Approach:** No mocking libraries (like `unittest.mock`) are utilized.
- **Database isolation:** Tests perform in-place setup and teardown on the live SQLite database (cleaning up records using SQL `DELETE` calls during teardown) or interact with dummy target identifiers (e.g., `slug = "test_asset"`).
- **Network calls:** External APIs (like MT5 or Firebase) are tested by making real connection attempts.

## Coverage

- **Requirements:** None. No coverage statistics are collected or enforced.
- **Exclusions:** All files are excluded as there is no coverage runner configured.

## Test Types

**Unit Tests:**
- Evaluates specific functions like `save_kalman_state` guards or `compute_from_db` pre-market calculations.
- Executed manually using script files.

**Integration Tests:**
- Verifies system integration by calling local FastAPI endpoints (via `scratch/test_endpoints.py` or curl) while uvicorn is running.

**Manual Verification (Frontend):**
1. Launch full stack via `start_irai.bat`.
2. Access dashboard in browser at `http://localhost:5175`.
3. Check the card overview: verify that 20 targets load and display directional probability percentages.
4. Select a specific asset: verify probability curve, NWE envelope, GEX levels toggle, and heatmap rendering.
5. Toggle WebSocket data updates: verify that tick changes propagate in real time without screen flashing.

---

*Testing analysis: 2026-07-11*
*Update when test patterns change*
