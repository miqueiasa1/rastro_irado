# PRD — IRAI (Intraday Risk Appetite Index)

**Versão:** 3.0 (Pós-Calibração Universal)
**Status:** Operacional
**Owner:** Miqueias
**Última atualização:** 2026-04-30

---

## 1. Visão

Construir um indicador intraday que mostra, em tempo real, a **probabilidade de cada ativo global fechar o dia em alta**, inferida a partir do comportamento de ativos cross-asset que historicamente lideram ou confirmam o movimento do índice alvo — sem olhar para o próprio ativo como fonte primária de sinal.

O objetivo é responder, a cada minuto e de forma visual, à pergunta: *"Neste momento do pregão, o resto do mundo está dizendo que este ativo deveria estar subindo ou caindo?"*

---

## 2. Problema

O IBOV é um índice **altamente dependente de fatores externos**: fluxo estrangeiro via EWZ, apetite global a risco via VIX, dólar global via DXY, e juros americanos via US10Y. Um trader olhando apenas o gráfico do IBOV (ou do WIN) perde contexto — o índice frequentemente anda por arrasto ou contra os pares, e identificar isso em tempo real exige monitorar 4–5 janelas simultâneas e fazer o cruzamento mental.

Problemas concretos:

- **Latência cognitiva:** o tempo entre o EWZ se mover e o operador perceber + reagir é longo demais pra decisões intraday.
- **Falta de síntese:** cada ativo tem escala diferente (VIX em pontos, DXY em pontos-índice, EWZ em %); comparar "apetite de risco" exige normalização que ninguém faz no olho.
- **Assimetria de informação:** EWZ abre antes da B3 (bolsa americana pré-market às 9:00 BRT contra abertura B3 às 10:00) e reflete reprecificação overnight que muitas vezes dita os primeiros 30 minutos do pregão.
- **Viés de confirmação:** olhar só o ativo operado reforça a tese pré-existente; um indicador cross-asset neutro força reavaliação.

---

## 3. Oportunidade / Hipótese

**Hipótese central:** uma combinação ponderada e normalizada de retornos intraday de fatores cross-asset (câmbio, juros, índices EM, commodities) tem poder preditivo sobre o sinal do retorno de fechamento do IBOV que é **materialmente superior** ao do próprio WIN/IBOV isolado.

**Hipótese VALIDADA ✅ — Acurácia direcional de 71.0% (brute-force 64 combinações).**

**Evidência empírica (252 sessões):**

- DOL$N × WIN$N: correlação -0.62 (fator dominante).
- DI1$N × WIN$N: correlação -0.48 (segundo fator).
- CHINA50 × WIN$N: correlação +0.34 (proxy EM risk appetite).
- USDMXN × WIN$N: correlação -0.34 (EM currency stress).
- VIX e IV ATM foram testados mas **descartados** por reduzir acurácia direcional.
- Bancos globais (Citi, Goldman, HSBC) publicam índices semelhantes — validação de que a abordagem tem base empírica.

**Produto resultante:** dashboard web que roda ao lado do setup de trading e atualiza automaticamente, substituindo a necessidade de olhar 5 janelas.

---

## 4. Objetivos & Não-objetivos

### 4.1 Objetivos (MVP)

1. **O1.** ✅ Calcular e exibir `P_up(t)` ∈ [0, 100]% a cada 60s durante a sessão do ativo (24h globais, 09h–18h B3), com reset no open.
2. **O2.** ✅ Decompor visualmente a contribuição de cada fator — cards ordenados por peso absoluto.
3. **O3.** ✅ Validar o modelo em tempo real mostrando o retorno real sobreposto à trajetória P(↑) do IRAI.
4. **O4.** ✅ Operar com três terminais MT5 sequenciais (XP + Tickmill + Axi) com tolerância a falha individual.
5. **O5.** ✅ Pesos calibrados via `calibrate_universal.py` com Regressão Ridge, filtros anti-multicolinearidade, e 31 fatores candidatos (incluindo DE40, 7 cross-pairs Forex, e 6 iShares Axi). Mínimo 6 fatores por cesta.
6. **O6.** ✅ Gráfico NWE (Nadaraya-Watson Envelope) com cor dinâmica por inclinação e bandas tracejadas.
7. **O7.** ✅ Dashboard acessível remotamente via Firebase Hosting (zero custo).

### 4.2 Não-objetivos (MVP)

