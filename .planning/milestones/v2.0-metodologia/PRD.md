# PRD — IRAI v2.0: Metodologia Preditiva Calibrada do Rastro

**Versão:** 1.1 (decisões Q1–Q4 registradas em 10/11/2026; Q5 em aberto)
**Status:** Planejado — nenhuma fase iniciada
**Milestone:** v2.0 Metodologia Preditiva Calibrada (fases 15–22)
**Owner:** danh banh
**Data:** 2026-11-10
**Documentos irmãos:** [`SPEC.md`](./SPEC.md) (especificação técnica) · [`PHASES.md`](./PHASES.md) (quebra em fases GSD)
**Base de evidência:** auditoria de 10/11/2026 (Page "Rastro Irado — Auditoria da metodologia e proposta"), feita sobre uma cópia somente leitura de `data/irai_live.db`.

> Convenção deste documento: **números medidos** vêm da auditoria e citam o período/amostra. Tudo marcado **[META]** é alvo a atingir, não resultado.

---

## 1. Visão

O rastro (P(↑)) deve passar a responder a uma pergunta **preditiva e verificável**: *"qual a probabilidade de o WIN/WDO estar mais alto daqui a 60 minutos, dado o que se sabe até agora?"* (horizonte de produto: **60 min**, decisão D1; o fechamento do pregão é só horizonte secundário de avaliação), exibindo uma probabilidade **calibrada** (quando o painel diz 60%, sobe cerca de 60% das vezes), com **faixa de incerteza**, **sem repainting** e com **assertividade medida continuamente** fora da amostra.

A leitura atual ("o resto do mundo está coerente com o movimento do ativo até agora?") continua útil como **leitura do dia (nowcast)**, mas deixa de ser apresentada como probabilidade direcional.

---

## 2. Problema (medido)

Amostra: snapshots imutáveis ao vivo (`irai_live_snapshots`, `is_ghost=0`, gravados até 10 min após a barra), pregão B3 09:00–18:25 (horário de Brasília), **03/08/2026 a 10/11/2026 10:45**, **65 pregões**: WIN 6.637 barras, WDO 6.633 barras. IC 95% por bootstrap de pregões.

### 2.1 O P(↑) não antecipa a direção

| Horizonte | WIN AUC (IC 95%) | WDO AUC (IC 95%) |
|---|---|---|
| 5 min | 0,494 (0,477–0,503) | 0,493 (0,477–0,508) |
| 15 min | 0,479 (0,453–0,498) | 0,497 (0,472–0,520) |
| 30 min | 0,482 (0,452–0,505) | 0,497 (0,465–0,526) |
| 60 min | 0,474 (0,431–0,503) | 0,486 (0,441–0,529) |
| Fechamento | 0,525 (0,433–0,599) | 0,488 (0,398–0,578) |
| **Nowcast** (retorno já realizado no dia) | **0,711** | **0,754** |

- Mesmo padrão nos 14 alvos do painel: nowcast 0,71–0,96; AUC 30/60 min entre 0,474 e 0,516.
- O PRD v3.0 (`.planning/docs/PRD.md`) definia o objetivo como "probabilidade de fechar o dia em alta"; contra o fechamento o P(↑) mediu 0,525 (WIN) e 0,488 (WDO).

### 2.2 As probabilidades exibidas são superconfiantes

- **Brier skill score** (vs. taxa-base): WIN −0,315 a −0,402; WDO −0,265 a −0,286 (5 min a fechamento). Todos os 14 alvos com BSS negativo em 60 min (−0,05 a −0,40).
- Faixa P(↑) > 80 (WIN, P médio 91,3%): subiu em 30 min em **49,9%** das vezes; até o fechamento, 54,1%.
- **38,5%** das barras do WIN ficam com P < 20 ou P > 80; o painel passa a maior parte do pregão em COMPRA/VENDA.
- α do WIN e do WDO = **1,00** (piso do guard rail [1; 3,5] em `scripts/calibrate_universal.py`); intercepto do WDO = −0,25 (limite). A nota `.planning/notes/kalman-vs-logistic-calibration.md` declara α como "sensibilidade visual desejada".

