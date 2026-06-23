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
| 1 | 🇦🇺 **AUD/USD** | **91.1%** | **0.7605** | 8 | CADCHF (0.6693) |
| 2 | 🇪🇺🇨🇭 **EUR/CHF** | **91.1%** | **0.8519** | 8 | USDCAD (0.9042) |
| 3 | 🇨🇦🇨🇭 **CAD/CHF** | **90.1%** | **0.7448** | 8 | EURCHF (0.7038) |
| 4 | 🇺🇸 **S&P 500** | **89.6%** | **0.8508** | 8 | iSharesUSEmerging+ (0.3320) |
| 5 | 🇪🇺 **EUR/USD** | **89.1%** | **0.8059** | 8 | USDCAD (-0.6745) |
| 6 | 🇨🇭 **USD/CHF** | **89.1%** | **0.7530** | 8 | USDJPY (0.8958) |
| 7 | 💻 **Nasdaq 100** | **86.6%** | **0.7754** | 8 | USDCAD (-0.3927) |
| 8 | 🇬🇧 **GBP/USD** | **85.6%** | **0.7272** | 8 | AUDUSD (0.5421) |
| 9 | 🇧🇷 **Mini Índice** | **85.1%** | **0.5801** | 8 | US500 (1.1943) |
| 10 | 💵 **Mini Dólar** | **84.2%** | **0.5844** | 8 | US500 (1.0302) |
| 11 | 🏛️ **Dow Jones** | **84.2%** | **0.7412** | 8 | EURUSD (2.1776) |
| 12 | 🇨🇦 **USD/CAD** | **84.2%** | **0.6066** | 8 | EURUSD (-0.4683) |
| 13 | 🇪🇺🇦🇺 **EUR/AUD** | **81.7%** | **0.6186** | 8 | CADCHF (-0.5625) |
| 14 | 🇯🇵 **USD/JPY** | **81.2%** | **0.5663** | 8 | USDCHF (0.9302) |
| 15 | 🇦🇺🇳🇿 **AUD/NZD** | **80.7%** | **0.2577** | 8 | EURAUD (-0.3237) |
| 16 | 🇪🇺🇬🇧 **EUR/GBP** | **75.7%** | **0.3110** | 8 | EURAUD (0.4468) |
| 17 | 🇬🇧🇯🇵 **GBP/JPY** | **75.7%** | **0.4363** | 8 | DXY (1.0783) |
| 18 | ₿ **Bitcoin** | **75.2%** | **0.4358** | 8 | EURGBP (-5.4844) |
| 19 | 🥇 **Ouro** | **73.3%** | **0.2852** | 8 | AUDNZD (0.9794) |
| 20 | 🇪🇺🇯🇵 **EUR/JPY** | **72.3%** | **0.2433** | 8 | EURAUD (0.9532) |

---

## Detalhamento Completo por Ativo

### 1. 🇦🇺 AUD/USD (AUDUSD) — ACC 91.1% (Sessão: 00h - 24h)
```
α=4.1079

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  CADCHF      0.669348    0.00377   ↑ COMPRA
  USDCHF      -0.639418   0.00485   ↓ VENDA
  USDJPY      -0.317674   0.00513   ↓ VENDA
  GBPJPY      0.230890    0.00404   ↑ COMPRA
  USDMXN      -0.209704   0.00528   ↓ VENDA
  XAUUSD      0.048682    0.01626   ↑ COMPRA
  VIX         -0.044918   0.03882   ↓ VENDA
  US500       -0.020257   0.00830   ↓ VENDA
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
α=3.0346

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURCHF      0.703797    0.00262   ↑ COMPRA
  EURUSD      -0.496117   0.00430   ↓ VENDA
  EURAUD      -0.300946   0.00417   ↓ VENDA
  USTEC       0.069411    0.01114   ↑ COMPRA
  iSharesTreasury20+  -0.050724   0.00405   ↓ VENDA
  DE40        -0.044616   0.01013   ↓ VENDA
  VIX         0.017502    0.03882   ↑ COMPRA
  BTCUSD      -0.001735   0.02724   ↓ VENDA
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

### 5. 🇪🇺 EUR/USD (EURUSD) — ACC 89.1% (Sessão: 00h - 24h)
```
α=3.7326

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  USDCAD      -0.674460   0.00277   ↓ VENDA
  CADCHF      -0.573498   0.00377   ↓ VENDA
  USDMXN      -0.195532   0.00528   ↓ VENDA
  US500       0.090057    0.00830   ↑ COMPRA
  DE40        -0.066232   0.01013   ↓ VENDA
  US30        -0.046266   0.00828   ↓ VENDA
  GBPJPY      -0.042832   0.00404   ↓ VENDA
  BRENT       -0.036548   0.02759   ↓ VENDA
```

### 6. 🇨🇭 USD/CHF (USDCHF) — ACC 89.1% (Sessão: 00h - 24h)
```
α=2.7545

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  USDJPY      0.895776    0.00513   ↑ COMPRA
  EURJPY      -0.834758   0.00356   ↓ VENDA
  AUDUSD      -0.097391   0.00537   ↓ VENDA
  US30        -0.083914   0.00828   ↓ VENDA
  VIX         -0.036424   0.03882   ↓ VENDA
  iSharesCurrencyBond+  -0.016587   0.00915   ↓ VENDA
  USTEC       0.014880    0.01114   ↑ COMPRA
  BTCUSD      -0.004031   0.02724   ↓ VENDA
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

