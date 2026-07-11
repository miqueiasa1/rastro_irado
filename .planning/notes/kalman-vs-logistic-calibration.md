---
title: Paradigma do Filtro de Kalman vs Calibração Logística
date: 2026-05-12
context: "Fixing extreme alpha/intercept values caused by offline logistic calibration"
---

# Paradigma do Filtro de Kalman vs Calibração Logística

No desenvolvimento inicial do IRAI, as probabilidades de subida (P_up) eram calculadas aplicando os pesos (betas) exatos retornados por uma regressão linear múltipla em dados históricos, e então mapeando esse "score" numérico para 0-100% usando os parâmetros `alpha` e `intercept` obtidos de uma regressão logística subsequente.

Com a migração para a "v2", implementamos o **Filtro de Kalman** rodando em tempo real (veja `engine.py`). O Kalman ajusta dinamicamente a importância (peso/beta) de cada fator baseando-se na co-variância instantânea do mercado, ignorando os pesos estáticos do banco de dados.

### O Problema do Escalonamento (Scaling)

Ao substituir os betas estáticos pelos betas dinâmicos do Kalman, o "score" (que é `sum(beta_i * z_score_i)`) muda de escala estruturalmente. A antiga regressão logística offline (`calibrate_universal.py`) tenta espremer a probabilidade nos dados em lote, o que frequentemente resulta em hiper-otimização:
- **Alphas muito grandes (ex: > 4.0):** Acontece quando os fatores cravam a direção nos dados passados com precisão artificial. Quando levado pra o online (v2), torna a linha "P_up" binária (salta de 10% pra 90% sem transição suave).
- **Alphas muito pequenos (ex: < 0.5):** Acontece com ativos ruidosos. O resultado online é uma linha de `P_up` perfeitamente estática/reta, pois a função sigmoide é achatada e a volatilidade dos fatores nunca supera o multiplicador diminuto.
- **Intercepts absurdos (ex: > 1.0 ou < -1.0):** A regressão logística compensa tendências globais do mercado (bull/bear market) embutindo vieses massivos (uma probabilidade base de 80% ou 20%). Isso destrói a "justiça" intradiária.

### Solução Estrutural (Guard Rails)

Para suportar o paradigma v2, a função da calibração offline (`alpha` e `intercept`) deixa de ser "acertar a estatística histórica com exatidão matemática" e passa a ser **"prover a sensibilidade visual desejada no Dashboard"**.

- O `alpha` deve atuar apenas como um multiplicador de agilidade (responsividade). Valores ideais ficam entre **1.0 e 3.5**.
- O `intercept` deve ser neutro (**0.0**) ou próximo disso, permitindo que a variação probabilística advenha integralmente do mérito dos fatores em tempo real, sem preconceito tendencioso da base histórica.

Esses limites (Guard Rails) foram implementados em `scripts/calibrate_universal.py`.