### 2.3 Falhas de construção

- **Alvo contemporâneo:** a calibração regride o retorno do pregão inteiro do alvo contra o dos fatores no mesmo pregão (explicação, não previsão).
- **Bug de unidade β/z:** β estimado em retorno bruto e aplicado a z = ret/σ. No WDO a acurácia in-sample do próprio modelo cai de **73,0% → 64,7%** (AUC 0,798 → 0,742) e AUDNZD vira o maior peso (−1,00 normalizado) enquanto WIN cai para −0,15.
- **Viés de seleção:** força bruta sem validação. Demo com 38.760 cestas de 6 fatores: melhor cesta 73,0% no treino → 66–68% no teste; cesta mediana 65% no teste. A "acc" exibida (71,4% WIN) é in-sample e contemporânea, e alimenta a convicção (`frontend/src/utils/signalAnalyzer.js`).
- **Normalização temporal:** retorno parcial ÷ σ do pregão inteiro (`Z_TIME_SCALING = False`); |P−50| médio do WIN vai de 19,9 (09h) a 27,4 (15h).
- **Repainting por recalibração destrutiva:** `save_to_db` apaga os parâmetros antigos. Recalcular pregões anteriores a 28/10 com os pesos atuais muda P em mediana **18,1 pp (WIN) / 16,9 pp (WDO)** e troca o lado em **34,3% / 38,9%** das barras. Com os mesmos parâmetros (após 28/10), o desvio mediano é 0,5 / 0,4 pp e 1,7% / 1,6% de troca de lado.
- **Marcadores visuais sem edge:** sinal unificado P+NWE com média −3,2 bp (WIN) e −2,9 bp (WDO) em 60 min; pontos de |Z rastro| ≥ 2 com média +1,0 bp (WIN, IC −3,8 a +6,6) e +2,0 bp (WDO, IC −0,8 a +5,3), não significativos. NWE com atraso médio de 6,1 barras (cerca de 30 min).
- **GEX** não entra no cálculo (só linhas no gráfico).

### 2.4 Evidência de que existe algo a ganhar (protótipo)

Logística L2 com features causais, walk-forward mensal (treino em barras M5 desde 06/2025, teste ago–nov/2026 nas mesmas barras ao vivo), configuração fixada antes de rodar:

| Alvo / horizonte | Atual AUC / BSS | Protótipo AUC (IC 95%) / BSS |
|---|---|---|
| WIN 60 min | 0,473 / −0,403 | 0,540 (0,502–0,574) / +0,004 |
| WIN fechamento | 0,525 / −0,316 | 0,550 (0,481–0,631) / −0,009 |
| WDO 60 min | 0,486 / −0,285 | 0,503 (0,470–0,532) / −0,010 |
| WDO fechamento | 0,488 / −0,286 | 0,587 (0,507–0,666) / +0,002 |

Ganho principal: **calibração** (BSS de cerca de −0,3 para cerca de 0). Ganho de ordenação: pequeno e com IC próximo de 0,50. 30 min não mostrou sinal (WIN 0,501; WDO 0,514).

---

## 3. Objetivos e Não-objetivos

### 3.1 Objetivos

1. **O1 — Medir sempre:** assertividade fora da amostra calculada todo pregão a partir de snapshots imutáveis, visível no painel e em relatório.
2. **O2 — Honestidade:** nenhuma métrica in-sample exibida como acurácia; probabilidades exibidas calibradas.
3. **O3 — Previsão:** novo modelo de P(↑ em 60 min) para WIN$N e WDO$N (horizonte de produto, D1), treinado em walk-forward, rodando em shadow mode ao lado do atual. P(↑ até o fechamento) é treinado e avaliado só como horizonte secundário, sem exibição.
4. **O4 — Zero repaint:** parâmetros versionados e imutáveis; qualquer recálculo de data passada usa a versão vigente naquela data.
5. **O5 — Testabilidade de novas fontes:** GEX (projeto WDO) e fluxo (delta acumulado) entram como features candidatas, aceitas só se melhorarem o Brier fora da amostra.
6. **O6 — Corte controlado:** troca do sinal principal só por critério objetivo (seção 8) após período em shadow.
7. **O7 — Transparência pública:** `p_fwd_60` (com faixa) e o card de assertividade publicados também no site público (Firebase), decisão D4.