- **NO1.** Não é um sistema de execução automatizada — o IRAI é **suporte à decisão**, não sinal de entrada/saída.
- **NO2.** Não substitui análise técnica no timeframe do trader — é uma camada adicional de contexto macro.
- **NO3.** Não integra com o ecossistema SQX / 55 robôs neste MVP (possível V2).
- **NO4.** Não faz backtest de estratégia "comprar IBOV quando P_up > 70" — isso pode ser exposto posteriormente mas não é o objetivo do produto.
- **NO5.** Não tem autenticação / multi-usuário — é ferramenta pessoal rodando localmente.

---

## 5. Personas & Casos de Uso

### 5.1 Persona primária: Miqueias (trader / pesquisador)

- Opera algoritmicamente via MT5 + SQX, mas tem interesse em leitura discricionária do regime de mercado para ajustes de risco global (aumentar/reduzir exposição dos robôs).
- Quer um painel que rode em segunda tela, atualize sozinho, e responda "qual regime o dia está desenvolvendo" sem clicar em nada.

### 5.2 Casos de uso

| ID  | Cenário                                                   | Comportamento esperado                                                       |
|-----|-----------------------------------------------------------|------------------------------------------------------------------------------|
| UC1 | Pregão abre, quero saber se o dia vai ser pró-risco       | Dashboard mostra `P_up` primeira leitura às 10:05 já refletindo overnight    |
| UC2 | P_up caiu de 70% para 40% nas últimas 3 barras            | Gráfico mostra reversão clara + sidebar aponta qual fator virou              |
| UC3 | VIX dispara intraday mas IBOV ignora                      | Contribuição negativa do VIX visível no stacked area; possível divergência   |
| UC4 | Broker internacional cai às 14:30                         | Dashboard mostra status "stale" nos fatores afetados, mantém cálculo parcial |
| UC5 | Quero revisar o dia de ontem                              | Endpoint `/session/{date}` retorna a série completa histórica                |
| UC6 | Rodar calibração semanal dos pesos                        | Script `calibrate.py` roda sábado, atualiza `model_params`, gera relatório   |

---

## 6. Requisitos Funcionais

### 6.1 Coleta de dados

- **RF-01.** ✅ Sistema coleta barras M5 de 34 símbolos: WIN$N, DOL$N, DI1$N, WDO$N (XP); US500, US30, USTEC, DE40, EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, XAUUSD, BTCUSD, VIX, DXY, BRENT, CHINA50, USDMXN, AUDNZD, CADCHF, EURGBP, EURCHF, EURJPY, GBPJPY, EURAUD (Tickmill); iSharesBrazil+, iSharesTreasury20+, iSharesTreasury10-20+, iSharesTreasury1-3+, iSharesUSEmerging+, iSharesCurrencyBond+ (Axi — fatores de calibração apenas).
- **RF-02.** ✅ Collector unificado conecta sequencialmente aos 3 terminais MT5 (XP → Tickmill → Axi) a cada ciclo.
- **RF-03.** ✅ Coleta roda a cada 60s, 24h para ativos globais, 09h–18h para B3.
- **RF-04.** ✅ Timestamps armazenados em UTC; conversão BRT apenas na apresentação.

### 6.2 Cálculo do IRAI

- **RF-05.** ✅ Para cada fator i ∈ {DOL, DI, DXY, BRENT, CHINA50, USDMXN}: `z_i(t) = (P_i(t) - P_i(open)) / (σ_i · √(t/T))`.
- **RF-06.** ✅ Score: `S(t) = Σ w_i · z_i(t)` com 6 fatores otimizados.
- **RF-07.** ✅ Probabilidade: `P_up(t) = sigmoid(α · S(t) + intercept) · 100`.
- **RF-08.** ✅ Pesos e α lidos de `model_params`, atualizáveis via `calibrate_m5.py`.
- **RF-09.** ✅ Cálculo idempotente — determinístico para mesma barra.

### 6.3 Reset diário

- **RF-10.** No open B3 (10:00 BRT), o preço de referência para todos os fatores é **congelado** e usado como denominador dos z-scores até o fechamento.
- **RF-11.** Para fatores internacionais que abrem antes da B3, o "open" do IRAI ainda é 10:00 BRT — não o open NYSE.
- **RF-12.** Se um fator não tem cotação às 10:00 BRT exatas (VIX só negocia em horário CBOE), usar último preço disponível anterior.

### 6.4 Apresentação

