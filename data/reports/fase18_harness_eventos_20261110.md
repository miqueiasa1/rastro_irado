# Assertividade do rastro — 2026-08-03 a 2026-11-10

- **Gerado pelo harness** `scripts/eval_assertividade.py` (versão 18.0)
- **Modelo avaliado:** P(↑) atual gravado em `irai_live_snapshots` (nowcast), sem recálculo
- **Período:** sessões 2026-08-03 a 2026-11-10; corte de dados (as-of) 2026-11-10 13:50:00 UTC
- **Fonte:** `irai_live.db` aberto em `mode=ro`
- **git SHA:** `090fdf5-dirty` · **config hash:** `569b5e8afb3f` · **seed:** 0 · **bootstrap:** B = 300 por pregão
- **Horizonte primário:** 60m (decisão D1); **secundário:** fechamento (só avaliação)

Convenções: live_bar: is_ghost=0 e created_at − abertura da barra (BRT) em [0, 10.0] min; session: barras M5 com abertura em [09:00, 18:25) BRT; target: sinal do retorno do fechamento da barra até h barras à frente no mesmo pregão; retorno zero excluído; nowcast: sinal do retorno do dia (fechamento da barra / abertura do pregão − 1); bss: contra a taxa-base do próprio conjunto avaliado; ece: 10 bins de largura igual; ci: bootstrap de pregões, B=300, seed=0.

## WIN$N

- Pregões com barras ao vivo: 65 (2026-08-07 a 2026-11-10); barras ao vivo: 6637
- Barras com snapshot que são ao vivo: 88,0% (6634 de 7539); cobertura sobre todas as barras do pregão: 86,1% (6634 de 7704, 69 pregões com barras)
- Atraso de gravação (created_at − abertura da barra), mediana: 4,42 min (todas) / 4,30 min (ao vivo)
- Barras com P < 20 ou P > 80: 38,5%

| Horizonte | Papel | n | Pregões | Taxa de alta | AUC (IC 95%) | BSS (IC 95%) | ECE (pp) | Hit | Empates excl. |
|---|---|---|---|---|---|---|---|---|---|
| 5m | relatório | 6522 | 65 | 50,7% | 0,493 (0,477 a 0,503) | -0,364 (-0,416 a -0,313) | 25,5 | 49,7% | 105 |
| 15m | relatório | 6546 | 65 | 50,7% | 0,479 (0,457 a 0,496) | -0,393 (-0,453 a -0,336) | 26,8 | 48,4% | 61 |
| 30m | relatório | 6526 | 65 | 51,3% | 0,481 (0,453 a 0,504) | -0,391 (-0,461 a -0,331) | 26,2 | 49,0% | 48 |
| 60m | primário | 6156 | 65 | 50,5% | 0,474 (0,437 a 0,505) | -0,402 (-0,487 a -0,333) | 26,6 | 48,9% | 34 |
| close | secundário | 6612 | 65 | 53,7% | 0,525 (0,436 a 0,617) | -0,315 (-0,517 a -0,111) | 23,8 | 52,2% | 25 |
| nowcast | nowcast | 6622 | 65 | 43,6% | 0,710 (0,633 a 0,790) | 0,076 (-0,099 a 0,228) | 11,9 | 66,3% | 15 |

**Baselines (REQ-V06), AUC / hit:**

| Horizonte | Taxa-base (alta) | Momentum (retorno do dia) | Contrarian (−retorno do dia) |
|---|---|---|---|
| 60m | 50,5% | 0,448 / 45,2% | 0,552 / 55,0% |
| close | 53,7% | 0,455 / 43,3% | 0,545 / 56,5% |

**Confiabilidade — 60m:**

| Bin de P | n | P médio | Freq. de alta |
|---|---|---|---|
| 0–10 | 976 | 4,2% | 53,6% |
| 10–20 | 447 | 14,6% | 54,6% |
| 20–30 | 596 | 25,2% | 50,7% |
| 30–40 | 605 | 35,1% | 52,2% |
| 40–50 | 702 | 44,8% | 46,9% |
| 50–60 | 636 | 55,0% | 56,6% |
| 60–70 | 675 | 65,5% | 49,9% |
| 70–80 | 574 | 74,4% | 43,6% |
| 80–90 | 434 | 85,1% | 48,6% |
| 90–100 | 511 | 96,3% | 46,6% |

**Confiabilidade — nowcast:**

