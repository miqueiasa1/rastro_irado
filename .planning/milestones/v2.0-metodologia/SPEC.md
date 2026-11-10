# SPEC — IRAI v2.0: Metodologia Preditiva Calibrada do Rastro

**Versão:** 1.1 (incorpora as decisões D1–D4 de 10/11/2026 do PRD §12.1; Q5 em aberto)
**Status:** Planejado — nenhuma fase iniciada
**Milestone:** v2.0 (fases 15–22) · Requisitos em [`PRD.md`](./PRD.md) · Fases em [`PHASES.md`](./PHASES.md)
**Data:** 2026-11-10

> **Decisões aplicadas (10/11/2026):** D1 horizonte de produto = 60 min (fechamento só avaliação); D2 só WIN$N e WDO$N; D3 no-go → sem rótulos direcionais, P atual como "Leitura do dia (nowcast)"; D4 `p_fwd_60` e card de assertividade no site público, deploy só com aprovação explícita.

> Números **medidos** vêm da auditoria de 10/11/2026 (snapshots ao vivo de 03/08 a 10/11/2026, 65 pregões). Itens **[META]** são alvos. Caminhos citados existem no repo hoje, salvo quando marcados **(novo)**.

---

## 0. Princípios

1. **Causalidade estrita:** todo valor usado no instante t é função apenas de dados com timestamp ≤ t (e de parâmetros treinados só com pregões anteriores à sessão de t).
2. **Imutabilidade:** parâmetros, snapshots fechados e relatórios nunca são apagados nem reescritos.
3. **Medir antes de exibir:** nada aparece como "probabilidade" ou "acurácia" sem métrica fora da amostra que o sustente.
4. **Aditivo e reversível:** migrações só adicionam tabelas/colunas; cada mudança de comportamento tem flag.
5. **Regras do `.agents/AGENTS.md` continuam valendo** (pair spread visível, sync, anti-reset de zoom, Regra 4 de pré-mercado). Este milestone propõe uma **Regra 5** (parâmetros versionados, nunca apagados).

---

## 1. Arquitetura atual (resumo da auditoria)

```
MT5 (XP/Tickmill/Axi) ──collector 20s──▶ market_bars (SQLite WAL, relógio broker NY+7)
scripts/calibrate_universal.py (força bruta, retorno do pregão inteiro, 252 pregões)
        └─ DELETE + INSERT ─▶ model_params (β, σ diário, α∈[1;3,5], b∈[±0,25]) + asset_models.accuracy (in-sample)
backend/irai/engine.py compute_from_db(v2):
   rᵢ,ₜ desde 09:00 → zᵢ = rᵢ/σᵢ (sem √t) → Kalman nos β (clamp [0,3β]) → P = sigmoid(α Σ βᵢ zᵢ + b)
   → veredito 65/55/45/35 → NWE (bw 8, 3×MAE) + resíduos (Z rastro, pair Z)
backend/workers/collector.py persist_live_snapshots_cycle → irai_live_snapshots (fechadas: INSERT OR IGNORE)
backend/api/main.py /api/irai/series (mode=live lê snapshots; senão recalcula com params ATUAIS)
scripts/firebase_sync.py → RTDB → site público
frontend: SignalGauge / signalProcessor (60/40 + NWE) / TVNweChart (estrelas) / Overview ("acc NN%")
GEX (projeto WDO) → scripts/sync_gex_to_irai.py → gex_levels → apenas linhas no gráfico
```

Defeitos endereçados: alvo contemporâneo; probabilidade não calibrada; bug β/z; seleção sem OOS; σ sem √t; recalibração destrutiva (repaint de 34–39% das barras ao recalcular datas anteriores a 28/10); marcadores sem edge; GEX fora do modelo.

---

## 2. Arquitetura alvo

```
                         ┌───────────────────── model registry (novo) ─────────────────────┐
                         │ model_versions (imutável) ◀── scripts/train_forecast.py (novo)  │
                         │ model_params (+version_id) ◀── scripts/calibrate_universal.py   │
                         └───────────────┬─────────────────────────────────────────────────┘
market_bars ─┬─▶ backend/irai/features.py (novo, causal) ─▶ backend/irai/forecast.py (novo)
gex_levels ──┘                                                │  p_fwd_60, p_fwd_close, lo/hi
             └─▶ backend/irai/engine.py (P nowcast, versão vigente, β/z corrigido)
                                   │
                      collector.persist_live_snapshots_cycle
                                   ▼
                 irai_live_snapshots (+model_version, +forecast_version, +p_fwd_*)
                                   │
   scripts/eval_assertividade.py (novo) ──▶ forecast_eval_daily (novo) + data/reports/assertividade_*.md
                                   │
        backend/api/main.py: /api/irai/series, /api/eval/assertividade (novo), /api/model/versions (novo)
                                   │
              frontend (flag forecast_ui) ◀── firebase_sync (campos novos fluem por série)
```

