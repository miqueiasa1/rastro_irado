# API Reference — IRAI

Base URL: `http://localhost:8888`

## Endpoints REST

### GET `/api/irai/targets`

Lista todos os targets disponíveis com status de calibração.

**Response:**
```json
{
  "targets": [
    {
      "target": "WIN$N",
      "slug": "win",
      "display_name": "WIN Futures",
      "icon": "🇧🇷",
      "accuracy": 0.68,
      "r_squared": 0.31,
      "calibrated": true,
      "model_version": "win-nowcast-20261028T190510Z",
      "forecast_mode": "off",
      "forecast_ui": "off",
      "session_start_h": 13,
      "session_hours": "13h-21h"
    }
  ]
}
```

Fase 17:
- `calibrated` indica que o alvo tem parâmetros (pesos) carregados; **não depende** de `accuracy`.
- `accuracy` é a acurácia in-sample da calibração (direção do fechamento na janela de treino). Mantida por compatibilidade;
  a UI não a exibe quando `forecast_ui` ≠ `off`.
- `forecast_ui` (`off` | `nowcast_only` | `on`, padrão `off`): modo de exibição do painel. `off` = UI atual;
  `nowcast_only`/`on` = painel honesto (P(↑) rotulado como "Leitura do dia (nowcast)", z do par/macro só descritivo,
  sem COMPRA/VENDA derivado de z e sem "acc"). Muda via `UPDATE asset_models SET forecast_ui = ...` (aprovação do owner).
- `forecast_mode` (`off` | `shadow` | `on`, padrão `off`): reservado para o modelo de 60 min (fase 19).

---

### GET `/api/irai/overview`

Snapshot atual de todos os targets calibrados.

| Parâmetro | Tipo | Default | Descrição |
|-----------|------|---------|-----------|
| `session_date` | string | hoje | Data YYYY-MM-DD |
| `version` | string | `v2` | Motor: `v1` (estático), `v2` (dinâmico), `both` |

**Response:**
```json
{
  "session_date": "2026-06-05",
  "version": "v2",
  "targets": [
    {
      "target": "WIN$N",
      "slug": "win",
      "display_name": "WIN Futures",
      "icon": "🇧🇷",
      "p_up": 62.3,
      "score": 0.5012,
      "verdict": "ALTA",
      "win_return": 0.0034,
      "bars": 48,
      "accuracy": 0.68,
      "forecast_ui": "off",
      "flow_confirms": true,
      "price_diverges": false,
      "price_diverge_z": -0.12,
      "nwe_slope": 0.000042,
      "sparkline": [55.1, 56.2, 58.4, ...],
      "is_preview": false
    }
  ]
}
```

---

### GET `/api/irai/series`

Série IRAI completa para uma sessão + target.

| Parâmetro | Tipo | Default | Descrição |
|-----------|------|---------|-----------|
| `session_date` | string | hoje | Data YYYY-MM-DD |
| `target` | string | `WIN$N` | Target: WIN$N, US500, USTEC, etc. |
| `version` | string | `v2` | Motor: `v1`, `v2`, `both` |

**Response:**
```json
{
  "session_date": "2026-06-05",
  "target": "WIN$N",
  "display_name": "WIN Futures",
  "icon": "🇧🇷",
  "bars": 48,
  "is_b3": true,
  "history_closes": [138450.0, 138500.0, ...],
  "series": [
    {
      "timestamp": "2026-06-05T13:00:00Z",
      "session_date": "2026-06-05",
      "bar_idx": 0,
      "t_frac": 0.0,
      "p_up": 50.0,
      "score": 0.0,
      "verdict": "NEUTRO",
      "verdict_color": "#94A3B8",
      "factors": {"DXY": -0.12, "VIX": 0.34, ...},
      "win_return": 0.0,
      "win_open": 138450.0,
      "win_current": 138450.0,
      "stale_factors": [],
      "bar_delta": 0.0,
      "cum_delta": 0.0,
      "cum_delta_norm": 0.0,
      "flow_confirms": null,
      "price_diverges": false,
      "price_diverge_z": null,
      "pair_z": null,
      "pair_factor": null,
      "pair_beta": null,
      "pair_signal": null,
      "is_preview": false,
      "is_ghost": false
    }
  ],
  "summary": {
    "p_up_min": 38.2,
    "p_up_max": 72.1,
    "p_up_final": 62.3,
    "score_final": 0.5012,
    "verdict": "ALTA",
    "win_return": 0.0034,
    "timestamp": "2026-06-05T17:00:00Z",
    "accuracy": 0.68,
    "forecast_ui": "off"
  }
}
```

