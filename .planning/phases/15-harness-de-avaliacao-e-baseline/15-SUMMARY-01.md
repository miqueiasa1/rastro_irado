# Phase 15 Summary: Harness de Avaliação e Baseline Congelada

**Implementada:** 2026-11-10 (branch local `v2/fase-15-harness`, commit local, sem push)
**Status:** Em revisão — critério 3 em andamento (precisa de 5 pregões seguidos de relatório automático para fechar)

## Results Summary
- **Pacote `backend/eval/`** (novo, isolado do live): métricas, leitura `mode=ro`, painel, harness, relatório e store próprio.
- **CLI `scripts/eval_assertividade.py`**: período ou últimos N pregões, `as-of`, `--persist` (store `data/eval/forecast_eval.db`), `--freeze`, `--check-baseline`.
- **Baseline congelada:** `data/eval/baseline/assertividade_baseline_20261110.json` + `data/reports/assertividade_baseline_20261110.md` (sessões 2026-08-03 a 2026-11-10, as-of 13:50 UTC, B = 1000, seed 0, config `360a4722edfc`, código `5904ef5-dirty`). A mesma execução sobre a extração da auditoria bate dentro de ±0,005.
- **Testes:** 23 novos (`test_eval_metrics.py`, `test_eval_baseline.py`) verdes; suíte inteira (63 testes) verde numa cópia isolada em `%TEMP%` com a extração da auditoria no lugar do banco.

## Baseline medida (modelo atual, barras ao vivo)

| Alvo | Horizonte | n | AUC (IC 95%) | BSS | ECE (pp) | Hit |
|---|---|---|---|---|---|---|
| WIN$N | 60 min (primário) | 6.156 | 0,474 (0,432–0,509) | −0,402 | 26,6 | 48,9% |
| WIN$N | fechamento (secundário) | 6.612 | 0,525 (0,432–0,607) | −0,315 | 23,8 | 52,2% |
| WIN$N | nowcast | 6.622 | 0,710 (0,621–0,802) | +0,076 | 11,9 | 66,3% |
| WDO$N | 60 min (primário) | 5.941 | 0,486 (0,441–0,527) | −0,285 | 22,3 | 48,6% |
| WDO$N | fechamento (secundário) | 6.508 | 0,488 (0,384–0,588) | −0,286 | 22,2 | 49,0% |
| WDO$N | nowcast | 6.537 | 0,754 (0,663–0,835) | +0,167 | 11,9 | 68,2% |

## Success Criteria (PHASES.md)
1. Reproduz a baseline da auditoria (±0,005): **atendido** (WIN 60 min 0,4735; WDO 60 min 0,4859; WIN nowcast 0,7105).
2. Duas execuções idênticas (≤ 0,001): **atendido** (teste; live e extração também coincidem).
3. Relatório diário automático por 5 pregões seguidos: **em andamento** — tarefa "IRAI Daily Assertividade" criada em 10/11/2026 (seg–sex 18:45); execução manual de validação às 12:00 BRT com `LastTaskResult=0`. Fecha após 5 pregões seguidos com relatório gerado (conferir `logs/eval_assertividade.log`).
4. Nenhuma escrita além de `forecast_eval_daily`: **atendido, com desvio** — o banco fonte só é aberto em `mode=ro` (teste de hash); a tabela fica num store próprio.

## Decisões do owner (10/11/2026)
1. **Agendamento (REQ-O03):** tarefa própria no Agendador do Windows, "IRAI Daily Assertividade", seg–sex 18:45 (horário local), mesma conta e configuração da "IRAI Daily Maintenance" (usuário `ryzen`, logon interativo, privilégio limitado, `C:\Python313\python.exe`). Executa `scripts/run_eval_assertividade.bat`, que roda `eval_assertividade.py --window-sessions 20 --persist` e `--start 2026-08-03 --persist`, com log em `logs/eval_assertividade.log`. `scripts/daily_maintenance.py` não foi editado.
2. **Store:** `forecast_eval_daily` fica em `data/eval/forecast_eval.db` até a fase 16.
3. **API (REQ-A02):** `GET /api/eval/assertividade` fica para a fase 19; o contrato JSON já é gerado em `data/eval/latest/`.
4. **Fixture:** `tests/fixtures/eval_baseline_fixture.db.gz` (~600 KB) vai para o git.
5. **Baseline:** aceita com `code_git_sha = 5904ef5-dirty` (a sujeira é só `frontend/src/gexLevels.js`, dado diário de GEX, sem efeito no harness).

## Key Files Created
- `backend/eval/__init__.py`, `metrics.py`, `data.py`, `harness.py`, `report.py`
- `scripts/eval_assertividade.py`, `scripts/run_eval_assertividade.bat` (wrapper da tarefa agendada)
- `tests/test_eval_metrics.py`, `tests/test_eval_baseline.py`, `tests/fixtures/make_eval_fixture.py`, `tests/fixtures/eval_baseline_fixture.db.gz`
- `data/eval/baseline/assertividade_baseline_20261110.json`, `data/reports/assertividade_baseline_20261110.md`
- `.gitignore` (store e saídas diárias regeneráveis)