Componentes novos:

| Módulo | Responsabilidade |
|---|---|
| `backend/irai/features.py` (novo) | Construção causal de features a partir de `market_bars` e `gex_levels`; mesma função para treino e ao vivo |
| `backend/irai/forecast.py` (novo) | Carrega a versão vigente/shadow, faz inferência, calibração e faixa de incerteza |
| `backend/irai/model_registry.py` (novo) | CRUD imutável de versões; resolução "vigente em D"; promoção de status |
| `backend/eval/metrics.py` (novo) | AUC, Brier, BSS, ECE, confiabilidade, bootstrap por pregão |
| `scripts/train_forecast.py` (novo) | Walk-forward/purged CV, seleção de hiperparâmetro, calibração, registro de versão |
| `scripts/eval_assertividade.py` (novo) | Harness reprodutível sobre snapshots imutáveis |

---

## 3. Definição formal do alvo

Notação: sessão s (pregão B3, 09:00–18:25 horário de Brasília, convertida do relógio do broker por `backend/timeconv.py`); barras M5 indexadas k = 0..Kₛ−1 pela abertura; Cₛ,ₖ = fechamento da barra k; o instante de decisão da barra k é o seu fechamento (abertura + 5 min).

Retorno futuro:

- **Primário (produto, D1):** 60 min: `y60(s,k) = log(C(s,k+12) / C(s,k))`, definido só se k+12 ≤ Kₛ−1 (não cruza o fim do pregão).
- **Secundário (só avaliação):** fechamento: `yclose(s,k) = log(C(s,Kₛ−1) / C(s,k))`, definido para k < Kₛ−1. Treinado e medido no mesmo protocolo, gravado em `p_fwd_close*`, nunca exibido nem usado no corte.

Alvos do v2.0 (D2): só `WIN$N` e `WDO$N`. Os demais alvos não recebem modelo `forecast`.

Rótulo binário: `Y = 1[y > 0]`; amostras com `y = 0` (comum no WIN pelo tick de 5 pts) ficam **fora** do treino e da métrica principal e são reportadas à parte (taxa de empates).

Variante opcional (REQ-F08): três classes com zona morta |y| ≤ 0,5·σ̂ₕ, onde σ̂ₕ é o desvio do retorno de horizonte h nas 60 sessões anteriores.

Probabilidade publicada: `p_fwd_h(s,k) = P(Y=1 | ℱ(s,k))`, onde ℱ(s,k) contém apenas barras com abertura ≤ k (fechadas) e parâmetros da versão vigente em s.

Horizontes de 5–30 min ficam só no relatório (o protótipo não mostrou sinal em 30 min: WIN 0,501; WDO 0,514).

---

## 4. Features causais e normalizações

### 4.1 Regras

- **R1:** estatísticas de escala (σ) vêm de janela **trailing de sessões anteriores** (padrão: 60 sessões até s−1), nunca da amostra inteira. (O protótipo usou constantes de escala globais; como o `StandardScaler` é reajustado no treino, o efeito é só de escala, mas a implementação deve usar σ trailing.)
- **R2:** retornos parciais são normalizados por √n (n = barras desde a abertura), eliminando a compressão de manhã e a saturação à tarde.
- **R3:** fatores que ainda não negociaram na sessão contribuem 0 (Regra 4 do `AGENTS.md`); forward-fill máximo de 12 barras (60 min); além disso, `NaN` → 0 com flag de staleness.
- **R4:** padronização (`StandardScaler`) e qualquer β de resíduo são ajustados **só no treino** de cada dobra e gravados na versão.
- **R5:** teste de **invariância por truncamento**: para amostras aleatórias (s,k), `features(bars até k)` = `features(todas as barras)[k]` com tolerância 1e-12.

### 4.2 Conjunto inicial (v2.0-a)

Para alvo T com fatores F (WIN: WDO, DI1, US500, USTEC, VIX, DXY, USDMXN, XAUUSD, BRENT, CHINA50; WDO: WIN, DI1, US500, DXY, USDMXN, VIX, EURUSD, XAUUSD, BRENT, USDJPY — conjunto do protótipo, fixo e econômico, sem força bruta):

