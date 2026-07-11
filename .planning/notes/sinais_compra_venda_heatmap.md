---
title: Decisão: Substituir Gráfico Z-Score por Heatmap de Sinais D-P-Z-E
date: 2026-05-05
context: Discussão sobre a necessidade de ter sinais mais diretos de compra e venda.
---

# Heatmap de Sinais (D-P-Z-E)

## Problema
Atualmente, apenas o Z-Score possui histórico (histograma e linha no tempo) no dashboard do sistema. Os sinais auxiliares de tomada de decisão:
- Divergência (D)
- Pullback NWE (P)
- Exaustão NWE (E)

Apenas "piscam" no frontend reagindo ao tick ao vivo, mas não mantêm um registro na linha do tempo. Isso dificulta a análise de confluência (ex: "faz 3 barras que tivemos uma divergência, e agora o pullback alinhou com a exaustão").

## Solução (Decisão de UX)
Vamos substituir (ou complementar) a interface de linha tradicional por um **Signal Heatmap (Matriz de Sinais)**, contendo:
- 4 linhas horizontais fixas (uma para cada sinal: D, P, Z, E)
- Colunas temporais sincronizadas com os gráficos
- Cores de estado: Verde (Compra), Vermelho (Venda) ou Escuro/Vazio (Neutro).

## Requisitos de Implementação
1. **API/Backend:** O backend precisa passar a montar o array histórico para D, P, e E. Atualmente, provavelmente os calcula ao vivo ou apenas os passa de forma instantânea.
2. **Frontend:** Implementar o componente gráfico de Heatmap substituindo ou ficando acima do gráfico Z-score atual, para ser o farol visual direto de ação do trader.
