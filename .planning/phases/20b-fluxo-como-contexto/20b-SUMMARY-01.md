# Fase 20b Summary 01: fluxo como filtro de GEX + price action (WIN$N)

**Executada:** 16/11/2026, 09:52–09:55 BRT, branch local `v2/fase-19-21a`. Pré-registro `20b-PREREG.md` commitado antes (`a86906b`), config congelada `8dac9d8f8ab1`. Resultado: `data/eval/fase20b/flow20b_8dac9d8f8ab1.json`. Só pesquisa; nada ligado ao vivo.

## Veredito: **INCONCLUSIVO** (não é GO)

| Braço | n | Pregões | Média líq./op. | IC 95% (pregões) | Desenho (n; média) | Validação (n; média) | Acerto | PF |
|---|---|---|---|---|---|---|---|---|
| **F_T3_C1** (primário: T3 + C1 + fluxo) | 53 | 31 | **+83,6 pts** | −45,8 a +236,3 | 35; +59,1 | 18; +131,1 | 53% | 1,51 |
| C_T3_C1 (base, sem fluxo) | 147 | 71 | +29,4 | −49,2 a +113,7 | 96; +15,7 | 51; +55,1 | 47% | 1,15 |
| P1 (T3 + C1 + fluxo fora das zonas) | 54 | — | −44,3 | −153,5 a +83,2 | — | — | — | — |

- O braço base reproduz exatamente a fase 20 (147 operações, +29,4, mesmo IC), o que confere o pipeline.
- Cobertura do fluxo: `cdn(t−1)` definido em 99,1% das barras; 208 pregões (118 desenho / 90 validação).

## Critérios (pré-registrados)
1. IC 95% da média > 0 — **não** (−45,8 a +236,3).
2. Média > 0 nas duas metades com n ≥ 30 em cada — **não** (médias positivas, mas a validação tem só 18 operações).
3. Incremento do fluxo, IC de (F − base) > 0 — **não** (−43,1 a +175,8; P(diferença > 0) = 0,85).
4. Controles — **não**: IC de (F − P1) −48,9 a +307,0 (P > 0 = 0,92); placebo P2 no percentil 90,5 (precisava ≥ 95; mediana P2 +1,6, p95 +103,5).
5. Robustez — **sim**: 2× custo +73,6; k 0,25 +46,1; k 1,0 +68,7.

INCONCLUSIVO porque a média é positiva no total e nas duas metades e fica acima do base, do P1 e da mediana do P2, sem passar nos critérios 1–4.

## Leitura
- O filtro de fluxo vai na direção certa (média de +29 para +84 por operação, P1 negativo), mas com 53 operações o IC continua largo e cruza zero.
- Concentração: outubro tem 2 operações com média +1.015 (2.030 dos 4.430 pts do total); sem outubro a média cai para ~+47. Junho (8 operações, −104) e novembro (3, −172) negativos.
- O braço base foi escolhido nos mesmos dados (fase 20), viés de seleção declarado no pré-registro.
- Descritivos (sem peso no veredito): F_T2_C1 n 7, +295 (amostra pequena demais); F_T3_C0 n 161, +17,1 (desenho −27,6, validação +96,6).

## Decisão sugerida (owner)
Nada vai ao vivo. Opções: (a) acompanhar F_T3_C1 offline nos próximos ≥ 40 pregões (sem refazer a busca) e reavaliar com os mesmos critérios; (b) encerrar a linha GEX + PA + fluxo.
