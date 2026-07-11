---
title: "Decisão Arquitetural: Sincronia Temporal Contínua (Forward-Fill)"
date: "2026-05-05"
context: "Exploração sobre assimetria de fuso horário entre ativos 24/7 (BTC) e pregões locais (B3 WIN/WDO)"
---

# Sincronia Temporal e Forward-Fill (NWE vs Rastro)

**Problema:**
Ativos da B3 (WIN/WDO) operam em horários rígidos (09h00 às 18h00), enquanto fatores globais e criptomoedas operam 24/7. Isso cria uma dessincronia na precificação de fatores externos (Kalman) durante a noite e problemas de "gap" na plotagem do NWE.

**Decisão Arquitetural:**
Em vez de criarmos lógicas complexas de "horário de corte de sessão" (ex: forçar o NWE a recomeçar às 00h00 Tickmill ou às 09h00 B3), vamos adotar uma abordagem de **Preenchimento Contínuo (Forward-Fill) de Barras**.

**Mecânica:**
1. **Ativos Fechados (Night Session):** Durante a madrugada ou finais de semana, o `collector.py` / `engine.py` deve projetar "barras fantasmas" para o ativo alvo mantendo estritamente o último preço de fechamento (variação de 0%).
2. **NWE Plano:** Como o preço do ativo fechado não oscila nessas barras fantasmas, a janela deslizante do NWE não observa nova volatilidade. As bandas ficarão estaticamente planas e lineares durante todo o overnight.
3. **Kalman Ativo (Rastro Dinâmico):** Embora o ativo alvo esteja "congelado", os fatores macroeconômicos globais (US30, BTC, DXY) continuarão a oscilar e enviar inputs em tempo real para a equação do Kalman. O Rastro (Z-Score e `p_up`) reagirá e absorverá esses choques macro, se movendo durante o overnight.
4. **Resumo Visual:** O eixo do tempo no painel passará a ser único e ininterrupto para todos os ativos. 

Essa abstração remove a necessidade de âncoras locais e unifica o dashboard no tempo global.
