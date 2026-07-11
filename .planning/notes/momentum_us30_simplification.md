---
title: Momentum Tracking e Simplificação de Cestas para Índices (US30)
date: 2026-05-05
---

# Momentum Tracking e Simplificação de Cestas para Índices

Durante testes de estabilização visual da probabilidade direcional (`P_up`) para o Dow Jones (US30), observamos que o modelo universal que exige um mínimo de 6 fatores (com trava anti-colinearidade entre índices americanos) frequentemente resultava em cestas repletas de pares de forex cruzados (ex: EURGBP, GBPJPY) com pesos diluídos e contraditórios. Isso causava uma alta instabilidade visual (flickering) no `P_up` devido à sensibilidade do modelo a ruídos cambiais de micro-momentos.

**Decisão Arquitetural:**
Para ativos altamente colineares do mesmo setor/país (como US30, US500, USTEC), a abordagem de **Momentum Tracker** provou-se matematicamente superior à busca por diversificação forçada.

1. **Exceção de Colinearidade**: Permitiu-se que o `US500` fizesse parte da cesta do `US30`.
2. **Redução de Dimensionalidade**: O mínimo de fatores foi reduzido (para algo entre 3 a 5 fatores), permitindo cestas mais puras.

**Resultados no US30:**
O algoritmo concentrou quase todo o peso no `US500` (beta em torno de +0.85), transformando o S&P 500 no principal balizador direcional (preço justo guiado por momentum). O restante da cesta (ex: EURCHF, BRENT) funciona apenas como redutor de spread de risco residual.

**Impacto:**
- **R² subiu de 0.74 para 0.78**
- **Acurácia saltou de 84% para 87%**
- O `P_up` tornou-se visualmente muito mais liso e intencional, removendo o comportamento caótico gerado por moedas estrangeiras fracamente relacionadas.