- **RF-13.** ✅ Dashboard React exibe: linha principal P_up(t), gráfico NWE (preço + média + envelope), Z-score de divergência, timestamp da última atualização.
- **RF-14.** ✅ Banda de indecisão (40–60%) visualmente marcada com limiares compra/venda.
- **RF-15.** ✅ Badge de convicção: forte/moderada/fraca com cores dinâmicas na overview.
- **RF-16.** ✅ Dashboard faz polling HTTP a cada 60 segundos (local). Firebase SSE para modo nuvem.

### 6.5 Calibração

- **RF-17.** Script offline `calibrate.py` roda sobre 60 dias de dados diários, estima pesos via regressão linear multivariada com IBOV retorno diário como Y.
- **RF-18.** Script estima σ_i (vol diária anualizada / √252) de cada fator.
- **RF-19.** α é calibrado via regressão logística sobre score intraday × sinal de fechamento em amostra histórica.
- **RF-20.** Resultados gravados em `model_params` com timestamp; histórico de calibrações preservado.

### 6.6 Robustez & observabilidade

- **RF-21.** Health check endpoint mostra: status de cada MT5, timestamp da última barra recebida por símbolo, idade do cálculo mais recente.
- **RF-22.** Se um símbolo está atrasado > 2 barras, marcar como stale e exibir aviso no dashboard.
- **RF-23.** Logs estruturados (JSON) em arquivo rotativo por worker.
- **RF-24.** Reconexão automática ao MT5 em caso de desconexão, com backoff exponencial.

---

## 7. Requisitos Não-Funcionais

| ID     | Categoria       | Requisito                                                                         |
|--------|-----------------|-----------------------------------------------------------------------------------|
| RNF-01 | Latência        | P_up(t) deve estar disponível na API em ≤ 5 segundos após o fechamento da barra   |
| RNF-02 | Disponibilidade | 99% durante pregão (um outage curto de 1 min por semana é aceitável no MVP)       |
| RNF-03 | Reprodutibilidade | Dado o mesmo conjunto de barras, P_up e componentes devem ser determinísticos    |
| RNF-04 | Simplicidade    | Stack local invisível no Windows via NSSM, interface web remota servida via nuvem |
| RNF-05 | Observabilidade | Qualquer discrepância entre valor esperado e calculado rastreável via logs        |
| RNF-06 | Custos          | Zero custo mensal de infra; frontend e banco remoto via Firebase Free Tier        |

---

## 8. Métricas de Sucesso

### 8.1 Métricas técnicas

- **Taxa de barras entregues no prazo:** ≥ 98% ✅ (collector 60s com 2 terminais).
- **Uptime do agregado:** ≥ 99% ✅ (operacional desde 2026-04-23).
- **Latência p95:** < 1 segundo ✅ (SQLite local, sem rede).

### 8.2 Métricas de modelo (validação) — RESULTADOS REAIS

| Métrica | Target | **Resultado** | Status |
|---------|--------|--------------|--------|
| R² (OLS) | > 0.35 | **0.5801** (WIN) / **0.5844** (WDO) | ✅ |
| Acurácia direcional (WIN) | > 60% | **85.1%** | ✅ |
| Acurácia direcional (WDO) | > 60% | **84.2%** | ✅ |
| Acurácia média (20 ativos) | > 70% | **86.5%** | ✅ |
| R² top-3 (EURJPY, GBPJPY, EURGBP) | > 0.90 | **0.96–0.98** | ✅ |
| Reliability P_up 0-25% | ~20% real alta | **19.1%** | ✅ |
| Reliability P_up 75-100% | ~80% real alta | **84.6%** | ✅ |

### 8.3 Métricas de uso (pessoais)

- Dashboard ficou aberto em segunda tela durante pelo menos 80% dos pregões da semana.
- Pelo menos 1 decisão por semana (ajuste de exposição, pausa de robô, entrada/saída manual) tomada com apoio do IRAI.

---

## 9. Escopo

### 9.1 V1 (concluído ✅)

- ✅ Collector MT5 unificado (XP + Tickmill) a cada 30s.
- ✅ SQLite WAL centralizando dados (~700k barras).
- ✅ FastAPI (porta 8888) servindo endpoints REST.
- ✅ Dashboard React + Vite (porta 5175) com polling 30s.
- ✅ Engine IRAI: z-score + OLS + logística com 6 fatores otimizados.
- ✅ Calibração offline com relatório automatizado.
- ✅ Brute-force de 64 combinações de fatores → 71% accuracy.
- ✅ Fluxo Delta (book pressure) como indicador auxiliar.
- ✅ Velocímetro P(↑) com sinal visual COMPRA/VENDA/NEUTRO.
- ✅ Navegação por sessões históricas (date picker).

