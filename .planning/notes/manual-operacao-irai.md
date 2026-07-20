---
title: "Manual de Operação IRAI — Playbook de Trading"
date: 2026-07-20
context: "Definição formal das regras e critérios operacionais do sistema IRAI"
---

# Manual de Operação IRAI — Playbook Operacional

Este manual detalha o protocolo operacional de tomada de decisão do sistema IRAI. A execução deve seguir rigorosamente a sequência de validação em 5 etapas: **Contexto ➔ Zona ➔ Sinal ➔ Confirmação ➔ Entrada (Flip)**.

---

## Fluxo Operacional

```mermaid
graph TD
    A[1. Contexto] -->|Alinhado| B[2. Zona]
    A -->|Desalinhado| A1{Aguardar Exaustão Extrema?}
    A1 -->|Sim| B
    A1 -->|Não| A2[Sem Operação]
    
    B -->|Preço respeita a região| C[3. Sinal]
    C -->|Exaustão detectada| D[4. Confirmação]
    D -->|Martelo / Blended Candle| E[5. Entrada: Gatilho no Flip]
```

---

## 1. Contexto (Tendência Macro e Micro)
O contexto determina a direção permitida para o dia ou para o movimento atual. É composto por dois indicadores principais:

*   **Rastro Macro**: Indica a direção de maior prazo (Compra ou Venda).
*   **Linha Gauss (Média/Tendência)**: A cor da linha define a tendência imediata do ativo (Verde para Compra, Vermelha para Venda).

### Regras de Validação do Contexto
1.  **Cenário Ideal (Alinhamento)**: O Rastro Macro e a Linha Gauss apontam para o mesmo lado (ambos Compra ou ambos Venda). Apenas operações nesta direção são permitidas.
2.  **Cenário Desalinhado**: Rastro Macro e Linha Gauss em sentidos opostos.
    *   *Regra de Segurança*: **Não operar** tendências indefinidas.
    *   *Exceção*: Operar contra a tendência imediata apenas se houver sinal claro de **Exaustão Extrema** do movimento na Zona de interesse.

---

## 2. Zona (Regiões de Interesse / Liquidez)
As zonas são faixas de preço no gráfico onde há alta probabilidade de interesse de grandes players e instituições. O preço deve chegar a essas regiões para que o trade seja cogitado.

### Zonas Identificadas (Mesma Prioridade/Peso)
*   **GEX (Gamma Exposure)**: Níveis de maior acúmulo de gama e potenciais suportes/resistências dinâmicos.
*   **Regiões de Liquidez Diária**:
    *   Ajuste do dia anterior.
    *   Máxima do dia anterior.
    *   Mínima do dia anterior.
*   **Pontos de Liquidez**: Marcações específicas plotadas no gráfico de fluxo e volume.

### Regra de Validação da Zona
*   **Respeito à Região**: A zona só é considerada válida se o preço reagir ao tocá-la, mostrando rejeição inicial (defesa dos players na faixa de preço).

---

## 3. Sinal (Gatilho de Exaustão)
O sinal aponta que o movimento de teste da zona atingiu uma saturação (exaustão), aumentando a probabilidade de reversão imediata.

### Fontes de Sinal (Basta uma delas ocorrer na Zona)
1.  **Banda Gauss**: Preço tocando ou ultrapassando os limites externos das bandas de desvio Gauss.
2.  **Z-Score do Pair Trading**: Desvio estatístico extremo do spread entre ativos correlacionados (ex: `WIN$N` vs `WDO$N`), indicando distorção pronta para correção.
3.  **Pullback na Média Gauss**: Reteste saudável e exaustão no toque de retorno à média da Linha Gauss após rompimento.

---

## 4. Confirmação (Leitura de Fluxo)
A confirmação é o sinal visual de que os compradores/vendedores defenderam a região e começaram a deslocar o preço na direção oposta ao movimento anterior.

### Padrões de Confirmação (Inversão de Fluxo no Candle)
*   **Martelo / Estrela Cadente**: Candle com pavio longo (pelo menos 2x o tamanho do corpo) indicando absorção e rejeição da zona de liquidez.
*   **Blended Candle**: Uma combinação de candles seguidos que, se somados (fundidos no tempo), formam a figura de um martelo/pavio de rejeição.

