# Phase 16: Versionamento Imutável de Parâmetros e Anti-Repaint - Context

**Gathered:** 2026-11-10
**Status:** Implementada, aguardando aprovação de commit e migração
**Source:** `.planning/milestones/v2.0-metodologia/PHASES.md` (Phase 16), `SPEC.md` §9, §10, §11, §17, `PRD.md` REQ-P01–P06, REQ-A03, REQ-N04–N06

<domain>
## Phase Boundary

Nunca mais apagar calibrações e fazer qualquer recálculo usar a versão de parâmetros vigente na data
da sessão. Sem mudança no cálculo do P: a versão vigente ao vivo continua sendo a calibração de
28/10/2026, agora registrada como a primeira versão `active` de cada alvo.
</domain>

<mapping>
## Onde o repaint acontecia (mapa do código, branch `v2/fase-15-harness`)

### Escrita/sobrescrita/remoção de parâmetros
- `scripts/calibrate_universal.py::save_to_db` — **`DELETE FROM model_params WHERE param_name LIKE '<slug>\_%'`**
  (bloco "[purge]") e depois `INSERT` dos novos pesos com `effective_from` = agora (UTC). Em seguida
  **`UPDATE asset_models SET factors, factor_labels, accuracy, r_squared, n_sessions, calibrated_at`**:
  o conjunto de fatores também era sobrescrito. É a origem do repaint: os parâmetros anteriores a 28/10
  deixaram de existir.
- `scripts/archive/_fix_win_params.py`, `_restore_win_params.py` (arquivados, fora do fluxo).
- `backend/db.py::save_kalman_state` — `INSERT OR REPLACE` em `kalman_state` (estado, não parâmetro), sem versão.
- `backend/workers/recalibrate_kalman.py` — reescreve o estado do Kalman (reset/decay) a partir dos pesos atuais.

### Leitura dos parâmetros e cálculo do P
- `backend/irai/engine.py::IRAIEngine._load_params` — `asset_models` (fatores) + `model_params` com
  `MAX(effective_from)` **por parâmetro**: sempre a calibração mais recente, independentemente da data.
- `IRAIEngine._get_model_config(target)` → `compute_from_db(session_date, ...)` — usa esse modelo único para
  QUALQUER data; `compute()` faz `P = sigmoid(α·Σ wᵢ·zᵢ + b)`; o v2 inicializa o Kalman com os mesmos pesos e
  carrega `load_kalman_state` (descarta só por dimensão).
- Consumidores: `backend/workers/collector.py::persist_live_snapshots_cycle` (ao vivo, grava
  `irai_live_snapshots`), `backend/api/main.py::_get_series_data_sync` (`mode=live` lê snapshot; `mode=recalculated`
  ou data sem snapshot **recalcula com os parâmetros ATUAIS**), `_enrich_top8_overlay`, `/api/irai/overview`,
  `/api/irai/current`; `recalibrate_kalman.load_models` (mesmo `MAX(effective_from)`).
- Medido na auditoria (PRD §3): recalcular pregões anteriores a 28/10 com os pesos atuais muda P em mediana
  18,1 pp (WIN) / 16,9 pp (WDO) e troca o lado em 34,3% / 38,9% das barras.

### Fatos do banco (cópia de 10/11/2026 13:25 BRT)
- `model_params`: 380 linhas; WIN 14 e WDO 18 parâmetros, todos com `effective_from` 2026-10-28T19:05:10Z /
  19:05:12Z (16:05 BRT, **pregão em andamento** → 28/10 é sessão mista). JP225 e US2000 seguem com a calibração de
  23/07/2026. 14 alvos ativos.
- `irai_live_snapshots`: 318.707 linhas; `kalman_state`: 1.663 linhas.
</mapping>

<decisions>
## Implementation Decisions