| Feature | Definição | Normalização |
|---|---|---|
| `own_rtd_z` | log(C(s,k)/O(s,0)) do alvo | ÷ (σ̂₅ₘ · √(k+1)) |
| `own_r{1,3,6,12}` | log-retorno das últimas h barras | ÷ vol realizada (24 barras, mín. 6) |
| `f_rtd_z[f]` | retorno de f desde a abertura da B3 | ÷ (σ̂₅ₘ,f · √(k+1)) |
| `f_r3[f]` | retorno de f nas últimas 3 barras (lead-lag) | ÷ σ̂₅ₘ,f |
| `resid` | `own_rtd_z − Σ γ_f f_rtd_z[f] − γ₀` | γ ajustado no treino da dobra |
| `nwe_pos` | (C − centro NWE) / (3·MAE) | kernel causal de `backend/irai/nwe.py` (bw 8, lookback 95) |
| `rvol` | vol realizada 24 barras ÷ σ̂₅ₘ | — |
| `tod`, `tod²` | minutos desde 09:00 ÷ 565 | — |
| `gap_z` | log(O(s,0)/C(s−1,último)) | ÷ σ̂ diário |

### 4.3 Candidatas (testadas na fase 20)

| Feature | Definição | Regra as-of |
|---|---|---|
| `gex_dist_wall` | (C − wall mais próxima) ÷ (σ̂ diário · O) | run de `gex_levels` com publicação < 09:00 de s |
| `gex_side`, `gex_wall_type` | acima/abaixo; `wall`/`mid_wall` | idem |
| `flow_cdn` | `cum_delta_norm` do engine | só barras fechadas |
| `p_nowcast` | P atual (pós-correção β/z) como feature | versão vigente em s |

---

## 5. Modelo

### 5.1 Base

Regressão logística com penalidade L2 (`sklearn.linear_model.LogisticRegression`, `solver=lbfgs`), pipeline `StandardScaler → LogisticRegression`. Hiperparâmetro C ∈ {0,01; 0,03; 0,05; 0,1; 0,3} escolhido por **Brier médio** num walk-forward interno ao treino. O protótipo usou C = 0,05 fixo.

### 5.2 Alternativas (REQ-F08)

- Gradient boosting raso (`HistGradientBoostingClassifier`, profundidade ≤ 3, `max_iter` ≤ 200, restrições monotônicas em `resid` e `own_rtd_z` quando fizer sentido).
- Ordinal/3 classes com zona morta.
- Adoção somente com ΔBSS > 0 e IC 95% de ΔBSS acima de 0 no mesmo protocolo.

### 5.3 Incerteza

Ensemble de B = 50 modelos reajustados em reamostras bootstrap **por pregão** do treino; `p_lo`/`p_hi` = percentis 10/90 das previsões calibradas; `p` = média calibrada. Custo de inferência: 50 produtos escalares por barra (desprezível).

### 5.4 Limiares de exibição

Por alvo, só para 60 min (D1), gravados na versão: `thr_up` = menor limiar u ≥ 0,5 tal que, no OOS do treino, as barras com `p_lo > u` tenham frequência de alta ≥ u e n ≥ 200; análogo para `thr_down`. Sem limiar válido → apenas "neutro". Substitui 60/40 e 65/35 fixos.

**Modo sem previsão (D3, REQ-U07):** com `asset_models.forecast_ui='nowcast_only'` (ver §10.5), o ativo não exibe rótulo direcional nenhum (nem limiares do forecast, nem o veredito 65/55/45/35 do P atual). O gauge mostra o P atual como "Leitura do dia (nowcast)".

---

## 6. Validação: walk-forward com purge e embargo

### 6.1 Split externo (avaliação)

- Blocos mensais de teste M₁..Mₙ. Para cada Mᵢ: treino = sessões com data < início(Mᵢ) − embargo; teste = sessões de Mᵢ.
- **Purge:** remove do treino qualquer amostra cujo rótulo termine em ou após o início do teste (com alvo intradiário, equivale a remover sessões ≥ início do teste).
- **Embargo:** 1 sessão antes do teste (padrão) e 2 sessões no CV interno.
- Janela: expansiva (padrão) ou móvel de 250 sessões (configurável); ambas reportadas na fase 18.

### 6.2 CV interno (hiperparâmetro e calibração)

Purged K-fold por sessão (K = 5) **dentro do treino**, com embargo de 2 sessões entre as dobras; o calibrador é ajustado nas previsões out-of-fold do treino.

### 6.3 Dependência e incerteza

Rótulos de 60 min se sobrepõem (cada barra compartilha 11 barras de janela com a vizinha); ICs sempre por **bootstrap de pregões** (B = 1000 no relatório, 300 no CI rápido). Opcional: pesos de unicidade.

### 6.4 Pré-registro

Cada execução da fase 18/20 grava, antes de rodar, `config.yaml` (features, C, janelas, alvos) com hash; o relatório lista **todas** as configurações tentadas.

---

## 7. Calibração de probabilidade

