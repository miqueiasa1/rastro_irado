# Roadmap & Backlog (IRAI Multi-Asset)

Este documento centraliza as próximas propostas de evolução e ideias futuras identificadas para o projeto.

---

## 🎯 Milestone Ativa: v1.0 Otimização do Cálculo NWE

| Fase | Título | Objetivo | Requisitos |
|------|--------|----------|------------|
| 1 | Implementação e Testes Unitários de NWE no Backend | Complete (0/0) | 2026-07-13 |
| 2 | Integração de NWE no Endpoint da API | Complete (0/0) | 2026-07-13 |
| 3 | Refatoração do Frontend React | Complete (0/0) | 2026-07-13 |
| 4 | Robustez de Infraestrutura (Concorrência e Persistência) | Complete (0/0) | 2026-07-18 |
| 5 | Expansão de Ativos no Rastro (Índices Globais: DE40, US2000, JP225, CHINA50) | Complete (2/2) | 2026-07-23 |
| 6 | Comparação Detalhada e Alinhamento com o Fork | Complete (2/2) | 2026-07-24 |
| 7 | Merge Backend e Banco | Resolver conflitos e consolidar banco de dados | 2026-08-01 |
| 8 | Portabilidade dos Scripts e Testes | Trazer testes e scripts PIT do fork | 2026-08-05 |
| 9 | Unificação do Frontend e Gráficos | Trazer Lightweight-charts e refatorações | 2026-08-10 |
| 10 | Homologação e Verificação UAT | Testar final unificado em staging | 2026-08-12 |
| 11 | Resolução Automática de Contratos Ativos B3 em Contas Demo | Mapear WIN$N/WDO$N/DI1$N para contratos vigentes no boot | 2026-07-27 |
| 12 | Motor de Armazenamento de Snapshots Imutáveis em Tempo Real (Zero-Repainting Live Mode) | Complete (3/3) | 2026-07-30 |
| 13 | Rastro de Mini Índice (Top 8 Ações IBOV) | Complete (4/4) | 2026-08-12 |
| 14 | Auditoria Waves 0-5 (cofre Pine, fuso do broker, sessão B3 09:00 & NWE gap stitching, sync estrito dos gráficos, endurecimento GEX e manutenção diária) | Complete (6/6) | 2026-10-29 |

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

### Phase 4: Robustez de Infraestrutura (Concorrência e Persistência)
* **Goal:** Aplicar melhorias de robustez identificadas no fork `brenoperucchi/rastro_irado` para eliminar race conditions de boot, proteger a persistência do Kalman contra replays acidentais, e auditar a tabela GEX — tudo sem alterar as fórmulas de P Dinâmico ou Pair Spread.
* **Requirements:** INFRA-01, INFRA-02, INFRA-03
* **Success Criteria:**
  1. Migrações de banco rodam sem crash quando API e Collector iniciam simultaneamente (guard `_add_column` idempotente).
  2. Replays históricos via `compute_from_db()` não sobrescrevem o estado Kalman de sessões mais recentes (guard monotônico de timestamp).
  3. Tabela `gex_levels` possui schema atualizado com coluna `run_name` e dados legados estão íntegros.

### Phase 5: Expansão de Ativos no Rastro (Índices Globais: DE40, US2000, JP225, etc.)
* **Goal:** Cadastrar, calibrar e habilitar 4 novos índices globais (DAX 40 / DE40, Russell 2000 / US2000, Nikkei 225 / JP225, etc.) no coletor, no motor de calibração universal, na API e no dashboard do Rastro Irai.
* **Requirements:** ASSET-01, ASSET-02, ASSET-03
* **Success Criteria:**
  1. Novos ativos configurados para coleta de barras no `collector.py` via MT5 (Tickmill / Axi).
  2. Modelos estatísticos calibrados via `calibrate_universal.py` com regressão Ridge, Johansen e filtro Kalman, persistidos em `asset_models` e `model_params`.
  3. API (`engine.py`) e Dashboard React renderizando os 4 novos ativos de forma integrada no Rastro Irai com gráficos de Z-Score, NWE e Pair Spread.