### 3.2 Não-objetivos

- **Execução automática de ordens** ou envio de sinais para EAs/MT5. O IRAI permanece **suporte à decisão**.
- Integração com `supervisor_regime` / Regime Supervisor (item 1 do backlog do ROADMAP) — fora do v2.0; no máximo expor leitura versionada para uso futuro.
- Alertas push/Telegram (item 2 do backlog).
- Reescrever NWE, GARCH, cesta cambial ou o pair Z existentes (continuam como estão; só deixam de compor o "sinal" se não tiverem edge medido).
- Prometer acurácia alta: o problema é de baixa relação sinal/ruído; o objetivo é probabilidade honesta com edge pequeno e medido.
- **Outros alvos além de WIN$N e WDO$N** (os demais 12 alvos do painel: globais, forex etc.) ficam fora do v2.0 (decisão D2). Continuam com o P atual e entram no harness só como leitura; a expansão do novo modelo para eles é trabalho futuro, em milestone posterior.
- **Exibir P(↑ fechamento) na UI** (painel local ou site público): o fechamento é só horizonte de avaliação (decisão D1).
- **Deploy do Firebase feito por agente:** publicar regras do RTDB, hosting ou ligar novos nós de sync exige aprovação explícita do usuário a cada deploy (REQ-S06).

---

## 4. Usuários e casos de uso

**Persona primária:** operador/pesquisador (dono do projeto), opera WIN/WDO discricionariamente com suporte do painel local (`http://localhost:5175`) e do site público (Firebase).

**Persona secundária:** leitores do site público (somente leitura).

| ID | Caso de uso |
|---|---|
| UC-01 | Durante o pregão, ver P(↑ 60 min) do WIN/WDO com faixa de incerteza e um rótulo claro (compra/venda/neutro) derivado de limiares calibrados. |
| UC-02 | Ver, no painel local e no site público, a assertividade recente (últimos 20 pregões): AUC, Brier skill e curva de confiabilidade (60 min e nowcast). |
| UC-03 | Rever um pregão passado e ver exatamente o que foi mostrado ao vivo (sem repaint) e qual versão de modelo estava vigente. |
| UC-04 | Recalibrar um modelo sem perder o histórico: a nova versão entra em shadow; a antiga continua consultável. |
| UC-05 | Avaliar uma nova feature (ex.: distância à wall de GEX) com o harness e decidir aceitar/rejeitar por critério objetivo. |
| UC-06 | Continuar vendo o P atual rotulado como "Leitura do dia (nowcast)", para contexto. |
| UC-07 | Leitor do site público vê o mesmo P(↑ 60 min), a faixa e o card de assertividade que o painel local, sem acesso de escrita. |

---

## 5. Requisitos funcionais

Prioridade: **P0** obrigatório para o corte; **P1** desejável no v2.0; **P2** opcional.

### 5.1 Avaliação e relatório (REQ-V)

- **REQ-V01 (P0):** Harness reprodutível que lê apenas snapshots imutáveis (abrindo o banco em `mode=ro` ou uma cópia via backup API) e calcula, por alvo × horizonte {5, 15, 30, 60 min, fechamento} e para o nowcast: n, AUC, IC 95% por bootstrap de pregões, hit rate, Brier, Brier skill score, ECE e tabela de confiabilidade.
- **REQ-V02 (P0):** Definição de "barra ao vivo" explícita e configurável (padrão: `created_at` ≤ 10 min após a barra, `is_ghost=0`, dentro da sessão B3).
- **REQ-V03 (P0):** Persistência diária das métricas em tabela própria e relatório Markdown em `data/reports/`.
- **REQ-V04 (P0):** Linha de base congelada: métricas do P(↑) atual para o período 03/08–10/11/2026 reproduzidas pelo harness com tolerância de ±0,005 de AUC frente à auditoria.
- **REQ-V05 (P1):** Segmentação por hora do pregão, mês e regime de volatilidade realizada (tercis).
- **REQ-V06 (P0):** Baselines obrigatórias em todo relatório: taxa-base, momentum (retorno do dia) e contrarian (−retorno do dia).
- **REQ-V07 (P1):** Avaliação dos marcadores visuais (sinal unificado, estrelas, bandas NWE) com média em bp, hit rate e IC.

