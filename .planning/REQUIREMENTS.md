# Requirements (Milestone v1.0: Otimização do Cálculo NWE)

Este documento especifica os requisitos funcionais e não-funcionais que devem ser validados nesta milestone.

## Requisitos do Escopo

### 1. Algoritmo de Cálculo no Backend (NWE-CALC)

- [x] **NWE-CALC-01**: O sistema deve calcular o valor central do Nadaraya-Watson Envelope usando regressão kernel gaussiana causal (lookback-only) com bandwidth ($bw$) igual a $8$ e limite de lookback de $95$ barras.
- [x] **NWE-CALC-02**: O sistema deve calcular a largura do envelope dinâmico com base no Erro Absoluto Médio (MAE) dos preços de fechamento frente à linha central com multiplicador ($mult$) igual a $3$.
- [x] **NWE-CALC-03**: O sistema deve implementar o "gap stitching" (costura de gap noturno), adicionando a diferença de preço entre o primeiro preço da sessão atual e o último fechamento histórico a todos os dados históricos de fechamento antes do cálculo.
- [x] **NWE-CALC-04**: O sistema deve detectar barras do tipo `is_ghost` (overnight) e congelar os valores das bandas do NWE, repetindo o último valor real computado para manter a estabilidade horizontal das curvas.
- [x] **NWE-CALC-05**: Deve haver testes unitários de paridade matemática rigorosa com tolerância de erro de ponto flutuante menor que $10^{-9}$ comparando a saída da nova biblioteca em Python/NumPy com a saída Javascript original.

### 2. Payload da API & Cache (NWE-API)

- [x] **NWE-API-01**: O endpoint `/api/irai/series` deve chamar a biblioteca NWE do backend e enriquecer o dicionário de cada barra da lista `"series"` com os novos campos calculados.
- [x] **NWE-API-02**: O payload final deve incluir os campos:
  - `nwe_center`, `nwe_upper`, `nwe_lower` (percentuais relativos ao preço de abertura `win_open`)
  - `nwe_center_price`, `nwe_upper_price`, `nwe_lower_price` (valores absolutos em preço)
  - `nwe_slope` (inclinação absoluta)
  - `nwe_up`, `nwe_down` (percentual de acordo com a direção/transição, ou null)
  - `nwe_up_price`, `nwe_down_price` (preço de acordo com a direção/transição, ou null)
- [x] **NWE-API-03**: O cache da API deve preservar e armazenar o payload com os dados de NWE integrados, com invalidação ativa a cada tick recebido do coletor.

### 3. Interface Visual do Dashboard (NWE-UI)

- [ ] **NWE-UI-01**: O frontend React deve ter a função `computeNWE` removida e passar a consumir as variáveis de NWE diretamente da resposta JSON da API.
- [ ] **NWE-UI-02**: Os gráficos de NWE e suas colorações dinâmicas por inclinação no dashboard devem reter 100% de paridade visual e funcional com a exibição original.

---

## Requisitos Futuros (Backlog)

- **NWE-DYN-01**: Bandwidth auto-adaptativo baseado na volatilidade do mercado em tempo real.
- **NWE-ALRT-01**: Disparo de alertas no Telegram caso o preço cruze as bandas extremas do envelope.

---

## Fora de Escopo (Out of Scope)

- Implementar novos estilos de gráficos de envelopes (ex: envelopes Keltner ou bandas de Bollinger) no painel principal.
- Recalibração dos pesos Ridge a partir das bandas do NWE.

---

## Matriz de Rastreabilidade (Traceability)

*(Preenchido no roadmap de fases)*
