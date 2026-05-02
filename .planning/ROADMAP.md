# Roadmap & Backlog (IRAI Multi-Asset)

Este documento centraliza as próximas propostas de evolução e ideias futuras identificadas para o projeto.

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

---

## 🔜 Próximos Passos

### 1. Integração com Regime Supervisor (Automated Risk Adjustment)
* **Objetivo:** Integrar o sinal de `P_up` e a flag de `price_diverges` do IRAI diretamente nos EAs do Regime Supervisor.
* **Impacto:** Permitir que o portfólio de robôs no MT5 trave o direcional (Buy Only / Sell Only / Block) e ajuste lotes automaticamente de acordo com o clima macro inferido pelo modelo Ridge.

### 2. Otimização do Cálculo NWE
* **Problema:** O `computeNWE` atual é O(n²) — com 287 barras são ~82k iterações de kernel por render.
* **Proposta:** Migrar o cálculo para o backend (Python/NumPy), servindo `nwe_center`, `nwe_upper`, `nwe_lower` já computados na resposta da API. Isso elimina o custo no React e permite bandwidths maiores sem impacto visual.

### 3. Alertas Inteligentes (Push / Telegram)
* **Objetivo:** Disparar eventos webhook para Telegram ou Discord quando houver inversão dramática de convicção.
* **Trigger:** WIN$N caindo de 80% para 20% em menos de duas barras, ou acionando `price_diverges` com alto Z-score.

### 4. NWE Filter Toggle
* **Objetivo:** Checkbox no dashboard que, quando ativado, filtra/suprime sinais de consenso que colidem com a direção do NWE. Ex: se NWE mostra baixa, sinais de "compra" ficam visualmente atenuados.

### 5. Backtest de Sinais IRAI
* **Objetivo:** Usando os dados históricos acumulados (500+ dias de M5), construir um framework de backtest para medir: "Se eu seguisse o sinal IRAI com determinado threshold, qual seria o resultado?"
* **Requisito:** Pode virar projeto separado.

### 6. Evolução Z-Score: Kalman Filter + Johansen Cointegration
* **Objetivo:** Substituir a regressão Ridge/OLS estática diária por uma abordagem mais dinâmica.
* **Proposta:**
  - **Johansen:** Rodar teste de cointegração para o cluster de fatores e garantir que a relação é estacionária no regime atual antes de "autorizar" sinais.
  - **Kalman Filter:** Atualizar o Beta/Hedge Ratio a cada tick/barra para rastrear o "Fair Price" dinamicamente.
  - **Sinal:** Usar o "Resíduo de Inovação" (Erro) do Kalman para gerar a divergência, normalizado por uma variância móvel de curto prazo. Sinal de stop acionado instantaneamente se o Johansen perder a significância (mudança de regime).

---
*Last updated: 2026-04-28*