- Platt (sigmoide sobre o logit) por padrão; isotônica se n de treino ≥ 20.000 amostras e se reduzir o ECE no CV interno.
- Métricas: Brier, BSS = 1 − Brier/Brier(taxa-base do treino), ECE (10 bins de igual frequência), inclinação e intercepto de confiabilidade (meta de inclinação entre 0,7 e 1,3 **[META]**).
- **P atual (nowcast) corrigido:** após REQ-M01, α e intercepto são reestimados por logística sem clamp; o guard rail [1; 3,5] e [±0,25] de `scripts/calibrate_universal.py` é removido (o nowcast deixa de alegar ser probabilidade direcional, mas a escala fica estatisticamente consistente).

---

## 8. Correção do bug de unidade β/z (REQ-M01)

Hoje (`scripts/calibrate_universal.py` e `engine.compute`): β estimado em `y_ret = Xβ` (retornos brutos) e score = Σ βᵢ·(rᵢ/σᵢ). O preditor linear correto é Σ βᵢ·rᵢ = Σ (βᵢσᵢ)·zᵢ.

Medido na janela de calibração (252 pregões até 28/10): WDO acc 73,0% (Σβr) vs. 64,7% (Σβz), AUC 0,798 vs. 0,742; WIN AUC 0,792 vs. 0,783.

Correção (escolher A; B como alternativa):

- **A (mínima):** gravar `w_z,i = βᵢ·σᵢ` como peso do score; score = Σ w_z,i·zᵢ; refazer a logística de α/b sobre esse score.
- **B:** reestimar diretamente em z (`X_z = X/σ`), com as mesmas restrições de sinal.

Kalman (`backend/irai/engine.py`, bloco v2): a observação é em %, e os β do estado estão no espaço bruto; aplicar a mesma conversão (`weight_z = βᵢ·σᵢ`, com σ em fração: o β do Kalman é razão de retornos e não depende da unidade %) **antes** do clamp; documentar a unidade em comentário. `obs_cov` (padrão 1e-3 %²) passa a ser estimado da variância do resíduo intradiário no treino e gravado na versão (`kalman_obs_cov`); `trans_cov` idem. Teste de equivalência numérica entre A e B em dados sintéticos.

---

## 9. Versionamento imutável de parâmetros (REQ-P)

### 9.1 Modelo de dados

- Nova tabela `model_versions` (seção 10). Toda calibração (`calibrate_universal.py`) e todo treino (`train_forecast.py`) criam **uma linha nova**; `model_params` ganha `version_id`.
- `save_to_db` em `scripts/calibrate_universal.py`: **remover o `DELETE`** (linhas do bloco "[purge]"); inserir com `version_id` novo; status inicial `shadow`.
- Vigência: `effective_from` (sessão a partir da qual vale), `effective_to` (NULL = vigente). Promover = fechar a vigência da `active` anterior e abrir a da nova (única operação de UPDATE permitida, em `status`/`effective_to`).

### 9.2 Resolução no engine

`IRAIEngine._load_params` passa a carregar por `(slug, session_date)`: `SELECT ... FROM model_versions WHERE slug=? AND kind='nowcast' AND status IN ('active','retired') AND effective_from <= ? AND (effective_to IS NULL OR effective_to > ?)`. Fallback legado: sem versão registrada → comportamento atual (MAX(effective_from)), com `model_version='legacy'` no snapshot.

### 9.3 Correção do repaint

- `/api/irai/series?mode=recalculated` e o fallback de datas sem snapshot passam a recalcular com a versão vigente naquela data.
- O estado do Kalman (`kalman_state`) ganha `model_version`; `load_kalman_state` só aceita estado da mesma versão (hoje descarta só por dimensão).
- Migração do legado: versão sintética `legacy-pre-2026-10-28` não é reconstruível (os parâmetros antigos foram apagados); para esses pregões, a verdade é o snapshot. O recálculo de datas anteriores à primeira versão registrada fica **bloqueado** (retorna snapshot ou erro explícito).

### 9.4 Regra 5 (proposta para `.agents/AGENTS.md`)

"Parâmetros de modelo nunca são apagados. Recalibrar = nova versão. Recalcular uma data passada = usar a versão vigente naquela data."

---

## 10. Mudanças de schema SQLite (migrações aditivas)

Aplicadas em `backend/db.py::init_db` com o guard idempotente `_add_column` (fase 4) e `CREATE TABLE IF NOT EXISTS`. Nenhuma coluna é removida ou renomeada.