### 5.2 Versionamento de parâmetros e anti-repaint (REQ-P)

- **REQ-P01 (P0):** Nenhuma calibração apaga parâmetros antigos; cada calibração cria uma **versão imutável** com vigência, janela de treino, configuração, métricas e hash do código.
- **REQ-P02 (P0):** O engine resolve os parâmetros pela versão **vigente na data da sessão** (não pela mais recente).
- **REQ-P03 (P0):** Cada snapshot grava `model_version` (P atual) e `forecast_version` (novo modelo).
- **REQ-P04 (P0):** Recalcular um pregão passado com a versão vigente reproduz os snapshots fechados (limite em REQ-N05).
- **REQ-P05 (P1):** Estado do Kalman associado à versão; troca de versão inicializa o estado de forma explícita e registrada.
- **REQ-P06 (P0):** Promoção de versão (shadow → active → retired) é operação explícita e auditável; nunca automática silenciosa.

### 5.3 Correções do modelo atual (REQ-M0x)

- **REQ-M01 (P0):** Corrigir o bug de unidade β/z: o score passa a usar pesos no espaço z (βᵢ·σᵢ, ou reestimação direta em z); α e intercepto reestimados sem clamp visual.
- **REQ-M02 (P0):** Remover a "acc" in-sample da UI e da fórmula de convicção; substituir por métricas OOS do harness.
- **REQ-M03 (P1):** Rótulo do P atual passa a ser "Leitura do dia (nowcast)" na UI local e no site público.
- **REQ-M04 (P2):** Kalman: observação e ruído reespecificados (obs_cov estimado a partir do resíduo) ou desligado por ativo se não vencer o v1 no harness.

### 5.4 Novo modelo preditivo (REQ-F)

- **REQ-F01 (P0):** Alvo primário (D1): sinal do log-retorno de t (fechamento da barra M5) a t+12 barras (60 min). Alvo secundário, só de avaliação: até o último fechamento do pregão (SPEC §3).
- **REQ-F02 (P0):** Features estritamente causais com normalização por σ trailing (sessões anteriores) e escala temporal √t; teste de invariância por truncamento obrigatório.
- **REQ-F03 (P0):** Modelo base: regressão logística L2 sobre features padronizadas; hiperparâmetro escolhido por walk-forward interno.
- **REQ-F04 (P0):** Validação walk-forward mensal com purge e embargo de ≥ 1 pregão; nenhuma informação do mês de teste no treino.
- **REQ-F05 (P0):** Calibração de probabilidade (Platt ou isotônica) ajustada só em dados de treino; ECE reportado.
- **REQ-F06 (P0):** Faixa de incerteza por barra (percentis 10–90 de um ensemble bootstrap por pregão).
- **REQ-F07 (P0):** Inferência ao vivo a cada ciclo do collector, gravando `p_fwd_60` e faixa no snapshot (shadow mode, sem UI). `p_fwd_close` e faixa também são gravados, só para avaliação (P1), e nunca são exibidos.
- **REQ-F08 (P1):** Alternativas avaliadas no mesmo harness (gradient boosting raso, ordinal 3 classes com zona morta); adotadas só com ΔBSS > 0 e IC.
- **REQ-F09 (P1):** Retreino agendado (mensal) gerando nova versão em shadow; promoção conforme REQ-P06.

### 5.5 GEX e fluxo como features (REQ-G)

- **REQ-G01 (P1):** Features de GEX "as-of": níveis publicados antes da abertura do pregão (distância à wall mais próxima em unidades de σ, lado, tipo de wall).
- **REQ-G02 (P1):** Teste de causalidade do histórico de GEX (o nível usado em D foi publicado antes de D 09:00?); dias sem garantia ficam fora do treino.
- **REQ-G03 (P1):** Feature de fluxo (`cum_delta_norm`) avaliada da mesma forma.
- **REQ-G04 (P0 se G01 for adotado):** Aceite de feature só com melhora de Brier OOS e IC de ΔBSS acima de 0 em ≥ 40 pregões.