---

### GET `/api/irai/dates`

Datas com dados disponíveis.

| Parâmetro | Tipo | Default | Descrição |
|-----------|------|---------|-----------|
| `target` | string | null | Filtrar por target específico |

**Response:**
```json
{
  "dates": ["2026-06-05", "2026-06-04", "2026-06-03", ...]
}
```

---

### GET `/api/irai/current`

Snapshot mais recente (última barra processada).

| Parâmetro | Tipo | Default | Descrição |
|-----------|------|---------|-----------|
| `version` | string | `v1` | Motor |

---

### GET `/api/model/params`

Parâmetros do modelo calibrado para um target.

| Parâmetro | Tipo | Default | Descrição |
|-----------|------|---------|-----------|
| `target` | string | `WIN$N` | Target |

**Response:**
```json
{
  "target": "WIN$N",
  "slug": "win",
  "weights": {"DXY": -0.42, "VIX": 0.31, ...},
  "sigmas": {"DXY": 0.005, "VIX": 0.012, ...},
  "alpha": 1.0,
  "intercept": 0.0,
  "factors": ["dxy", "vix", "btcusd", ...],
  "model_version": "win-nowcast-20261028T190510Z",
  "versioned": true,
  "effective_from": "2026-10-29"
}
```

`model_version` = `"legacy"` e `versioned` = `false` enquanto a migração da fase 16 não estiver aplicada.

---

### GET `/api/model/versions` (fase 16)

Histórico de versões de modelo (sem o artefato com os coeficientes), status e vigência.

| Parâmetro | Tipo | Default | Descrição |
|-----------|------|---------|-----------|
| `target` | string | — | Target (ex.: `WIN$N`). Vazio = todos |

**Response:**
```json
{
  "registry": true,
  "target": "WIN$N",
  "slug": "win",
  "versions": [
    {
      "version_id": "win-nowcast-20261028T190510Z",
      "slug": "win", "kind": "nowcast", "status": "active",
      "fitted_at": "2026-10-28T19:05:10Z",
      "effective_from": "2026-10-29", "effective_to": null,
      "train_start": null, "train_end": null,
      "config": {"adopted_from_legacy": true, "...": "..."},
      "metrics": {"accuracy": 71.4, "r2": 0.3, "n_sessions": 252, "in_sample": true},
      "code_git_sha": "…", "notes": "…"
    }
  ]
}
```

Sem a migração aplicada: `{"registry": false, "versions": []}`. Status: `shadow` (registrada, não usada),
`active` (vigente), `retired` (vigência encerrada em `effective_to`), `rejected`.

**Regras (Regra 5 do `.agents/AGENTS.md`):** recalibrar cria versão nova `shadow`; promoção explícita via
`scripts/model_versions.py promote`; `/api/irai/series?mode=recalculated` usa a versão vigente na data.
Para datas anteriores à primeira versão registrada o recálculo é bloqueado: devolve o snapshot ao vivo
(`recalc_blocked: true`) ou HTTP 409 com `error_code: "model_version_unavailable"`.
Com a migração aplicada, cada barra da série passa a ter `model_version` (ausente/nulo em snapshots antigos).

---

### GET `/api/health`

Status do sistema.

**Response:**
```json
{
  "status": "ok",
  "bars_total": 125000,
  "last_bar": "2026-06-05T17:00:00Z",
  "models_loaded": 11,
  "targets": ["WIN$N", "WDO$N", "US500", ...]
}
```

---

### POST `/api/internal/notify_update`

Endpoint interno chamado pelo collector após inserir novas barras. Invalida caches e dispara broadcast WebSocket.

---

## WebSocket

### WS `/ws/irai`

Push em tempo real de dados IRAI.

**Conexão:** `ws://localhost:8888/ws/irai`

**Configuração (enviar JSON):**
```json
{
  "target": "US500",
  "version": "both"
}
```

**Mensagens recebidas:**
```json
{
  "type": "update",
  "session_date": "2026-06-05",
  "overview": { ... },
  "series": { ... }
}
```

O servidor envia updates automaticamente quando o collector insere novas barras (a cada ~60s).
