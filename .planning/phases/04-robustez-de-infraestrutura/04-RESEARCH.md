# Phase 4: Robustez de Infraestrutura — Research

**Date:** 2026-07-18
**Status:** RESEARCH COMPLETE

## 1. Achados Críticos da Pesquisa

### 1.1 Concorrência Real do Sistema (Descoberta Principal)

**A race condition de boot NÃO ocorre no cenário atual.**

Investiguei todos os call-sites de `init_db()` e `migrate_*()`:

| Processo | Chama `init_db()` no startup? | Chama `migrate_*()`? |
|----------|-------------------------------|---------------------|
| API (`backend/api/main.py`) | ❌ Não | ❌ Não |
| Collector (`backend/workers/collector.py`) | ❌ Não | ❌ Não |
| `scripts/collect_history.py` | ✅ Sim (manual) | Via init_db |
| `backend/db.py __main__` | ✅ Sim (manual) | Via init_db |

O `start_irai.bat` inicia API e Collector em janelas separadas, mas nenhum deles chama `init_db()`.
A API apenas cria o `IRAIEngine()` no `lifespan`, e o Collector apenas chama `get_connection()`.

**O fork `brenoperucchi` MUDOU isso** — adicionou `migrate_to_head()` tanto na API lifespan quanto no collector `main()`. É por isso que o fork precisou do `_add_column` guard. No nosso código atual, a race não existe porque as migrações só rodam manualmente.

**Conclusão**: O `_add_column` guard é útil como **melhoria preventiva** — se no futuro adicionarmos `init_db()` ao startup (o que é boa prática), o guard evitará crashes. Mas o cenário de crash atual é teórico, não prático.

### 1.2 Guard Monotônico do Kalman (Já Implementado)

O `save_kalman_state()` em `db.py:L234-260` **já tem** o guard de timestamp:

```python
row = conn.execute("""
    SELECT timestamp_utc FROM kalman_state
    WHERE slug = ? AND timeframe = ? AND session_date = ?
""", (slug, timeframe, session_date)).fetchone()
if row:
    existing_ts = row["timestamp_utc"]
    if timestamp_utc <= existing_ts:
        return
```

Adicionalmente, a API em `main.py:L361` **já controla via `persist_state`**:

```python
is_today = (session_date == date.today().isoformat())
snapshots = engine.compute_from_db(..., persist_state=is_today)
```

Isso significa que consultas históricas (`session_date != today`) já passam `persist_state=False` e **nem chegam** ao `save_kalman_state()`.

**Proteção em camadas:**
1. **Camada 1**: API passa `persist_state=False` para sessões passadas → `save_kalman_state` nunca é chamado
2. **Camada 2**: Se `persist_state=True` e o banco já tem estado mais recente → guard rejeita silenciosamente

**Conclusão**: O guard existente é correto e funcional. A contribuição real é criar **testes automatizados** que comprovem isso.

### 1.3 Padrões de Migração Existentes (Inconsistências)

Identifiquei 3 padrões diferentes de proteção nas funções `migrate_*`:

| Função | Proteção usada |
|--------|---------------|
| `migrate_delta` | `PRAGMA table_info` → verifica colunas → `ALTER TABLE` direto (sem try/except) |
| `migrate_kalman_state` | `CREATE TABLE IF NOT EXISTS` (idempotente nativo) |
| `migrate_gex_levels` | `PRAGMA table_info` → DROP + `CREATE TABLE IF NOT EXISTS` |
| `migrate_garch_volatility` | `CREATE TABLE IF NOT EXISTS` (idempotente nativo) |
| `migrate_timeframe_constraint` | `SELECT sql FROM sqlite_master` → recria tabela |
| `migrate_kalman_state_timeframe` | `SELECT sql` → recria tabela |
| `migrate_divergence_config` | `PRAGMA table_info` → `ALTER TABLE` com try/except genérico |

**Risco**: `migrate_delta` e `migrate_divergence_config` fazem `ALTER TABLE ADD COLUMN` sem proteção adequada contra race conditions. O `migrate_divergence_config` tem um `except Exception` genérico que engole QUALQUER erro (incluindo erros legítimos de disco cheio, permissão, etc.) — deveria capturar apenas `duplicate column`.

### 1.4 Schema da Tabela `gex_levels`

A migração `migrate_gex_levels` faz DROP + CREATE se `run_name` não existe. Isso é destrutivo mas correto (os dados GEX são re-downloadados do B3). O CREATE TABLE IF NOT EXISTS é idempotente por natureza.

Contagem atual:
```sql
SELECT COUNT(*) FROM gex_levels;
SELECT COUNT(DISTINCT session_date) FROM gex_levels;
```

### 1.5 Diretório de Testes

Existe em `tests/` com 2 arquivos de teste (NWE parity), mas nenhum teste de `db.py`.

## 2. Riscos e Edge Cases

1. **`migrate_divergence_config` engole erros legítimos**: O `except Exception` genérico mascara erros reais (disco cheio, tabela corrompida, etc.)
2. **`migrate_delta` sem try/except**: Se rodar em paralelo (cenário futuro), crasha com `duplicate column`
3. **Sem testes para db.py**: Nenhum teste automatizado valida as migrações ou o guard do Kalman

## 3. Recomendações para os Planos

### Plan 01 (Guard Concorrente)
- **Escopo expandido**: Além de criar `_add_column`, adicionar `init_db()` ao startup da API (lifespan) e ao collector para auto-heal em deploys futuros
- **Fix adicional**: Corrigir o `except Exception` genérico em `migrate_divergence_config` para capturar apenas `duplicate column`

### Plan 02 (Guard Kalman)
- **Escopo correto**: Apenas testes — o guard já existe e funciona. Documentar as duas camadas de proteção.

### Plan 03 (Auditoria GEX)
- **Escopo correto**: Log de auditoria + teste de idempotência.

## Validation Architecture

### Dimension 1: Unit Tests
- Testes de `_add_column` com duplicata simulada
- Testes de `save_kalman_state` monotonicity

### Dimension 2: Integration Tests
- `init_db()` paralelo (multiprocessing)
- `migrate_gex_levels()` repetida

### Dimension 3: Regression Tests
- Nenhuma função de cálculo deve ser alterada (grep verification)
