# Phase 3: Refatoração do Frontend React - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Remoção da lógica local redundante de cálculo do NWE no frontend (`computeNWE` em `frontend/src/App.jsx`) e adaptação dos estados e componentes de gráfico para renderizarem diretamente os dados pré-calculados recebidos da API/WebSockets, com tratamento preventivo de valores nulos.

</domain>

<decisions>
## Implementation Decisions

### Remoção de Código Redundante
- **D-01:** A função de cálculo `computeNWE` e todas as constantes/variáveis locais de cálculo (como `NWE_BW`, `NWE_LOOKBACK`, etc.) serão removidas completamente do arquivo `frontend/src/App.jsx` para limpar a codebase.

### Tratamento Seguro de Valores Nulos
- **D-02:** O dashboard e o componente de gráfico (`TVNweChart.jsx`) tratarão valores `null` de NWE de forma elegante: se as bandas vierem vazias/nulas, elas simplesmente não serão renderizadas no gráfico TradingView, evitando erros de renderização ou quebras de script (`TypeError`).

### Mapeamento Direto de Chaves
- **D-03:** As chaves de preço absoluto (`nwe_center_price`, `nwe_upper_price`, etc.) serão consumidas diretamente das propriedades retornadas pelo payload JSON da API e WebSockets, eliminando a necessidade de mapeamento ou renomeação local.

### the agent's Discretion
- Formato exato do tratamento de carregamento e estado vazio do gráfico.
- Ordem de limpeza das variáveis locais não utilizadas no React.

</decisions>

<canonical_refs>
## Canonical References

### Requisitos e Roadmap
- `.planning/REQUIREMENTS.md` — Requisitos da seção NWE-UI.
- `.planning/ROADMAP.md` — Definição e critérios de sucesso da Fase 3.

### Código do Frontend
- `frontend/src/App.jsx` — Componente principal com fluxo de estados e renderização.
- `frontend/src/components/TVNweChart.jsx` — Renderizador do gráfico TradingView.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/components/TVNweChart.jsx` — Utiliza `nwe_center_price`, `nwe_upper_price`, `nwe_lower_price` e `nwe_slope` para plotagem.

### Integration Points
- `frontend/src/App.jsx` §387-520 — Localização da antiga função `computeNWE` a ser removida.
- Atualização do estado de série temporária no tratamento de eventos HTTP e WebSocket do React.

</code_context>

<deferred>
## Deferred Ideas

- Nenhuma — a discussão cobriu todo o escopo restante desta milestone.

</deferred>

---

*Phase: 03-refatora-o-do-frontend-react*
*Context gathered: 2026-07-13*
