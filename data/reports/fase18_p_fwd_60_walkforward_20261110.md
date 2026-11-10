# Modelo de 60 minutos (p_fwd_60) — walk-forward da fase 18

- **Script:** `scripts/train_forecast.py` · **config hash:** `034caeb69793` (pré-registro em `.config.json`) · seed 0
- **Walk-forward:** blocos mensais a partir de 2025-04, janela expansiva, embargo de 1 pregão; interno purgado K = 5 com embargo de 2 pregões escolhe C ∈ [0.01, 0.03, 0.05, 0.1, 0.3] pelo Brier; calibração Platt (isotônica só com n ≥ 20 mil e ECE menor); ensemble B = 50 para a faixa p_lo/p_hi; bootstrap B = 1000 por pregão
- **Conjuntos de features:** `A_base` = SPEC §4.2 sem valor justo (próprio ativo + retornos da cesta); `B_base_valor_justo` = A + gap do valor justo da cesta (z) + gap do par (β OLS 20 pregões); `C_so_valor_justo` = gap da cesta + gap do par + retorno do dia + horário
- **Critérios (SPEC §9):** BSS ≥ 0 fora da amostra, ECE ≤ 3 pp, AUC ≥ protótipo (WIN$N 0,540, WDO$N 0,503) e IC da AUC acima de 0,5

## WIN$N

44130 barras de 442 pregões (2025-01-31 a 2026-11-10); 18 blocos de teste.

| Conjunto | Período | n | AUC (IC 95%) | BSS (IC 95%) | ECE (pp) | Inclinação da confiabilidade | Desvio de p | Barras com p > 55% ou < 45% |
|---|---|---|---|---|---|---|---|---|
| A_base | fora da amostra | 36048 | 0,496 (0,481 a 0,510) | -0,0003 (-0,0018 a 0,0007) | 0,6 | 0,00 | 0,011 | 0,6% |
| A_base | fora da amostra 2025 | 14795 | 0,500 (0,479 a 0,519) | -0,0006 (-0,0041 a 0,0013) | 0,7 | 0,30 | 0,014 | 1,4% |
| A_base | fora da amostra 2026 | 21253 | 0,496 (0,475 a 0,516) | -0,0002 (-0,0029 a 0,0006) | 0,8 | 0,00 | 0,006 | 0,0% |
| B_base_valor_justo | fora da amostra | 36048 | 0,499 (0,484 a 0,514) | -0,0003 (-0,0018 a 0,0008) | 0,8 | 0,00 | 0,011 | 0,4% |
| B_base_valor_justo | fora da amostra 2025 | 14795 | 0,497 (0,473 a 0,522) | -0,0010 (-0,0046 a 0,0012) | 1,4 | -0,08 | 0,014 | 0,9% |
| B_base_valor_justo | fora da amostra 2026 | 21253 | 0,504 (0,482 a 0,523) | 0,0000 (-0,0028 a 0,0010) | 0,8 | 1,13 | 0,007 | 0,1% |
| C_so_valor_justo | fora da amostra | 36048 | 0,496 (0,479 a 0,513) | -0,0010 (-0,0031 a 0,0003) | 0,7 | -0,38 | 0,012 | 0,5% |
| C_so_valor_justo | fora da amostra 2025 | 14795 | 0,506 (0,482 a 0,531) | -0,0009 (-0,0046 a 0,0012) | 0,9 | 0,00 | 0,013 | 0,5% |
| C_so_valor_justo | fora da amostra 2026 | 21253 | 0,490 (0,466 a 0,513) | -0,0013 (-0,0049 a 0,0004) | 1,0 | -0,60 | 0,011 | 0,5% |

- Baselines no mesmo conjunto: momentum AUC 0,496, contrarian AUC 0,504, taxa-base BSS 0.
- B − A (valor justo acrescentado): ΔBSS -0,00001 (IC -0,00052 a 0,00046); ΔAUC +0,0031 (IC -0,0036 a 0,0104).
- Decisão pré-registrada: BSS ≥ 0 não; ECE ≤ 3 pp sim; AUC ≥ protótipo não; IC da AUC > 0,5 não → **rejected**.

## WDO$N

43053 barras de 442 pregões (2025-01-31 a 2026-11-10); 18 blocos de teste.

| Conjunto | Período | n | AUC (IC 95%) | BSS (IC 95%) | ECE (pp) | Inclinação da confiabilidade | Desvio de p | Barras com p > 55% ou < 45% |
|---|---|---|---|---|---|---|---|---|
| A_base | fora da amostra | 35124 | 0,501 (0,487 a 0,515) | -0,0007 (-0,0025 a 0,0002) | 0,6 | -0,21 | 0,011 | 0,4% |
| A_base | fora da amostra 2025 | 14456 | 0,499 (0,474 a 0,523) | -0,0004 (-0,0029 a 0,0004) | 1,0 | -0,71 | 0,007 | 0,0% |
| A_base | fora da amostra 2026 | 20668 | 0,501 (0,484 a 0,519) | -0,0010 (-0,0035 a 0,0004) | 0,4 | -0,18 | 0,013 | 0,7% |
| B_base_valor_justo | fora da amostra | 35124 | 0,501 (0,487 a 0,515) | -0,0007 (-0,0025 a 0,0002) | 0,6 | -0,22 | 0,011 | 0,4% |
| B_base_valor_justo | fora da amostra 2025 | 14456 | 0,498 (0,471 a 0,521) | -0,0005 (-0,0030 a 0,0003) | 0,9 | -1,04 | 0,006 | 0,0% |
| B_base_valor_justo | fora da amostra 2026 | 20668 | 0,502 (0,484 a 0,521) | -0,0009 (-0,0033 a 0,0005) | 0,4 | 0,00 | 0,013 | 0,6% |
| C_so_valor_justo | fora da amostra | 35124 | 0,483 (0,467 a 0,498) | -0,0021 (-0,0049 a -0,0004) | 0,6 | -1,07 | 0,013 | 0,3% |
| C_so_valor_justo | fora da amostra 2025 | 14456 | 0,482 (0,456 a 0,507) | -0,0022 (-0,0055 a 0,0001) | 1,6 | -0,74 | 0,015 | 0,6% |
| C_so_valor_justo | fora da amostra 2026 | 20668 | 0,486 (0,468 a 0,507) | -0,0020 (-0,0062 a -0,0002) | 0,3 | -2,48 | 0,011 | 0,1% |

- Baselines no mesmo conjunto: momentum AUC 0,492, contrarian AUC 0,508, taxa-base BSS 0.
- B − A (valor justo acrescentado): ΔBSS +0,00003 (IC -0,00016 a 0,00022); ΔAUC +0,0002 (IC -0,0023 a 0,0027).
- Decisão pré-registrada: BSS ≥ 0 não; ECE ≤ 3 pp sim; AUC ≥ protótipo sim; IC da AUC > 0,5 não → **rejected**.

Leitura: o modelo calibrado aprende a não opinar (p quase sempre entre 45% e 55%), por isso o ECE é baixo e o BSS fica em torno de zero. Não há vantagem sobre a taxa-base nem sobre momentum/contrarian; o valor justo da cesta não acrescenta nada mensurável.

