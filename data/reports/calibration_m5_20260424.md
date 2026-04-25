# IRAI — Calibração Intraday (M5)

**Data:** 2026-04-24 21:05
**Sessões analisadas:** 252
**R² (OLS end-of-day):** 0.4654
**Alpha:** 1.3311
**Intercept:** 0.1586
**Acurácia direcional:** 66.4%

## Fatores (5 fatores finais)

| Fator | Peso | Sinal Esperado | σ sessão |
|-------|------|----------------|----------|
| dol | -0.4105 | − ✓ | 0.005593 |
| di | -0.2867 | − ✓ | 0.006311 |
| vix | -0.0674 | − ✓ | 0.024366 |
| dxy | +0.0146 | − ⚠️ INV | 0.002814 |
| brent | +0.0280 | + ✓ | 0.017667 |
| iv | +0.0000 | − ⚠️ INV | 0.001000 |
| china | +0.1039 | + ✓ | 0.003106 |
| mxn | -0.0303 | − ✓ | 0.003731 |

## Modelo

```
Score(t) = Σ wᵢ · zᵢ(t)
zᵢ(t) = retᵢ(t) / (σᵢ · √t)
P_up(t) = sigmoid(α · Score(t) + intercept)
```

## Parâmetros

```json
{
  "w_dol": -0.41050009425309997,
  "w_di": -0.2867277443585347,
  "w_vix": -0.06744958191524297,
  "w_dxy": 0.01462457571402536,
  "w_brent": 0.02799362516384304,
  "w_iv": 1.3877787807814457e-17,
  "w_china": 0.10393536784645438,
  "w_mxn": -0.030320798008800026,
  "sigma_dol_session": 0.005593464925892642,
  "sigma_di_session": 0.006311296078146768,
  "sigma_vix_session": 0.024366308348349585,
  "sigma_dxy_session": 0.002814461350972344,
  "sigma_brent_session": 0.017666796814145253,
  "sigma_iv_session": 0.001,
  "sigma_china_session": 0.0031058211360761178,
  "sigma_mxn_session": 0.0037310624852264452,
  "alpha": 1.3311334909775199,
  "intercept": 0.15855173193243843
}
```