### Phase 6: Comparação Detalhada e Alinhamento com o Fork
* **Goal:** Realizar a auditoria de conflitos e comparação detalhada das divergências de código entre o branch local `main` e o fork `brenoperucchi/rastro_irado`, detalhando a estratégia de integração de ambas as frentes.
* **Requirements:** COMPAR-01, COMPAR-02
* **Success Criteria:**
  1. Comparação detalhada gerada em documento de artefato (`fork_comparison.md`) mapeando arquivos novos, deletados e conflitos específicos.
  2. Plano de integração e merge de frentes divergentes estruturado e documentado em `.planning/phases/06-comparacao-detalhada-e-alinhamento-com-o-fork/06-PLAN-01.md`.
  3. Relatório de encerramento (`06-SUMMARY-01.md`) validando a fase como completa.

### Phase 7: Merge Backend e Banco
* **Goal:** Consolidar os conflitos nos arquivos `engine.py`, `main.py`, `db.py` e `collector.py` entre a versão local e o fork.
* **Requirements:** MERGE-01
* **Success Criteria:** Consolidação realizada sem quebras.

### Phase 8: Portabilidade dos Scripts e Testes
* **Goal:** Trazer as rotinas de testes robustos e scripts PIT do fork para o ambiente local.
* **Requirements:** PORT-01
* **Success Criteria:** Todos os testes rodando com sucesso.

### Phase 9: Unificação do Frontend e Gráficos
* **Goal:** Migrar o frontend unificado para usar a base pura de Lightweight-charts, re-implementando os novos painéis locais de Z-score (sem bolinhas) e stop GARCH.
* **Requirements:** UI-UNIFY-01
* **Success Criteria:** Interface modular, rápida e limpa de dependências antigas.

### Phase 10: Homologação e Verificação UAT
* **Goal:** Testar e validar o sistema integrado fim-a-fim em staging/simulação.
* **Requirements:** UAT-01
* **Success Criteria:** Verificação de integridade de dados e latência.

### Phase 11: Resolução Automática de Contratos Ativos B3 em Contas Demo
* **Goal:** Permitir que o coletor resolva dinamicamente os símbolos contínuos B3 (`WIN$N`, `WDO$N`, `DI1$N`) para seus contratos vigentes reais (ex: `WINQ26`) quando o terminal estiver conectado a uma conta demo que não suporte os símbolos contínuos nativamente.
* **Requirements:** FALLBACK-DEMO-01, FALLBACK-DEMO-02
* **Success Criteria:**
  1. O coletor detecta a ausência do símbolo contínuo e mapeia para o contrato futuro ativo equivalente de maior liquidez e com vencimento futuro.
  2. A gravação no SQLite é feita usando o símbolo contínuo original (`WIN$N`, `WDO$N`, `DI1$N`), garantindo compatibilidade do backend e frontend.
  3. API e Dashboard funcionam perfeitamente em contas demo.

### Phase 12: Motor de Armazenamento de Snapshots Imutáveis em Tempo Real (Zero-Repainting Live Mode)
* **Goal:** Criar e integrar uma tabela append-only (`irai_live_snapshots`) para gravar os snapshots calculados minuto a minuto em tempo real, eliminando 100% o repainting retroativo gerado pelo re-ancoramento dos preços de abertura B3 (09h00) e EUA (10h30).
* **Requirements:** LIVE-SNAP-01, LIVE-SNAP-02, LIVE-SNAP-03
* **Success Criteria:**
  1. Tabela `irai_live_snapshots` criada e migrada com sucesso via `db.py`.
  2. Worker `collector.py` gravando snapshots live ao final de cada ciclo de coleta.
  3. Endpoint `/api/irai/series` suportando o parâmetro `mode=live` (padrão) com resposta instantânea e suporte ao modo `mode=recalculated`.
  4. Interface web exibindo indicador visual **"LIVE IMUTÁVEL (Sem Repaint)"** com 100% de estabilidade nos dados passados.