### 9. 🇧🇷 Mini Índice (WIN$N) — ACC 85.1% (Sessão: 09h - 18h)
```
α=1.1496

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  US500       1.194278    0.00642   ↑ COMPRA
  USTEC       -0.834236   0.00817   ↓ VENDA
  WDO$N       -0.769140   0.00686   ↓ VENDA
  iSharesTreasury1-3+  -0.493084   0.00037   ↓ VENDA
  USDCAD      0.329174    0.00196   ↑ COMPRA
  DI1$N       -0.310747   0.00785   ↓ VENDA
  iSharesCurrencyBond+  -0.084860   0.00969   ↓ VENDA
  VIX         0.006319    0.02637   ↑ COMPRA
```

### 10. 💵 Mini Dólar (WDO$N) — ACC 84.2% (Sessão: 09h - 18h)
```
α=1.1708

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  US500       1.030170    0.00642   ↑ COMPRA
  USDCAD      0.970785    0.00196   ↑ COMPRA
  USTEC       -0.747573   0.00817   ↓ VENDA
  WIN$N       -0.489016   0.00930   ↓ VENDA
  USDCHF      -0.280307   0.00365   ↓ VENDA
  XAUUSD      -0.089474   0.01088   ↓ VENDA
  DE40        0.040124    0.00990   ↑ COMPRA
  VIX         0.022795    0.02637   ↑ COMPRA
```

### 11. 🏛️ Dow Jones (US30) — ACC 84.2% (Sessão: 00h - 24h)
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

### 12. 🇨🇦 USD/CAD (USDCAD) — ACC 84.2% (Sessão: 00h - 24h)
```
α=3.5231

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURUSD      -0.468285   0.00430   ↓ VENDA
  EURAUD      0.291690    0.00417   ↑ COMPRA
  EURCHF      0.212414    0.00262   ↑ COMPRA
  US500       -0.088244   0.00830   ↓ VENDA
  iSharesTreasury20+  0.058508    0.00405   ↑ COMPRA
  iSharesCurrencyBond+  -0.040806   0.00915   ↓ VENDA
  VIX         -0.030874   0.03882   ↓ VENDA
  EURJPY      0.016553    0.00356   ↑ COMPRA
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
α=3.0542

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURAUD      0.446752    0.00417   ↑ COMPRA
  AUDNZD      0.248348    0.00269   ↑ COMPRA
  AUDUSD      0.233684    0.00537   ↑ COMPRA
  iSharesUSEmerging+  -0.100358   0.00276   ↓ VENDA
  USDMXN      0.022419    0.00528   ↑ COMPRA
  DE40        -0.021328   0.01013   ↓ VENDA
  BTCUSD      -0.014160   0.02724   ↓ VENDA
  VIX         -0.003122   0.03882   ↓ VENDA
```

### 17. 🇬🇧🇯🇵 GBP/JPY (GBPJPY) — ACC 75.7% (Sessão: 00h - 24h)
```
α=1.4608

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  DXY         1.078345    0.00394   ↑ COMPRA
  EURUSD      1.040510    0.00430   ↑ COMPRA
  EURGBP      -0.897446   0.00270   ↓ VENDA
  AUDNZD      0.166706    0.00269   ↑ COMPRA
  iSharesTreasury20+  -0.139522   0.00405   ↓ VENDA
  USDMXN      -0.139205   0.00528   ↓ VENDA
  AUDUSD      -0.052249   0.00537   ↓ VENDA
  USTEC       0.027178    0.01114   ↑ COMPRA
```

### 18. ₿ Bitcoin (BTCUSD) — ACC 75.2% (Sessão: 00h - 24h)
```
α=0.2683

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURGBP      -5.484364   0.00270   ↓ VENDA
  EURJPY      4.572824    0.00356   ↑ COMPRA
  GBPJPY      -3.970316   0.00404   ↓ VENDA
  USTEC       1.389608    0.01114   ↑ COMPRA
  USDMXN      -0.819306   0.00528   ↓ VENDA
  AUDNZD      0.433649    0.00269   ↑ COMPRA
  AUDUSD      0.431543    0.00537   ↑ COMPRA
  US500       -0.422680   0.00830   ↓ VENDA
```

### 19. 🥇 Ouro (XAUUSD) — ACC 73.3% (Sessão: 00h - 24h)
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

### 20. 🇪🇺🇯🇵 EUR/JPY (EURJPY) — ACC 72.3% (Sessão: 00h - 24h)
```
α=0.8970

  Fator       Peso        σ         Direção
  ──────────  ──────────  ────────  ─────────
  EURAUD      0.953191    0.00417   ↑ COMPRA
  DXY         0.909319    0.00394   ↑ COMPRA
  AUDUSD      0.906924    0.00537   ↑ COMPRA
  USDMXN      -0.166216   0.00528   ↓ VENDA
  iSharesTreasury20+  -0.163755   0.00405   ↓ VENDA
  AUDNZD      0.127697    0.00269   ↑ COMPRA
  USDCHF      0.081861    0.00485   ↑ COMPRA
  DE40        -0.025875   0.01013   ↓ VENDA
```

