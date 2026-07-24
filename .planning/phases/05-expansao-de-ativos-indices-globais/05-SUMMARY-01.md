# Plan 05-PLAN-01 Execution Summary

**Phase:** 5 (Expansão de Ativos - Índices Globais)
**Wave:** 1
**Completed:** 2026-07-23

## Accomplished Tasks
1. **Adicionado US2000 e JP225 no Coletor MT5 (`backend/workers/collector.py`)**:
   - Atualizada a lista de `symbols` do terminal Tickmill para incluir `US2000` e `JP225` ao lado de `DE40` e `CHINA50`.
2. **Criado e executado o script de registro (`scripts/maintenance/register_global_indices.py`)**:
   - Cadastrados e ativados os 4 alvos em `asset_models`: `DE40`, `US2000`, `JP225`, `CHINA50` com sessão 24h.
   - Confirmado o total de 24 ativos ativos na base SQLite `data/irai_live.db`.
3. **Refatorado `backend/irai/engine.py` para carregamento dinâmico**:
   - Substituída a query hardcoded por `WHERE active=1 ORDER BY target` em `_load_params()`.

## Verification
- `collector.py` validado sintaticamente.
- Script de registro executado com sucesso [OK].
- Tabela `asset_models` contendo os 24 ativos ativos.
