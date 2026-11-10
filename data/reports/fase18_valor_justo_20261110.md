# Valor justo da cesta — pesquisa da fase 18

- **Script:** `scripts/research_fair_value.py` · **config hash:** `7d474b00a0ca` · seed 0 · bootstrap B = 300 por pregão
- **Período:** 2024-12-01 a 2026-11-10; **desenho** até 2025-12-31, **validação** depois (2026, nada escolhido nela)
- **Custos (ida e volta, por contrato):** WIN$N 10,0 pts, WDO$N 1,0 pts
- **Eventos:** primeiro cruzamento de |z| ≥ limiar na janela 09:30–17:00 BRT; limiares 1,5, 2,0, 2,5; direções contrarian (aposta no fechamento do gap) e segue; horizontes 15 min, 30 min, 60 min e fechamento
- **Testes por parte:** 336 (correção de Benjamini–Hochberg e Bonferroni dentro de cada parte)

Variantes:

- `cesta_w60`: cesta completa, γ por OLS em 60 pregões anteriores, incrementos de 30 min; z = gap ÷ σ do gap no mesmo horário nos 60 pregões anteriores
- `cesta_w20`: cesta completa, γ por OLS em 20 pregões anteriores, incrementos de 30 min; z = gap ÷ σ do gap no mesmo horário nos 60 pregões anteriores
- `cesta_w60_5min`: cesta completa, γ por OLS em 60 pregões anteriores, incrementos de 5 min; z = gap ÷ σ do gap no mesmo horário nos 60 pregões anteriores
- `cesta_w60_movel40`: cesta completa, γ por OLS em 60 pregões anteriores, incrementos de 30 min; z = gap ÷ desvio móvel de 40 barras (passadas)
- `par_ols20`: só o par WIN↔WDO, γ por OLS em 20 pregões anteriores, incrementos de 30 min; z = gap ÷ σ do gap no mesmo horário nos 60 pregões anteriores
- `par_ols60`: só o par WIN↔WDO, γ por OLS em 60 pregões anteriores, incrementos de 30 min; z = gap ÷ σ do gap no mesmo horário nos 60 pregões anteriores
- `par_ols20_z_atual`: só o par WIN↔WDO, γ por OLS em 20 pregões anteriores, incrementos de 30 min; z com a padronização atual do engine (para comparação)

## WIN$N

Pregões: 482 (2024-12-02 a 2026-11-10).