| Bin de P | n | P médio | Freq. de alta |
|---|---|---|---|
| 0–10 | 1055 | 4,1% | 22,2% |
| 10–20 | 470 | 14,7% | 34,5% |
| 20–30 | 646 | 25,1% | 26,3% |
| 30–40 | 639 | 35,0% | 27,4% |
| 40–50 | 745 | 44,7% | 38,1% |
| 50–60 | 701 | 55,1% | 48,4% |
| 60–70 | 713 | 65,5% | 48,8% |
| 70–80 | 627 | 74,5% | 60,6% |
| 80–90 | 463 | 85,0% | 69,8% |
| 90–100 | 563 | 96,5% | 83,7% |

**Marcadores visuais (REQ-V07, parcial), retorno médio em bp (IC 95%) e hit:**

| Marcador | n | Por pregão | 60 min bp | 60 min hit | Fechamento bp |
|---|---|---|---|---|---|
| ponto_z_rastro | 2055 | 31,6 | 0,97 (-3,90 a 6,32) | 55,0% | 2,63 (-11,28 a 18,77) |
| estrela_dourada | 482 | 7,4 | 0,38 (-10,47 a 12,73) | 55,7% | 3,09 (-16,92 a 28,24) |

**Descolamentos gravados ao vivo como eventos (fase 18): cobertura de |z| > 2 e P&L por evento (contrarian, pontos por contrato, líquido de 10,0 pts de custo; IC 95% por pregão):**

| z | Barras com |z| > 2 | Eventos | Por pregão | 15 min líq. | 60 min líq. (IC 95%) | Hit 60 min | t 60 min | Fechamento líq. |
|---|---|---|---|---|---|---|---|---|
| pair_fixed_z | 32,3% | 207 | 3,18 | 4,1 | 17,8 (-125,8 a 138,6) | 54,1% | 0,25 | -53,2 |
| pair_z | 34,0% | 210 | 3,23 | -30,3 | -11,3 (-171,7 a 148,3) | 48,1% | -0,15 | -87,2 |
| price_diverge_z | 30,7% | 220 | 3,38 | -3,6 | -10,2 (-131,3 a 134,8) | 48,2% | -0,14 | 4,0 |

Um z bem padronizado tem |z| > 2 em cerca de 5% das barras; muito acima disso, o z não é um z de verdade.

**Segmentação por hora (BRT) (REQ-V05), AUC / BSS:**

| hora (BRT) | Barras | Pregões | 60 min | Fechamento | Nowcast |
|---|---|---|---|---|---|
| 9 | 736 | 62 | 0,502 / -0,261 | 0,452 / -0,352 | 0,605 / -0,098 |
| 10 | 741 | 63 | 0,418 / -0,463 | 0,415 / -0,511 | 0,652 / -0,010 |
| 11 | 729 | 61 | 0,478 / -0,397 | 0,473 / -0,436 | 0,715 / 0,106 |
| 12 | 732 | 61 | 0,444 / -0,497 | 0,516 / -0,362 | 0,752 / 0,160 |
| 13 | 732 | 61 | 0,516 / -0,343 | 0,572 / -0,232 | 0,733 / 0,115 |
| 14 | 741 | 62 | 0,467 / -0,439 | 0,548 / -0,279 | 0,778 / 0,209 |
| 15 | 743 | 62 | 0,405 / -0,583 | 0,554 / -0,280 | 0,735 / 0,110 |
| 16 | 734 | 63 | 0,525 / -0,329 | 0,620 / -0,123 | 0,686 / -0,004 |
| 17 | 701 | 63 | 0,575 / -0,228 | 0,540 / -0,302 | 0,704 / 0,051 |
| 18 | 48 | 9 | — / — | 0,671 / -0,057 | 0,849 / 0,214 |

**Segmentação por mês (REQ-V05), AUC / BSS:**

| mês | Barras | Pregões | 60 min | Fechamento | Nowcast |
|---|---|---|---|---|---|
| 2026-08 | 1702 | 17 | 0,485 / -0,267 | 0,411 / -0,504 | 0,800 / 0,267 |
| 2026-09 | 2143 | 21 | 0,462 / -0,470 | 0,457 / -0,498 | 0,672 / -0,007 |
| 2026-10 | 2264 | 21 | 0,455 / -0,508 | 0,609 / -0,177 | 0,679 / -0,068 |
| 2026-11 | 528 | 6 | 0,538 / -0,113 | 0,796 / 0,081 | 0,865 / 0,362 |

