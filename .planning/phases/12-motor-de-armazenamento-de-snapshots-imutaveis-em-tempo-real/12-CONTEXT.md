# Phase 12: Motor de Armazenamento de Snapshots Imutáveis em Tempo Real (Zero-Repainting Live Mode) - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning
**Source:** User request & architectural analysis

<domain>
## Phase Boundary

This phase creates an append-only snapshot storage engine for IRAI in `rastro_irado`.
It persists real-time calculated values (P_up, score, verdict, price_diverge_z, pair_z, NWE curves, cumulative delta) into a new SQLite table `irai_live_snapshots` as each market bar completes.
It provides zero-repainting live chart viewing, sub-5ms API response latency, and realistic point-in-time signal auditability while maintaining an optional recalculated mode for model calibration.
</domain>

<decisions>
## Implementation Decisions

### Schema & Persistence (`backend/db.py`)
- New table `irai_live_snapshots` with composite primary key `(target, timeframe, session_date, timestamp_utc)`.
- Includes fields: `p_up`, `score`, `verdict`, `verdict_color`, `price_diverge_z`, `price_diverges`, `pair_z`, `pair_factor`, `pair_beta`, `pair_signal`, `win_return`, `win_current`, `win_open`, `cum_delta`, `cum_delta_norm`, `nwe_center_price`, `nwe_upper_price`, `nwe_lower_price`, `nwe_slope`, `nwe_up_price`, `nwe_down_price`, `is_ghost`, `is_live_captured`.
- Migration function `migrate_live_snapshots(db_path)` executed on `init_db()`.
- Helper functions `save_live_snapshots()` and `get_live_snapshots()`.

### Collector Worker (`backend/workers/collector.py`)
- At the conclusion of `run_collection_cycle()`, automatically calculate and persist the newest completed bar snapshots for active assets using `save_live_snapshots()`.

### API Endpoint (`backend/api/main.py`)
- Endpoint `/api/irai/series` supports query param `mode` (`live` | `recalculated`, default `live`).
- If `mode=live`, query `irai_live_snapshots`. Fallback seamlessly to `compute_from_db()` and backfill if live snapshots are missing for today.
- If `mode=recalculated`, execute `compute_from_db()` on-the-fly.

### Frontend Integration (`frontend/src/`)
- `useIraiData.js` passes `mode=live` by default in `fetchSeries`.
- `DetailHeader.jsx` displays badge **"LIVE IMUTÁVEL (Sem Repaint)"** and optional toggle.
</decisions>

<canonical_refs>
## Canonical References

- `backend/db.py` — Database schema, migration and connection handling
- `backend/workers/collector.py` — Real-time MT5 polling worker
- `backend/irai/engine.py` — Calculation engine for P_up, Z-scores, Kalman & Johansen
- `backend/api/main.py` — FastAPI service endpoints
- `frontend/src/hooks/useIraiData.js` — React data fetching hook
- `frontend/src/components/DetailHeader.jsx` — Header UI component
</canonical_refs>
