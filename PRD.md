# PRD — IRAI (Intraday Risk Appetite Index)

**Versão:** 0.1 (MVP)
**Status:** Draft
**Owner:** Miqueias
**Última atualização:** 2026-04-23

---

## 1. Visão

Construir um indicador intraday que mostra, em tempo real, a **probabilidade de o IBOV fechar o dia em alta**, inferida a partir do comportamento de ativos cross-asset que historicamente lideram ou confirmam o movimento do índice brasileiro — sem olhar para o próprio IBOV como fonte primária de sinal.

O objetivo é responder, a cada 5 minutos e de forma visual, à pergunta: *"Neste momento do pregão, o resto do mundo está dizendo que o IBOV deveria estar subindo ou caindo?"*

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

**Hipótese central:** uma combinação ponderada e normalizada de retornos intraday de EWZ, VIX, DXY e US10Y tem poder preditivo sobre o sinal do retorno de fechamento do IBOV que é **materialmente superior** ao do próprio WIN/IBOV isolado no mesmo horário.

**Evidência de suporte:**

- Correlação diária IBOV × EWZ tipicamente 0.85+ em janelas de 60 dias.
- VIX e DXY têm correlação negativa persistente (−0.3 a −0.6) com IBOV.
- Bancos globais (Citi, Goldman, HSBC) publicam índices semelhantes ("Risk Appetite Indicator", "Global Macro Financial Conditions") com metodologia análoga — validação de que a abordagem tem base empírica.

**Produto resultante:** dashboard web que roda ao lado do setup de trading e atualiza automaticamente, substituindo a necessidade de olhar 5 janelas.

---

## 4. Objetivos & Não-objetivos

### 4.1 Objetivos (MVP)

1. **O1.** Calcular e exibir `P_up(t)` ∈ [0, 100]% a cada 5 min durante o pregão B3 (10:00–17:55 BRT), com reset no open.
2. **O2.** Decompor visualmente a contribuição de cada fator (EWZ, VIX, DXY, US10Y) para o score — o usuário deve identificar em segundos qual ativo está puxando o sinal.
3. **O3.** Validar o modelo em tempo real mostrando o IBOV/WIN real sobreposto à trajetória do IRAI.
4. **O4.** Operar com dois terminais MT5 simultâneos (um BR, um internacional) com tolerância a falha individual — se um cai, o outro continua alimentando o sistema com aviso de *stale data*.
5. **O5.** Pesos do modelo devem ser calibrados em dados históricos reais e recalibráveis via script (não hardcoded em produção).

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

- **RF-01.** Sistema deve coletar barras de 5 min de 6 símbolos: IBOV, WIN (BR); EWZ, VIX, DXY, US10Y (INTL).
- **RF-02.** Dois terminais MT5 independentes, cada um com sua conta/broker, conectados via workers Python separados.
- **RF-03.** Coleta deve rodar durante o pregão B3 (10:00–17:55 BRT) e ser agendada para executar 3 segundos após o fechamento de cada barra de 5 min (10:00:03, 10:05:03, ...).
- **RF-04.** Timestamps devem ser armazenados em **UTC**; conversões de timezone acontecem apenas na camada de apresentação.

### 6.2 Cálculo do IRAI

- **RF-05.** Para cada fator i ∈ {EWZ, VIX, DXY, US10Y}, calcular `z_i(t) = (P_i(t) - P_i(open)) / (σ_i · √(t/T))`, onde σ_i é a vol diária histórica e T é a duração da sessão em barras.
- **RF-06.** Score composto: `S(t) = w_EWZ·z_EWZ + w_VIX·z_VIX + w_DXY·z_DXY + w_US10Y·z_US10Y`.
- **RF-07.** Probabilidade: `P_up(t) = sigmoid(α · S(t)) · 100`.
- **RF-08.** Pesos e α lidos da tabela `model_params`, atualizáveis sem redeploy.
- **RF-09.** Cálculo deve ser idempotente — rodar de novo na mesma barra produz o mesmo resultado.

### 6.3 Reset diário

- **RF-10.** No open B3 (10:00 BRT), o preço de referência para todos os fatores é **congelado** e usado como denominador dos z-scores até o fechamento.
- **RF-11.** Para fatores internacionais que abrem antes da B3, o "open" do IRAI ainda é 10:00 BRT — não o open NYSE.
- **RF-12.** Se um fator não tem cotação às 10:00 BRT exatas (VIX só negocia em horário CBOE), usar último preço disponível anterior.

### 6.4 Apresentação

