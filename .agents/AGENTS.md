# Regras do Projeto IRAI (Preservação de Layout, Sincronização e Zoom)

Este arquivo contém as regras e restrições críticas do projeto. Qualquer agente de IA ou desenvolvedor deve ler e seguir estritamente estas diretrizes antes de realizar qualquer alteração no repositório.

## 1. Preservação do Gráfico de Pair Spread (Z-Score dinâmico)
- **Regra**: O gráfico de Pair Spread (`TVPairwiseZScoreChart`) **deve estar sempre visível** na tela de detalhes quando o ativo selecionado for o Mini Índice (`WIN$N`).
- **Comportamento Esperado**: Mesmo durante horários de pré-mercado ou em dias sem dados ativos (onde o array de pontos de dados está em branco ou com `pair_z` nulo), o componente deve ser renderizado e exibir os eixos vazios na interface, em vez de sumir completamente.
- **Implementação**: A visibilidade do gráfico deve depender do ativo (`selectedTarget === 'WIN$N'`) e não apenas da presença física de valores não-nulos (`seriesWithNWE.some(...)`).

## 2. Sincronização Estrita dos Gráficos
- **Regra**: Todos os gráficos de série temporal na visualização de detalhes (Gráfico principal NWE, Pair Spread, Divergência de Preço, Pesos Kalman, Volatilidade GARCH) devem ter suas escalas horizontais sincronizadas em tempo real.
- **Comportamento Esperado**: Fazer zoom ou arrastar lateralmente um gráfico deve atualizar a escala horizontal de todos os outros de forma idêntica e instantânea.
- **Implementação**: Utilizar referências como `isSyncingRef` em `App.jsx` para coordenar o ajuste do `setVisibleLogicalRange` de forma limpa e sem causar loops infinitos de redimensionamento.

## 3. Preservação de Zoom e Posição do Usuário (Anti-Reset)
- **Regra**: O zoom horizontal e a posição (pan) definidos manualmente pelo usuário **nunca devem ser resetados** para o padrão quando novos dados ou ticks em tempo real chegarem via API ou WebSocket.
- **Comportamento Esperado**:
  - Se o usuário estiver olhando para o passado (analisando dados históricos), a posição do zoom e a área visualizada devem permanecer completamente imóveis.
  - Se o usuário estiver posicionado na borda direita do gráfico (tempo real), o gráfico deve continuar rolando suavemente para a direita para acompanhar os novos ticks que entram, mantendo o nível de zoom atual.
- **Implementação**: Armazenar o range visível no `savedRangeRef` e analisar a proximidade com a borda direita (`prevValidCountRef`) antes de decidir mover o foco horizontal dos gráficos.