```sql
-- 10.1 Registro de versões (novo)
CREATE TABLE IF NOT EXISTS model_versions (
    version_id      TEXT PRIMARY KEY,          -- ex.: 'win-nowcast-20261110T1900Z'
    slug            TEXT NOT NULL,             -- 'win', 'wdo'
    kind            TEXT NOT NULL CHECK (kind IN ('nowcast','forecast')),
    status          TEXT NOT NULL CHECK (status IN ('shadow','active','retired','rejected')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    effective_from  TEXT,                      -- session_date (YYYY-MM-DD)
    effective_to    TEXT,
    train_start     TEXT, train_end TEXT,
    config_json     TEXT NOT NULL,             -- features, C, janelas, horizontes, limiares
    artifact_json   TEXT NOT NULL,             -- coeficientes, scaler, calibrador, ensemble
    metrics_json    TEXT,                      -- métricas OOS do walk-forward
    code_git_sha    TEXT,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_mv_slug_kind ON model_versions(slug, kind, effective_from);

-- 10.2 Parâmetros do nowcast ligados à versão
ALTER TABLE model_params ADD COLUMN version_id TEXT;          -- NULL = legado

-- 10.3 Snapshots
ALTER TABLE irai_live_snapshots ADD COLUMN model_version TEXT;
ALTER TABLE irai_live_snapshots ADD COLUMN forecast_version TEXT;
ALTER TABLE irai_live_snapshots ADD COLUMN p_fwd_60 REAL;
ALTER TABLE irai_live_snapshots ADD COLUMN p_fwd_60_lo REAL;
ALTER TABLE irai_live_snapshots ADD COLUMN p_fwd_60_hi REAL;
ALTER TABLE irai_live_snapshots ADD COLUMN p_fwd_close REAL;      -- secundário, só avaliação (D1)
ALTER TABLE irai_live_snapshots ADD COLUMN p_fwd_close_lo REAL;
ALTER TABLE irai_live_snapshots ADD COLUMN p_fwd_close_hi REAL;
ALTER TABLE irai_live_snapshots ADD COLUMN feature_stale INTEGER DEFAULT 0;

-- 10.4 Kalman ligado à versão
ALTER TABLE kalman_state ADD COLUMN model_version TEXT;

-- 10.5 Flags por alvo
ALTER TABLE asset_models ADD COLUMN forecast_mode TEXT DEFAULT 'off';   -- off|shadow|active
ALTER TABLE asset_models ADD COLUMN forecast_ui TEXT DEFAULT 'off';    -- off|on|nowcast_only (D3); diferente de off só para WIN$N/WDO$N (D2)

-- 10.6 Métricas diárias (novo)
CREATE TABLE IF NOT EXISTS forecast_eval_daily (
    eval_date     TEXT NOT NULL,     -- data do relatório
    target        TEXT NOT NULL,
    model         TEXT NOT NULL,     -- 'nowcast' | 'forecast' | 'baseline_momentum' | ...
    version_id    TEXT,
    horizon       TEXT NOT NULL,     -- '5m','15m','30m','60m','close','nowcast'
    window_sessions INTEGER NOT NULL,
    n             INTEGER, auc REAL, auc_lo REAL, auc_hi REAL,
    brier REAL, bss REAL, ece REAL, hit REAL,
    config_hash   TEXT, code_git_sha TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (eval_date, target, model, horizon, window_sessions)
);
```

Gravação de snapshots (`backend/db.py::save_live_snapshots`): estender `_snap_to_tuple` e `COLUMNS_SQL` com os campos novos; manter a política "fechadas = INSERT OR IGNORE, última = INSERT OR REPLACE".

---

## 11. API (`backend/api/main.py`)

| Endpoint | Mudança |
|---|---|
| `GET /api/irai/series` | Cada barra ganha `model_version`, `forecast_version`, `p_fwd_60`, `p_fwd_60_lo`, `p_fwd_60_hi`, `p_fwd_close`, `p_fwd_close_lo`, `p_fwd_close_hi` (secundários, só para avaliação; o frontend não os exibe), `feature_stale` (`null` se ausente). `summary.accuracy` mantido até a fase 22 como **deprecated**; novo `summary.eval` com métricas OOS. `mode=recalculated` usa a versão vigente da data (§9.3). |
| `GET /api/irai/targets` | Adiciona `calibrated` (bool, independente de `accuracy`), `forecast_mode`, `forecast_ui`, `thresholds` (60 min). `forecast_mode`/`forecast_ui` diferentes de `off` só para `WIN$N`/`WDO$N` (D2, REQ-A05). |
| `GET /api/irai/overview` | O filtro `if not t.get("accuracy"): continue` (em `_get_overview_data_sync`) passa a usar `calibrated`. |
| `GET /api/eval/assertividade?target=&window=20` **(novo)** | Lê `forecast_eval_daily`: por horizonte e modelo, n, AUC (IC), BSS, ECE, hit e tabela de confiabilidade. |
| `GET /api/model/versions?target=` **(novo)** | Lista versões (sem `artifact_json`), status, vigência e métricas. |
| `GET /api/health` | Adiciona `forecast: {active_version, shadow_version, last_inference_ts, inference_ms_p95, stale_features}`. |