### Phase 13: Rastro de Mini Índice (Top 8 Ações IBOV)
* **Goal:** Criar um modelo estatístico e rastro em tempo real para o Mini Índice (`WIN$N`) baseado na combinação ponderada das 8 ações de maior peso da carteira do Ibovespa (VALE3, PETR4, ITUB4, BBDC4, ELET3, WEGE3, ABEV3, B3SA3).
* **Requirements:** WIN-TOP8-01, WIN-TOP8-02, WIN-TOP8-03, WIN-TOP8-04
* **Success Criteria:**
  1. Configuração da coleta M1/M5 das 8 ações líderes do IBOV via MetaTrader 5 no `collector.py`.
  2. Motor de calibração (`calibrate_universal.py` / Ridge + Kalman + Johansen) calibrando os pesos dinâmicos e persistindo em `asset_models` / `model_params`.
  3. API e backend enviando métricas de Z-score, Pair Spread e NWE para o rastro do Mini Índice com Top 8 Ações.
  4. Visualização e gráficos no Frontend integrados mantendo as regras estritas de Zero-Repainting, Sincronização e visibilidade do Pair Spread.

### Phase 14: Auditoria Waves 0-5
* **Goal:** Registrar e consolidar as correções da auditoria de 28/10/2026, entregues no commit `f2b6d0d` (29/10/2026, 08:55 horário de Brasília / America/Sao_Paulo): segurança do cofre Pine, normalização do fuso do broker, sessão B3 às 09:00 com gap stitching do NWE, sincronização estrita dos gráficos, endurecimento do GEX e manutenção diária.
* **Requirements:** a confirmar (o commit não define IDs formais de requisito; o código cita os itens de auditoria A1, A6, A15, A16, A17 e M2)
* **Success Criteria:**
  1. **Wave 0 — Segurança do cofre Pine:** arquivos `.pine` deixam de ser versionados ou servidos no Hosting (`.gitignore`, `frontend/firebase.json`); download autenticado via `PineDownloadModal` e `GET /api/gex/pine` com chave `sha256(PINE_SALT:PINE_PASSWORD)`; publicação no Firebase RTDB em `pine_vault/<chave>` (`scripts/sync_gex_to_irai.py`) e regras em `frontend/database.rules.json`. No mesmo conjunto de endurecimento da API (item A6): bind em `127.0.0.1:8888`, CORS restrito ao Vite local e `/api/internal/notify_update` apenas no loopback.
  2. **Wave 1 — Normalização do fuso do broker:** módulo `backend/timeconv.py` documenta que `market_bars.timestamp_utc` usa o relógio do broker (Nova York + 7h: GMT+3 no verão americano, GMT+2 no inverno) e converte a B3 de BRT com offset dinâmico (+6h/+5h); script `scripts/migrate_b3_broker_time.py` para o histórico B3; testes em `tests/test_timeconv.py`. As ondas 1 e 2 são nomeadas em `scripts/deploy_onda1_2.ps1` como “fuso/sessão B3 + Regra 4”.
  3. **Wave 2 — Sessão B3 09:00 e NWE gap stitching:** pregão regular definido como 09:00–18:30 BRT; a abertura do alvo B3 é a 1ª barra a partir das 09:00 BRT (não o after-market de ontem); pré-sessão com retorno, Z-score e contribuição iguais a zero (Regra 4 / item A1 em `backend/irai/engine.py`); gap stitching no NWE (`backend/irai/nwe.py`) para o salto noturno não inflar o MAE; testes em `tests/test_engine_session_invariants.py` e `tests/test_nwe_gap.py`; Regra 4 documentada em `.agents/AGENTS.md`.
  4. **Wave 3 — Sincronização estrita dos gráficos:** o range lógico inicial é aplicado uma vez por série (Regra 3, `TVGarchVolChart` e demais painéis Lightweight Charts); polls seguintes preservam o range visível, avançando apenas se o usuário estiver na borda direita; os gráficos compartilham o mesmo range, sem `fitContent` local dessincronizando os outros painéis.
  5. **Wave 4 — Endurecimento do GEX:** `scripts/backfill_gex_history.py` reconstrói níveis históricos a partir do git do projeto GEX; `scripts/standardize_win_gex_history.py` audita e padroniza coletas `WIN$N` na tabela `gex_levels` (objetivo declarado no script: corrigir 7 coletas anômalas e aplicar a metodologia ancorada de custódia); `scripts/sync_gex_to_irai.py` grava níveis no SQLite e no RTDB, com `frontend/src/gexLevels.js` como fallback estático — o site público lê o RTDB, sem redeploy. Se as 7 correções foram de fato aplicadas no banco de produção: a confirmar.
  6. **Wave 5 — Manutenção diária:** `scripts/daily_maintenance.py` (itens A16, A17 e M2) faz backup consistente do SQLite (7 cópias em `D:\irai_backups` ou `data\backups`), retenção de logs com mais de 14 dias e retenção de 60 dias no RTDB; tarefa agendada “IRAI Daily Maintenance” (seg–sex 19:15), documentada em `docs/DEPLOYMENT.md`.

  Também presentes no mesmo commit, com atribuição de wave a confirmar: motor de cesta cambial (`backend/irai/forex_basket.py`, `frontend/src/utils/forex.js`, testes e UI/gauges associados); `scripts/health_watchdog.py` (item A15: restart via NSSM, limite de 4 reinícios/hora e restart do Firebase Sync parado); alterações pontuais em `backend/db.py`, `scripts/calibrate_universal.py` e `scripts/firebase_sync.py`.

