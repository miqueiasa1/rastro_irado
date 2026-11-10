# Regras do Projeto IRAI (Preservação de Layout, Sincronização, Zoom e Anti-Repainting)

Este arquivo contém as regras e restrições críticas do projeto IRAI. Qualquer agente de IA ou desenvolvedor deve ler e seguir estritamente estas diretrizes.

## 1. Preservação do Gráfico de Pair Spread (Z-Score dinâmico)
- **Regra**: O gráfico de Pair Spread (`TVPairwiseZScoreChart`) **deve estar sempre visível** na tela de detalhes para todos os ativos.
- **Comportamento Esperado**: Mesmo durante horários de pré-mercado ou em dias sem dados ativos (onde o array de pontos de dados está em branco ou com `pair_z` nulo), o componente deve ser renderizado e exibir os eixos vazios na interface para todos os ativos, em vez de sumir completamente.
- **Implementação**: A visibilidade do gráfico deve ser garantida (ex: `showPairZ = true`) e não depender apenas da presença física de valores não-nulos (`seriesWithNWE.some(...)`) ou de filtros específicos de ativos.

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

## 4. Prevenção de Repainting & Pré-Mercado (Zero-Repainting Rule)
- **Regra**: Ativos que ainda não abriram negócios na sessão do dia atual (sem barras registradas hoje) **NUNCA devem calcular retornos ou Z-Scores em cima da janela de aquecimento da sessão anterior**.
- **Comportamento Esperado**:
  - Enquanto um ativo não possuir barras negociadas na sessão atual (`session_bars`), o preço de abertura de referência (`open_price`) deve ser fixado no último preço conhecido (último fechamento de ontem).
  - Isso garante matematicamente `Retorno = 0.0%`, `Z-Score = 0.0` e `Contribuição = 0.0` até que a primeira barra oficial do dia seja negociada no mercado real, evitando saltos verticais (repainting) quando a bolsa abre (09:00 na B3, 10:30 em NY).
- **Gap Stitching no Nadaraya-Watson Envelope (NWE)**:
  - No cálculo do NWE (`backend/irai/nwe.py`), aplicar gap stitching (`history_prices = [p + gap for p in history_prices]`) para alinhar o histórico ao preço de abertura de hoje.
  - Isso impede que o salto do gap noturno infle artificialmente o erro médio (MAE), evitando bandas "desfiguradas" ou estufadas como um balão no início da sessão.

## 5. Parâmetros de Modelo Imutáveis (Versionamento — fase 16)
- **Regra**: Parâmetros de modelo **nunca são apagados**. Recalibrar = nova versão. Recalcular uma data passada = usar a versão vigente naquela data.
- **Comportamento Esperado**:
  - `scripts/calibrate_universal.py` grava uma versão nova em `model_versions` (status `shadow`) e linhas novas em `model_params` com `version_id`; nunca executa `DELETE`/`UPDATE` em parâmetros (triggers no banco bloqueiam).
  - Promover (`shadow → active`) é explícito e auditável (`scripts/model_versions.py promote <version_id> --effective-from AAAA-MM-DD`), sempre com vigência em sessão futura; a versão anterior vira `retired` com `effective_to`.
  - O engine resolve os parâmetros pela versão vigente na data da sessão; cada snapshot grava `model_version`, e o estado do Kalman só é reaproveitado dentro da mesma versão.
  - Datas anteriores à primeira versão registrada não são recalculadas: a API devolve o snapshot gravado ao vivo ou um erro explícito (`model_version_unavailable`).
