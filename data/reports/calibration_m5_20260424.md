# IRAI — Calibração Intraday (M5)

**Data:** 2026-04-24 20:58
**Sessões analisadas:** 252
**R² (OLS end-of-day):** 0.4661
**Alpha:** 1.3308
**Intercept:** 0.1575
**Acurácia direcional:** 66.2%

## Fatores (5 fatores finais)

| Fator | Peso | Sinal Esperado | σ sessão |
|-------|------|----------------|----------|
| dol | -0.4064 | − ✓ | 0.005593 |
| di | -0.2885 | − ✓ | 0.006311 |
| vix | -0.0832 | − ✓ | 0.024366 |
| dxy | +0.0192 | − ⚠️ INV | 0.002814 |
| brent | +0.0189 | + ✓ | 0.017667 |
| iv | -0.0000 | − ✓ | 0.001000 |
| china | +0.1109 | + ✓ | 0.003106 |
| mxn | -0.0364 | − ✓ | 0.003731 |
| dax | -0.0381 | + ⚠️ INV | 0.007859 |

## Modelo

```
Score(t) = Σ wᵢ · zᵢ(t)
zᵢ(t) = retᵢ(t) / (σᵢ · √t)
P_up(t) = sigmoid(α · Score(t) + intercept)
```

## Parâmetros

```json
{
  "w_dol": -0.40640402353639604,
  "w_di": -0.28852603936535176,
  "w_vix": -0.08318246578498639,
  "w_dxy": 0.019207305435585038,
  "w_brent": 0.018907980163792346,
  "w_iv": -6.938893903907228e-18,
  "w_china": 0.11089237724265374,
  "w_mxn": -0.03640780907109241,
  "w_dax": -0.03813104025458887,
  "sigma_dol_session": 0.005593464925892642,
  "sigma_di_session": 0.006311296078146768,
  "sigma_vix_session": 0.024366308348349585,
  "sigma_dxy_session": 0.002814461350972344,
  "sigma_brent_session": 0.017666796814145253,
  "sigma_iv_session": 0.001,
  "sigma_china_session": 0.0031058211360761178,
  "sigma_mxn_session": 0.0037310624852264452,
  "sigma_dax_session": 0.007858973209994182,
  "alpha": 1.3308412961696108,
  "intercept": 0.15748900441126648
}
```
