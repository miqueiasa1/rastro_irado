---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Metodologia Preditiva Calibrada
status: executing
last_updated: "2026-11-16T13:00:00.000Z"
last_activity: 2026-11-16
progress:
  total_phases: 9
  completed_phases: 5
  note: "v2.0 = fases 15–22 + 20b; v1.0 (fases 1–14) concluída e mantida como registro histórico"
---

# STATE — IRAI (rastro_irado)

## Posição atual (16/11/2026)

- **Milestone ativa:** v2.0 Metodologia Preditiva Calibrada — documentos em `.planning/milestones/v2.0-metodologia/` (`PRD.md`, `SPEC.md`, `PHASES.md`).
- **Branch de produção:** a pasta `rastro_irado` roda a branch que estiver em checkout (local, sem push). Branches v2 locais: `v2/fase-15-harness`, `v2/fase-16-versionamento`, `v2/fase-17-18` (fases 15–18, hardening de 13/11 e merge da fase 20), `v2/fase-20-gex-pa` (worktree `rastro_irado_wt_f17_18`), `v2/fase-19-21a` (19A/21A, em checkout na produção desde 16/11).
- **Serviços (NSSM):** IRAI_API (FastAPI :8888), IRAI_Collector, IRAI_FirebaseSync, IRAI_Frontend (Vite :5175). Banco `data/irai_live.db` (SQLite WAL).
- **Regras do owner:** nunca dar push, publicar no Firebase ou apagar dados/backups sem aprovação explícita; commits só locais; backup em `data/backups/<nome>_<data>` antes de mexer no banco ou em arquivos importantes.

## Status das fases v2.0

| Fase | Título | Status |
|---|---|---|
| 15 | Harness de avaliação e baseline congelada | Em revisão — critério 3 (5 pregões seguidos de relatório automático) fecha com o relatório de 16/11 18:45 |
| 16 | Versionamento imutável e anti-repaint | Em produção desde 10/11/2026 |
| 17 | Correção β/z e honestidade do painel | Em produção desde 10/11 (versões corrigidas vigentes desde 11/11) |
| 18 | Features causais + walk-forward | Concluída com resultado **negativo** (p_fwd_60 rejeitado) |
| 19 | Shadow mode ao vivo | Replanejada: sem modelo forecast aprovado. **19A feita em 16/11** (`/api/eval/assertividade`, guarda REQ-A05, sync sem `p_fwd_close*`); inferência shadow suspensa |
| 20 | Regiões de GEX + gatilho de price action | Pesquisa W1–W4 concluída em 10/11: WIN INCONCLUSIVO, WDO NO-GO; nada ligado ao vivo |
| 20b | Fluxo (delta acumulado) como contexto | Teste único pré-registrado (WIN, F_T3_C1, config `8dac9d8f8ab1`) rodado em 16/11: **INCONCLUSIVO** (+83,6 pts/op., n 53, IC −45,8 a +236,3). **Encerrada** pelo owner em 16/11 10:03, junto com a linha GEX + PA + fluxo; sem acompanhamento |
| 21 | UI com incerteza e card de assertividade | Replanejada. **21A feita em 16/11** (ReliabilityCard, sem compra/venda no gráfico de P, marcadores exp. desligados) e **publicada no site** rastromacro.web.app em 16/11 09:45 (regra `eval/$target` + nó `eval/<target>` no RTDB), com aprovação do owner |
| 22 | Go/No-Go e corte | **Aberta** (owner recusou fechar em 16/11). Sem candidato em shadow; `nowcast_only` (D3) segue vigente enquanto isso |

## Contexto acumulado

### Fase 15 — harness (10/11/2026)
- `scripts/eval_assertividade.py` + pacote `backend/eval/`; baseline congelada em `data/eval/baseline/assertividade_baseline_20261110.json` (WIN 60 min AUC 0,474; WDO 0,486; nowcast 0,710 / 0,754).
- Tarefa "IRAI Daily Assertividade" seg–sex 18:45 (`scripts/run_eval_assertividade.bat`): janela dos últimos 20 pregões + período desde 03/08; relatórios em `data/reports/assertividade_<data>[_ultimos20].md`, JSON em `data/eval/latest/`, métricas em `data/eval/forecast_eval.db` (`forecast_eval_daily`), log em `logs/eval_assertividade.log`.
- Relatórios automáticos: 10/11, 11/11, 12/11 e 13/11 (4 pregões seguidos, rc 0). O 5º é 16/11 18:45.
- Revisão em 16/11 (versões corrigidas da fase 17, só 3 pregões: 11–13/11): nowcast AUC 0,916 (WIN) / 0,851 (WDO), BSS 0,246 / 0,236, acerto 78,3% / 73,4%, ECE 22,3 / 17,1 pp; baseline congelada 0,710 / 0,754 (BSS 0,076 / 0,167, ECE 11,9). Discriminação acima da baseline e coerente com a estimativa offline da fase 17 (0,828 / 0,869), mas IC largo (BSS do WIN −3,1 a 0,44) e calibração pior. 60 min segue sem habilidade (AUC 0,32 / 0,52, BSS −0,27 / −0,24). Veredito: harness aprovado (falta o 5º relatório); nowcast corrigido mantido; reavaliar com 20 pregões (~09/12); `nowcast_only` continua.

