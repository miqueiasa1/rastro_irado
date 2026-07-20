# Phase 4: Robustez de Infraestrutura (Concorrência e Persistência) - Context

**Gathered:** 2026-07-18
**Status:** Ready for planning
**Source:** Análise comparativa fork `brenoperucchi/rastro_irado` (performance_comparison.md + formula_impact_analysis.md)

<domain>
## Phase Boundary

Aplicar 3 melhorias de robustez de infraestrutura identificadas na comparação com o fork de Breno Perucchi, **sem alterar nenhuma fórmula de cálculo** (P Dinâmico, Pair Spread, Z-Score, Johansen). O escopo é exclusivamente "plumbing" — concorrência, persistência e auditoria de schema.

</domain>

<decisions>
## Implementation Decisions

### Guard Concorrente de Boot (INFRA-01)
- Criar helper `_add_column(conn, sql)` em `backend/db.py` que wrapa `ALTER TABLE ... ADD COLUMN` num try/except e captura `duplicate column` silenciosamente
- Substituir todas as chamadas diretas de `ALTER TABLE ... ADD COLUMN` nas funções `migrate_*` pelo wrapper `_add_column`
- O wrapper retorna `True` se a coluna foi adicionada, `False` se já existia
- Manter o padrão existente de `PRAGMA table_info` como primeira linha de defesa; o `_add_column` é a segunda rede de segurança para race conditions
- **NÃO** alterar a assinatura ou o comportamento de `init_db()`, `get_connection()`, ou o SCHEMA base

### Guard Monotônico do Kalman (INFRA-02)
- O `save_kalman_state()` atual em `backend/db.py` (L234) **já tem** um guard de timestamp (`if timestamp_utc <= existing_ts: return`)
- Verificar se o guard está correto e funcional para o caso de replay histórico via `compute_from_db(session_date="2026-01-15", persist_state=True)`
- Se o guard existente já cobre o cenário, apenas adicionar um teste de integração que prove a proteção
- **NÃO** alterar a assinatura `(conn, slug, timeframe, session_date, ...)` — manter a PK composta `(slug, timeframe, session_date)` existente
- **NÃO** adotar o schema simplificado do fork (PK apenas `slug`) — o nosso schema com session_date por dia é mais granular e correto para análise de sessões individuais

### Auditoria da Tabela GEX (INFRA-03)
- Verificar que `migrate_gex_levels()` em `backend/db.py` (L192) está idempotente
- Confirmar que a coluna `run_name` existe e funciona corretamente
- Adicionar um log de auditoria simples que conta registros por sessão/target na migração
- **NÃO** alterar o uso da tabela GEX em nenhum endpoint ou módulo de cálculo

### Discretion do Agente
- Ordem exata dos testes a criar
- Formato dos logs de auditoria
- Detalhes de mensagens de print/log nas migrações

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Database
- `backend/db.py` — Schema, migrações, `save_kalman_state()`, `load_kalman_state()`, `_add_column` target

### Engine (LEITURA APENAS — NÃO MODIFICAR)
- `backend/irai/engine.py` — Referência de como `save_kalman_state` e `load_kalman_state` são chamados (L828-835, L647-665)

### Fork de Referência
- `breno/main:backend/db.py` — Implementação de referência do `_add_column` e `migrate_to_head`

</canonical_refs>

<specifics>
## Specific Ideas

### Trecho exato do `_add_column` do fork (referência):
```python
def _add_column(conn, sql):
    try:
        conn.execute(sql)
        return True
    except sqlite3.OperationalError as exc:
        if "duplicate column" not in str(exc).lower():
            raise
        return False
```

### Guard monotônico existente no nosso `save_kalman_state` (L239-247):
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

### Cenário de crash concorrente a resolver:
- API (uvicorn) inicia e chama `init_db()` → `migrate_delta()` → `ALTER TABLE ... ADD COLUMN real_volume`
- Collector (apscheduler) inicia ~200ms depois e chama `init_db()` → `migrate_delta()` → `ALTER TABLE ... ADD COLUMN real_volume`
- Segundo `ALTER TABLE` falha com `OperationalError: duplicate column name: real_volume`
- Com o guard `_add_column`, o segundo processo captura o erro e continua

</specifics>

<deferred>
## Deferred Ideas

- **Filtro de σ quase-nula no Pair Spread**: melhoria de lógica do fork que muda a eleição do par ativo — fora do escopo desta fase (alteraria cálculos)
- **Reset de histórico ao trocar de par**: melhoria de lógica que zera `pair_residual_history` na troca de fator — fora do escopo desta fase (alteraria cálculos)
- **Schema simplificado do Kalman (PK slug only)**: o fork usa PK simples em vez da nossa PK composta `(slug, timeframe, session_date)` — manter a granularidade por sessão
- **`factor_signature` column**: coluna nova do fork para rastrear quando a cesta de fatores muda — pode ser adicionada em fase futura se necessário
- **`migrate_to_head()` centralizador**: wrapper do fork que substitui `init_db()` — nice to have mas não necessário agora

</deferred>

---

*Phase: 04-robustez-de-infraestrutura*
*Context gathered: 2026-07-18 via fork comparison analysis*