Contrato documentado em `docs/API.md`.

---

## 12. Frontend (`frontend/src`)

| Arquivo | Mudança |
|---|---|
| `components/SignalGauge.jsx` | Com `forecast_ui=on`: um mostrador de P(↑ 60 min) com faixa `p_lo–p_hi` e rótulo por `thresholds` da API (sem mostrador de fechamento, D1); antes do corte, selo "em avaliação". Com `nowcast_only` (D3) ou sem flag: P atual rotulado "Leitura do dia (nowcast)"; com `nowcast_only`, sem COMPRA/VENDA nem veredito. |
| `utils/signalAnalyzer.js` | `calculateConviction` deixa de usar `accuracy`; convicção = largura/posição da faixa em relação ao limiar. `calculateStability` mantido. |
| `Overview.jsx` | Remover "acc NN%" (linha que monta `acc {accuracy...}`); exibir AUC/BSS OOS da janela de 20 pregões quando disponível. |
| `App.jsx` (tooltip `CustomTooltip`) | Trocar `pUp >= 60 / <= 40` pelos limiares da API; mostrar `p_fwd_60` e faixa quando houver; em `nowcast_only`, sem rótulo direcional. |
| `utils/signalProcessor.js` | Limiares 60/40 parametrizados; marcadores sem edge medido atrás do toggle "experimental" (padrão desligado). |
| `components/TVNweChart.jsx` | Estrelas/pontos atrás do mesmo toggle; manter regras de sync/zoom do AGENTS.md. |
| `components/TVProbabilityChart.jsx` | Série de `p_fwd_60` com banda `lo/hi` (área) e linha 50%. |
| `components/ReliabilityCard.jsx` **(novo)** | Card de assertividade: AUC, BSS, ECE e mini curva de confiabilidade; estado "degradado" se BSS rolante < −0,02 **[META de alarme]**. |
| `hooks/useIraiData.js` | Buscar `/api/eval/assertividade` (local) ou o nó `eval/<target>` do RTDB (site público, D4); tolerar campos ausentes em snapshots antigos e `eval` ausente. |

---

## 13. Harness de avaliação e relatório contínuo

`scripts/eval_assertividade.py` **(novo)**, também importável por `backend/eval/metrics.py`:

1. **Fonte:** cópia consistente do banco via `sqlite3.Connection.backup` para `%TEMP%` (ou `file:...?mode=ro`); nunca escreve no banco de produção, exceto no modo `--persist`, que grava somente em `forecast_eval_daily`.
2. **Seleção:** barras de `irai_live_snapshots` com `is_ghost=0`, dentro da sessão, `created_at` ≤ `ts + live_max_lag` (padrão 10 min; conversão de fuso por `backend/timeconv.py`).
3. **Retornos futuros:** a partir de `market_bars` M5 do alvo (fechamento da barra k → k+h no mesmo pregão).
4. **Métricas:** §7 + baselines (taxa-base, momentum, contrarian) + marcadores (§12) + segmentações por hora, mês e tercil de vol.
5. **Saída:** `data/reports/assertividade_YYYYMMDD.md` (tabelas) + `forecast_eval_daily` + JSON para a API; cabeçalho com git SHA, hash da config, seed e intervalo de dados.
6. **Reprodutibilidade:** seeds fixas; teste de regressão que reproduz a baseline da auditoria (WIN AUC 60 min 0,474 ± 0,005; WDO 0,486 ± 0,005; WIN nowcast 0,711 ± 0,005).
7. **Agendamento:** após o fechamento, como etapa de `scripts/daily_maintenance.py` (tarefa "IRAI Daily Maintenance", seg–sex 19:15) ou tarefa própria às 18:45; a decisão fica para a fase 15.

Backtest de treino (`scripts/train_forecast.py`) usa o mesmo módulo de métricas e o mesmo split, e grava o relatório walk-forward em `data/reports/forecast_wf_<version>.md`.

---

## 14. Inferência ao vivo e shadow mode

- `backend/workers/collector.py::persist_live_snapshots_cycle`: após `engine.compute_from_db(...)`, se `forecast_mode != 'off'`, chama `forecast.predict_session(target, session_date, bars)` e funde `p_fwd_*` em `series_data` antes de `save_live_snapshots`.
- `forecast.predict_session` recalcula as features da sessão inteira de forma causal (barata, porque o pregão tem cerca de 113 barras M5) e devolve apenas valores para barras fechadas + a barra em formação; a barra em formação segue a política de REPLACE.
- Falha no forecast **nunca** derruba o ciclo: `try/except` com log e `feature_stale=1`.
- `shadow`: grava, não exibe; `active`: grava e a API sinaliza `forecast_ui`.