| Variante | Parte | Barras | |z| > 2 | desvio do z | AUC −z 15m | 30m | 60m | Eventos z≥2 | Líq. 60m (pts, IC 95%) | t | Fecha em 60m | Fecha no pregão | Parcela do alvo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cesta_w60 | desenho | 25803 | 4,4% | 0,97 | 0,500 | 0,503 | 0,505 | 95 | -88,1 (-203,7 a 40,5) | -1,42 | 0,0% | 14,7% | 0,91 |
| cesta_w60 | validacao | 23917 | 8,0% | 1,12 | 0,490 | 0,489 | 0,490 | 134 | 231,8 (3,9 a 506,4) | 1,74 | 7,5% | 19,4% | 1,08 |
| cesta_w20 | desenho | 25803 | 3,9% | 0,97 | 0,500 | 0,503 | 0,505 | 88 | -15,0 (-138,3 a 133,2) | -0,20 | 2,3% | 26,1% | 1,01 |
| cesta_w20 | validacao | 23917 | 8,0% | 1,11 | 0,491 | 0,491 | 0,491 | 132 | 234,5 (-26,7 a 468,7) | 1,81 | 5,3% | 22,7% | 1,12 |
| cesta_w60_5min | desenho | 25803 | 4,3% | 0,97 | 0,499 | 0,503 | 0,505 | 95 | -107,4 (-221,9 a 14,4) | -2,00 | 1,1% | 16,8% | 0,84 |
| cesta_w60_5min | validacao | 23917 | 8,1% | 1,12 | 0,491 | 0,491 | 0,494 | 125 | 189,6 (-78,3 a 500,3) | 1,16 | 8,0% | 23,2% | 1,11 |
| cesta_w60_movel40 | desenho | 25573 | 12,7% | 1,37 | 0,503 | 0,500 | 0,495 | 990 | 7,2 (-32,1 a 46,3) | 0,38 | 42,6% | 91,1% | 1,00 |
| cesta_w60_movel40 | validacao | 21787 | 12,3% | 1,39 | 0,491 | 0,491 | 0,491 | 828 | -55,9 (-123,1 a 6,2) | -1,63 | 44,1% | 88,8% | 0,88 |
| par_ols20 | desenho | 25803 | 3,9% | 0,97 | 0,499 | 0,502 | 0,502 | 102 | -10,7 (-148,5 a 146,4) | -0,15 | 5,9% | 23,5% | 0,86 |
| par_ols20 | validacao | 23917 | 7,3% | 1,10 | 0,489 | 0,489 | 0,489 | 115 | 211,8 (-56,0 a 530,1) | 1,29 | 6,1% | 27,0% | 0,98 |
| par_ols60 | desenho | 25803 | 4,0% | 0,97 | 0,499 | 0,502 | 0,504 | 96 | 15,6 (-98,2 a 173,0) | 0,23 | 5,2% | 24,0% | 0,88 |
| par_ols60 | validacao | 23917 | 7,3% | 1,10 | 0,489 | 0,490 | 0,491 | 144 | 225,9 (21,1 a 481,8) | 1,78 | 6,2% | 24,3% | 1,00 |
| par_ols20_z_atual | desenho | 26818 | 54,5% | 2,87 | 0,495 | 0,497 | 0,490 | 886 | 11,4 (-33,9 a 55,8) | 0,56 | 24,0% | 47,0% | 0,99 |
| par_ols20_z_atual | validacao | 22852 | 58,1% | 5,02 | 0,493 | 0,493 | 0,490 | 652 | 9,8 (-64,9 a 81,6) | 0,26 | 21,9% | 43,1% | 1,07 |

Baselines (AUC por barra, sinal do retorno do dia): desenho: 60m momentum 0,507 / contrarian 0,493; validacao: 60m momentum 0,502 / contrarian 0,498

## WDO$N

Pregões: 482 (2024-12-02 a 2026-11-10).

| Variante | Parte | Barras | |z| > 2 | desvio do z | AUC −z 15m | 30m | 60m | Eventos z≥2 | Líq. 60m (pts, IC 95%) | t | Fecha em 60m | Fecha no pregão | Parcela do alvo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cesta_w60 | desenho | 25808 | 4,1% | 1,01 | 0,504 | 0,499 | 0,492 | 66 | -1,3 (-7,7 a 3,8) | -0,44 | 3,0% | 21,2% | 1,04 |
| cesta_w60 | validacao | 23913 | 5,5% | 1,05 | 0,504 | 0,502 | 0,502 | 119 | 1,0 (-2,6 a 4,9) | 0,49 | 7,6% | 26,9% | 0,92 |
| cesta_w20 | desenho | 25808 | 4,5% | 1,01 | 0,504 | 0,497 | 0,488 | 78 | -0,3 (-3,9 a 4,9) | -0,11 | 1,3% | 21,8% | 0,95 |
| cesta_w20 | validacao | 23913 | 5,3% | 1,06 | 0,507 | 0,507 | 0,508 | 145 | -0,1 (-2,7 a 2,9) | -0,11 | 2,1% | 18,6% | 0,90 |
| cesta_w60_5min | desenho | 25808 | 4,4% | 1,01 | 0,505 | 0,499 | 0,492 | 91 | -0,3 (-4,0 a 3,9) | -0,15 | 5,5% | 24,2% | 1,09 |
| cesta_w60_5min | validacao | 23913 | 5,3% | 1,05 | 0,504 | 0,502 | 0,501 | 125 | 2,0 (-0,8 a 5,5) | 1,16 | 4,8% | 22,4% | 1,13 |
| cesta_w60_movel40 | desenho | 25578 | 11,9% | 1,34 | 0,521 | 0,517 | 0,511 | 980 | -0,7 (-1,8 a 0,5) | -1,21 | 45,1% | 89,6% | 0,81 |
| cesta_w60_movel40 | validacao | 21783 | 12,7% | 1,40 | 0,519 | 0,512 | 0,498 | 842 | -0,3 (-1,1 a 0,5) | -0,69 | 43,0% | 90,6% | 0,98 |
| par_ols20 | desenho | 25808 | 4,7% | 0,99 | 0,502 | 0,497 | 0,491 | 112 | -2,7 (-5,6 a 0,6) | -1,69 | 5,4% | 26,8% | 0,86 |
| par_ols20 | validacao | 23913 | 5,5% | 1,04 | 0,510 | 0,510 | 0,512 | 85 | 2,7 (-1,3 a 6,4) | 1,30 | 2,4% | 17,6% | 1,18 |
| par_ols60 | desenho | 25808 | 5,0% | 0,99 | 0,502 | 0,497 | 0,492 | 108 | -3,8 (-7,3 a -0,6) | -2,10 | 5,6% | 25,0% | 0,85 |
| par_ols60 | validacao | 23913 | 4,9% | 1,03 | 0,511 | 0,511 | 0,512 | 74 | 2,2 (-1,5 a 7,4) | 0,99 | 1,4% | 14,9% | 1,02 |
| par_ols20_z_atual | desenho | 26823 | 54,2% | 2,69 | 0,501 | 0,496 | 0,497 | 930 | -1,8 (-3,0 a -0,8) | -3,19 | 18,2% | 43,3% | 0,92 |
| par_ols20_z_atual | validacao | 22848 | 53,4% | 3,13 | 0,510 | 0,511 | 0,513 | 775 | -0,9 (-2,0 a -0,1) | -1,85 | 18,8% | 45,4% | 1,00 |

