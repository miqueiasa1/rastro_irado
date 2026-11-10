# Correção β/z e ruído do Kalman — fase 17

- **Scripts:** `scripts/fase17_unit_fix.py` (análise e registro shadow) e `scripts/compare_nowcast_versions.py` (recálculo antigo × corrigido nas mesmas barras)
- **Bug:** β estimado com retornos brutos, mas o score somava β·z (z = r/σ). O preditor da regressão é Σ β·r = Σ (β·σ)·z. Correção: contribuição = β·σ·z ÷ score_scale; α e intercepto refeitos por logística sem o clamp visual.
- **Kalman:** R = variância real do resíduo intradiário (%²); Q = variância por barra da deriva dos β de janelas de 20 pregões.

## Janela de calibração (in-sample, 252 pregões)

| Alvo | Janela | AUC antigo | AUC corrigido | AUC regressor | Acc antigo | Acc corrigido | Acc regressor | α novo | b novo | score_scale | R antigo → novo | Q antigo → novo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WIN$N | 2025-10-16 a 2026-10-28 | 0,762 | 0,775 | 0,775 | 71,4% | 70,6% | 71,0% | 1,354 | +0,148 | 0,0055 | 1e-03 → 0,569 | 1e-05 → 4,8e-05 |
| WDO$N | 2025-10-16 a 2026-10-28 | 0,706 | 0,770 | 0,770 | 65,1% | 70,2% | 76,2% | 1,243 | -0,390 | 0,0043 | 1e-03 → 0,150 | 1e-05 → 2,8e-05 |

AUC do score corrigido = AUC do regressor (mesma ordenação, por construção). A acurácia com P > 50% difere da do regressor porque o intercepto da logística desloca o corte; o regressor usa o intercepto da regressão de retornos.

## Recálculo nas mesmas barras (engine v2, versão forçada)

### WIN$N: `win-nowcast-20261028T190510Z` × `win-nowcast-20261110T185016Z`

69 pregões, 7759 barras (2026-08-03 a 2026-11-10); fora da amostra = sessões ≥ 2026-10-29 (depois do fim da janela de calibração).

| Versão | Parte | Nowcast AUC | Nowcast BSS (IC 95%) | Nowcast ECE (pp) | 60m AUC | 60m BSS | Fechamento AUC | Fechamento BSS | P < 20 ou > 80 |
|---|---|---|---|---|---|---|---|---|---|
| atual | todas | 0,774 | 0,165 (0,012 a 0,278) | 13,1 | 0,461 | -0,251 | 0,493 | -0,195 | 19,8% |
| atual | in sample | 0,763 | 0,137 (-0,050 a 0,259) | 14,2 | 0,447 | -0,266 | 0,464 | -0,237 | 18,1% |
| atual | fora da amostra | 0,873 | 0,390 (-0,225 a 0,571) | 8,4 | 0,555 | -0,126 | 0,755 | 0,128 | 33,4% |
| corrigida | todas | 0,828 | 0,266 (0,137 a 0,368) | 10,5 | 0,450 | -0,297 | 0,472 | -0,271 | 24,0% |
| corrigida | in sample | 0,815 | 0,235 (0,073 a 0,346) | 11,4 | 0,435 | -0,314 | 0,439 | -0,320 | 22,0% |
| corrigida | fora da amostra | 0,935 | 0,512 (0,115 a 0,641) | 12,1 | 0,570 | -0,161 | 0,765 | 0,101 | 40,0% |

### WDO$N: `wdo-nowcast-20261028T190512Z` × `wdo-nowcast-20261110T185016Z`

69 pregões, 7757 barras (2026-08-03 a 2026-11-10); fora da amostra = sessões ≥ 2026-10-29 (depois do fim da janela de calibração).

| Versão | Parte | Nowcast AUC | Nowcast BSS (IC 95%) | Nowcast ECE (pp) | 60m AUC | 60m BSS | Fechamento AUC | Fechamento BSS | P < 20 ou > 80 |
|---|---|---|---|---|---|---|---|---|---|
| atual | todas | 0,757 | 0,147 (0,015 a 0,245) | 10,4 | 0,494 | -0,168 | 0,447 | -0,249 | 14,6% |
| atual | in sample | 0,769 | 0,177 (0,062 a 0,264) | 11,6 | 0,483 | -0,182 | 0,436 | -0,262 | 13,9% |
| atual | fora da amostra | 0,617 | -1,200 (-5,484 a -0,256) | 32,6 | 0,561 | -0,082 | 0,517 | -0,155 | 19,5% |
| corrigida | todas | 0,869 | 0,261 (0,112 a 0,363) | 17,5 | 0,454 | -0,235 | 0,385 | -0,348 | 15,3% |
| corrigida | in sample | 0,872 | 0,286 (0,149 a 0,383) | 17,3 | 0,449 | -0,244 | 0,364 | -0,384 | 15,2% |
| corrigida | fora da amostra | 0,803 | -0,909 (-5,185 a 0,034) | 31,3 | 0,444 | -0,184 | 0,530 | -0,070 | 16,1% |

Nota: nos dois recálculos acima o Kalman começa do zero em cada pregão (cópia sem estado salvo), para comparar as versões nas mesmas condições. Numa cópia do banco com o estado salvo do live, a versão atual usa esse estado a partir de 29/10 e fica com nowcast fora da amostra WIN AUC 0,756 / BSS 0,154 e WDO 0,667 / −0,911; a corrigida não tem estado salvo e dá os mesmos números da tabela. O WDO fora da amostra (9 pregões) está mal calibrado nas duas versões (ECE ~31 pp).

Leitura: a versão corrigida descreve melhor o dia (nowcast) nas mesmas barras. Ela continua sem prever os próximos 60 minutos (BSS negativo nos dois casos); por isso o painel passa a chamá-la de leitura do dia quando `forecast_ui` for ligado.

