# IRAI Multi-Asset — Mapa de Fatores por Ativo

> [!NOTE]
> 20 modelos ativos extraídos diretamente do banco de dados (irai.db).
> Regras aplicadas:
> 1. Ativos internacionais **não** utilizam ativos BR (WIN, DOL, DI1).
> 2. Índices americanos (US500, US30, USTEC) **não** utilizam outros índices americanos.
> 3. Horários das Sessões respeitados.
> 4. **Otimização (Score Misto):** Modelos classificados por 70% Acurácia + 30% R² para garantir robustez estrutural.

---

## Ranking por Acurácia (Pós-Isolamento e Score Misto)

| # | Ativo | ACC | R² | Fatores | Fator Principal |
|---|---|---|---|---|---|
| 1 | 🇦🇺 **AUD/USD** | **91.1%** | **0.7532** | 8 | USDJPY (-0.5702) |
| 2 | 🇪🇺🇨🇭 **EUR/CHF** | **91.1%** | **0.8519** | 8 | USDCAD (0.9042) |
| 3 | 🇨🇦🇨🇭 **CAD/CHF** | **90.1%** | **0.7376** | 8 | EURCHF (0.7352) |
| 4 | 🇺🇸 **S&P 500** | **89.6%** | **0.8508** | 8 | iSharesUSEmerging+ (0.3320) |
| 5 | 🇪🇺 **EUR/USD** | **88.6%** | **0.8104** | 8 | iSharesTreasury1-3+ (0.7097) |
| 6 | 🇨🇭 **USD/CHF** | **88.1%** | **0.7752** | 8 | GBPUSD (-1.0670) |
| 7 | 💻 **Nasdaq 100** | **86.6%** | **0.7754** | 8 | USDCAD (-0.3927) |
| 8 | 🇬🇧 **GBP/USD** | **85.6%** | **0.7272** | 8 | AUDUSD (0.5421) |
| 9 | 💵 **Mini Dólar** | **84.2%** | **0.5473** | 8 | USDCHF (-7.7652) |
| 10 | 🏛️ **Dow Jones** | **84.2%** | **0.7412** | 8 | EURUSD (2.1776) |
| 11 | 🇨🇦 **USD/CAD** | **84.2%** | **0.5904** | 8 | EURGBP (-0.4798) |
| 12 | 🇧🇷 **Mini Índice** | **83.2%** | **0.5876** | 8 | WDO$N (-0.6479) |
| 13 | 🇪🇺🇦🇺 **EUR/AUD** | **81.7%** | **0.6186** | 8 | CADCHF (-0.5625) |
| 14 | 🇯🇵 **USD/JPY** | **81.2%** | **0.5663** | 8 | USDCHF (0.9302) |
| 15 | 🇦🇺🇳🇿 **AUD/NZD** | **80.7%** | **0.2577** | 8 | EURAUD (-0.3237) |
| 16 | 🇪🇺🇬🇧 **EUR/GBP** | **75.7%** | **0.3103** | 7 | EURAUD (0.4392) |
| 17 | ₿ **Bitcoin** | **75.2%** | **0.4323** | 8 | EURGBP (-1.2881) |
| 18 | 🥇 **Ouro** | **73.3%** | **0.2852** | 8 | AUDNZD (0.9794) |
| 19 | 🇪🇺🇯🇵 **EUR/JPY** | **72.3%** | **0.2326** | 7 | EURAUD (0.9797) |
| 20 | 🇬🇧🇯🇵 **GBP/JPY** | **69.8%** | **0.1879** | 7 | EURUSD (-0.2611) |

---

## Detalhamento Completo por Ativo

### 1. 🇦🇺 AUD/USD (AUDUSD) — ACC 91.1% (Sessão: 00h - 24h)
```
α=3.0445

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  USDJPY      -0.570217   0.00513   ↓ VENDA
  USDCAD      -0.562368   0.00277   ↓ VENDA
  EURJPY      0.284779    0.00356   ↑ COMPRA
  GBPJPY      0.250872    0.00404   ↑ COMPRA
  CADCHF      0.152769    0.00377   ↑ COMPRA
  XAUUSD      0.058449    0.01626   ↑ COMPRA
  CHINA50     0.049264    0.00941   ↑ COMPRA
  VIX         -0.045878   0.03882   ↓ VENDA
```