**Segmentação por tercil de vol. realizada do pregão (REQ-V05), AUC / BSS:**

| tercil de vol. realizada do pregão | Barras | Pregões | 60 min | Fechamento | Nowcast |
|---|---|---|---|---|---|
| alta | 2479 | 23 | 0,417 / -0,540 | 0,469 / -0,445 | 0,755 / 0,143 |
| baixa | 1784 | 19 | 0,501 / -0,286 | 0,514 / -0,330 | 0,720 / 0,104 |
| media | 2374 | 23 | 0,510 / -0,352 | 0,577 / -0,222 | 0,647 / -0,072 |

## WDO$N

- Pregões com barras ao vivo: 65 (2026-08-07 a 2026-11-10); barras ao vivo: 6633
- Barras com snapshot que são ao vivo: 88,0% (6630 de 7536); cobertura sobre todas as barras do pregão: 86,1% (6630 de 7702, 69 pregões com barras)
- Atraso de gravação (created_at − abertura da barra), mediana: 4,42 min (todas) / 4,30 min (ao vivo)
- Barras com P < 20 ou P > 80: 28,7%

| Horizonte | Papel | n | Pregões | Taxa de alta | AUC (IC 95%) | BSS (IC 95%) | ECE (pp) | Hit | Empates excl. |
|---|---|---|---|---|---|---|---|---|---|
| 5m | relatório | 5865 | 65 | 50,4% | 0,493 (0,477 a 0,508) | -0,273 (-0,343 a -0,216) | 21,3 | 49,7% | 758 |
| 15m | relatório | 6121 | 65 | 51,0% | 0,497 (0,472 a 0,517) | -0,265 (-0,311 a -0,206) | 21,1 | 49,9% | 482 |
| 30m | relatório | 6223 | 65 | 51,2% | 0,497 (0,466 a 0,524) | -0,265 (-0,340 a -0,206) | 21,2 | 49,7% | 348 |
| 60m | primário | 5941 | 65 | 50,4% | 0,486 (0,440 a 0,528) | -0,285 (-0,379 a -0,212) | 22,3 | 48,6% | 246 |
| close | secundário | 6508 | 65 | 53,3% | 0,488 (0,388 a 0,587) | -0,286 (-0,489 a -0,125) | 22,2 | 49,0% | 125 |
| nowcast | nowcast | 6537 | 65 | 55,4% | 0,754 (0,664 a 0,838) | 0,167 (-0,017 a 0,297) | 11,9 | 68,2% | 96 |

**Baselines (REQ-V06), AUC / hit:**

| Horizonte | Taxa-base (alta) | Momentum (retorno do dia) | Contrarian (−retorno do dia) |
|---|---|---|---|
| 60m | 50,4% | 0,439 / 45,9% | 0,561 / 53,8% |
| close | 53,3% | 0,351 / 38,6% | 0,649 / 61,3% |

**Confiabilidade — 60m:**

| Bin de P | n | P médio | Freq. de alta |
|---|---|---|---|
| 0–10 | 521 | 4,9% | 45,9% |
| 10–20 | 227 | 14,7% | 49,3% |
| 20–30 | 535 | 25,7% | 50,3% |
| 30–40 | 802 | 35,4% | 51,2% |
| 40–50 | 981 | 44,9% | 56,6% |
| 50–60 | 823 | 54,5% | 50,5% |
| 60–70 | 526 | 64,5% | 54,6% |
| 70–80 | 558 | 76,0% | 52,0% |
| 80–90 | 599 | 84,6% | 46,2% |
| 90–100 | 369 | 94,2% | 36,9% |

**Confiabilidade — nowcast:**

| Bin de P | n | P médio | Freq. de alta |
|---|---|---|---|
| 0–10 | 565 | 4,9% | 15,4% |
| 10–20 | 243 | 14,8% | 13,6% |
| 20–30 | 618 | 25,8% | 14,1% |
| 30–40 | 877 | 35,4% | 46,6% |
| 40–50 | 1042 | 44,9% | 61,2% |
| 50–60 | 925 | 54,5% | 71,2% |
| 60–70 | 580 | 64,6% | 76,6% |
| 70–80 | 606 | 75,9% | 70,6% |
| 80–90 | 676 | 84,6% | 73,4% |
| 90–100 | 405 | 94,2% | 83,7% |

