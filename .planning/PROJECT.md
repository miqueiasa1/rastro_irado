# IRAI — Intraday Risk Appetite Index

## What This Is

Dashboard cross-asset em tempo real que estima a probabilidade de o IBOV fechar o dia em alta, inferida a partir do comportamento de ativos que historicamente lideram ou confirmam o movimento do índice brasileiro — sem olhar para o próprio IBOV como fonte primária de sinal. Ferramenta pessoal de suporte à decisão para trading algorítmico e discricionário.

## Core Value

Responder a cada 5 minutos, de forma visual e quantitativa, à pergunta: *"Neste momento do pregão, o resto do mundo está dizendo que o IBOV deveria estar subindo ou caindo?"* — sintetizando 7 fatores em um único número (P_up ∈ 0–100%).

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Calibrar pesos dos 7 fatores cross-asset sobre 1 ano de dados históricos
- [ ] Coletar barras M5 de 3 terminais MT5 (XP, Tickmill) em tempo real
- [ ] Calcular P_up(t) a cada barra de 5 min durante pregão B3
- [ ] Dashboard React exibindo P_up, contribuições por fator, z-scores, regime
- [ ] Validação visual: IBOV real sobreposto à trajetória do IRAI
- [ ] Tolerância a falha: se um terminal cai, sistema continua com stale flags
- [ ] Calibração recalibrável via script offline semanal

### Out of Scope

- Execução automatizada de ordens — IRAI é suporte à decisão, não sistema de trading
- Multi-usuário / SaaS — ferramenta pessoal localhost
- Integração com supervisor SQX dos robôs — possível V2
- Backtest de estratégia baseada no IRAI — pode virar projeto separado
- App mobile — web-first

## Context

### Infraestrutura existente

- **MT5 BR (XP):** `C:\Program Files\MetaTrader 5 Terminal\terminal64.exe` — WIN$N, DOL$N, DI1$N
- **Tickmill:** `C:\Program Files\Tickmill MT5 Terminal\terminal64.exe` — VIX, DXY, BRENT, US500, BTCUSD
- **IC Trading:** `C:\Program Files\IC Trading (MU) MT5 Terminal\terminal64.exe` — NÃO conecta via Python MT5 lib (IPC timeout); descartado no MVP

### Fatores do modelo (5 fatores + 1 alvo)

| # | Fator | Símbolo | Terminal | Papel | Peso M5 | Sinal |
|---|-------|---------|----------|-------|---------|-------|
| 1 | **WIN** (alvo) | `WIN$N` | BR (XP) | Retorno IBOV — variável dependente | — | — |
| 2 | **DOL** | `DOL$N` | BR (XP) | Câmbio BRL/USD | **−0.423** | − ✓ |
| 3 | **DI** | `DI1$N` | BR (XP) | Juros futuros BR | **−0.272** | − ✓ |
| 4 | **VIX** | `VIX` | Tickmill | Vol implícita S&P 500 | **−0.136** | − ✓ |
| 5 | **DXY** | `DXY` | Tickmill | Índice dólar global | −0.026 | − ✓ |
| 6 | **BRENT** | `BRENT` | Tickmill | Petróleo Brent | +0.015 | + ✓ |

**Calibração M5 (2026-04-24):** R²=0.46 | α=1.4154 | Acurácia=67.5%
**Removidos:** US500 e BTCUSD (sinal invertido na calibração D1; baixo poder explicativo)

### Profundidade de dados disponível (M5)

| Símbolo | Barras M5 | Desde | Até | Dias |
|---------|-----------|-------|-----|------|
| WIN$N | 75.000 | 2023-08-17 | 2026-04-24 | 980 |
| DOL$N | 75.000 | 2023-08-25 | 2026-04-24 | 972 |
| DI1$N | 75.000 | 2023-07-06 | 2026-04-24 | 1023 |
| VIX | 75.000 | 2024-08-19 | 2026-04-24 | 613 |
| DXY | 75.000 | 2025-02-26 | 2026-04-24 | 422 |
| BRENT | 75.000 | 2025-02-25 | 2026-04-24 | 423 |
| US500 | 75.000 | 2025-04-02 | 2026-04-24 | 387 |
| BTCUSD | 75.000 | 2025-07-30 | 2026-04-24 | 267 |

**Janela útil M5 (interseção):** ~267 dias (limitada pelo BTCUSD).
**Janela útil D1:** 500 barras (~2 anos) para todos.

### Stack escolhida

- Python 3.11+ (MetaTrader5 lib 5.0.5640)
- FastAPI + Uvicorn (API REST)
- SQLite WAL mode (zero infra)
- React + Vite + Recharts (dashboard — protótipo existente)
- APScheduler (cron de coleta)
- statsmodels / scikit-learn (calibração)

### Experiência do operador

- Opera algoritmicamente via MT5 + SQX com 55+ robôs em produção
- Regime Supervisor já em produção com NSSM Windows Services
- Pair trading dashboard (WDO×WIN) com React + FastAPI em produção
- Familiaridade total com a stack

## Constraints

- **Plataforma:** Windows (MT5 não roda nativo Linux)
- **Custo:** Zero — apenas contas demo/existentes dos brokers
- **MT5 Python lib:** Uma conexão por processo — workers separados
- **IC Trading:** Terminal não conecta via Python lib (IPC timeout) — descartado, EWZ substituído por US500 + BTCUSD
- **Horário:** Pregão B3 10:00–17:55 BRT; fatores INTL podem abrir antes ou depois

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 3 terminais → 2 terminais (XP + Tickmill) | IC Trading não conecta via Python MT5 lib (IPC timeout persistente) | — Pending |
| EWZ substituído por US500 + BTCUSD | Proxy de apetite global a risco + crypto como risk-on asset | — Pending |
| DI1$N como fator de juros | Substitui US10Y (não disponível nos brokers); juros BR é mais direto para IBOV | — Pending |
| BRENT adicionado como fator | Petróleo é relevante para Brasil (Petrobras = 15% do IBOV) | — Pending |
| 1 ano de dados para calibração (D1) | Janela mais longa que os 60d originais do SPEC; M5 limitada a ~267d pelo BTCUSD | — Pending |
| Calibração antes de infra real-time | Validar que o modelo tem poder preditivo antes de investir em pipeline | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-24 after initialization*
