# Phase 17: Correção β/z e Honestidade do Painel - Context

**Gathered:** 2026-11-10
**Status:** Implementada, aguardando aprovação (sem commit, sem ativação)
**Source:** `.planning/milestones/v2.0-metodologia/PHASES.md` (Phase 17), `SPEC.md` §8, §11, §12, `PRD.md` REQ-M01–M04, REQ-U04, REQ-A04; auditoria do spread (Page "Rastro Irado — auditoria do spread WIN×WDO", 10/11/2026)

<domain>
## Phase Boundary

Corrigir o cálculo do nowcast (unidade β/z, α/intercepto sem clamp, ruído do Kalman) **como versão nova em shadow**,
e deixar o painel honesto (sem COMPRA/VENDA derivado do z do par, sem acurácia in-sample) **atrás da flag
`asset_models.forecast_ui`**, que continua `'off'` em todos os alvos. Com a flag desligada e sem promoção de versão,
o live não muda.
</domain>

<findings>
## O que a auditoria e a fase 15 mostraram

- **Bug de unidade (REQ-M01):** β vem de y = Xβ com retornos brutos, mas o score somava β·z com z = r/σ.
  O preditor da regressão é Σ β·r = Σ (β·σ)·z. Fatores de σ pequeno (moedas) ficavam sub-ponderados e os de σ
  grande (VIX, BTC) sobre-ponderados.
- **Clamp visual:** α preso em [1; 3,5] e intercepto em [±0,25]. Nas versões ativas de 28/10, α = 1,0 (no limite) nos
  dois alvos, e o intercepto do WDO em −0,25 (no limite).
- **Kalman (REQ-M04):** R = 1e-3 (%²) contra uma variância real do resíduo de ~0,57 %² (WIN) e ~0,15 %² (WDO), ou seja,
  R uns 570× (WIN) e 150× (WDO) pequeno demais (a auditoria do spread, com outra janela e outra medida, estimou ~90×; nas duas medidas R fica cerca de duas ordens de grandeza abaixo do real). Com R tão baixo, o filtro persegue o ruído.
- **Spread/par:** WIN×WDO não é cointegrado; o z do par não é um z de verdade (|z| > 2 em 31–36% das barras ao vivo);
  nenhum evento teve vantagem líquida de custos (10 pts WIN, 1 pt WDO). Rotular COMPRA/VENDA a partir desse z é enganoso.
- **"acc" no card:** acurácia in-sample da calibração (direção do fechamento), sem relação com o que o painel parece
  prometer (P de subir).
</findings>

<decisions>
## Decisões de implementação

- Opções numéricas por versão (`model_params` da versão): `unit_fix`, `score_scale`, `kalman_obs_cov`,
  `kalman_trans_cov`. Ausentes = comportamento anterior (`ENGINE_OPTION_DEFAULTS`). Versões legado/adotadas
  continuam calculando exatamente igual.
- Com `unit_fix=1`: contribuição = β·σ·z ÷ `score_scale` (desvio de Σ β·r na janela de calibração), de modo que o
  score fica em "desvios" e o limite de divergência V2→V1 de 3,0 continua comparável.
- α e intercepto: logística (C = 1e6, sem clamp) sobre o score corrigido.
- Kalman: R = variância do resíduo intradiário (retorno % acumulado do alvo − Σ β·retorno % acumulado dos fatores);
  Q = variância por barra da deriva dos β de janelas de 20 pregões (incrementos de 30 min).
- `compute_from_db(model_version_id=...)` força uma versão (qualquer status) para avaliação e não grava estado do Kalman.
- API: `calibrated` = alvo com pesos carregados (não depende de `accuracy`); `forecast_mode`, `forecast_ui` e
  `model_version` em `/api/irai/targets`; `forecast_ui` no card do overview e no `summary` da série.
- Frontend: `utils/honesty.js`; com `forecast_ui ∈ {on, nowcast_only}` o card e os gauges mostram posição descritiva
  do z ("acima/abaixo da ref."), o P(↑) vira "Leitura do dia (nowcast)" ("dia em alta/baixa"), a convicção não usa a
  acurácia e o rodapé não mostra "acc". O gráfico do z do par continua visível (Regra 1).
</decisions>

<out_of_scope>
## Fora do escopo

- Promover as versões corrigidas e ligar `forecast_ui` (dependem de aprovação; ver SUMMARY).
- Alvos além de WIN/WDO (D2): o código vale para todos, mas só WIN/WDO ganharam versões corrigidas.
- Deploy do Firebase (o site público não muda sem deploy aprovado).
</out_of_scope>