---

## 🗓️ Milestone Planejada: v2.0 Metodologia Preditiva Calibrada

Planejada em 2026-11-10 a partir da auditoria de metodologia do rastro. Documentos: [`milestones/v2.0-metodologia/PRD.md`](./milestones/v2.0-metodologia/PRD.md), [`SPEC.md`](./milestones/v2.0-metodologia/SPEC.md) e [`PHASES.md`](./milestones/v2.0-metodologia/PHASES.md). Requisitos com IDs `REQ-*` no PRD.

**Decisões de 10/11/2026 (PRD §12.1):** D1 horizonte de produto = 60 min para WIN e WDO (fechamento só avaliação) · D2 só WIN$N e WDO$N · D3 no-go → sem rótulos direcionais, P atual como "Leitura do dia (nowcast)" · D4 `p_fwd_60` e card de assertividade também no site público (Firebase); deploy só com aprovação explícita. **Em aberto:** Q5 (GEX do WDO publicado antes de 09:00 e flag de backfill).

| Fase | Título | Status | Requisitos |
|------|--------|--------|------------|
| 15 | Harness de Avaliação e Baseline Congelada | Em revisão | REQ-V01–V07, REQ-A02, REQ-O03, REQ-N02 |
| 16 | Versionamento Imutável de Parâmetros e Anti-Repaint | Implementada, aguardando aprovação de commit e migração | REQ-P01–P06, REQ-A03, REQ-N04–N06 |
| 17 | Correção β/z e Honestidade do Painel | Não iniciada | REQ-M01–M04, REQ-U04, REQ-A04 |
| 18 | Features Causais e Treino Walk-Forward com Calibração | Não iniciada | REQ-F01–F06, REQ-F08, REQ-N01 |
| 19 | Shadow Mode ao Vivo (Inferência, Snapshots, API, Firebase) | Não iniciada | REQ-F07, REQ-F09, REQ-A01, REQ-A05, REQ-S01, REQ-O01–O02, REQ-N03–N04, REQ-N07 |
| 20 | GEX e Fluxo como Features Testáveis | Não iniciada | REQ-G01–G04 |
| 21 | UI de Probabilidade com Incerteza e Limiares Calibrados | Não iniciada | REQ-U01–U03, REQ-U05–U07, REQ-S02–S06 |
| 22 | Avaliação Go/No-Go e Corte | Não iniciada | Critérios do PRD §8 (por ativo, 60 min) |

### Phase 15: Harness de Avaliação e Baseline Congelada
* **Goal:** Medir a assertividade de forma reprodutível e contínua a partir de `irai_live_snapshots`, antes de mudar qualquer modelo.
* **Status:** Em revisão (implementada em 2026-11-10 e commitada na branch local `v2/fase-15-harness`, sem push; critério 3 em andamento — tarefa "IRAI Daily Assertividade" seg–sex 18:45; ver `phases/15-harness-de-avaliacao-e-baseline/15-SUMMARY-01.md`) · **Depende de:** 12, 14
* **Success Criteria:** reproduz a baseline da auditoria (WIN AUC 60 min 0,474; WDO 0,486; WIN nowcast 0,711) com tolerância de ±0,005; relatório diário automático por 5 pregões; nenhuma escrita fora de `forecast_eval_daily`.

