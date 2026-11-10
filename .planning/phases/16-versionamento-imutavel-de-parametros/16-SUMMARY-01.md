# Phase 16 Summary: Versionamento Imutável de Parâmetros e Anti-Repaint

**Implementada:** 2026-11-10 (branch local `v2/fase-16-versionamento`, criada de `v2/fase-15-harness`; sem commit, sem push)
**Status:** Implementada, aguardando aprovação de commit e migração. Nada foi aplicado ao `data\irai_live.db` e nenhum serviço foi reiniciado.

## Results Summary
- **Onde o repaint acontecia:** `scripts/calibrate_universal.py::save_to_db` apagava todos os parâmetros do alvo
  (`DELETE FROM model_params ... LIKE '<slug>\_%'`) e sobrescrevia `asset_models.factors`; o engine
  (`IRAIEngine._load_params`) carregava sempre `MAX(effective_from)` e `compute_from_db` usava esse modelo único para
  qualquer data. `/api/irai/series?mode=recalculated` e datas sem snapshot recalculavam o passado com os pesos atuais.
- **Registro imutável** (`backend/irai/model_registry.py`): `model_versions` + `model_version_events` (auditoria),
  triggers que bloqueiam `DELETE`/`UPDATE` em `model_params` e em `model_versions` (exceto status/vigência).
- **Calibração** sem `DELETE`: cada execução cria uma versão `shadow` com janela de treino, config, métricas (in-sample)
  e SHA do código; o live só muda com `scripts/model_versions.py promote <id> --effective-from AAAA-MM-DD`
  (sessão futura; a anterior vira `retired`). Sem a migração, a calibração aborta antes de rodar.
- **Engine:** parâmetros pela versão vigente na data (`resolve_version`), `model_version` em cada snapshot e no estado do
  Kalman; datas anteriores à 1ª versão levantam `ModelVersionUnavailable` (API: snapshot com `recalc_blocked: true` ou 409).
- **API:** `GET /api/model/versions` (sem artefato); `/api/model/params` com `model_version`/`versioned`/`effective_from`.
- **Migração** `scripts/migrate_fase16_model_versions.py`: aditiva, idempotente, transação única, `--dry-run`,
  `--confirm-live` obrigatório para o banco de produção; adota a calibração atual como 1ª versão `active` de cada alvo
  ativo (14 versões; vigência 29/10/2026, JP225/US2000 24/07/2026). **Não** foi ligada ao `init_db()`.
- **Regra 5** adicionada ao `.agents/AGENTS.md`; contrato em `docs/API.md`.

## Verificação (cópia isolada em `%TEMP%\irai_p16`, banco copiado via backup API às 13:25 BRT)
- Migração na cópia: 3,8 s; 2ª execução sem mudanças (idempotente); dry-run sem gravação; nenhuma linha ou objeto a menos
  (`model_params` 380 → 380, `irai_live_snapshots` 318.707 → 318.707, `kalman_state` 1.663 → 1.663).
- **Live idêntico (critério 3):** 14 alvos × 5 pregões (04–10/11), 19.153 barras, ΔP máximo legado × migrado = **0,00 pp**.
- **Código antigo sobre o banco migrado** (fase 15): calcula e grava normalmente (colunas novas ficam NULL); o
  `DELETE` antigo da calibração é bloqueado pelo trigger.
- **Bloqueio (critério 4):** WIN$N/WDO$N em 27/10 → `ModelVersionUnavailable` (1ª versão vale a partir de 29/10).
- **Suíte:** 87 testes verdes com o banco legado e 87 verdes com o banco migrado (inclui os 23 da fase 15 e
  22 novos: `test_model_registry.py` 11, `test_repaint_versioned.py` 11).
- **Critério 1:** duas calibrações seguidas só acrescentam linhas (teste).
- **Critério 2 [META] — ainda não atingido, e não é causado por parâmetros:** recálculo com a versão vigente vs.
  snapshot ao vivo, 29/10–09/11: WIN mediana 0,50 pp, p90 2,38 pp, 17,1% das barras ≤ 0,1 pp, 1,6% troca de lado;
  WDO 0,35 pp, p90 1,32 pp, 21,0% ≤ 0,1 pp, 1,3% troca de lado (mesma ordem do PRD: "com os mesmos parâmetros,
  mediana 0,5 pp"). O resíduo vem do próprio recálculo (barras de fatores que chegam depois, forward-fill, captura
  da barra em formação, evolução do Kalman), não da versão. No teste sintético com versão registrada o recálculo
  reproduz o snapshot exatamente. Fica como item aberto para a fase 19/22.

## Testes ajustados (consequência esperada da Regra 5)
- `tests/test_engine.py` (20/07 → 04/11), `tests/test_api_nwe.py` (10/07 → 04/11) e
  `tests/test_engine_session_invariants.py` (27/10 → 29/10): recalculavam datas anteriores à 1ª versão registrada, o que
  passa a ser bloqueado depois da migração. As asserções não mudaram.

## Ativação em produção (pendente de aprovação do owner)
1. Aprovar o commit na branch local `v2/fase-16-versionamento` (sem push).
2. Após o pregão (depois das 18:30 BRT) e de preferência depois do backup da "IRAI Daily Maintenance" (19:15):
   `C:\Python313\python.exe scripts\migrate_fase16_model_versions.py --db data\irai_live.db --dry-run --confirm-live`
   e, conferido o relatório, o mesmo comando sem `--dry-run`.
3. Reiniciar `IRAI_Collector`, `IRAI_API` e `IRAI_FirebaseSync` (este importa `backend.api.main` como fallback).
   `IRAI_Frontend` não precisa. Até o reinício, o código em memória segue o caminho legado com o mesmo resultado.
4. Conferir `GET /api/model/versions?target=WIN$N`, `GET /api/model/params?target=WIN$N` (`versioned: true`) e
   `model_version` preenchido nos snapshots novos.
- Reverter: voltar o código para `v2/fase-15-harness` funciona com o banco migrado; os objetos novos podem ser removidos
  manualmente (`DROP TRIGGER trg_*`, `DROP TABLE model_versions, model_version_events`), as colunas novas ficam NULL.

## Em aberto (decisão do owner)
1. Ligar `ensure_schema` ao `init_db()` depois da migração (auto-heal no boot) ou manter só o script.
2. `forecast_eval_daily` continua em `data/eval/forecast_eval.db` (não movida para o `irai_live.db`).
3. Vigência das versões adotadas: 29/10 (28/10 tratado como sessão mista; a calibração foi às 16:05 BRT).
4. `calibrate_universal.py --all` (sem `--force`) não marca mais `calibrated_at` na calibração (só na promoção);
   rodar de novo cria outra versão `shadow` para os mesmos alvos pendentes.
5. Resíduo de repaint não ligado a parâmetros (critério 2 [META]).

## Key Files
- Novos: `backend/irai/model_registry.py`, `scripts/migrate_fase16_model_versions.py`, `scripts/model_versions.py`,
  `tests/fase16_fixtures.py`, `tests/test_model_registry.py`, `tests/test_repaint_versioned.py`
- Alterados: `backend/irai/engine.py`, `backend/db.py`, `backend/api/main.py`, `backend/workers/recalibrate_kalman.py`,
  `scripts/calibrate_universal.py`, `tests/test_engine.py`, `tests/test_engine_session_invariants.py`,
  `tests/test_api_nwe.py`, `.agents/AGENTS.md`, `docs/API.md`
