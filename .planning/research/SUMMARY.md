# Project Research Summary

**Project:** IRAI — Intraday Risk Appetite Index
**Domain:** Quantitative Web Applications
**Researched:** 2026-07-13
**Confidence:** HIGH

## Executive Summary

Esta pesquisa investiga a migração do cálculo do Nadaraya-Watson Envelope (NWE) do frontend React para o backend FastAPI (Python/NumPy). O objetivo principal é sanar o gargalo de performance do dashboard, onde o cálculo no cliente em $O(n^2)$ com dados acumulativos de 5 minutos gerava travamentos de tela (UI lags).

A abordagem recomendada é implementar uma biblioteca matemática vetorizada no backend em Python (`nwe.py`), alimentada com dados do banco e histórico necessário para costurar lacunas de gap (stitch gap). A API do FastAPI retornará as curvas do envelope prontas, reduzindo a complexidade de renderização do React a uma plotagem linear simples. Os maiores riscos envolvem pequenos desvios de precisão float ou erros de indexação (off-by-one), que serão mitigados com testes unitários de paridade matemática.

## Key Findings

### Recommended Stack

*   **Python + NumPy:** O NumPy permite vetorizar as operações de média ponderada exponencial (Gaussian Kernel) e desvio absoluto (MAE), executando em milissegundos o que o loop do JS no React levava centenas de milissegundos para recomputar a cada render.
*   **FastAPI:** Framework existente que continuará servindo as séries temporais de forma otimizada.
*   **pytest:** Ferramenta para validação de paridade matemática rigorosa entre os resultados do Python e do Javascript original.

### Expected Features

*   **Gauss Causal NWE (Lookback 95, bw=8):** Garantir paridade visual total do cálculo central do envelope.
*   **Envelope MAE Dinâmico (mult=3):** Banda de envelope baseada no desvio absoluto médio.
*   **Stitching & Ghost Bars Support:** Suporte a costura de gap e manutenção de retas em barras overnight sem desfigurar o gráfico de abertura.

### Architecture Approach

O backend FastAPI (`main.py`) irá costurar as 95 barras de fechamento históricas (do dia anterior) com a série atual da sessão e chamar o novo módulo `backend/quantitative/nwe.py`. A série computada em percentual e preço absoluto será fatiada de volta para o tamanho da sessão e mapeada no payload JSON final para o frontend React.

### Critical Pitfalls

1.  **Off-by-one Errors:** Diferenças de slices entre os loops indexados de JS e Python.
2.  **Gap Stitching Distortions:** Falha ao tratar gaps noturnos que geram picos falsos na abertura.
3.  **Float Mismatch:** Diferenças sutis de arredondamento de precisão de float entre JS e Python.

## Implications for Roadmap

Com base nesta pesquisa, a Milestone v1.0 será dividida em 3 fases de execução claras:

### Phase 1: Implementação e Testes Unitários de NWE no Backend
*   **Rationale:** Precisamos garantir a lógica matemática correta no Python antes de tocar em endpoints ou no frontend.
*   **Delivers:** Módulo `backend/quantitative/nwe.py` e testes automatizados de paridade via `pytest`.
*   **Avoids:** Erros de off-by-one e falhas de paridade matemática.

### Phase 2: Integração de NWE no Endpoint da API
*   **Rationale:** Depois de validado matematicamente, o cálculo deve ser acoplado à rota `/api/irai/series` do FastAPI.
*   **Delivers:** Endpoint enriquecido com campos de NWE e cache server-side funcional.

### Phase 3: Refatoração do Frontend React
*   **Rationale:** O frontend deve ser limpo de todo o peso computacional de NWE e adaptado para consumir os novos campos.
*   **Delivers:** Dashboard rápido, sem flickering ou latência de render.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | NumPy e FastAPI são ferramentas padrão da indústria e já estão no projeto. |
| Features | HIGH | O algoritmo JS atual do NWE está documentado e mapeado em detalhes. |
| Architecture | HIGH | O pipeline de dados da API e do cache já suporta este tipo de extensão. |
| Pitfalls | HIGH | Os riscos foram completamente mapeados e serão travados via testes de unidade. |

**Overall confidence:** HIGH

## Sources

*   [Nadaraya-Watson Kernel Regression] — https://en.wikipedia.org/wiki/Kernel_regression
*   [Frontend codebase] — [App.jsx:L387-520](file:///c:/Users/ryzen/Downloads/Antigravity/rastro_irado/frontend/src/App.jsx#L387-L520)