### 5.6 API (REQ-A)

- **REQ-A01 (P0):** `/api/irai/series` inclui os novos campos por barra, mantendo compatibilidade (campos ausentes = `null`).
- **REQ-A02 (P0):** Novo `GET /api/eval/assertividade` com as métricas OOS recentes por alvo/horizonte.
- **REQ-A03 (P1):** Novo `GET /api/model/versions` (histórico de versões e vigência).
- **REQ-A04 (P0):** `/api/irai/targets` e overview deixam de depender de `accuracy` para listar alvos (flag `calibrated`).
- **REQ-A05 (P0):** `forecast_mode`/`forecast_ui` só podem sair de `off` para `WIN$N` e `WDO$N` no v2.0 (D2); a API recusa ou ignora para os demais alvos.

### 5.7 Frontend (REQ-U)

- **REQ-U01 (P0):** Gauge mostra P(↑ 60 min) com faixa de incerteza, atrás de feature flag, para WIN e WDO. Sem mostrador de fechamento (D1).
- **REQ-U02 (P0):** Rótulos compra/venda/neutro vêm de limiares calibrados por ativo para 60 min, publicados com a versão (não 60/40 fixo).
- **REQ-U03 (P0):** Card de assertividade (últimos 20 pregões) com AUC (IC), BSS e confiabilidade de 60 min e do nowcast, no painel local e no site público; estado "degradado" quando BSS rolante < −0,02 **[META de alarme]**.
- **REQ-U04 (P0):** Remover "acc NN%" in-sample do Overview e a convicção baseada nele.
- **REQ-U05 (P1):** Marcadores sem edge medido ficam desligados por padrão (toggle "experimental").
- **REQ-U06 (P0):** Respeitar as regras do `.agents/AGENTS.md` (pair spread sempre visível, sincronização, anti-reset de zoom, zero-repainting).
- **REQ-U07 (P0) — Modo sem previsão (D3):** se um ativo não passar no go/no-go (seção 8), a UI daquele ativo (local e pública) remove os rótulos direcionais (COMPRA/VENDA, veredito 65/55/45/35, setas) e mostra o P atual só como "Leitura do dia (nowcast)", sem limiares de entrada. Controlado por flag por alvo e coberto por teste.

### 5.8 Site público / Firebase (REQ-S) — decisão D4

- **REQ-S01 (P0):** `scripts/firebase_sync.py` publica nas séries de WIN/WDO `p_fwd_60`, `p_fwd_60_lo`, `p_fwd_60_hi`, `forecast_version`, `model_version` e `feature_stale`. `p_fwd_close*` **não** vai para o RTDB (só avaliação).
- **REQ-S02 (P0):** Novo nó `eval/<target>` no RTDB com o resumo do card (janela de 20 pregões, 60 min e nowcast: n, AUC e IC, BSS, ECE, tabela de confiabilidade, estado degradado, data de geração), atualizado após o relatório diário.
- **REQ-S03 (P0):** `frontend/database.rules.json` ganha `"eval": { "$target": { ".read": true } }`. A raiz continua `.read/.write: false`, e nenhuma escrita pública é aberta (escrita só pelo Admin SDK do sync).
- **REQ-S04 (P0):** `targets` no RTDB ganha `calibrated`, `forecast_mode`, `forecast_ui` e `thresholds` (60 min); `accuracy` fica até a fase 22 para o site antigo não quebrar.
- **REQ-S05 (P0):** O site público exibe o mesmo que o painel local, com a mesma flag `forecast_ui`. Enquanto o ativo não passar no corte, `p_fwd_60` aparece com o selo "em avaliação" e sem rótulos COMPRA/VENDA; o card de assertividade fica sempre visível.
- **REQ-S06 (P0):** Deploy de regras do RTDB e do hosting, e a primeira ativação de nós novos no sync, só com **aprovação explícita do usuário** a cada deploy. As fases entregam o artefato e o checklist; o deploy é um passo separado e aprovado.

