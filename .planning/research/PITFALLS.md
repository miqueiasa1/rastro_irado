# Pitfalls Research

**Domain:** Nadaraya-Watson Envelope (NWE) Backend Migration
**Researched:** 2026-07-13
**Confidence:** HIGH

## Critical Pitfalls & Mitigation Strategies

### 1. Desalinhamento do Preço de Abertura (`win_open` / `open`)
*   **Risco:** Os valores percentuais do NWE no frontend são normalizados como `((currentCenter[i] / open) - 1) * 100` onde `open` é `d.win_open`. No backend, precisamos garantir que o preço `win_open` esteja presente e seja idêntico para a normalização.
*   **Prevenção:** Usar exatamente o valor correspondente a `win_open` (o preço de abertura do ativo alvo no início da sessão diária) para calcular os retornos percentuais de NWE no backend.

### 2. Diferenças de Indexação e Limites de Janela (Off-by-one)
*   **Risco:** O loop Javascript calcula pesos baseados em `lookbackLimit = Math.min(t, NWE_LOOKBACK - 1)`. Traduzir isso incorretamente para slices do NumPy (`t - i` e janelas retroativas) causará distorções graves nas primeiras 95 barras de cada sessão.
*   **Prevenção:** Escrever um teste unitário rigoroso comparando o resultado do script Python com o resultado do algoritmo JS sobre um vetor de teste idêntico.

### 3. Tratamento de Ghost Bars na Costura Noturna (Overnight Gap)
*   **Risco:** Se o backend calcular o NWE ignorando as flags de `is_ghost` ou a lógica de gap stitching da XP B3, as bandas do envelope sofrerão deformações enormes na abertura do pregão (09:00 BRT).
*   **Prevenção:** Replicar fielmente o gap stitching de `history_closes` e a repetição estável dos valores de NWE anteriores para barras identificadas como `is_ghost=True`.

### 4. Cache Desatualizado ou Invalidação Tardia
*   **Risco:** O endpoint `/api/irai/series` possui cache no backend. Se os valores do NWE forem embutidos na resposta da API, a invalidação do cache deve continuar funcionando perfeitamente a cada novo ciclo de atualização de barra (`notify_update`).
*   **Prevenção:** Como a estrutura da API de cache não será alterada (apenas o payload final é enriquecido), a invalidação do cache server-side já existente cobrirá o NWE de forma nativa.