### 9.2 V2 (concluídos ✅)

- ✅ Painel Central Multi-Ativo com Divergência de Preço e NWE.
- ✅ Multi-target: expansão para 20 ativos globais e BR (CADCHF + AUDNZD + cross-pairs adicionados).
- ✅ **Espelhamento Cloud Híbrido:** Firebase Hosting e Sync para acesso remoto sem abrir a rede local.
- ✅ Execução em background invisível via Windows Services (NSSM).
- ✅ Sessão 24h para ativos globais (00:00–24:00 UTC).
- ✅ NWE (Nadaraya-Watson Envelope) com cor dinâmica por inclinação (bw=8, mult=3).
- ✅ Cache server-side por (target, date) com invalidação no collector.
- ✅ Polling HTTP 60s (WebSocket revertido por estabilidade).
- ✅ **Refinamentos UI/UX:** Navegação profunda com `Brush` (Zoom/Pan) nos gráficos e iconografia padronizada em códigos de 2 letras substituindo emojis.
- ✅ **Hierarquia Visual de Alertas (Global vs Local):** Restrição do blink global da placa (AssetCard) apenas para cenários críticos (Divergência de Retorno). Adição de 4 micro-badges locais (D-P-Z-E) para status secundários (Divergence, Pullback, Z-Score, Exhaustion).
- ✅ **Design Minimalista Mobile:** Remoção do sparkline (gráfico P_up pequeno) na Overview para reduzir a carga cognitiva, priorizando a legibilidade dos sinais D-P-Z-E e valores absolutos.
- ✅ **Cálculo de Retorno Intradiário vs Brokers:** Retorno (win_return) indexado à abertura da sessão (ignorando Gaps de fechamento anterior), diferente do MT5. (Documentado em `IRAI_RETURN_VS_MT5.md`).
- ✅ **iShares Axi:** 6 ETFs (EWZ, TLT, TLH, SHY, EMB, LEMB) integrados como fatores de calibração via 3º terminal MT5 (Axi). Filtro anti-multicolinearidade (max 1 Treasury + 1 EM Bond por cesta). 12/20 modelos melhorados.

### 9.3 V3 (próximos passos)

- [ ] Integração IRAI × Regime Supervisor (ajuste de exposição dos EAs por P_up).
- [ ] Walk-forward validation automática na calibração.
- [ ] Backtester de estratégias baseadas em thresholds de P_up.
- [ ] Otimização NWE: migrar cálculo para backend (Python/NumPy).
- [ ] Alertas desktop/Telegram ao cruzar thresholds.
- [ ] NWE Filter toggle (supressão visual de sinais contra a tendência).

### 9.4 Fora de escopo

- Execução de ordens.
- Versão mobile / app nativo.
- Multi-usuário / SaaS.

---

## 10. Riscos & Mitigações

| Risco                                                        | Impacto | Prob. | Mitigação                                                                                    |
|--------------------------------------------------------------|---------|-------|----------------------------------------------------------------------------------------------|
| Broker BR não tem dados de qualidade de IBOV intraday        | Alto    | Média | Validar na fase de setup; fallback pra WIN + reconstrução implícita do IBOV                  |
| Broker INTL não tem US10Y nativo                             | Médio   | Alta  | Substituir por TLT (inverso) ou ZN (10Y Note future); documentar trade-off                   |
| Os dois MT5 têm server time diferente                        | Médio   | Alta  | Normalizar tudo pra UTC no momento da ingestão; nunca confiar em hora local do terminal      |
| Pesos calibrados overfitam em 60 dias                        | Médio   | Média | Validação out-of-sample no `calibrate.py`; comparar com janela 120d                          |
| Gap de abertura IBOV dominado por earnings BR não capturados | Alto    | Baixa | Documentar como limitação conhecida; IRAI é cross-asset macro, não responde a news idiossin. |
| VIX não abre até 10:30 BRT (CBOE)                            | Médio   | Alta  | Primeiros 30 min da sessão B3 usam VIX de fechamento anterior; sinalizar "VIX stale"         |
| MT5 Python lib limita 1 conexão por processo                 | Alto    | Certo | Arquitetura explicitamente com 2 workers separados — resolvido por design                    |

---

## 11. Dependências

