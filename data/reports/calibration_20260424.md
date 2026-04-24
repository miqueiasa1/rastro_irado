# IRAI — Relatório de Calibração

**Data:** 2026-04-24 13:45
**Janela:** 236 dias úteis
**R²:** 0.5327
**Alpha (sigmoid):** 0.2919

## Pesos Estimados

| Fator | Peso | Sinal Esperado | Status |
|-------|------|----------------|--------|
| dol | -0.4450 | - | OK |
| di | -0.2876 | - | OK |
| vix | -0.2554 | - | OK |
| dxy | -0.0515 | - | OK |
| brent | +0.0296 | + | OK |
| us500 | -0.0536 | + | INVERTIDO |
| btcusd | -0.0327 | + | INVERTIDO |

## Volatilidades Diarias

| Fator | sigma_diaria | sigma_anual |
|-------|-------------|------------|
| dol | 0.00808 | 12.83% |
| di | 0.00917 | 14.56% |
| vix | 0.04540 | 72.06% |
| dxy | 0.00443 | 7.03% |
| brent | 0.02332 | 37.01% |
| us500 | 0.01187 | 18.84% |
| btcusd | 0.02709 | 43.01% |

## Interpretação

- **R² = 0.5327**: Bom poder explicativo dos fatores sobre o retorno WIN.
- **Alpha = 0.2919**: Controla quão agressivamente o score vira probabilidade.

## Parâmetros para model_params

```json
{
  "w_dol": -0.44500584404673377,
  "w_di": -0.2875668857901786,
  "w_vix": -0.2554283889982902,
  "w_dxy": -0.05146176700435462,
  "w_brent": 0.029631490111767116,
  "w_us500": -0.05364258897912983,
  "w_btcusd": -0.032684906828407495,
  "sigma_dol_daily": 0.008079715083439685,
  "sigma_di_daily": 0.009170847045303849,
  "sigma_vix_daily": 0.045395921830813896,
  "sigma_dxy_daily": 0.004425756645437375,
  "sigma_brent_daily": 0.02331538207959545,
  "sigma_us500_daily": 0.011870109179130558,
  "sigma_btcusd_daily": 0.02709322395249966,
  "alpha": 0.2919411590488433
}
```