### 5.9 Observabilidade e operação (REQ-O)

- **REQ-O01 (P0):** `/api/health` expõe versão ativa/shadow, timestamp da última inferência, latência e staleness das features.
- **REQ-O02 (P1):** `scripts/health_watchdog.py` alerta (log) se `p_fwd_*` faltar por > 2 barras seguidas durante o pregão.
- **REQ-O03 (P1):** Relatório diário de assertividade gerado após o fechamento (junto da manutenção diária ou tarefa própria).

---

## 6. Requisitos não funcionais (REQ-N)

- **REQ-N01 — Causalidade:** nenhuma feature, normalização, seleção ou calibração usa dado posterior ao instante de decisão. Verificado por teste automatizado (invariância por truncamento) e pelo split walk-forward.
- **REQ-N02 — Reprodutibilidade:** qualquer relatório e qualquer versão de modelo são reproduzíveis a partir de (snapshot do banco, git SHA, config, seed). Diferença de AUC ≤ 0,001 entre duas execuções **[META]**.
- **REQ-N03 — Latência:** inferência do novo modelo ≤ 1 s por alvo por ciclo do collector (ciclo atual: 20 s) **[META]**; o snapshot de cada barra continua sendo gravado antes do fechamento dela (medido hoje: mediana 4,65 min após a abertura de uma barra de 5 min) **[META: p95 ≤ 5,5 min]**.
- **REQ-N04 — Compatibilidade:** snapshots antigos (sem campos novos) continuam legíveis na API, no frontend local e no site público (Firebase).
- **REQ-N05 — Zero repaint:** para pregões com versão registrada, recálculo vs. snapshot fechado: |ΔP| ≤ 0,1 pp em ≥ 99% das barras e 0% de troca de lado **[META]** (hoje, com os mesmos parâmetros: mediana 0,5 pp, p90 2,5 pp, 1,7% de troca no WIN).
- **REQ-N06 — Imutabilidade:** nenhuma operação de calibração/treino executa `DELETE` ou `UPDATE` em parâmetros de versões existentes (exceto o campo de status/vigência).
- **REQ-N07 — Segurança/operação:** sem novas portas expostas; API continua em loopback (`127.0.0.1:8888`). No Firebase, só se escreve o que já é sincronizado, os novos campos de série (REQ-S01), os campos novos de `targets` (REQ-S04) e o nó `eval` (REQ-S02); qualquer deploy segue o REQ-S06.
- **REQ-N08 — Encoding:** arquivos novos em UTF-8 sem BOM, LF.

---

## 7. Métricas de sucesso

Todas medidas pelo harness (REQ-V01) **fora da amostra**, em barras ao vivo, por alvo, com IC 95% por bootstrap de pregões.

| Métrica | Hoje (medido) | Limiar de sucesso **[META]** |
|---|---|---|
| Brier skill score 60 min (primário) | WIN −0,403; WDO −0,285 | ≥ 0,000 por ativo |
| Brier skill score fechamento (secundário) | WIN −0,316; WDO −0,286 | só reportado; sem limiar de corte |
| ECE (erro de calibração esperado, 10 bins) | não medido no atual | ≤ 3 pp |
| AUC 60 min (primário) | WIN 0,474; WDO 0,486 | ≥ 0,53 e limite inferior do IC > 0,50, por ativo |
| AUC fechamento (secundário) | WIN 0,525; WDO 0,488 | só reportado; sem limiar de corte |
| Repaint (recálculo vs. snapshot) | até 28/10: 34–39% troca de lado | 0% troca de lado; |ΔP| ≤ 0,1 pp em 99% das barras |
| Acurácia in-sample exibida | "acc 71%" no Overview | 0 ocorrências na UI |
| Latência de inferência | — | ≤ 1 s por alvo por ciclo |
| Cobertura de snapshots ao vivo | 87,6% das barras do WIN com snapshot no período (6.637 de 7.579) | ≥ 95% das barras do pregão |
| Disponibilidade de `p_fwd_60` em shadow | — | ≥ 98% das barras do pregão |
| `eval/<target>` no site público atualizado | — | todo pregão, até 1 h após o relatório diário |