---

## 15. Firebase: sync, RTDB e regras (decisão D4)

O site público passa a mostrar `p_fwd_60` com faixa e o card de assertividade (REQ-S01–S06).

- **Séries:** `scripts/firebase_sync.py` já envia cada barra da série inteira, removendo só `factors` e `stale_factors` das barras fechadas. Os campos novos fluem sem mudança estrutural, mas o sync passa a **remover também `p_fwd_close`, `p_fwd_close_lo` e `p_fwd_close_hi`**, que são só de avaliação (D1). `clean_for_firebase` deve aceitar `None` (verificar na fase 19).
- **`targets`:** adicionar `calibrated`, `forecast_mode`, `forecast_ui` e `thresholds` (60 min); manter `accuracy` até a fase 22 para o site antigo não quebrar.
- **Novo nó `eval/<target>`** (só `WIN$N` e `WDO$N`): resumo do card gerado de `forecast_eval_daily` após o relatório diário. Conteúdo: `{generated_at, window_sessions, horizons: {"60m": {...}, "nowcast": {...}}, degraded, forecast_version}`, em que cada horizonte traz `n, auc, auc_lo, auc_hi, bss, ece, base_rate, reliability[10]`. Payload estimado: menos de 2 KB por alvo **[estimativa]**.
- **Regras (`frontend/database.rules.json`):** hoje a raiz é `.read/.write: false` com leitura pública nó a nó (`dates`, `overview`, `targets`, `series/$target`, `summaries/$target`, `history/$target`, `garch/$target`, `health`, `health_watchdog`, `last_update`, `pine_vault/$key`). Adicionar só `"eval": { "$target": { ".read": true } }`, sem nenhum `.write`. Teste: o emulador ou o simulador de regras confirma leitura anônima de `eval/WIN$N` e escrita negada.
- **Deploy (REQ-S06):** `firebase deploy` de regras ou hosting, e a primeira execução do sync que cria `eval`, só com aprovação explícita do usuário, registrada no SUMMARY da fase. Os agentes entregam diff e checklist; não fazem deploy.
- Retenção de 60 dias no RTDB (`scripts/daily_maintenance.py`) continua igual.

---

## 16. Papel do GEX como feature testável

- **Fonte:** `gex_levels(session_date, target, run_name, levels_json, updated_at)`, alimentada por `scripts/sync_gex_to_irai.py` a partir do projeto WDO. Medido hoje: WIN$N com 132 sessões (11/05–10/11/2026, 100 runs distintos); runs recentes publicados por volta das 07:30 (horário de Brasília).
- **As-of:** usar o último run com `updated_at` (UTC) < 09:00 de Brasília da sessão s; se a sessão tiver só runs posteriores ou o histórico vier de backfill (`scripts/backfill_gex_history.py`), marcar `gex_asof_ok=0` e excluir do treino da feature.
- **Features:** §4.3, em unidades de σ diário; nenhuma informação intradiária do GEX além dos níveis do dia.
- **Aceite (REQ-G04):** ΔBSS OOS > 0 com IC 95% acima de 0 em ≥ 40 pregões com `gex_asof_ok=1`; senão, a feature não entra na versão.
- O GEX continua desenhado no gráfico independentemente do resultado.

---

## 17. Testes

Novos testes em `tests/` (pytest, padrão dos existentes como `tests/test_live_snapshots.py`):

| Teste **(novo)** | Verifica |
|---|---|
| `tests/test_features_causal.py` | Invariância por truncamento (R5); σ trailing; fatores sem negócio = 0 |
| `tests/test_walkforward_split.py` | Nenhuma sessão de teste ou embargo no treino; purge correto |
| `tests/test_eval_metrics.py` | AUC/Brier/ECE contra implementações de referência; bootstrap por pregão determinístico com seed |
| `tests/test_eval_baseline.py` | Reprodução da baseline da auditoria com tolerância ±0,005 (usa fixture de banco reduzida) |
| `tests/test_model_registry.py` | Calibrar duas vezes não apaga nada; vigência resolve a versão certa por data; promoção fecha a anterior |
| `tests/test_unit_fix.py` | Score β·σ·z == β·r; regressão da acurácia (WDO 64,7% → 73,0% no fixture da janela de calibração) |
| `tests/test_repaint_versioned.py` | Recalcular sessão com a versão vigente reproduz o snapshot fechado (REQ-N05) |
| `tests/test_forecast_snapshot.py` | Colunas novas gravadas; fechadas imutáveis; falha do forecast não derruba o ciclo |
| `tests/test_api_eval.py` | Contratos de `/api/eval/assertividade` e `/api/model/versions`; compat de séries antigas |

