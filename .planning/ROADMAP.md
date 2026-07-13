# Roadmap & Backlog (IRAI Multi-Asset)

Este documento centraliza as próximas propostas de evolução e ideias futuras identificadas para o projeto.

---

## 🎯 Milestone Ativa: v1.0 Otimização do Cálculo NWE

| Fase | Título | Objetivo | Requisitos |
|------|--------|----------|------------|
| 1 | Implementação e Testes Unitários de NWE no Backend | Complete (0/0) | 2026-07-13 |
| 2 | Integração de NWE no Endpoint da API | Acoplar o cálculo NWE às rotas do FastAPI (/api/irai/series) com cache ativo | NWE-API-01, NWE-API-02, NWE-API-03 |
| 3 | Refatoração do Frontend React | Remover cálculo local computeNWE e consumir dados prontos da API | NWE-UI-01, NWE-UI-02 |

---

### Phase 1: Implementação e Testes Unitários de NWE no Backend
* **Goal:** Criar o algoritmo de cálculo vetorizado do NWE no backend em Python/NumPy e validar a paridade absoluta frente ao Javascript original.
* **Requirements:** NWE-CALC-01, NWE-CALC-02, NWE-CALC-03, NWE-CALC-04, NWE-CALC-05
* **Success Criteria:**
  1. Novo módulo `backend/quantitative/nwe.py` criado e validado.
  2. Testes de unidade em `tests/` comprovando desvio numérico nulo (< 1e-9) do cálculo de preço e percentual de NWE frente ao algoritmo JS original.

### Phase 2: Integração de NWE no Endpoint da API
* **Goal:** Enriquecer o payload de retorno das séries temporais da API FastAPI com as métricas do NWE pré-calculadas.
* **Requirements:** NWE-API-01, NWE-API-02, NWE-API-03
* **Success Criteria:**
  1. Endpoint `/api/irai/series` retorna os campos `nwe_center`, `nwe_upper`, `nwe_lower`, `nwe_slope`, `nwe_up` e `nwe_down` integrados no dicionário de cada barra da lista `series`.
  2. O cache da API funciona corretamente sem afetar ou corromper os dados do NWE em cache.

### Phase 3: Refatoração do Frontend React
* **Goal:** Eliminar a carga de processamento de NWE no cliente removendo a função `computeNWE` e conectando diretamente os valores pré-calculados.
* **Requirements:** NWE-UI-01, NWE-UI-02
* **Success Criteria:**
  1. Função `computeNWE` removida com sucesso do frontend React.
  2. Exibição do gráfico Nadaraya-Watson Envelope funcionando perfeitamente em `http://localhost:5175` com cores dinâmicas e sem lag de rendering.

---

## ✅ Concluídos

### Cobertura de Novos Ativos (CADCHF, AUDNZD)
* Pares menos correlacionados com DXY adicionados ao collector, calibrados via `calibrate_v2.py`, e exibidos no dashboard. Total: **20 alvos** (recentemente EURGBP, EURCHF, EURJPY, GBPJPY, EURAUD).

### Calibração Universal (Mínimo 6 fatores + DE40)
* O motor de calibração (`calibrate_universal.py`) passou a exigir um mínimo de 6 fatores por cesta (max 8) para forçar o algoritmo de força bruta a selecionar combinações mais estáveis e mitigar *overfitting*.
* O índice **DE40** foi adicionado e se provou um fator macro estrutural essencial, compondo a cesta de 8 alvos (incluindo US500, USTEC, EURGBP, WDO$N).

### Filtro Nadaraya-Watson Envelope (NWE)
* Substituiu o Cumulative Delta no dashboard por um gráfico separado NWE com:
  - Linha de preço (branca)
  - Linha central suavizada com cor dinâmica por segmento (verde=alta, vermelho=baixa)
  - Bandas de envelope tracejadas (MAD × 3)
  - Parâmetros: `bw=8`, `mult=3`

### Sessão 24h para Ativos Globais
* Ativos Tickmill agora coletam e exibem dados de 00:00 a 24:00 UTC. B3 mantém 09:00–18:00.

### Estabilização e Refinamento do Dashboard (UI/UX)
* **Performance & Interatividade:** Remoção de WebSockets (que causavam flickering e race conditions), substituído por HTTP polling 60s estável. Cache server-side implementado.
* **Zoom & Pan:** Adição do componente `Brush` (Recharts) aos gráficos principais, permitindo navegação profunda no histórico intraday.
* **Ícones Profissionais:** Substituição de emojis por códigos alfanuméricos de 2 letras consistentes com padrões de mercado financeiro.