### Fase 16 — versionamento (em produção desde 10/11/2026)
- `model_versions` + `model_version_events` (`backend/irai/model_registry.py`), calibração sem `DELETE`, engine resolvendo a versão vigente na data, `model_version` nos snapshots e no Kalman, `GET /api/model/versions`, Regra 5 no `.agents/AGENTS.md`.
- Migração aplicada ao `irai_live.db` em 10/11 13:46 BRT (backup `data/backups/irai_live_pre_fase16_20261110.db`). Repaint residual não ligado a parâmetros (mediana 0,5 pp WIN / 0,35 pp WDO) segue em aberto.

### Fase 17 — correção β/z e painel honesto (em produção)
- Score corrigido (β·σ·z ÷ score_scale), α/b sem clamp, R/Q do Kalman medidos.
- Promovidas com vigência a partir de 11/11/2026: `win-nowcast-20261110T192649Z` (α 1,354, b +0,148) e `wdo-nowcast-20261110T192649Z` (α 1,243, b −0,390); backup `data/backups/irai_live_pre_fase17_20261110.db`.
- `forecast_ui='nowcast_only'` em WIN$N e WDO$N desde 10/11 16:23 BRT (sem acc, sem COMPRA/VENDA no z, P como "Leitura do dia").

### Fase 18 — resultado negativo (10/11/2026)
- Valor justo da cesta (γ walk-forward, z causal): nenhum descolamento previu 15/30/60 min de forma útil (AUC 0,49–0,52), sem P&L líquido que sobreviva a BH.
- p_fwd_60 walk-forward (361 pregões fora da amostra): AUC 0,48–0,50, BSS ≤ 0 → **rejeitado**, não exibido.

### Fase 20 — GEX + price action (pesquisa, 10/11/2026)
- Config pré-registrada `c985f6b2365e`; WIN INCONCLUSIVO (C·T3+C1 +29,4 pts/op., n 147, IC −49,2 a +113,7), WDO NO-GO. Nenhum braço passou nos critérios de GO.
- Histórico de GEX: CSV oficial do projeto WDO (`mt5/Files/jumba_gex_*_history.csv`); fallback = primeiro run < 09:00 em `gex_levels` (regra adotada para a pesquisa; ver Q5).
- Commit `c5333c1` (branch `v2/fase-20-gex-pa`), mergeado em `v2/fase-17-18` (`5cca370`) em 16/11.

### Hardening de 13/11/2026 (commit `144d3e9`)
- `scripts/health_watchdog.py`: o collector se reinicia via `os._exit(3)` (NSSM religa); demais serviços com stop/start síncrono; idade da barra lida do SQLite read-only; carência (ciclo 1, 10 min de processo/boot, 3 falhas seguidas da API, timeout 15 s); só age seg–sex 09:10–18:25 BRT fora de feriados.
- `backend/api/main.py`: endpoints pesados como `def` (threadpool), cache em `/api/health`; `/api/health/sources` e `/api/irai/dates` via índice PK (~2,5 s / 1,4 s → ~10 ms).
- `scripts/firebase_sync.py`: falha de série pula só série/summary/history, mantendo GARCH e GEX (93 chaves por ciclo).
- `data/b3_holidays.txt`: feriados B3 2026 (oficial) e 2027 (provisório — revisar quando a B3 publicar o calendário, normalmente em janeiro).

## Decisões do owner (10/11/2026, PRD §12.1)
- D1: horizonte de produto = 60 min (fechamento só avaliação). D2: só WIN$N e WDO$N no v2.0. D3: se o go/no-go falhar, sem rótulos direcionais e P como "Leitura do dia (nowcast)". D4: `p_fwd_60` e card de assertividade também no site público — todo deploy do Firebase exige aprovação explícita.
- Princípio orientador: rastro = contexto, GEX = região, price action = gatilho.

## Decisões do owner em 16/11/2026
- `/api/gex` sem `run`: em pregões passados usa o último run antes de 09:00 (as-of); hoje segue o mais recente (commit `148e2ab`).
- Deploy do Firebase aprovado e feito: regras do RTDB com `eval/$target` e hosting a partir de `v2/fase-19-21a`; backup em `data/backups/firebase_deploy_20261116/`.
- 20b: um único teste pré-registrado, só WIN, só pesquisa → INCONCLUSIVO (ver `phases/20b-fluxo-como-contexto/20b-SUMMARY-01.md`).
- 10:03: linha de pesquisa GEX + price action + fluxo **encerrada**; 20b fechada como INCONCLUSIVA e não será acompanhada. O GEX segue só como linha no gráfico.
- Fase 22 permanece aberta.

## Em aberto
- Q5 (GEX publicado antes de 09:00 e marca de backfill): resolvida para a pesquisa (CSV oficial + fallback primeiro run < 09:00); para uso ao vivo continua pendente do projeto WDO.
- Resíduos conhecidos: Quarta de Cinzas (pregão só à tarde) pode gerar restart desnecessário do collector de manhã; queda do collector de madrugada só é religada às 09:10; FirebaseSync usa data UTC à noite; DXY no fallback teórico (razão fixa 3,55); `frontend/src/gexLevels.js` é regenerado todo dia e fica fora dos commits.

## Próximo passo
- Fechar o critério 3 da fase 15 com o relatório de 16/11 18:45 e reavaliar o nowcast corrigido com mais pregões.
- Fase 22 aberta até existir candidato ou nova decisão do owner (a linha GEX + PA + fluxo foi encerrada e não gera candidato).
