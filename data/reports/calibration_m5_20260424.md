# IRAI — Calibração Intraday (M5)

**Data:** 2026-04-24 21:35
**Sessões analisadas:** 252
**R² (OLS end-of-day):** 0.4630
**Alpha:** 1.3065
**Intercept:** 0.1580
**Acurácia direcional:** 66.4%

## Fatores (5 fatores finais)

| Fator | Peso | Sinal Esperado | σ sessão |
|-------|------|----------------|----------|
| dol | -0.4142 | − ✓ | 0.005593 |
| di | -0.2928 | − ✓ | 0.006311 |
| dxy | +0.0294 | − ⚠️ INV | 0.002814 |
| brent | +0.0187 | + ✓ | 0.017667 |
| china | +0.1409 | + ✓ | 0.003106 |
| mxn | -0.0414 | − ✓ | 0.003731 |

## Modelo

```
Score(t) = Σ wᵢ · zᵢ(t)
zᵢ(t) = retᵢ(t) / (σᵢ · √t)
P_up(t) = sigmoid(α · Score(t) + intercept)
```

## Parâmetros

```json
{
  "w_dol": -0.4142261713847629,
  "w_di": -0.292805602375866,
  "w_dxy": 0.02937329310207982,
  "w_brent": 0.018736667192921073,
  "w_china": 0.14094891494068296,
  "w_mxn": -0.04141429278341956,
  "sigma_dol_session": 0.005593464925892642,
  "sigma_di_session": 0.006311296078146768,
  "sigma_dxy_session": 0.002814461350972344,
  "sigma_brent_session": 0.017666796814145253,
  "sigma_china_session": 0.0031058211360761178,
  "sigma_mxn_session": 0.0037310624852264452,
  "alpha": 1.3064578581673973,
  "intercept": 0.15801395752887024
}
```
