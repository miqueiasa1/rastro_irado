# Phase 1: Implementação e Testes Unitários de NWE no Backend - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Desenvolvimento do algoritmo vetorizado do Nadaraya-Watson Envelope (NWE) no backend em Python/NumPy, garantindo paridade absoluta com a lógica matemática e tratamento de gaps/ghost bars do original em JavaScript, acompanhado por testes automatizados de unidade.

</domain>

<decisions>
## Implementation Decisions

### Local do Cálculo
- **D-01:** O cálculo do NWE ocorrerá sob demanda (on-the-fly) na API FastAPI a cada requisição de série histórica, aproveitando a velocidade da vetorização do NumPy. A estrutura de tabelas do banco de dados não será alterada para salvar dados de NWE.

### Campos do Payload
- **D-02:** A API retornará apenas preços absolutos do NWE (`nwe_center_price`, `nwe_upper_price`, `nwe_lower_price`, `nwe_slope`, `nwe_up_price`, `nwe_down_price`). Valores percentuais de retorno não serão embutidos no payload de séries por não serem consumidos no layout do gráfico.

### Estruturação de Testes de Paridade
- **D-03:** A validação será executada via testes unitários com o `pytest`, consumindo uma massa de teste real salva em JSON (contendo a entrada de série original e a saída exata calculada pelo frontend) e afirmando paridade absoluta das curvas de preço com tolerância $< 10^{-9}$.

### a agent's Discretion
- Organização interna do novo módulo `backend/quantitative/nwe.py`.
- Lógica de encapsulamento e carregamento da massa de dados JSON para o caso de teste.

</decisions>

<canonical_refs>
## Canonical References

### Requisitos e Roadmap
- `.planning/REQUIREMENTS.md` — Requisitos de cálculo da seção NWE-CALC.
- `.planning/ROADMAP.md` — Definição e critérios de sucesso da Fase 1.

### Referência de Implementação Original
- `frontend/src/App.jsx` §387-520 — Implementação da função `computeNWE` original com gap stitching e ghost bar logic.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/db.py` — Função `get_connection()` para acessar o banco de dados.

### Integration Points
- `backend/quantitative/nwe.py` [NEW] — Biblioteca que conterá a função `compute_nwe`.
- `tests/test_nwe_parity.py` [NEW] — Teste unitário para validar paridade.

</code_context>

<deferred>
## Deferred Ideas

- Acoplamento do cálculo de NWE com o endpoint de websocket da API — Fase 2.
- Refatoração dos componentes do React para consumir os dados pré-calculados — Fase 3.

</deferred>

---

*Phase: 01-implementa-o-e-testes-unit-rios-de-nwe-no-backend*
*Context gathered: 2026-07-13*