### 2. 🇪🇺🇨🇭 EUR/CHF (EURCHF) — ACC 91.1% (Sessão: 00h - 24h)
```
α=2.4198

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  USDCAD      0.904151    0.00277   ↑ COMPRA
  USDJPY      -0.876736   0.00513   ↓ VENDA
  CADCHF      0.873897    0.00377   ↑ COMPRA
  EURJPY      0.866244    0.00356   ↑ COMPRA
  iSharesTreasury1-3+  -0.164514   0.00052   ↓ VENDA
  CHINA50     0.022658    0.00941   ↑ COMPRA
  iSharesBrazil+  0.016980    0.01074   ↑ COMPRA
  VIX         0.003487    0.03882   ↑ COMPRA
```

### 3. 🇨🇦🇨🇭 CAD/CHF (CADCHF) — ACC 90.1% (Sessão: 00h - 24h)
```
α=2.9138

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURCHF      0.735162    0.00262   ↑ COMPRA
  EURUSD      -0.504610   0.00430   ↓ VENDA
  EURAUD      -0.327520   0.00417   ↓ VENDA
  iSharesCurrencyBond+  0.030213    0.00915   ↑ COMPRA
  CHINA50     -0.022322   0.00941   ↓ VENDA
  iSharesBrazil+  0.012769    0.01074   ↑ COMPRA
  VIX         0.011566    0.03882   ↑ COMPRA
  XAUUSD      0.003633    0.01626   ↑ COMPRA
```

### 4. 🇺🇸 S&P 500 (US500) — ACC 89.6% (Sessão: 00h - 24h)
```
α=6.3754

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  iSharesUSEmerging+  0.331968    0.00276   ↑ COMPRA
  CADCHF      0.241108    0.00377   ↑ COMPRA
  AUDUSD      0.239462    0.00537   ↑ COMPRA
  DE40        0.213314    0.01013   ↑ COMPRA
  EURAUD      0.171631    0.00417   ↑ COMPRA
  VIX         -0.128661   0.03882   ↓ VENDA
  XAUUSD      0.027193    0.01626   ↑ COMPRA
  iSharesBrazil+  0.003823    0.01074   ↑ COMPRA
```

### 5. 🇪🇺 EUR/USD (EURUSD) — ACC 88.6% (Sessão: 00h - 24h)
```
α=1.9826

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  iSharesTreasury1-3+  0.709679    0.00052   ↑ COMPRA
  USDCAD      -0.640315   0.00277   ↓ VENDA
  CADCHF      -0.537442   0.00377   ↓ VENDA
  USDMXN      -0.214483   0.00528   ↓ VENDA
  DE40        -0.074282   0.01013   ↓ VENDA
  US500       0.065346    0.00830   ↑ COMPRA
  BRENT       -0.033581   0.02759   ↓ VENDA
  BTCUSD      -0.007523   0.02724   ↓ VENDA
```

### 6. 🇨🇭 USD/CHF (USDCHF) — ACC 88.1% (Sessão: 00h - 24h)
```
α=2.8308

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  GBPUSD      -1.066989   0.00430   ↓ VENDA
  GBPJPY      0.948677    0.00404   ↑ COMPRA
  EURJPY      -0.888009   0.00356   ↓ VENDA
  iSharesTreasury20+  -0.081708   0.00405   ↓ VENDA
  DE40        -0.037358   0.01013   ↓ VENDA
  iSharesBrazil+  0.026624    0.01074   ↑ COMPRA
  BRENT       -0.026073   0.02759   ↓ VENDA
  VIX         -0.016427   0.03882   ↓ VENDA
```

### 7. 💻 Nasdaq 100 (USTEC) — ACC 86.6% (Sessão: 00h - 24h)
```
α=2.3919

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  USDCAD      -0.392714   0.00277   ↓ VENDA
  DE40        0.282226    0.01013   ↑ COMPRA
  CADCHF      0.268248    0.00377   ↑ COMPRA
  VIX         -0.148015   0.03882   ↓ VENDA
  EURUSD      0.124679    0.00430   ↑ COMPRA
  EURAUD      -0.108168   0.00417   ↓ VENDA
  BTCUSD      0.068173    0.02724   ↑ COMPRA
  iSharesTreasury10-20+  -0.054078   0.00332   ↓ VENDA
```

