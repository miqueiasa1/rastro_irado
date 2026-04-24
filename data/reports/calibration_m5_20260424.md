# IRAI — Calibração Intraday (M5)

**Data:** 2026-04-24 15:30
**Sessões analisadas:** 252
**R² (OLS end-of-day):** 0.4598
**Alpha:** 1.4154
**Intercept:** 0.1661
**Acurácia direcional:** 67.5%

## Fatores (5 fatores finais)

| Fator | Peso | Sinal Esperado | σ sessão |
|-------|------|----------------|----------|
| dol | -0.4231 | − ✓ | 0.005585 |
| di | -0.2723 | − ✓ | 0.006308 |
| vix | -0.1364 | − ✓ | 0.024366 |
| dxy | -0.0256 | − ✓ | 0.002813 |
| brent | +0.0149 | + ✓ | 0.017665 |

## Modelo

```
Score(t) = Σ wᵢ · zᵢ(t)
zᵢ(t) = retᵢ(t) / (σᵢ · √t)
P_up(t) = sigmoid(α · Score(t) + intercept)
```

## Parâmetros

```json
{
  "w_dol": -0.4230965259960284,
  "w_di": -0.2723322624197104,
  "w_vix": -0.13639345750099363,
  "w_dxy": -0.025615181083411057,
  "w_brent": 0.014894334926810452,
  "sigma_dol_session": 0.005585321544772558,
  "sigma_di_session": 0.006308009314367369,
  "sigma_vix_session": 0.02436566272622027,
  "sigma_dxy_session": 0.0028131934765727997,
  "sigma_brent_session": 0.01766530076608562,
  "alpha": 1.4153748081510242,
  "intercept": 0.1660542552308479
}
```
