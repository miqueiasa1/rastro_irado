---
status: resolved
trigger: não abre o dashboard. verifique a causa.
updated: 2026-05-03
---

# Symptoms
- Expected: Dashboard opens at http://localhost:5175
- Actual: Dashboard crashes completely (blank screen)
- Timeline: Started after unifying V1 and V2 models

# Root Cause
1. `Overview.jsx`: `hasV2` checks were evaluating `now.p_up_v2 !== undefined`. Since the backend returns `null` for `p_up_v2` when V2 data isn't fully initialized, `null !== undefined` evaluated to `true`. React then tried to execute `pUpV2.toFixed(0)` where `pUpV2` was `null`, throwing a fatal error.
2. `App.jsx` (Detailed View): During the V1/V2 API merge, the `score` property was renamed to `score_v1`. However, `App.jsx` line 1128 still tried to render `now.score.toFixed(2)`. Since `now.score` was `undefined`, this threw `Cannot read properties of undefined (reading 'toFixed')` and crashed the app when an asset was clicked.

# Fix
1. Updated `!== undefined` to `!= null` in both `Overview.jsx` and `App.jsx` to correctly handle `null` values.
2. Updated `App.jsx` to use `(now.score_v1 || now.score || 0).toFixed(2)` instead of `now.score.toFixed(2)`.
3. Added default values to `SignalGauge` arguments (`pUp = 50`, `score = 0`) to prevent any further undefined references.

# Files Changed
- `c:\Users\ryzen\Downloads\Antigravity\rastro_irado\frontend\src\Overview.jsx`
- `c:\Users\ryzen\Downloads\Antigravity\rastro_irado\frontend\src\App.jsx`