### Phase 16: Versionamento Imutável de Parâmetros e Anti-Repaint
* **Goal:** Nunca apagar calibrações (`model_versions`, `version_id`) e recalcular datas passadas com a versão vigente na data.
* **Status:** Implementada, aguardando aprovação de commit e migração (2026-11-10, branch local `v2/fase-16-versionamento`, sem commit/push; migração não aplicada ao `irai_live.db`; ver `phases/16-versionamento-imutavel-de-parametros/16-SUMMARY-01.md`) · **Depende de:** 15
* **Success Criteria:** calibrar duas vezes não remove linhas; recálculo vs. snapshot com |ΔP| ≤ 0,1 pp em ≥ 99% das barras e 0% de troca de lado [META]; comportamento ao vivo inalterado.

### Phase 17: Correção β/z e Honestidade do Painel
* **Goal:** Corrigir o score (pesos no espaço z), recalibrar α/intercepto sem clamp visual, remover "acc" in-sample e rotular o P atual como nowcast.
* **Status:** Não iniciada · **Depende de:** 16
* **Success Criteria:** o score corrigido reproduz a acurácia do regressor (WDO 73,0% em vez de 64,7%); nenhuma métrica in-sample na UI; overview lista todos os alvos.

### Phase 18: Features Causais e Treino Walk-Forward com Calibração
* **Goal:** Modelo P(↑ 60 min) para WIN/WDO (fechamento só como horizonte secundário de avaliação): logística L2, purged CV com embargo, walk-forward mensal, Platt/isotônica, faixa bootstrap.
* **Status:** Não iniciada · **Depende de:** 15, 16
* **Success Criteria:** testes de causalidade e de split verdes; em 60 min, BSS ≥ 0 por ativo e ECE ≤ 3 pp no walk-forward [META]; versão registrada com config, artefato e métricas.

### Phase 19: Shadow Mode ao Vivo (Inferência, Snapshots, API, Firebase)
* **Goal:** Inferência (só WIN$N e WDO$N) a cada ciclo do collector gravando `p_fwd_60` (e `p_fwd_close` só para avaliação) nos snapshots, sem exibir.
* **Status:** Não iniciada · **Depende de:** 18
* **Success Criteria:** `p_fwd_60` em ≥ 98% das barras por 10 pregões [META]; p95 ≤ 1 s por alvo [META]; site público compatível e sem `p_fwd_close*` no RTDB.

### Phase 20: GEX e Fluxo como Features Testáveis
* **Goal:** Testar GEX (projeto WDO, regra as-of) e delta acumulado pelo mesmo protocolo; aceitar só com ΔBSS > 0 e IC.
* **Status:** Não iniciada · **Depende de:** 18, 19
* **Success Criteria:** decisão por feature com ΔBSS e IC em ≥ 40 pregões elegíveis [META]; nenhuma sessão sem garantia as-of no treino.

### Phase 21: UI de Probabilidade com Incerteza e Limiares Calibrados
* **Goal:** Gauge com P(↑ 60 min), faixa de incerteza, limiares calibrados e card de assertividade, atrás de feature flag, no painel local e no site público (nó `eval/<target>`, regra do RTDB, modo `nowcast_only`).
* **Status:** Não iniciada · **Depende de:** 15, 19
* **Success Criteria:** flag desligada = UI atual (mais as mudanças da fase 17); `nowcast_only` sem nenhum rótulo direcional; site público com `p_fwd_60` (selo "em avaliação") e card; regras 1–4 do `.agents/AGENTS.md` verificadas no UAT; deploy do Firebase só após aprovação explícita do usuário.

### Phase 22: Avaliação Go/No-Go e Corte
* **Goal:** Após ≥ 40 pregões em shadow, aplicar os critérios do PRD §8 por ativo, em 60 min, e promover (ou não) o novo modelo a sinal principal; ativo reprovado vai para `nowcast_only` (D3).
* **Status:** Não iniciada · **Depende de:** 15, 19, 21 (e 20, se aplicável)
* **Success Criteria:** decisão registrada por ativo com os números dos 6 critérios; flags aplicadas no local e no site público (deploy aprovado pelo usuário); reversão testada sem perda de dados.

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
*Last updated: 2026-11-10*