### Segurança do live (restrições do owner)
- Os serviços NSSM rodam desta pasta. Nada foi reiniciado; nenhuma migração foi aplicada ao `data\irai_live.db`.
- **A migração NÃO foi ligada ao `init_db()`** (que roda no boot da API e do Collector), ao contrário do SPEC §10:
  se fosse, qualquer reinício de serviço aplicaria o schema sem aprovação. Ela é um script explícito
  (`scripts/migrate_fase16_model_versions.py`, exige `--confirm-live` para o banco de produção). Ligar ao `init_db`
  depois da aprovação é opcional.
- **Sem a migração, o código novo segue o caminho legado byte a byte** (mesmo SQL de `MAX(effective_from)`,
  mesmo parser de parâmetros, `model_version='legacy'` só em memória; payload da API e do Firebase inalterados).
- `calibrate_universal.py` sem a migração **aborta antes de calibrar** (não há como gravar sem apagar).

### Modelo de dados (SPEC §10, aditivo)
- `model_versions` (SPEC §10.1 + coluna `fitted_at`); `model_version_events` (novo, append-only) para auditar
  registro/promoção/aposentadoria (REQ-P06).
- Colunas: `model_params.version_id` (10.2), `irai_live_snapshots.model_version` (10.3, só esta coluna nesta fase;
  `forecast_version`/`p_fwd_*`/`feature_stale` ficam para a fase 19), `kalman_state.model_version` (10.4),
  `asset_models.forecast_mode`/`forecast_ui` com padrão `'off'` (10.5). `forecast_eval_daily` (10.6) continua em
  `data/eval/forecast_eval.db` (decisão 2 da fase 15).
- Triggers de imutabilidade (REQ-N06): `DELETE`/`UPDATE` em `model_params` bloqueados; `DELETE` em `model_versions`
  bloqueado; `UPDATE` em `model_versions` só em `status`/`effective_from`/`effective_to`; eventos append-only.
- O artefato (`artifact_json`) guarda a cópia exata dos parâmetros (sem prefixo) e a lista/ordem de fatores — é a
  fonte da verdade do engine. Linhas legadas de `model_params` não são tocadas (nem recebem `version_id`).

### Vigência
- Versão adotada do legado: `effective_from` = primeira sessão inteira após a calibração. B3: mesmo dia se antes
  de 09:00 BRT, senão dia seguinte; globais: dia seguinte do broker. Resultado: **29/10/2026** para os 12 alvos
  recalibrados em 28/10 e 24/07/2026 para JP225/US2000.
- 28/10 e datas anteriores: recálculo **bloqueado** (SPEC §9.3); a API devolve o snapshot ao vivo com
  `recalc_blocked: true` ou HTTP 409 `model_version_unavailable`.
- Promoção só para sessão futura (> hoje em BRT e no relógio do broker; `--allow-today` explícito para hoje).
  Ao promover: active anterior → `retired` com `effective_to` = nova vigência; `asset_models` (fatores, acurácia,
  `calibrated_at`) é espelhado nesse momento, não na calibração.
- Calibração nova nasce `shadow`; o caminho legado ignora linhas com `version_id` (uma shadow nunca vira "a mais recente").

### Kalman (REQ-P05)
- Estado gravado com `model_version`; `load_kalman_state` só aceita estado da mesma versão (troca de versão =
  reinicialização registrada no log). Estados sem versão (anteriores à migração) são aceitos só pela versão adotada
  do legado — senão o Kalman reiniciaria no primeiro pregão após a migração e o live mudaria.
</decisions>

<canonical_refs>
## Canonical References

- `.planning/milestones/v2.0-metodologia/SPEC.md` — §9 (versionamento), §10 (schema), §11 (API), §17 (testes)
- `.planning/milestones/v2.0-metodologia/PRD.md` — §5.2 (REQ-P), REQ-A03, REQ-N04–N06
- `.agents/AGENTS.md` — Regra 5 (nova)
- `backend/irai/model_registry.py`, `scripts/migrate_fase16_model_versions.py`, `scripts/model_versions.py`
</canonical_refs>