### 8. 🇬🇧 GBP/USD (GBPUSD) — ACC 85.6% (Sessão: 00h - 24h)
```
α=3.5699

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  AUDUSD      0.542119    0.00537   ↑ COMPRA
  EURAUD      0.302787    0.00417   ↑ COMPRA
  USDCHF      -0.256739   0.00485   ↓ VENDA
  AUDNZD      -0.250597   0.00269   ↓ VENDA
  iSharesTreasury1-3+  0.229630    0.00052   ↑ COMPRA
  EURCHF      0.215639    0.00262   ↑ COMPRA
  EURJPY      -0.098968   0.00356   ↓ VENDA
  BTCUSD      0.021716    0.02724   ↑ COMPRA
```

### 9. 💵 Mini Dólar (WDO$N) — ACC 84.2% (Sessão: 09h - 18h)
```
α=0.0421

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  USDCHF      -7.765198   0.00365   ↓ VENDA
  GBPUSD      -7.533221   0.00363   ↓ VENDA
  EURGBP      -7.362397   0.00288   ↓ VENDA
  EURCHF      7.254712    0.00231   ↑ COMPRA
  USDCAD      1.023892    0.00196   ↑ COMPRA
  WIN$N       -0.460299   0.00930   ↓ VENDA
  iSharesUSEmerging+  -0.233063   0.00248   ↓ VENDA
  US30        0.163472    0.00630   ↑ COMPRA
```

### 10. 🏛️ Dow Jones (US30) — ACC 84.2% (Sessão: 00h - 24h)
```
α=0.7276

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURUSD      2.177559    0.00430   ↑ COMPRA
  GBPJPY      -2.117778   0.00404   ↓ VENDA
  USDJPY      2.049438    0.00513   ↑ COMPRA
  EURGBP      -2.040464   0.00270   ↓ VENDA
  USDCAD      -0.315434   0.00277   ↓ VENDA
  DE40        0.309352    0.01013   ↑ COMPRA
  VIX         -0.112025   0.03882   ↓ VENDA
  iSharesCurrencyBond+  0.028426    0.00915   ↑ COMPRA
```

### 11. 🇨🇦 USD/CAD (USDCAD) — ACC 84.2% (Sessão: 00h - 24h)
```
α=3.2962

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURGBP      -0.479817   0.00270   ↓ VENDA
  GBPUSD      -0.471013   0.00430   ↓ VENDA
  EURAUD      0.297551    0.00417   ↑ COMPRA
  EURCHF      0.197526    0.00262   ↑ COMPRA
  iSharesCurrencyBond+  -0.040227   0.00915   ↓ VENDA
  USDMXN      -0.023349   0.00528   ↓ VENDA
  VIX         -0.016616   0.03882   ↓ VENDA
  BTCUSD      -0.009903   0.02724   ↓ VENDA
```

### 12. 🇧🇷 Mini Índice (WIN$N) — ACC 83.2% (Sessão: 09h - 18h)
```
α=2.1141

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  WDO$N       -0.647882   0.00686   ↓ VENDA
  USDMXN      -0.541251   0.00440   ↓ VENDA
  US30        0.366348    0.00630   ↑ COMPRA
  DI1$N       -0.358153   0.00785   ↓ VENDA
  DXY         0.245463    0.00313   ↑ COMPRA
  USTEC       -0.215609   0.00817   ↓ VENDA
  CHINA50     -0.199719   0.00446   ↓ VENDA
  BTCUSD      -0.047452   0.01464   ↓ VENDA
```

### 13. 🇪🇺🇦🇺 EUR/AUD (EURAUD) — ACC 81.7% (Sessão: 00h - 24h)
```
α=2.0943

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  CADCHF      -0.562517   0.00377   ↓ VENDA
  EURCHF      0.470995    0.00262   ↑ COMPRA
  AUDNZD      -0.408299   0.00269   ↓ VENDA
  EURJPY      0.375959    0.00356   ↑ COMPRA
  GBPJPY      -0.280607   0.00404   ↓ VENDA
  USDMXN      0.242702    0.00528   ↑ COMPRA
  USTEC       -0.076023   0.01114   ↓ VENDA
  BTCUSD      -0.012722   0.02724   ↓ VENDA
```

### 14. 🇯🇵 USD/JPY (USDJPY) — ACC 81.2% (Sessão: 00h - 24h)
```
α=2.1023

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  USDCHF      0.930239    0.00485   ↑ COMPRA
  EURCHF      -0.716065   0.00262   ↓ VENDA
  iSharesTreasury10-20+  -0.195726   0.00332   ↓ VENDA
  EURGBP      0.161761    0.00270   ↑ COMPRA
  USDMXN      -0.141604   0.00528   ↓ VENDA
  EURAUD      0.065219    0.00417   ↑ COMPRA
  US30        0.038823    0.00828   ↑ COMPRA
  BRENT       0.017218    0.02759   ↑ COMPRA
```