- **Externas:** três terminais MetaTrader 5 funcionais com contas (demo OK): XP (BR), Tickmill (INTL), Axi (iShares ETFs).
- **Técnicas:** Python 3.11+, `MetaTrader5` package, FastAPI, SQLite, Node 18+, React/Vite.
- **Infra:** máquina Windows (MT5 não roda nativo em Linux/Mac sem Wine); pode ser VPS Windows ou desktop local.

---

## 12. Perguntas resolvidas

1. ~~**Broker internacional preferido?**~~ → **Tickmill** (DXY, BRENT, CHINA50, USDMXN com boa qualidade M5).
2. ~~**SQLite é suficiente?**~~ → Sim. ~700k barras, ~50MB, sem problemas de performance.
3. ~~**Onde roda o frontend?**~~ → Vite dev server porta 5175, backend porta 8888.
4. ~~**Retenção histórica?**~~ → Mantém tudo; ainda longe de 1GB.

---

## 13. Decisões tomadas

| Data       | Decisão                                                        | Razão                                                                 |
|------------|----------------------------------------------------------------|-----------------------------------------------------------------------|
| 2026-04-23 | Stack: Python backend + React dashboard                        | Consistência com supervisor SQX e pair trading dashboard              |
| 2026-04-23 | SQLite WAL como store compartilhado                            | Pessoal, zero overhead de infra                                       |
| 2026-04-23 | Polling 30s no frontend                                        | WebSocket em V2; polling é trivial e suficiente                       |
| 2026-04-24 | Collector unificado (1 processo, 2 terminais sequenciais)      | Mais simples que 2 workers; reconexão sequencial funciona bem         |
| 2026-04-24 | **Remover VIX e IV ATM** dos fatores                           | Brute-force mostrou que reduzem acurácia direcional (67.2% → 66.2%) |
| 2026-04-24 | **Adicionar CHINA50 e USDMXN**                                | Brute-force: combo dol+di+dxy+brent+china+mxn = **71% accuracy**     |
| 2026-04-24 | **Remover DE40** após teste                                    | Correlação forte (+0.31) mas sinal invertido na OLS = ruído           |
| 2026-04-24 | Pesos calibrados offline (252 sessões rolling)                 | Walk-forward automático planejado para V3                             |
| 2026-04-27 | **Sessão 24h para ativos globais**                             | Forex/Crypto operam fora do B3; 09–18h descartava dados              |
| 2026-04-27 | **CADCHF + AUDNZD adicionados** (15 alvos)                    | Diversificação de cross-hedging fora do DXY                          |
| 2026-04-29 | **EURGBP, EURCHF, EURJPY, GBPJPY, EURAUD** (20 alvos)         | Expansão para mais pares Forex globais cross-currency                |
| 2026-04-28 | **NWE substituiu Cumulative Delta**                            | Delta era ruidoso; NWE dá leitura direcional limpa com envelope       |
| 2026-04-28 | **Polling HTTP 60s em vez de WebSocket**                       | WS causava flickering e race conditions de data                       |
| 2026-04-28 | **Cache server-side por (target, date)**                       | Evita recomputar a cada request; invalidado no notify_update          |
| 2026-04-28 | **iShares Axi como fatores macro**                            | 6 ETFs (EWZ, TLT, TLH, SHY, EMB, LEMB) via 3º terminal Axi; filtros anti-multicolinearidade (max 1 Treasury + 1 EM Bond por cesta). 12/20 modelos selecionaram iShares. |
| 2026-04-28 | **3 terminais MT5 sequenciais**                                | Axi adicionado exclusivamente para iShares ETFs (16h–23h UTC); não adiciona ativos ao painel |
| 2026-04-30 | **Reverter exclusão DE40 — reincluir na pool global**          | Calibração universal com min 6 fatores demonstrou que DE40 é estrutural (integrou 8/20 cestas). ACC média subiu 5pp vs. calibração anterior. |
| 2026-04-30 | **Mínimo 6 fatores por cesta (constraint)**                    | Cestas com 4 fatores tinham R² baixo e overfitting em cross-pairs. 6-8 fatores = equilíbrio robustez × complexidade. |
| 2026-04-30 | **Calibração Universal (4 ondas, 20 ativos)**                  | Brute-force completo com 31 candidatos × 20 alvos. Ganhos: EURGBP R²=0.96, GBPJPY ACC=96.5%, WIN ACC 74.8→85.1%, WDO ACC 76→84.2%. ADR-001 documenta. |
