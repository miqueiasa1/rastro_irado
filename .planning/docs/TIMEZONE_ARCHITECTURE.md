# IRAI Timezone Architecture & Data Alignment

## The Problem: Real-World Mismatch
The IRAI system merges data from two vastly different geographical contexts:
- **Global Macro Factors (Tickmill)**: Collects data such as BTCUSD, SPX500, EURUSD. The broker's server time is **EEST (Eastern European Summer Time, UTC+3)**.
- **Target Assets (XP Investimentos)**: Collects data for Brazilian assets like WIN$N and WDO$N. The broker's server time is **BRT (Brasília Time, UTC-3)**.

Because both brokers save their internal timestamps into the database without timezone-aware offsets (essentially storing local server time as UTC strings), the system was blindly merging the data.
For example, a bar collected at `09:00 BRT` for WIN$N was being paired with a global macro bar from `09:00 EEST`. However, `09:00 BRT` actually corresponds to `15:00 EEST`. This 6-hour mismatch caused the engine to evaluate global risks using data that occurred 6 hours prior to the actual Brazilian market movement, severely impacting the correlation algorithm and causing UI glitches (such as "ghost bars" extending for 6 hours).

## The Solution: Tickmill as the Global Reference (EEST)
To establish a causal, synchronized timeline, the entire quantitative engine must run on a unified temporal axis. We elected the **Tickmill Server Time (EEST)** as the primary axis because it commands over 20+ global macro assets that trade 24/5 or 24/7.

### 1. Backend Data Alignment (`engine.py`)
When loading `market_bars` from the SQLite database, the system identifies target assets originating from B3 (i.e., those with a configured `session_start_h` not equal to 0, like `WIN$N`).
For these assets, the system shifts the raw database timestamp forward by **+6 hours**:
```python
is_b3 = session_start != 0
if is_b3 and d["symbol"] == data_target:
    ts_dt += timedelta(hours=6)
```
This guarantees that `09:00 BRT` natively aligns with `15:00 EEST` within the `all_timestamps` array. The Kalman filter and Johansen Cointegration tests now receive true simultaneous tick snapshots. 

### 2. Pre-Market Ghost Bars & 0% Return Forcing
Before the market opens (e.g., from `00:00` to `08:55` BRT), B3 assets have no active data. The engine generates synthetic "ghost bars" to pad the timeline and allow the global macroeconomic risk (IRAI) to be visible 24/7.
- During this `is_pre_market` phase, the target's `win_return` is forcefully overridden to `0.0` in the `IRAISnapshot`.
- This ensures the UI displays a perfectly flat line strictly at the `0%` mark, preventing any false return "drift" calculated between yesterday's close and today's future open.

### 3. Frontend Dual-Axis Display (`App.jsx`)
Because the backend now transmits a mathematically pure Tickmill-aligned timeline, the frontend receives timestamps in **EEST**.
The React UI plots two separate X-Axes to accommodate the global vs. local context:
- **Primary Axis (Top - Tickmill Time)**: Receives the raw API timestamp (e.g., `15:00`). This unifies the visual flow for global macro events.
- **Secondary Axis (Bottom - BRT)**: If the API signals that the asset is a B3 target (`is_b3 = true`), the frontend mathematically reconstructs the Brazilian timeline by subtracting 6 hours (`toLocalTime(timeTickmill, -6)`), resulting in `09:00`. This amber-colored axis guides the local trader in their native timezone.

## Summary of Offsets
| Location | Timezone | Offset vs UTC | Difference vs B3 |
|----------|----------|---------------|------------------|
| XP (B3) | BRT | UTC-3 | 0 hours |
| Tickmill | EEST | UTC+3 | +6 hours |

**Rule of Thumb**: When reading the database directly, B3 assets are in BRT and Macro assets are in EEST. Once processed by `engine.py`, the entire system (including JSON responses) operates strictly in EEST.