Métricas de uso (qualitativas): o operador consegue responder "o painel está acertando?" olhando o card de assertividade, sem rodar scripts.

---

## 8. Critérios de aceite do milestone (go/no-go do corte)

A decisão é tomada **por ativo** (WIN$N e WDO$N separadamente), só no horizonte de 60 min (D1). O fechamento é reportado, mas não decide. O novo modelo substitui o P atual como **sinal principal** do gauge daquele ativo somente se, após **≥ 40 pregões em shadow mode** (inferência ao vivo, sem retreino no período):

1. BSS ≥ 0 em 60 min para o ativo **[META]**;
2. AUC de 60 min com limite inferior do IC 95% > 0,50 para o ativo **[META]**;
3. ECE ≤ 3 pp **[META]**;
4. Zero repaint conforme REQ-N05;
5. Nenhum incidente de latência (REQ-N03) em mais de 2 pregões;
6. Card de assertividade e relatório diário operando há ≥ 20 pregões.

Se algum dos critérios 1–3 falhar para um ativo (**decisão D3**): o novo modelo daquele ativo continua em pesquisa; a UI local e a pública removem os rótulos direcionais e mostram o P atual só como **"Leitura do dia (nowcast)"** (REQ-U07). O card de assertividade continua publicado.

---

## 9. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Edge real pequeno (AUC 0,53–0,56) ou inexistente | Alto | Objetivo primário é calibração honesta; critério de corte objetivo; manter nowcast rotulado |
| Poucos pregões ao vivo (65 hoje) → IC largo | Alto | Treinar com barras M5 desde 06/2025 (e 2022+ se a cobertura permitir); shadow ≥ 40 pregões |
| Múltiplas comparações (alvos × horizontes × features) | Médio | Pré-registrar configuração por fase; reportar todas as tentativas; exigir IC |
| Sazonalidade de horário dominando (visto no WDO) | Médio | Ablação com/sem features de horário; segmentação por hora no relatório |
| Mudança de regime | Médio | Retreino mensal versionado; alarme de BSS rolante |
| Histórico de GEX não causal (backfill recalculado depois) | Médio | REQ-G02; usar só dias com publicação comprovada antes da abertura |
| Migrações SQLite com API e collector simultâneos | Médio | Guard `_add_column` idempotente já existente (fase 4); migração só aditiva |
| Banco grande (3,4 GB) e WAL concorrente | Baixo | Harness sempre via cópia `backup` ou `mode=ro` |
| WDO sem sinal em 60 min no protótipo (AUC 0,503, IC 0,470–0,532; BSS −0,010), enquanto o melhor resultado do WDO foi no fechamento (0,587) | Alto | Decisão por ativo (seção 8); fechamento segue medido como secundário; mudar o horizonte do WDO exige nova decisão registrada |
| Métricas fracas ou "degradado" expostas no site público (D4) | Médio | Card mostra IC e taxa-base; texto explicativo fixo; selo "em avaliação" antes do corte |
| Regra nova do RTDB (`eval`) abrir leitura além do pretendido | Médio | Regra só em `eval/$target` com `.read: true`; raiz fechada; revisão da regra no checklist de deploy (REQ-S06) |
| Payload Firebase maior | Baixo | +3 floats e 2 strings curtas por barra de WIN/WDO (`p_fwd_close*` fora); lean series já remove `factors` |
| Confusão do usuário com dois "P" na tela | Médio | Rótulos explícitos (nowcast vs. previsão) e flag de UI |

---

## 10. Dependências

- **MT5 / collector:** barras M5 de XP (B3), Tickmill e Axi via `backend/workers/collector.py`; ciclo de 20 s; relógio do broker NY+7 (`backend/timeconv.py`).
- **GEX do projeto WDO** (`../wdo win pair trading/gex/`): níveis diários sincronizados por `scripts/sync_gex_to_irai.py` para `gex_levels` (SQLite) e RTDB; precisa de horário de publicação confiável por run (`run_name`, `updated_at`).
- **Snapshots imutáveis** (fase 12) e **sessão B3/fuso** (fase 14) — base do harness.
- **Firebase** (`scripts/firebase_sync.py`, `frontend/database.rules.json`, `frontend/firebase.json`) para o site público; deploy só com aprovação explícita do usuário (REQ-S06).
- **Python:** scikit-learn (já usado pela calibração), numpy, pandas, scipy; sem dependências novas obrigatórias.
- **supervisor_regime:** não é dependência do v2.0; consumidor futuro possível (fora de escopo).

