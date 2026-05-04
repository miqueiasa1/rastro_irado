# Phase 6 Context: Evolução Z-Score (Kalman + Johansen)

Este documento registra as decisões de implementação tomadas na sessão de exploração, que devem guiar o planejamento e a codificação da Fase 6.

## 1. Otimização Baseada em Dados (Sem "Chutes")
- **Decisão:** Não usaremos valores arbitrários (hardcoded) para a janela do Johansen ou para a covariância de transição do Kalman Filter.
- **Implementação:** Desenvolveremos um script de otimização dedicado (`scripts/optimize_zscore.py`) que testará múltiplas combinações no período In-Sample.

## 2. Metodologia de Validação (OOS)
- **Decisão:** Walk-Forward Analysis (WFO)
- **Implementação:** O dataset de M5 histórico será segmentado em janelas móveis (ex: treina 3 meses, testa 1 mês). Os parâmetros vencedores de uma janela serão aplicados APENAS no período Out-of-Sample imediatamente seguinte. Isso garante robustez extrema e evita curve-fitting.

## 3. Função Objetivo (Fitness Metric)
- **Decisão:** Misto (Estacionariedade + Win Rate do Z-Score)
- **Implementação:** O otimizador avaliará as rodadas combinando o p-value do Teste de Johansen (garantindo que a cesta é genuinamente cointegrada) e a taxa de acerto (Win Rate) do spread retornando à média após cruzar as bandas do Z-Score (ex: Z > 2.0 ou Z < -2.0).

## Diretrizes Adicionais para a Etapa de Planejamento
- A arquitetura (scikit-learn + statsmodels + pykalman) já está definida no `AI-SPEC.md`.
- O planner deve detalhar os passos para construir a engine do WFO (Walk-Forward Optimization) como a espinha dorsal desta fase.
- Garantir que o cálculo final seja estritamente causal, sem lookahead bias na fase Out-of-Sample.
