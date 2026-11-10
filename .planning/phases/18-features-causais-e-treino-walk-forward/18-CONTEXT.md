# Phase 18: Features Causais e Treino Walk-Forward com Calibração - Context

**Gathered:** 2026-11-10
**Status:** Implementada, aguardando aprovação (pesquisa offline; nada ligado ao live)
**Source:** `.planning/milestones/v2.0-metodologia/PHASES.md` (Phase 18), `SPEC.md` §3–7, `PRD.md` REQ-F01–F06, REQ-F08, REQ-N01; pedido do owner de 10/11/2026

<domain>
## Phase Boundary

Construir e avaliar **offline**, só com dados passados, (a) o valor justo do WIN e do WDO a partir da cesta de
referências e (b) o modelo P(↑ 60 min) com walk-forward e calibração. Nada vai para o live nesta fase:
o resultado é um relatório e, se passar nos critérios pré-registrados, uma versão `forecast` em shadow.
</domain>

<intent>
## Intenção do owner (10/11/2026)

"Uma referência melhor que só o dólar": usar DI, dólar e os demais índices da cesta para estimar onde o índice
"deveria" estar (valor justo) e comparar com onde o preço está. O descolamento (gap) seria a oportunidade de entrada,
**se** ele fechar. A pergunta testável é: quando o gap padronizado passa de um limiar, entrar contra o gap dá P&L
positivo **depois dos custos**, de forma estável entre períodos, e o gap ajuda a prever os próximos 60 minutos?
</intent>

<decisions>
## Decisões de desenho

### Valor justo da cesta (`backend/irai/features.py`)
- **Cesta:** WIN ← WDO, DI1, US500, USTEC, VIX, DXY, USDMXN, XAUUSD, BRENT, CHINA50; WDO ← WIN, DI1, US500, DXY,
  USDMXN, VIX, EURUSD, XAUUSD, BRENT, USDJPY (fatores sem dado no período contribuem 0).
- **Painel causal:** retorno log acumulado desde a abertura da B3 (09:00 BRT); fator ancorado na 1ª barra dele com
  abertura ≥ 09:00 (antes disso contribui 0); forward-fill máximo de 12 barras, depois congela (`stale_<f>`).
- **γ por sessão:** OLS sem intercepto (ridge mínimo) sobre incrementos não sobrepostos de 30 min das 60 (ou 20)
  sessões **anteriores**; gap = r_alvo − Σ γ·r_fator (log; > 0 = alvo caro frente à cesta).
- **z causal:** gap ÷ σ_k, com σ_k = RMS do gap no mesmo horário (barra k) nos 60 pregões anteriores (mínimo 20).
  Variante: desvio móvel de 40 barras passadas. Controle: a padronização atual do engine.
- **Par puro:** mesma construção com só WDO↔WIN (β OLS de 20 ou 60 pregões).

### Eventos (`backend/eval/events.py`)
- Evento = 1º cruzamento de |z| ≥ limiar (1,5; 2,0; 2,5) entre 09:30 e 17:00 BRT; direção contrarian (aposta que o gap
  fecha) e, como controle, a favor do gap; saída em 15/30/60 min ou no fechamento; P&L em pontos por contrato,
  líquido de 10 pts (WIN) e 1 pt (WDO) de ida e volta.
- Estatística por pregão: t com variância por cluster de pregão, IC por bootstrap de pregões; BH e Bonferroni sobre
  as 336 combinações de cada parte. Desenho = até 31/12/2025; validação = 2026 (nada escolhido nela).
- "O gap fecha?": |z| < 0,5 em até 60 min / até o fechamento, e a parcela do fechamento que veio do próprio alvo.

### Modelo p_fwd_60 (`scripts/train_forecast.py`, `backend/eval/walkforward.py`)
- Conjuntos: **A** (SPEC §4.2 sem valor justo), **B** (A + z da cesta + z do par), **C** (só valor justo + retorno do
  dia + horário).
- Logística L2; walk-forward mensal a partir de 2025-04 (janela expansiva, embargo de 1 pregão); CV interno purgado
  K = 5 com embargo de 2 pregões escolhe C pelo Brier; Platt (isotônica só com n ≥ 20 mil e ECE menor);
  ensemble bootstrap B = 50 para p_lo/p_hi; limiares de exibição pelo OOF.
- Pré-registro: `.config.json` com hash gravado antes do treino. Critérios (SPEC §9): BSS ≥ 0, ECE ≤ 3 pp, AUC ≥
  protótipo (WIN 0,540; WDO 0,503) e IC da AUC acima de 0,5.

### Harness diário (fase 15)
- Novo bloco: cobertura de |z| > 2 e P&L por evento (líquido) dos z gravados ao vivo (`pair_fixed_z`, `pair_z`,
  `price_diverge_z`), na grade completa de barras do pregão.
</decisions>

<data>
## Dados

- Exportados do `irai_live.db` em modo somente leitura (`mode=ro`, `query_only`) para `%TEMP%\irai_p1718`:
  barras M5 de 23 símbolos (WIN/WDO/DI1 desde 2022; fatores globais desde nov–dez/2024) e 48.976 snapshots WIN/WDO.
- Período útil da pesquisa: 2024-12-02 a 2026-11-10 (482 pregões); modelo: 442 pregões válidos por alvo,
  361 fora da amostra.
</data>
