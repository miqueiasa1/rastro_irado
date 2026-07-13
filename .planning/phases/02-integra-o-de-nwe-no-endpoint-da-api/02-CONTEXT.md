# Phase 2: Integração de NWE no Endpoint da API - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Acoplamento do algoritmo NWE (`compute_nwe`) ao backend FastAPI, especificamente integrando-o à rota HTTP `/api/irai/series` e à rota de WebSockets `/ws/irai`, garantindo a persistência correta e a invalidação de cache.

</domain>

<decisions>
## Implementation Decisions

### Tratamento de Dados Insuficientes
- **D-01:** Se a série temporal histórica possuir dados insuficientes (menos de 3 barras), a API deve retornar as barras normalmente com os campos do NWE definidos como `null` em vez de falhar ou retornar erro 404.

### Integração de WebSockets
- **D-02:** O cálculo do NWE será aplicado da mesma forma em tempo real nos payloads de séries temporais empurrados via WebSockets (`/ws/irai`), garantindo reatividade de plotagem instantânea nas novas barras.

### Universalidade de Ativos
- **D-03:** A API calculará o NWE para todos os 20 ativos registrados no IRAI (XP B3, Tickmill Forex, Crypto, e Índices), sem limitação específica de ativo.

### the agent's Discretion
- Local exato e formato de importação de `compute_nwe` no arquivo `backend/api/main.py`.
- Lógica de limpeza do cache da API após alterações no endpoint.

</decisions>

<canonical_refs>
## Canonical References

### Requisitos e Roadmap
- `.planning/REQUIREMENTS.md` — Requisitos da seção NWE-API.
- `.planning/ROADMAP.md` — Definição e critérios de sucesso da Fase 2.

### Módulos do Sistema
- `backend/api/main.py` — Roteamento da API, cache e WebSocket.
- `backend/irai/nwe.py` — Algoritmo de cálculo do NWE.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/irai/nwe.py` — Função `compute_nwe` implementada na Fase 1.
- `backend/api/main.py` — Lógica existente de cache `series_cache` e push do websocket.

### Integration Points
- `/api/irai/series` endpoint em `backend/api/main.py` §185-235.
- `/ws/irai` websocket endpoint em `backend/api/main.py` §503-540.

</code_context>

<deferred>
## Deferred Ideas

- Refatoração dos componentes do React para consumir os dados pré-calculados do payload da API — Fase 3.

</deferred>

---

*Phase: 02-integra-o-de-nwe-no-endpoint-da-api*
*Context gathered: 2026-07-13*