### Integração iShares Axi (Fatores Macro)
* 6 ETFs iShares adicionados como fatores candidatos via 3º terminal MT5 (Axi):
  - **EWZ** (iSharesBrazil+) — proxy equity Brasil
  - **TLT** (iSharesTreasury20+) — Treasury 20+ anos
  - **TLH** (iSharesTreasury10-20+) — Treasury 10-20 anos
  - **SHY** (iSharesTreasury1-3+) — Treasury 1-3 anos (money market proxy)
  - **EMB** (iSharesUSEmerging+) — EM debt denominada em USD
  - **LEMB** (iSharesCurrencyBond+) — EM debt moeda local
* Filtro anti-multicolinearidade: max 1 Treasury e 1 EM Bond por cesta.
* EWZ excluído para ativos BR (tautologia com mesma bolsa).
* **Resultado:** 12/20 modelos selecionaram iShares. WIN$N subiu de 74.8% para 84.5% (+10pp). US500 subiu de 82.3% para 87.4% (+5pp).

### Evolução Z-Score: Kalman Filter + Johansen Cointegration (Otimização V2)
* **Objetivo:** Substituiu a regressão OLS estática diária por uma abordagem 100% dinâmica.
* **Implementação:**
  - **Johansen Cointegration:** Teste pré-calculado paralelamente para o cluster de fatores para garantir estacionariedade no regime atual (corte de ruído no sinal).
  - **Kalman Filter:** Hedge Ratio dinâmico, atualizado a cada barra.
* **Achados da Fase de Otimização (PnL Real Spread em 90 dias M5):**
  - O antigo backtest cruzando zero era irreal. A V2 mede *Spread Financeiro Real* (`Y - X*beta`) travando o lock de trade (`in_trade`).
  - **WIN$N** revelou uma assimetria estrondosa (Net PnL +3.656 pts) e excelente Win Rate para *Scalp* em curtos espaços de tempo (ex: 25 min).
  - **WDO$N** fechou superavitário (Ret/DD 6.56, Net PnL +539 pts), mas exige o *Hold* até o gatilho de Z-Exit para extrair lucro. Scalps perdem consistência.
  - O chamado **"Cemitério de Forex"** sangrou na conta, perdendo Ret/DD. A regressão e o Johansen em janelas curtas não protegem pares de moedas de grandes desvios macro.
* **Ablation Test e Arquitetura Híbrida:** Um teste removendo a trava de Cointegração do Johansen provou que o mercado age de 2 formas. O Johansen **destrói** o PnL de ativos de Momentum direcional (WIN dobrou de lucro sem o filtro), mas **salva** do Drawdown ativos de Mean Reversion puro (Dólar, Ouro). Implementamos flag `use_johansen` nativa por ativo para ligar/desligar o teste.

---

## 🔜 Próximos Passos (Backlog de Evolução)

### 1. Integração com Regime Supervisor (Automated Risk Adjustment)
* **Objetivo:** Integrar o sinal de `P_up` e a flag de `price_diverges` do IRAI diretamente nos EAs do Regime Supervisor.
* **Impacto:** Permitir que o portfólio de robôs no MT5 trave o direcional (Buy Only / Sell Only / Block) e ajuste lotes automaticamente de acordo com o clima macro inferido pelo modelo Ridge.

### 2. Alertas Inteligentes (Push / Telegram)
* **Objetivo:** Disparar eventos webhook para Telegram ou Discord quando houver inversão dramática de convicção.
* **Trigger:** WIN$N caindo de 80% para 20% em menos de duas barras, ou acionando `price_diverges` com alto Z-score.

### 3. NWE Filter Toggle
* **Objetivo:** Checkbox no dashboard que, quando ativado, filtra/suprime sinais de consenso que colidem com a direção do NWE. Ex: se NWE mostra baixa, sinais de "compra" ficam visualmente atenuados.

### 4. Implementar Preenchimento Contínuo (Forward-Fill) de Barras no Motor
* **Objetivo:** Preencher os "buracos" de sessão (como o overnight da B3) com barras projetadas (mesmo valor do fechamento) para unificar os eixos de tempo do dashboard (24/7).
* **Impacto:** Isso fará com que o NWE (que depende apenas de volatilidade local) permaneça perfeitamente estável em uma reta durante o fechamento do ativo alvo, enquanto o Rastro (Z-Score/Kalman) flutua contínua e organicamente na madrugada com base em ativos globais de funcionamento ininterrupto (US30, BTC, etc).

### 5. Implementar Heatmap de Sinais (Matriz D-P-Z-E)
* **Objetivo:** Substituir o gráfico de linha do Z-Score por uma Matriz de Sinais (Heatmap) com 4 linhas: Divergência (D), Pullback NWE (P), Z-Score (Z) e Exaustão NWE (E). Isso tornará a decisão de compra e venda mais direta e visual.
* **Backend:** Modificar o pipeline de dados para armazenar e enviar o histórico completo (time-series) do estado desses 4 sinais, não apenas o booleano do tick atual.
* **Frontend:** Criar o novo componente gráfico de Heatmap e integrá-lo ao dashboard.

---
*Last updated: 2026-07-13*
