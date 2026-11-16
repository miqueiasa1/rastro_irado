# Fases 19A + 21A — Transparência fora da amostra e fechamento do modo honesto

**Executada:** 16/11/2026, ~09:00–09:30 BRT, branch local `v2/fase-19-21a` (a partir de `v2/fase-17-18` @ `ce16a0f`), em produção na pasta `rastro_irado`. Sem push, sem deploy do Firebase, sem migração do banco.
**Backup:** `data/backups/fase19_21a_20261116/` (main.py, engine.py, firebase_sync.py, App.jsx, useIraiData.js, TVProbabilityChart.jsx, TVNweChart.jsx).

## Por que "A"
A fase 18 rejeitou o `p_fwd_60` (AUC 0,48–0,50, BSS ≤ 0 em 361 pregões fora da amostra) e a fase 20 não teve GO. Não há modelo para rodar em shadow nem faixa/limiares de 60 min para mostrar. As partes das fases 19 e 21 que continuam valendo sem modelo novo foram feitas agora; inferência shadow, colunas `p_fwd_*` e gauge de 60 min ficam suspensos até existir um candidato.

## Entregue
### 19A (backend)
- `backend/eval/service.py`: `load_assertividade(target, window)` lê `data/eval/latest/assertividade_ultimos20.json` / `assertividade.json` (cache por mtime) e resume nowcast × 60 min × fechamento (AUC/IC, BSS/IC, ECE, acerto, confiabilidade em 10 bins, baselines, `degraded` = BSS < −0,02).
- `GET /api/eval/assertividade?target=WIN$N&window=20|full` (REQ-A02); 404 fora de WIN$N/WDO$N (D2).
- REQ-A05: `sanitize_forecast_flags()` em `backend/irai/engine.py` — `forecast_mode`/`forecast_ui` só valem para WIN$N/WDO$N.
- REQ-S01: `backend/public_payload.py::build_lean_series()` tira `p_fwd_close*` de todas as barras (e fatores das fechadas); `scripts/firebase_sync.py` usa a função e o fallback de `targets` agora leva `calibrated`/`model_version`/`forecast_*` como a API.
- Testes: `tests/test_api_eval.py` (5). `tests/test_unit_fix.py` ajustado: `irai_targets` é `def` desde 13/11 (o teste ainda usava `asyncio.run`) e a guarda REQ-A05 vale para o alvo da fixture (US500).
### 21A (painel local)
- `frontend/src/components/ReliabilityCard.jsx` + `hooks/useEvalAssertividade.js`: card "Assertividade fora da amostra" sob o gráfico de P (WIN/WDO), com nowcast × 60 min e mini curva de confiabilidade; selo "SEM EDGE · SÓ LEITURA DO DIA" quando o BSS de 60 min < −0,02. No site público o card lê `eval/<target>`, que ainda não existe (sem deploy) — o card simplesmente não aparece.
- `TVProbabilityChart.jsx`: em `on`/`nowcast_only` as linhas 60/40 viram referência neutra (sem "compra"/"venda"); legenda "P(↑) Leitura do dia (nowcast)" (REQ-U07).
- Botão "MARC. EXP." (REQ-U05): marcadores do z (ponto/estrela) desligados por padrão em modo honesto, ligados nos demais alvos como antes.

## Verificação
- Suíte numa cópia sem banco: 131 passed + 6 falhas; 5 são as conhecidas por falta de dados (`test_api_nwe`, `test_engine`, 3 de `test_engine_session_invariants`); a 6ª (`test_unit_fix`) foi corrigida e passa (13/13 em `test_unit_fix` + `test_api_eval`).
- `vite build` em pasta temporária ok. O ESLint do projeto está quebrado (falta `@eslint-community/eslint-utils` em `node_modules`), problema anterior.
- IRAI_API e IRAI_FirebaseSync reiniciados às 09:20 BRT; `/api/health` ok, `/api/eval/assertividade` WIN ok (nowcast AUC 0,883; 60 min BSS −0,329, `degraded_60m`), US500 → 404; sync com 147 chaves. Collector não reiniciado (a mudança no engine é só a guarda de flags, inerte no ciclo).

## Fica para o owner
- Deploy (regra `eval/$target` no RTDB + envio de `eval/<target>` no sync + hosting com o card e o modo honesto) — exige aprovação explícita (REQ-S06).
- 20b (fluxo) com pré-registro, ou encerrar a linha GEX+PA.
- Fechar a fase 22 como no-go direcional (D3) sem esperar 40 pregões de shadow.
- `/api/gex` sem `run` em datas passadas mostra o run pós-pregão (lookahead visual em ~75 sessões) — trocar o padrão para o run as-of muda o gráfico histórico.
