---
title: Descobertas e Otimização do Motor V2 (Kalman + Johansen)
date: 2026-05-02
context: Resultados do WFO grid search executado na Fase 6
---

# Descobertas da Otimização do IRAI V2

## 1. O Parâmetro Rei: Lookback = 50
Após rodar o script de Walk-Forward Optimization (`optimize_zscore.py`) para todos os 20 ativos da grade do IRAI utilizando histórico de 3 meses (M5), chegamos a um consenso matemático incontestável: **o Lookback ideal global para o Teste de Cointegração de Johansen é de 50 barras** (~4 horas).

19 dos 20 ativos testados elegeram 50 como sua melhor configuração. Exigir do mercado períodos maiores de cointegração (ex: 100 barras) derruba drasticamente o uptime do robô, pois a correlação intradiária das cestas de ativos muda muito ao longo do dia, com leilões, aberturas de mercado e notícias macro.

O US30 foi a única exceção que matematicamente obteve um *Fitness* marginalmente melhor no Lookback 200, mas como ele rodou de forma excelente também no 50 (96.25% de uptime com 92% de win rate), optou-se por padronizar **Lookback = 50 para todos os ativos sem exceção**, a fim de evitar overfittings.

## 2. A Irrelevância da Covariância no Z-Score
O grid search também validou a `kalman_trans_cov` (Covariância de Transição). Descobrimos que variar a covariância entre `1e-4`, `1e-5` e `1e-6` produziu exatamente **0.00% de diferença no Win Rate final**. 

*Por quê?* Porque o Z-Score normaliza o spread pelo seu Desvio Padrão móvel. Se o filtro de Kalman reagir mais devagar, a volatilidade do spread medido aumenta proporcionalmente, e o Z-Score resultante (que divide o spread por sua volatilidade) acaba esticando até as mesmas extremidades nas mesmas barras de tempo. 

## 3. Limiares (Z-Score Thresholds)
As otimizações focaram em estabilizar a topologia do gráfico (a forma da "Divergência de Preço" / Spread Z-Score), e não nos gatilhos. 
As linhas vermelhas de compra e venda (bandas) continuam operando no default conservador do sistema (`±2.0`). Qualquer otimização desses limites será relegada para análises futuras de Risco x Retorno, visto que o motor atual prova-se altamente assertivo sem a necessidade de estreitar ou alargar as bandas para além das métricas clássicas.