Baselines (AUC por barra, sinal do retorno do dia): desenho: 60m momentum 0,510 / contrarian 0,490; validacao: 60m momentum 0,478 / contrarian 0,522

## Correção para testes múltiplos

- **desenho:** 336 testes; 22 com q (BH) < 0,05, dos quais 0 com P&L líquido positivo; 14 passam Bonferroni.
  - menor p: WDO$N cesta_w60_movel40 z≥1,5 segue 15m: n 1661, líquido -1,4 pts, t -9,69, p 0,0000, q 0,000
  - menor p: WDO$N cesta_w60_movel40 z≥1,5 segue 30m: n 1661, líquido -1,6 pts, t -7,12, p 0,0000, q 0,000
  - menor p: WDO$N cesta_w60_movel40 z≥2,0 segue 15m: n 980, líquido -1,4 pts, t -6,38, p 0,0000, q 0,000
  - menor p: WDO$N par_ols20_z_atual z≥2,0 contrarian 15m: n 930, líquido -1,3 pts, t -5,59, p 0,0000, q 0,000
  - menor p: WDO$N par_ols20_z_atual z≥2,5 contrarian 15m: n 951, líquido -1,0 pts, t -4,95, p 0,0000, q 0,000
- **validacao:** 336 testes; 35 com q (BH) < 0,05, dos quais 0 com P&L líquido positivo; 19 passam Bonferroni.
  - menor p: WDO$N cesta_w60_movel40 z≥1,5 segue 15m: n 1368, líquido -1,6 pts, t -9,37, p 0,0000, q 0,000
  - menor p: WDO$N par_ols20_z_atual z≥1,5 segue 15m: n 778, líquido -1,7 pts, t -7,14, p 0,0000, q 0,000
  - menor p: WDO$N cesta_w60_movel40 z≥2,0 segue 15m: n 841, líquido -1,6 pts, t -7,00, p 0,0000, q 0,000
  - menor p: WDO$N cesta_w60_movel40 z≥1,5 segue 30m: n 1367, líquido -1,7 pts, t -6,78, p 0,0000, q 0,000
  - menor p: WDO$N cesta_w60_movel40 z≥2,5 segue 15m: n 429, líquido -2,2 pts, t -6,18, p 0,0000, q 0,000

Leitura: um z bem padronizado tem |z| > 2 em ~5% das barras. Os z da cesta e do par com σ causal ficam perto disso; a construção atual (`par_ols20_z_atual`) dá dezenas de por cento. Nenhum descolamento previu o retorno das barras seguintes (AUC ≈ 0,50) e nenhum evento teve P&L líquido positivo que sobrevivesse à correção para testes múltiplos.

