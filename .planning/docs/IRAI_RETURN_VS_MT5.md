# Cálculo de Retorno: IRAI vs MT5 (Tickmill)

Este documento esclarece a diferença fundamental entre como o **IRAI (Intraday Risk Appetite Index)** calcula o retorno dos ativos e como os terminais de negociação, como o **MetaTrader 5 (Tickmill)**, exibem a coluna "Mudança %" (Change %), o que frequentemente gera percepções de divergência visual.

## 1. O Padrão MT5 (Mudança % / Change %)
A plataforma MetaTrader 5 (assim como a maioria dos home brokers) exibe o ganho/perda diário com base no **fechamento da sessão anterior**.
*   **Base de Cálculo:** O último tick (fechamento) do dia de negociação anterior.
*   **Comportamento com Gaps:** Se um ativo como o S&P 500 (US500) fecha a sexta-feira em `7215.00` e abre no domingo/segunda-feira com um Gap de Alta em `7246.00`, qualquer preço acima de `7215.00` será exibido no MT5 como um retorno **positivo (azul/verde)**.
*   **Fuso Horário:** A Tickmill opera em EEST (GMT+3 durante o horário de verão). A virada do dia (00:00 no servidor) ocorre às **21:00 UTC**.

## 2. A Filosofia IRAI (win_return Intradiário)
O motor do IRAI foi desenhado estritamente como uma ferramenta **intradiária**. Seu objetivo é medir a força e a agressão do mercado *após a abertura da sessão*, ignorando os movimentos ocorridos enquanto o mercado esteve fechado.
*   **Base de Cálculo:** O preço de **Abertura (Open) da primeira barra** da sessão atual (`session_start_h` até `session_end_h` configurados no banco de dados).
*   **Comportamento com Gaps:** O IRAI ignora o Gap. Ele assume o preço de abertura como o "marco zero" (0.00%) do dia. 
*   **Exemplo Prático:** Usando o mesmo S&P 500 que abriu a segunda-feira em `7246.00`. Se o preço cai de `7246.00` para `7226.00` durante o pregão, o IRAI registra um retorno **negativo (vermelho)** de aproximadamente `-0.31%`, pois o movimento de preço *durante o dia de negociação ativo* é de queda.

## 3. O Falso Positivo de "Divergência" no Painel
Quando o modelo preditivo (IA) aponta a probabilidade para **ALTA**, mas o mercado passa o dia todo caindo após um Gap de Alta (ex: abre em 7246, cai para 7226), o sistema IRAI irá:
1.  Registrar o retorno intradiário como **Negativo**.
2.  Comparar o sinal da IA (ALTA) com o retorno real do dia (QUEDA).
3.  Acionar o gatilho de **DIVERGÊNCIA %**.

Ao olhar para o MT5, o usuário verá o ativo "Positivo" (+0.14%) e pode achar que o painel está errado. Na verdade, o painel está alertando que a "Alta" não está se sustentando *hoje*, e que o preço está devolvendo os ganhos do gap.

### Resumo Operacional
*   **MT5:** Mostra o resultado contra **ontem**.
*   **IRAI:** Mostra a realidade do fluxo **hoje**. 
*   **Gaps:** São os causadores dessa assimetria visual. O painel IRAI está sempre focado na dinâmica presente (intradiária), cumprindo sua função de alertar sobre fluxo contrário ao direcional de longo prazo.
