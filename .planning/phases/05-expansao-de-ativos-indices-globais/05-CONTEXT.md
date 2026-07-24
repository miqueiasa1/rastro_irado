# Phase 5: Expansão de Ativos no Rastro (Índices Globais: DE40, US2000, JP225, CHINA50) - Context

**Gathered:** 2026-07-23
**Status:** Ready for planning
**Source:** Alinhamento direto de produto e expansão de cobertura global de índices

<domain>
## Phase Boundary

Cadastrar, calibrar e habilitar 4 novos índices globais no Rastro Irai:
1. **DAX 40 (`DE40`)** — Alemanha
2. **Russell 2000 (`US2000`)** — EUA Small Caps
3. **Nikkei 225 (`JP225`)** — Japão
4. **China A50 (`CHINA50`)** — China Large-Cap

A fase abrange todo o fluxo ponta a ponta: Coletor de barras MT5, Tabela `asset_models` no SQLite, Calibração Universal de Regressão Ridge/Johansen/Kalman, suporte dinâmico no `backend/irai/engine.py` e exibição no Dashboard React cumprindo todas as diretrizes estritas do `AGENTS.md`.

</domain>

<decisions>
## Implementation Decisions

### 1. Definição e Mapeamento dos Ativos (ASSET-01)
- **`DE40`**: slug=`de40`, display_name=`DAX 40`, icon=`DE`, source=`tickmill`, session=`00:00 - 24:00 UTC`
- **`US2000`**: slug=`us2000`, display_name=`Russell 2000`, icon=`US`, source=`tickmill`, session=`00:00 - 24:00 UTC`
- **`JP225`**: slug=`jp225`, display_name=`Nikkei 225`, icon=`JP`, source=`tickmill`, session=`00:00 - 24:00 UTC`
- **`CHINA50`**: slug=`china50`, display_name=`China A50`, icon=`CN`, source=`tickmill`, session=`00:00 - 24:00 UTC`

### 2. Coleta de Dados MT5 (`backend/workers/collector.py`)
- Adicionar `US2000` e `JP225` ao array `symbols` do terminal Tickmill em `collector.py` (`DE40` e `CHINA50` já estão listados).
- Manter janela de coleta ininterrupta (sessão 24h) para todos os ativos globais da Tickmill.

### 3. Registro e Calibração Universal (ASSET-02)
- Criar script de manutenção/migração para cadastrar os 4 ativos na tabela `asset_models` (`active=1`).
- Executar `scripts/calibrate_universal.py` para cada um dos 4 alvos, forçando seleção de cesta ideal (6 a 8 fatores macro entre ETFs iShares, moedas e commodities).
- Executar `scripts/calc_sigmas.py` para atualizar `divergence_config` (métrica de desvio de divergência de preço).

### 4. Suporte Dinâmico no Backend (`backend/irai/engine.py`)
- Refatorar a consulta SQL em `engine.py` (`_load_params()`) removendo a lista estática hardcoded `WHERE target IN ('WIN$N', ...)` e substituindo por `WHERE active=1`, garantindo que qualquer ativo ativo em `asset_models` seja automaticamente carregado na memória do motor Rastro.

### 5. Frontend React & Regras Estritas de Layout (`AGENTS.md`)
- Incluir os novos ativos no seletor/abas do Dashboard React.
- **ENFORCE RULE 1**: Gráfico de Pair Spread (`TVPairwiseZScoreChart`) deve estar sempre visível para todos os ativos (inclusive quando não houver par ativo ou em pré-mercado).
- **ENFORCE RULE 2**: Manter sincronização de escala horizontal em tempo real entre todos os gráficos de série temporal.
- **ENFORCE RULE 3**: Preservar zoom e posição do usuário sem reset durante atualizações de dados.

### Discretion do Agente
- Ícones visuais / badges de país (DE, US, JP, CN).
- Ordem exata dos ativos no seletor do frontend.
- Scripts auxiliares de semente/migração.

</decisions>

<canonical_refs>
## Canonical References

### Project Rules
- `AGENTS.md` — Regras do Projeto IRAI (Pair Spread sempre visível, sincronização estrita, anti-reset de zoom).

### Collector & Database
- `backend/workers/collector.py` — Configuração de terminais e lista de símbolos por fonte.
- `backend/db.py` — Schema do SQLite, inicialização e helpers.

### Engine & Calibration
- `backend/irai/engine.py` — Motor Rastro (carregamento de ativos em `_load_params()`).
- `scripts/calibrate_universal.py` — Algoritmo de calibração universal força-bruta (Ridge + Johansen + Kalman).
- `scripts/calc_sigmas.py` — Cálculo de limiares de desvio de divergência.

</canonical_refs>

<deferred>
## Deferred Ideas

- **Agrupamento visual por abas de Mercado (B3 / US / Europa / Ásia)**: Pode ser refinado no futuro caso a lista de ativos cresça além de 30 alvos.

</deferred>

---

*Phase: 05-expansao-de-ativos-indices-globais*
*Context gathered: 2026-07-23*
