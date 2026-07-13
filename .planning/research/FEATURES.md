# Expected Features Research

**Domain:** Nadaraya-Watson Envelope (NWE) Indicator
**Researched:** 2026-07-13
**Confidence:** HIGH

## Expected Behaviors & Mathematical Model

O Nadaraya-Watson Envelope (NWE) atua como um rastreador de tendência não-paramétrico com envelopes de volatilidade dinâmica baseados em desvio médio absoluto (MAE). Ele deve comportar-se da seguinte forma:

1. **Kernel Gaussiano Causal (Lookback-only):**
   Para cada ponto no tempo $t$, o valor central do envelope (linha de regressão kernel) é calculado usando uma média ponderada dos preços passados (causal) sob uma janela de lookback fixa ($L = 95$ barras).
   O peso de cada barra retroativa $i$ ($0 \le i < L$) é determinado pelo kernel Gaussiano:
   $$w_i = \exp\left(-\frac{i^2}{2 \cdot bw^2}\right)$$
   onde $bw$ (bandwidth) é fixado em $8$.
   
2. **Largura Dinâmica do Envelope (Volatilidade):**
   Calculada a partir da Média Móvel Simples (SMA) do Erro Absoluto (MAE) entre os preços reais de fechamento e os valores centrais calculados do NWE sobre a mesma janela de lookback.
   O envelope superior/inferior é expandido por um multiplicador de envelope ($mult = 3$):
   $$\text{Upper} = \text{Center} + \text{MAE} \cdot 3$$
   $$\text{Lower} = \text{Center} - \text{MAE} \cdot 3$$

3. **Stitching de Histórico de Gap da Sessão (Overnight Gap):**
   Ao cruzar o gap noturno (overnight), para evitar que a regressão kernel sofra distorções violentas devido à lacuna de preço na abertura do mercado (B3), os preços históricos da sessão anterior devem ser ajustados adicionando a diferença:
   $$\text{gap} = P_{\text{first\_current}} - P_{\text{last\_history}}$$
   a todas as barras históricas, alinhando as curvas de continuidade.

4. **Tratamento de Ghost Bars (Barras Fictícias de Overnight):**
   Se uma barra é classificada como `is_ghost` (sem negociação real, mantida estável para alinhar sessões 24h), o cálculo do NWE deve reter e repetir o último valor computado, mantendo as bandas horizontais estáveis em vez de recomputar ruído.

## Feature Classifications

### Must Have (Table Stakes)
- **Implementação do Algoritmo Gaussiano Causal:** Fiel ao comportamento atual do frontend para garantir paridade matemática.
- **Envelope MAE Dinâmico:** Banda superior e inferior baseada no desvio absoluto médio com multiplicador 3.
- **Gap Stitching:** Costura lógica de dados históricos para prevenir saltos de NWE nas aberturas.
- **Envio via Payload API:** A API FastAPI deve servir a série pré-computada nos endpoints `/api/irai/series`.

### Should Have (Diferenciadores)
- **Cálculo de Transição / Slope Visual:** Enviar também a inclinação (slope) e flags de transição de cor (`nwe_up`, `nwe_down`) para que o frontend não precise computar nada além de plotar as cores corretas no gráfico.

### Defer (v2+)
- **Bandwidth Dinâmico Autoadaptativo:** Ajustar a largura de banda (bw) automaticamente de acordo com o regime de volatilidade (por exemplo, usando ATR). Deferido para evitar quebra de padrão com o visual atual.