### 15. 🇦🇺🇳🇿 AUD/NZD (AUDNZD) — ACC 80.7% (Sessão: 00h - 24h)
```
α=2.3008

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURAUD      -0.323664   0.00417   ↓ VENDA
  EURGBP      0.249708    0.00270   ↑ COMPRA
  USDCAD      0.145878    0.00277   ↑ COMPRA
  CHINA50     0.028811    0.00941   ↑ COMPRA
  US30        -0.023658   0.00828   ↓ VENDA
  XAUUSD      0.019366    0.01626   ↑ COMPRA
  BTCUSD      0.002038    0.02724   ↑ COMPRA
  VIX         -0.000874   0.03882   ↓ VENDA
```

### 16. 🇪🇺🇬🇧 EUR/GBP (EURGBP) — ACC 75.7% (Sessão: 00h - 24h)
```
α=3.0889

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURAUD      0.439183    0.00417   ↑ COMPRA
  AUDNZD      0.248898    0.00269   ↑ COMPRA
  AUDUSD      0.232116    0.00537   ↑ COMPRA
  iSharesUSEmerging+  -0.094134   0.00276   ↓ VENDA
  USDMXN      0.017955    0.00528   ↑ COMPRA
  DE40        -0.016286   0.01013   ↓ VENDA
  BTCUSD      -0.013435   0.02724   ↓ VENDA
```

### 17. ₿ Bitcoin (BTCUSD) — ACC 75.2% (Sessão: 00h - 24h)
```
α=0.4630

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURGBP      -1.288106   0.00270   ↓ VENDA
  USTEC       1.116439    0.01114   ↑ COMPRA
  USDCAD      -0.941058   0.00277   ↓ VENDA
  USDMXN      -0.895102   0.00528   ↓ VENDA
  USDJPY      0.506393    0.00513   ↑ COMPRA
  EURAUD      -0.241745   0.00417   ↓ VENDA
  AUDUSD      0.170112    0.00537   ↑ COMPRA
  iSharesCurrencyBond+  -0.164857   0.00915   ↓ VENDA
```

### 18. 🥇 Ouro (XAUUSD) — ACC 73.3% (Sessão: 00h - 24h)
```
α=0.3205

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  AUDNZD      0.979383    0.00269   ↑ COMPRA
  AUDUSD      0.932809    0.00537   ↑ COMPRA
  USDMXN      -0.783235   0.00528   ↓ VENDA
  USDCHF      -0.314539   0.00485   ↓ VENDA
  EURGBP      -0.192727   0.00270   ↓ VENDA
  VIX         0.126224    0.03882   ↑ COMPRA
  CHINA50     0.102693    0.00941   ↑ COMPRA
  BRENT       0.041678    0.02759   ↑ COMPRA
```

### 19. 🇪🇺🇯🇵 EUR/JPY (EURJPY) — ACC 72.3% (Sessão: 00h - 24h)
```
α=0.6462

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURAUD      0.979716    0.00417   ↑ COMPRA
  AUDUSD      0.926729    0.00537   ↑ COMPRA
  DXY         0.916582    0.00394   ↑ COMPRA
  iSharesTreasury10-20+  -0.219733   0.00332   ↓ VENDA
  AUDNZD      0.137973    0.00269   ↑ COMPRA
  iSharesBrazil+  0.031398    0.01074   ↑ COMPRA
  VIX         -0.009175   0.03882   ↓ VENDA
```

### 20. 🇬🇧🇯🇵 GBP/JPY (GBPJPY) — ACC 69.8% (Sessão: 00h - 24h)
```
α=2.2652

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURUSD      -0.261073   0.00430   ↓ VENDA
  USDMXN      -0.202845   0.00528   ↓ VENDA
  iSharesTreasury20+  -0.176322   0.00405   ↓ VENDA
  iSharesUSEmerging+  0.128549    0.00276   ↑ COMPRA
  AUDUSD      0.036001    0.00537   ↑ COMPRA
  BTCUSD      0.030391    0.02724   ↑ COMPRA
  DE40        -0.008393   0.01013   ↓ VENDA
```