---

## 5. Entrada (Gatilho no Flip)
A entrada é o gatilho exato para posicionar a ordem no mercado. Não entramos no fechamento do candle de confirmação, mas sim no comportamento do candle seguinte.

### O Gatilho do Flip (Micro Pivot)
O **Flip** é um micro pivot configurado no candle de entrada:
1.  O novo candle abre e inicialmente **se move na direção contrária** à nossa operação pretendida (testando novamente a zona).
2.  Em seguida, o fluxo entra forte na direção correta, fazendo o candle **romper o seu próprio preço de abertura** (virar de cor).
3.  **Execução**: A entrada é disparada no momento exato em que a abertura é rompida de volta (o "flip" da cor).

*   *Exemplo na Compra*: Candle de confirmação fecha deixando pavio de rejeição na mínima anterior. O candle seguinte abre, cai um pouco em direção à mínima (fica vermelho), reverte pro movimento de alta e rompe a sua própria linha de abertura (vira verde). A compra é executada nesse rompimento da abertura.

---

## Exemplos Visuais de Operações

### 1. Operação de Compra (Buy Setup)
Abaixo está a representação visual de um setup completo de Compra (Buy Setup). O preço testa a zona de liquidez inferior (GEX/Ajuste), ativa o sinal de exaustão na banda inferior, forma um Martelo de confirmação e aciona a entrada no **Flip** (abertura contrária seguida de rompimento da abertura).

![Exemplo de Compra (Buy Setup)](../../docs/buy_setup.png)

---

### 2. Operação de Venda (Sell Setup)
Abaixo está a representação visual de um setup completo de Venda (Sell Setup). O preço testa a zona de liquidez superior, ativa o sinal de exaustão na banda superior de Gauss, forma uma Estrela Cadente de confirmação e aciona a entrada no **Flip** de venda (candle seguinte abre subindo contra o trade, reverte e rompe a própria abertura para baixo).

![Exemplo de Venda (Sell Setup)](../../docs/sell_setup.png)

---

## 6. Gestão de Risco Quantitativa (GARCH)
O controle de risco do sistema IRAI é baseado diretamente no desvio padrão diário projetado pelo modelo **GARCH** (`h+1`). Isso assegura um stop dinâmico e matematicamente alinhado com a volatilidade do dia.

### Regra do Stop por Operação
*   **Tamanho do Stop**: Ajustado para **20% a 25%** da volatilidade esperada diária (`h+1`).
*   *Lógica*: Evita ser violinado por ruídos em dias voláteis e reduz financeiramente o stop em dias muito direcionais ou parados.

### Regra do Limite Diário (Stop Total)
*   **Limite Total**: Definido como **100% da volatilidade esperada (1σ GARCH)**.
*   *Lógica*: Equivale a exatamente **4 operações cheias** com stop de 25%, ou **5 operações** com stop de 20%. Atingir o limite de 100% do GARCH encerra as operações do dia.

### Exemplo Prático de Cálculo (Mini Índice - WIN)
Considerando abertura teórica a $120.000$ pontos e Projeção GARCH (`h+1`) de $1.07\%$:
*   **Volatilidade Diária Estimada (100% GARCH)**: $120.000 \times 1.07\% = 1.284 \text{ pontos}$.
*   **Stop Sugerido por Trade (25% GARCH)**: $1.284 \times 25\% = 321 \text{ pontos}$.
*   **Stop Sugerido por Trade (20% GARCH)**: $1.284 \times 20\% = 257 \text{ pontos}$.
*   **Limite de Perda do Dia (100% GARCH)**: $1.284 \text{ pontos}$ de prejuízo acumulado.

---

## Checklist Rápido de Execução

- [ ] **Contexto Alinhado?** (Se não, aguardar exaustão extrema)
- [ ] **Preço em Zona de Relevância?** (GEX, Ajuste, Máxima, Mínima ou Liquidez)
- [ ] **Sinal de Exaustão Presente?** (Banda Gauss, Z-Score Pair ou Reteste)
- [ ] **Candle Confirmou Inversão de Fluxo?** (Martelo ou Blended Candle)
- [ ] **Candle Seguinte Realizou o Flip?** (Micro pivot rompendo a própria abertura)
