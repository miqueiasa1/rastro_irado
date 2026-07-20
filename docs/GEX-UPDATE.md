# Atualização Diária do GEX (Gamma Exposure) e Sincronização do IRAI

Este documento descreve como o fluxo de atualização do GEX funciona, onde buscar os arquivos, logs, como a execução diária automatizada está configurada e como depurar ou rodar manualmente.

---

## 1. Visão Geral do Fluxo

A atualização do GEX consiste em três etapas sequenciais:
1. **Coleta e Processamento (GEX Engine):** Coleta dados de opções de 10 ativos, calcula a exposição gama (GEX) e gera os relatórios de níveis (Walls).
2. **Geração do Pine Script:** Exporta os níveis consolidados em um indicador unificado para o TradingView em `wdo win pair trading/gex/docs/jumba_tradingview.pine`.
3. **Sincronização com o IRAI (Dashboard):** Executa o script `sync_gex_to_irai.py` para parsear o arquivo Pine e gerar o arquivo `gexLevels.js` consumido pelo frontend do IRAI.

---

## 2. Configuração do Agendamento Diário

O fluxo está automatizado para rodar diariamente utilizando o **Agendador de Tarefas do Windows (Task Scheduler)**.

* **Nome da Tarefa:** `GEX Daily Update (Jumba Walls)`
* **Horário:** Segunda a Sexta-feira, às **07:30 BRT**.
* **Script de Execução:** `c:\Users\ryzen\Downloads\Antigravity\wdo win pair trading\GEX_DAILY_SCHEDULED.bat`
* **Diretório de Trabalho:** `c:\Users\ryzen\Downloads\Antigravity\wdo win pair trading`
* **Ação no Git:** Faz o commit automático das planilhas de opções baixadas, cache e do script Pine gerado sob a mensagem `chore(gex): atualizacao consolidada de GEX para 10 ativos e relatorios diarios`.

---

## 3. Scripts Envolvidos

### Wrapper do Agendador
* **Arquivo:** `wdo win pair trading/GEX_DAILY_SCHEDULED.bat`
* **Função:** Chama sequencialmente os scripts em python para atualizar o GEX de cada ativo, comita no Git e, no final, executa o script de sincronização com o dashboard.

### Sincronizador de Níveis do Dashboard
* **Arquivo:** `rastro_irado/scripts/sync_gex_to_irai.py`
* **Função:** Lê o arquivo Pine, extrai os preços de suporte/resistência (wall, min_gamma, max_gamma, gamma_flip) e cria o arquivo JS importado pelo dashboard (`rastro_irado/frontend/src/gexLevels.js`).

---

## 4. Onde Buscar os Logs e Depurar

Os logs de cada execução diária automática são gravados no seguinte diretório:
* **Pasta de Logs:** `wdo win pair trading/gex/logs/`
* **Nome do Arquivo:** `gex_daily_YYYYMMDD.log` (ex: `gex_daily_20260617.log`)

### Como verificar se funcionou corretamente?
Abra o último arquivo de log gerado no dia e verifique se a execução terminou com sucesso. O final do log deve ser similar a:
```text
[SYNC] Sincronizando niveis GEX no dashboard IRAI... 
Parsing: C:\Users\ryzen\Downloads\Antigravity\wdo win pair trading\gex\docs\jumba_tradingview.pine
  WIN$N: 34 niveis
  US500: 34 niveis
  ...
  Total: 566 niveis
Salvo em: C:\Users\ryzen\Downloads\Antigravity\rastro_irado\frontend\src\gexLevels.js
============================================================ 
[17/06/2026  7:58:35,89] GEX Daily Update FINALIZADO com sucesso! 
============================================================ 
```

---

## 5. Como Executar Manualmente

Caso precise forçar uma atualização imediata fora do horário agendado:

### Execução Completa (GEX + Sincronização)
Abra o terminal (PowerShell ou Command Prompt) e execute:
```bash
cd "c:\Users\ryzen\Downloads\Antigravity\wdo win pair trading"
.\GEX_DAILY_SCHEDULED.bat
```

### Execução Apenas da Sincronização (Pine -> Dashboard JS)
Caso o arquivo `.pine` já tenha sido atualizado e você só queira refletir os níveis no dashboard do IRAI:
```bash
cd "c:\Users\ryzen\Downloads\Antigravity\rastro_irado"
python scripts/sync_gex_to_irai.py
```
