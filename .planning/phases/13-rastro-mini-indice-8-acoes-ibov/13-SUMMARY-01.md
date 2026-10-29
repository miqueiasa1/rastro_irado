# Phase 13: Rastro de Mini Índice (Top 8 Ações IBOV) - Summary

**Completed:** 2026-08-12
**Status:** Complete ✓

## Accomplishments
1. **Collector Expansion (`backend/workers/collector.py`)**:
   - Adicionadas as 8 ações mais pesadas da B3 (VALE3, PETR4, ITUB4, BBDC4, ELET3, WEGE3, ABEV3, B3SA3) ao terminal BR (XP) do coletor de barras M1/M5 via MT5.
2. **Motor de Calibração (`scripts/calibrate_universal.py`)**:
   - Cadastrado alias `WIN$N_TOP8` -> `WIN$N` para utilizar a série de preço do Mini Índice.
   - Forçada a restrição da cesta de calibração estatística especificamente para as 8 ações líderes do IBOV.
3. **Database & Backend Engine (`backend/db.py` e `backend/irai/engine.py`)**:
   - Inserida a migração `migrate_win_top8_asset` em `init_db()` cadastrando o ativo `WIN$N_TOP8` na tabela `asset_models`.
   - Mapeado `WIN$N_TOP8` em `SYMBOL_ALIASES` no `engine.py`.
4. **Frontend & Dashboard Integration (`frontend/src/`)**:
   - Integrado `WIN$N_TOP8` nos seletores de ativos (`TargetSelector.jsx`, `useIraiData.js`, `Overview.jsx`, `App.jsx`).
   - Aplicadas todas as diretrizes de **Zero-Repainting**, **Sincronização de Eixos** e **Visibilidade do Pair Spread**.

## Verification
- Migração do banco testada e validada.
- Script de calibração testado com sucesso.
- Interface React atualizada para aceitar e renderizar o novo rastro.