Testes existentes que devem continuar verdes: `test_engine.py`, `test_engine_session_invariants.py`, `test_live_snapshots.py`, `test_nwe_gap.py`, `test_nwe_parity.py`, `test_timeconv.py`, `test_forex_basket.py`, `test_api_nwe.py`, `test_db_robustness.py`.

Frontend: verificação manual (UAT) em `http://localhost:5175` com e sem flag, seguindo as regras do AGENTS.md; `npm run lint`.

---

## 18. Observabilidade

- Log estruturado por ciclo: `target`, `version`, `inference_ms`, `n_bars`, `stale_features`.
- `/api/health.forecast` (§11) e verificação no `scripts/health_watchdog.py`: alerta se `p_fwd_*` faltar > 2 barras seguidas em pregão aberto, ou se `inference_ms_p95` > 1000 **[META]**.
- Drift: BSS rolante de 20 pregões por alvo/horizonte; abaixo de −0,02 **[META de alarme]**, o card mostra "degradado" e o relatório destaca.
- Cobertura: % de barras do pregão com snapshot ao vivo (medido hoje: 87,6% no WIN entre 03/08 e 10/11) — alvo ≥ 95% **[META]**.

---

## 19. Arquivos e módulos afetados

| Caminho | Tipo | Fase |
|---|---|---|
| `backend/db.py` | migrações §10, `save_live_snapshots`, `load_kalman_state` | 16, 19 |
| `backend/irai/engine.py` | versão vigente, correção β/z, Kalman | 16, 17 |
| `backend/irai/nwe.py` | reuso do kernel causal nas features (sem mudança de fórmula) | 18 |
| `backend/irai/features.py` | novo | 18 |
| `backend/irai/forecast.py` | novo | 19 |
| `backend/irai/model_registry.py` | novo | 16 |
| `backend/eval/__init__.py`, `backend/eval/metrics.py` | novos | 15 |
| `backend/api/main.py` | endpoints §11 | 15, 16, 19, 21 |
| `backend/workers/collector.py` | shadow inference | 19 |
| `backend/workers/recalibrate_kalman.py` | estado por versão | 16, 17 |
| `backend/timeconv.py` | reuso (sem mudança) | — |
| `scripts/calibrate_universal.py` | remover DELETE, versão, β/z, α sem clamp | 16, 17 |
| `scripts/train_forecast.py` | novo | 18 |
| `scripts/eval_assertividade.py` | novo | 15 |
| `scripts/daily_maintenance.py` | etapa de relatório diário | 15 |
| `scripts/health_watchdog.py` | checagem forecast | 19 |
| `scripts/firebase_sync.py` | filtro `p_fwd_close*`, targets, nó `eval` | 19, 21, 22 |
| `frontend/database.rules.json` | regra de leitura `eval/$target` | 21 |
| `frontend/src/components/SignalGauge.jsx`, `TVProbabilityChart.jsx`, `TVNweChart.jsx`, `ReliabilityCard.jsx` (novo) | UI | 17, 21 |
| `frontend/src/utils/signalAnalyzer.js`, `utils/signalProcessor.js` | limiares/convicção | 17, 21 |
| `frontend/src/Overview.jsx`, `App.jsx`, `hooks/useIraiData.js` | acc, tooltip, dados | 17, 21 |
| `tests/*` | §17 | todas |
| `docs/API.md`, `docs/ARCHITECTURE.md`, `.agents/AGENTS.md` (Regra 5) | documentação | 16, 22 |

---

## 20. Decisões de design registradas

| Decisão | Motivo |
|---|---|
| Logística L2 como base, e não boosting | Pouca amostra ao vivo, edge pequeno; coeficientes auditáveis; calibração simples |
| Cesta de fatores fixa e econômica | Força bruta mostrou viés de seleção (73% → 66–68%) |
| 60 min como único horizonte de produto; fechamento só avaliação (D1, 10/11/2026) | Decisão do owner. No protótipo, 60 min teve sinal no WIN (0,540) mas não no WDO (0,503); o corte é por ativo. 5–30 min só no relatório |
| Só WIN$N e WDO$N (D2) | Foco e amostra; os demais alvos ficam para milestone futuro |
| No-go → sem rótulos direcionais (D3) | Não exibir direção sem edge medido |
| Publicar `p_fwd_60` e o card no site público (D4) | Transparência; deploy só com aprovação explícita |
| Shadow ≥ 40 pregões antes do corte | IC por pregão: com 65 pregões o IC de AUC medido tem largura de 0,07 a 0,18 |
| Manter o P atual como nowcast | Explica bem o dia (AUC 0,71–0,75) e tem valor de contexto |