**Marcadores visuais (REQ-V07, parcial), retorno médio em bp (IC 95%) e hit:**

| Marcador | n | Por pregão | 60 min bp | 60 min hit | Fechamento bp |
|---|---|---|---|---|---|
| ponto_z_rastro | 2378 | 36,6 | 2,02 (-0,66 a 5,93) | 51,8% | 0,08 (-12,03 a 16,78) |
| estrela_dourada | 340 | 5,2 | 2,23 (-4,65 a 8,79) | 51,6% | 10,17 (-1,19 a 23,00) |

**Descolamentos gravados ao vivo como eventos (fase 18): cobertura de |z| > 2 e P&L por evento (contrarian, pontos por contrato, líquido de 1,0 pts de custo; IC 95% por pregão):**

| z | Barras com |z| > 2 | Eventos | Por pregão | 15 min líq. | 60 min líq. (IC 95%) | Hit 60 min | t 60 min | Fechamento líq. |
|---|---|---|---|---|---|---|---|---|
| pair_fixed_z | 36,0% | 221 | 3,40 | -0,8 | 0,3 (-1,5 a 2,2) | 44,8% | 0,31 | -2,5 |
| pair_z | 32,5% | 178 | 2,74 | -1,0 | 0,5 (-1,8 a 2,9) | 47,2% | 0,36 | 2,3 |
| price_diverge_z | 35,6% | 251 | 3,86 | -0,5 | -0,6 (-2,6 a 2,3) | 39,8% | -0,44 | -3,0 |

Um z bem padronizado tem |z| > 2 em cerca de 5% das barras; muito acima disso, o z não é um z de verdade.

**Segmentação por hora (BRT) (REQ-V05), AUC / BSS:**

| hora (BRT) | Barras | Pregões | 60 min | Fechamento | Nowcast |
|---|---|---|---|---|---|
| 9 | 734 | 62 | 0,474 / -0,230 | 0,553 / -0,198 | 0,634 / -0,010 |
| 10 | 741 | 63 | 0,445 / -0,340 | 0,498 / -0,311 | 0,685 / 0,073 |
| 11 | 729 | 61 | 0,552 / -0,154 | 0,513 / -0,249 | 0,762 / 0,184 |
| 12 | 732 | 61 | 0,509 / -0,249 | 0,475 / -0,336 | 0,773 / 0,197 |
| 13 | 732 | 61 | 0,440 / -0,383 | 0,463 / -0,323 | 0,728 / 0,127 |
| 14 | 741 | 62 | 0,512 / -0,292 | 0,464 / -0,348 | 0,738 / 0,095 |
| 15 | 743 | 62 | 0,466 / -0,367 | 0,471 / -0,330 | 0,785 / 0,205 |
| 16 | 733 | 63 | 0,490 / -0,345 | 0,504 / -0,277 | 0,832 / 0,298 |
| 17 | 701 | 63 | 0,518 / -0,267 | 0,489 / -0,310 | 0,820 / 0,294 |
| 18 | 47 | 9 | — / — | 0,656 / -0,276 | 0,775 / -0,151 |

**Segmentação por mês (REQ-V05), AUC / BSS:**

| mês | Barras | Pregões | 60 min | Fechamento | Nowcast |
|---|---|---|---|---|---|
| 2026-08 | 1702 | 17 | 0,476 / -0,304 | 0,327 / -0,547 | 0,895 / 0,345 |
| 2026-09 | 2143 | 21 | 0,480 / -0,266 | 0,496 / -0,258 | 0,698 / 0,123 |
| 2026-10 | 2260 | 21 | 0,483 / -0,352 | 0,578 / -0,296 | 0,729 / 0,110 |
| 2026-11 | 528 | 6 | 0,570 / -0,034 | 0,672 / 0,070 | 0,598 / -0,796 |

**Segmentação por tercil de vol. realizada do pregão (REQ-V05), AUC / BSS:**

| tercil de vol. realizada do pregão | Barras | Pregões | 60 min | Fechamento | Nowcast |
|---|---|---|---|---|---|
| alta | 2388 | 23 | 0,481 / -0,333 | 0,542 / -0,241 | 0,820 / 0,295 |
| baixa | 2036 | 20 | 0,494 / -0,182 | 0,414 / -0,288 | 0,663 / 0,051 |
| media | 2209 | 22 | 0,467 / -0,336 | 0,443 / -0,399 | 0,751 / 0,123 |

