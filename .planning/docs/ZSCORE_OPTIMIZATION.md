# Z-Score V2: Integração de Kalman Filter & Johansen Cointegration

## Contexto da Otimização
A arquitetura V1 do motor do IRAI utilizava uma regressão Ridge estática treinada no início do dia. Essa abordagem apresentava latência para identificar mudanças de regime estrutural, especialmente após choques macroeconômicos. 

A Fase de **Integração de AI e Modelagem Quantitativa Avançada** introduziu o motor V2:
1. **Filtro de Kalman:** Ajusta o coeficiente de regressão (`Beta`) a cada tick/barra para rastrear o "Fair Price" de forma adaptativa.
2. **Teste Johansen:** Varredura pré-calculada por paralelismo para atestar a validade estatística (cointegração) do cluster antes de processar os sinais.
3. **Métrica PnL de Spread Financeiro:** Substituiu o backtest puramente estatístico (cruzamento do Z-Score pelo zero) por uma métrica de Spread Financeiro Real (`Y - X*beta`), travando múltiplas entradas (`in_trade = True`).

## Achados Empíricos e "Edge" Operacional (90 Dias, M5)

### Resultados Finais: PnL Líquido e Retorno Forward (5 Barras / 25 min)
Avaliamos não apenas a campanha segurando a posição até o cruzamento oposto (Z-Exit), mas também a expectativa matemática cravada em 5 barras pós-entrada.

| Ativo | Trades (90d) | **Net PnL** | Ret/DD | Win Rate | Win Rate (5B) | Média Ganho (5B) | Média Perda (5B) |
|-------|--------------|-------------|--------|----------|---------------|------------------|------------------|
| **WIN$N** | 41 | **+3.656 pts** | 1.71 | 56.10% | **58.53%** | +812 pts | -517 pts |
| **WDO$N** | 401 | **+539.3 pts** | **6.56** | 59.60% | 50.37% | +14.4 pts | -12.5 pts |
| **US500** | 393 | **+454.6 pts** | 2.26 | 58.27% | 55.86% | +9.5 pts | -8.2 pts |
| **BTCUSD** | 670 | **+4.203 pts** | 1.33 | 59.85% | 52.08% | +170 pts | -177 pts |
| **USTEC** | 379 | **-1.326 pts** | -0.62 | 56.99% | 48.80% | +44.9 pts | -54.2 pts |
| **EURUSD** | 1292 | **-0.013 pts** | -0.27 | 56.04% | 50.46% | +0.0011 | -0.0011 |
| **USDJPY** | 236 | **-14.28 pts** | -0.90 | 52.54% | 47.23% | +0.30 | -0.40 |

### Insights Estruturais
1. **A Assimetria do WIN$N**: O mini-índice demonstrou extrema reatividade. A maior parte do prêmio financeiro é capturada nos primeiros 25 minutos após a entrada (Scalping), provando a validade do Z-Score em identificar exaustões do fluxo institucional local.
2. **O Trator Silencioso WDO$N (Dólar)**: Entregou +539 pontos de Dólar líquidos, porém expôs uma mecânica diametralmente oposta: exige que o operador "segure" o trade até o cruzamento reverso. Tentar arbitragem de tempo curto (5 barras) corta seu ganho financeiro pela raiz.
3. **O Risco da Nasdaq (USTEC "Fake News")**: Embora prometa um Win Rate > 56%, a Nasdaq quebrou o Net PnL (-1.326 pontos). Este ativo exibe *Fat Tail Risks* agudos — quando rompe a cointegração, não reverte para a média linear, resultando em drawdowns irreparáveis por um sistema não stopado.
4. **O Cemitério de Forex**: A imensa maioria dos pares cambiais (EURUSD, CADCHF, GBPUSD, etc.) sangrou a conta. A regressão estatística em espaço vetorial dinâmico de curto prazo *não é uma barreira suficiente* para os desvios causados por choques macroeconômicos em ativos de alta inércia.

## Estudo de Ablação (Com Johansen vs Sem Johansen)
Um teste de ablação isolando o filtro de Kalman puro (desligando a exigência de cointegração rígida) revelou que o mercado opera em duas personalidades distintas:

1. **Ativos Direcionais e de Momentum (WIN$N, BTCUSD):** O Johansen **atrapalha**. O filtro rígido remove o robô de grandes pernadas lucrativas.
   * *WIN$N Sem Johansen:* **+6.782 pts** (lucro quase dobrou).
   * *BTCUSD Sem Johansen:* **+8.264 pts** (dobrou o lucro, multiplicou trades).
2. **Ativos de "Mean Reversion" (WDO$N, XAUUSD, US500):** O Johansen é a **salvação**. Ele atua como um escudo anti-drawdown, filtrando falsos rompimentos.
   * *XAUUSD Com Johansen:* **+445 pts** (Ret/DD 4.58) vs +297 pts (Ret/DD 1.41) sem. Metade dos trades, triplo da segurança.
   * *WDO$N Com Johansen:* **+539 pts** (Ret/DD 6.56) vs +490 pts (Ret/DD 4.84) sem.

## Decisão Arquitetural e Recomendações
Com base nesses achados quantitativos, a atualização oficial foi validada para a subida ao painel V2:
* **Arquitetura Híbrida**: O motor agora possui a flag `use_johansen` nativa por ativo no banco de dados.
* O **WIN$N** e **BTCUSD** rodam com Johansen desligado (`use_johansen: false`), permitindo rastreamento ágil (Kalman puro).
* O **WDO$N**, **XAUUSD** e **US500** rodam com "guarda alta" (`use_johansen: true`), exigindo estatística rígida antes da entrada.
* **Ativos Restritos**: Isolamento dos pares "Exóticos" de Forex e Nasdaq (`USTEC`), onde nem o Kalman nem o Johansen conseguiram evitar Drawdowns severos.