---

## 11. Rollout

1. **Fase 15 (medição):** harness + baseline congelada. Nenhuma mudança de comportamento.
2. **Fase 16 (versionamento):** migração aditiva + engine resolvendo versão vigente. Comportamento ao vivo idêntico (mesma versão ativa).
3. **Fase 17 (correção β/z + honestidade):** nova versão do P atual calibrada em shadow; UI remove "acc" e passa a rotular nowcast.
4. **Fases 18–19 (novo modelo):** treino walk-forward e inferência ao vivo em **shadow mode** (`forecast_mode=shadow`): grava em snapshot, não aparece na UI.
5. **Fase 20 (GEX/fluxo):** features testadas offline; entram numa nova versão em shadow apenas se aprovadas.
6. **Fase 21 (UI):** nova UI atrás de **feature flag**, no painel local e no site público (D4): `eval/<target>`, regra do RTDB e `p_fwd_60` com selo "em avaliação". Deploy com aprovação explícita (REQ-S06).
7. **Fase 22 (corte):** avaliação go/no-go por ativo (seção 8) após ≥ 40 pregões em shadow. Ativo aprovado: promoção explícita para `active`, local e público. Ativo reprovado: modo sem previsão (D3, REQ-U07). Plano de reversão = voltar a flag e a versão anterior (sem perda de dados).

Feature flags: `asset_models.forecast_mode` ∈ {`off`, `shadow`, `active`} por alvo (backend) e `asset_models.forecast_ui` ∈ {`off`, `on`, `nowcast_only`} exposto por `/api/irai/targets` e pelo nó `targets` do RTDB (frontend local e público). Valores diferentes de `off` só para WIN$N e WDO$N (D2).

---

## 12. Decisões registradas e questões em aberto

### 12.1 Decisões (10/11/2026, pelo owner)

| ID | Questão original | Decisão | Consequências propagadas |
|---|---|---|---|
| D1 (ex-Q1) | Horizonte principal do gauge | **60 min** para WIN e WDO. Fechamento só como horizonte secundário de avaliação, nunca exibido. | REQ-F01, F07, U01, U02; métricas §7; critérios §8 só em 60 min; risco do WDO §9 |
| D2 (ex-Q2) | Escopo de ativos | **Só WIN$N e WDO$N** no v2.0. Demais alvos: não-objetivo, futuro. | §3.2; REQ-A05 |
| D3 (ex-Q3) | Se o go/no-go falhar | **Remover rótulos direcionais** e mostrar o P atual só como **"Leitura do dia (nowcast)"**. | §8; REQ-M03, REQ-U07 |
| D4 (ex-Q4) | Site público | **Publicar `p_fwd_60` e o card de assertividade no Firebase.** O deploy continua exigindo aprovação explícita do usuário. | O7; UC-02, UC-07; REQ-S01–S06; REQ-N07; rollout §11 |

### 12.2 Questões em aberto

| ID | Questão | Padrão proposto se não houver decisão |
|---|---|---|
| Q5 | O projeto WDO consegue garantir o horário de publicação de cada run de GEX (antes de 09:00 do pregão) e marcar o histórico reconstruído por backfill? **Pendente de consulta ao projeto WDO.** | Usar só runs com `updated_at` anterior a 09:00 do pregão; sessões sem garantia ficam fora do treino (REQ-G02) |
| Q6 | Cadência de retreino: mensal ou ao detectar degradação? | Mensal, com versão em shadow |
| Q7 | Manter Kalman/Johansen no P atual se não vencerem o v1 no harness? | Desligar por ativo (`use_johansen` já existe; para o Kalman, flag nova `use_kalman`) |