- **RF-13.** Dashboard React exibe: linha principal P_up(t), stacked area de contribuições, z-scores atuais, IBOV real sobreposto, timestamp da última atualização.
- **RF-14.** Banda de indecisão (40–60%) visualmente marcada.
- **RF-15.** Rotulagem textual do regime: RISK-ON (>65%), RISK-OFF (<35%), COMPRADOR/VENDEDOR leve, INDECISO.
- **RF-16.** Dashboard faz polling do backend a cada 30 segundos OU recebe push via WebSocket.

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
| RNF-04 | Simplicidade    | Stack deve rodar em um único notebook Windows sem containerização                 |
| RNF-05 | Observabilidade | Qualquer discrepância entre valor esperado e calculado rastreável via logs        |
| RNF-06 | Custos          | Zero custo mensal de infra; apenas contas demo dos dois brokers                   |

---

## 8. Métricas de Sucesso

### 8.1 Métricas técnicas

- **Taxa de barras entregues no prazo:** ≥ 98% das 96 barras diárias calculadas e armazenadas.
- **Uptime do agregado:** ≥ 99% do tempo de pregão com ambas MT5 conectadas.
- **Latência p95:** cálculo do IRAI ≤ 3 segundos após barra fechar.

### 8.2 Métricas de modelo (validação)

- **Correlação S(t) × retorno IBOV(t→close):** > 0.35 em janela de 30 dias corridos (sinal de que o score tem poder preditivo além do acaso).
- **Acurácia direcional em P_up > 70% ou < 30%:** > 60% (quando o modelo "se compromete", acerta mais que moeda).
- **Calibração:** frequências observadas em bucketização de P_up devem bater com as probabilidades declaradas (reliability plot).

### 8.3 Métricas de uso (pessoais)

- Dashboard ficou aberto em segunda tela durante pelo menos 80% dos pregões da semana.
- Pelo menos 1 decisão por semana (ajuste de exposição, pausa de robô, entrada/saída manual) tomada com apoio do IRAI.

---

## 9. Escopo

### 9.1 MVP (este ciclo)

- ✅ Dois workers MT5 (BR + INTL) coletando 5 min.
- ✅ SQLite centralizando dados.
- ✅ FastAPI servindo endpoints REST.
- ✅ Dashboard React (já prototipado).
- ✅ Script de calibração offline.
- ✅ Reset diário automático.
- ✅ Tolerância a falha de um broker.

### 9.2 V2 (depois do MVP)

- WebSocket push em vez de polling.
- Alertas sonoros/desktop quando cruza thresholds.
- Histórico intraday consultável (navegação por data no dashboard).
- Múltiplos alvos (não só IBOV — também WIN isolado, small caps, BRL).
- Integração com supervisor dos robôs SQX (pausar automaticamente robôs de swing quando regime vira hostil).

### 9.3 Fora de escopo (pode virar projeto separado)

- Execução de ordens.
- Backtest de estratégia baseada no IRAI.
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

- **Externas:** dois terminais MetaTrader 5 funcionais com contas (demo OK), cada um de broker apropriado para sua jurisdição de dados.
- **Técnicas:** Python 3.11+, `MetaTrader5` package, FastAPI, SQLite, Node 18+, React/Vite.
- **Infra:** máquina Windows (MT5 não roda nativo em Linux/Mac sem Wine); pode ser VPS Windows ou desktop local.

---

## 12. Perguntas abertas

1. **Broker internacional preferido?** Pepperstone, IC Markets, FTMO, XM — cada um tem cobertura de símbolos diferente. Decisão depende de qual tem US10Y/TNX de qualidade.
2. **SQLite é suficiente ou pular direto pra Postgres?** MVP com SQLite é mais simples; migração é trivial se necessário.
3. **Onde roda o frontend?** Mesmo host do backend (localhost:5173) ou servir static build via FastAPI? MVP: Vite dev server em paralelo.
4. **Retenção histórica?** SQLite mantém tudo por padrão; política de retenção/vacuum só se o arquivo crescer além de 1GB.

---

## 13. Decisões tomadas

| Data       | Decisão                                                        | Razão                                                                 |
|------------|----------------------------------------------------------------|-----------------------------------------------------------------------|
| 2026-04-23 | Stack: Python backend + React dashboard                        | Consistência com supervisor SQX e pair trading dashboard              |
| 2026-04-23 | Dois MT5, dois workers Python separados                        | MetaTrader5 lib só suporta 1 conexão por processo                     |
| 2026-04-23 | SQLite como store compartilhado                                | MVP pessoal, sem concorrência, zero overhead de infra                 |
| 2026-04-23 | Polling 30s no frontend no MVP                                 | WebSocket adicionado em V2; polling é trivial e suficiente            |
| 2026-04-23 | Pesos calibrados offline semanalmente                          | Recalibração intraday é overfitting; janela semanal é estável         |
