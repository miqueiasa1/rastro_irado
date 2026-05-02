# SPEC â€” IRAI (Intraday Risk Appetite Index)

**Versão:** 3.0 (Pós-Calibração Universal)
**Status:** Operacional
**Complementa:** PRD.md, AI-SPEC.md
**Última atualização:** 2026-05-02

---

## 1. Arquitetura

### 1.0 Documentação AI
A estratégia de calibração de Machine Learning, features e métricas de erro estão formalmente detalhadas no contrato de design: `AI-SPEC.md`.

### 1.1 Visão Geral
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  MT5 Terminal BR (XP)  â”‚         â”‚  MT5 Terminal Tickmill  â”‚         â”‚  MT5 Terminal Axi       â”‚
â”‚  WIN$N, DOL$N, DI1$N  â”‚         â”‚  DXY, BRENT, CHINA50,   â”‚         â”‚  iSharesBrazil+,        â”‚
â”‚  WDO$N                â”‚         â”‚  VIX, USDMXN + 14 mais â”‚         â”‚  iSharesTreasury20+ ... â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
            â”‚                                  â”‚                                  â”‚
            â”‚   mt5.initialize(path=...)       â”‚ (sequencial)                     â”‚
            â”‚                                  â”‚                                  â”‚
            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                           â–¼
              â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
              â”‚  collector.py          â”‚
              â”‚  loop 60s, sequencial  â”‚
              â”‚  (BR â†’ Tickmill â†’ Axi) â”‚
              â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                         â”‚
                         â”‚  INSERT OR IGNORE INTO market_bars
                         â–¼
                â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                â”‚  SQLite         â”‚
                â”‚  irai.db        â”‚
                â”‚  WAL mode       â”‚
                â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                         â”‚
                         â”‚ SELECT (sob demanda)
                         â–¼
                â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”       GET   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                â”‚  FastAPI        â”‚â—„â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚  firebase_sync.py  â”‚
                â”‚  main.py        â”‚             â”‚  (Loop 30s)        â”‚
                â”‚  port 8888      â”‚             â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”˜                       â”‚
                         â”‚                                â”‚ PUT /db.json
                         â”‚ REST (polling / local)         â–¼
                         â–¼                       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”     GET      â”‚ Firebase Realtime DB â”‚
                â”‚ React Dashboard â”‚â—„â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚ (Nuvem Publica)      â”‚
                â”‚ (Local Fallback)â”‚              â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

                â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                â”‚ calibrate_universal.py â”‚â”€â”€â”€â”€ roda offline
                â”‚ 27 fatores, brute-forceâ”‚
                â”‚ + filtros colinearidadeâ”‚
                â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```”€â”€â”€â”     GET      â”‚ Firebase Realtime DB â”‚
                â”‚ React Dashboard â”‚â—„â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚ (Nuvem PÃºblica)      â”‚
                â”‚ (Local Fallback)â”‚              â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                       â–²
                                                          â”‚ GET JSON
                                                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                                                 â”‚ React Dashboard      â”‚
                                                 â”‚ (Firebase Hosting)   â”‚
                                                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

                â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                â”‚ calibrate_v2.py â”‚â”€â”€â”€â”€ roda offline
                â”‚ atualiza        â”‚
                â”‚ model_params    â”‚
                â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### 1.2 PrincÃ­pios de design

1. **Isolamento de falha por broker.** Cada MT5 em um processo worker independente. Se o broker internacional cai, o worker BR continua gravando barras de IBOV/WIN; o cÃ¡lculo do IRAI segue com marcaÃ§Ã£o de *stale*.
2. **IdempotÃªncia na ingestÃ£o.** `INSERT OR IGNORE` com chave composta `(symbol, timestamp_utc)`. Rodar o worker duas vezes no mesmo minuto nÃ£o duplica dados.
3. **SeparaÃ§Ã£o cÃ¡lculo Ã— coleta.** Workers sÃ³ coletam. O cÃ¡lculo do IRAI Ã© feito no endpoint da API, sob demanda, lendo das tabelas. Evita recalcular tudo em cada barra.
4. **Estado zero entre processos.** Workers nÃ£o se conhecem. ComunicaÃ§Ã£o exclusivamente via banco. Facilita debug, restart e extensÃ£o.
5. **UTC everywhere internally.** Timezones sÃ³ aparecem na apresentaÃ§Ã£o ou em timestamps de log humanamente legÃ­veis.

---


### 1.3 PrincÃ­pios de CalibraÃ§Ã£o (V2 - Multi-Asset)

1. **Isolamento GeogrÃ¡fico:** Ativos internacionais (ex: EURUSD, US500) jamais podem usar fatores do Brasil (WIN, WDO, DI1) para evitar ruÃ­do.
2. **Anti-ContaminaÃ§Ã£o de Ãndices:** Ãndices americanos (US500, US30, USTEC) nÃ£o podem usar uns aos outros como fatores, forÃ§ando o modelo a ancorar na macroeconomia base (VIX, DXY, Ouro).
3. **Score Misto (70% ACC / 30% RÂ²):** A calibraÃ§Ã£o (brute-force) prioriza modelos que tenham alta acurÃ¡cia direcional (ACC) mas que mantenham forte aderÃªncia estrutural (RÂ²).
4. **Alinhamento de SessÃµes:** Sinais sÃ³ sÃ£o gerados dentro do horÃ¡rio lÃ­quido vÃ¡lido de cada ativo (BR: 09h Ã s 18h | INTL: 00h Ã s 24h / 24h contÃ­nuo).
5. **Filtro Anti-Multicolinearidade iShares:** MÃ¡ximo 1 Treasury (TLT/TLH/SHY) e 1 EM Bond (EMB/LEMB) por cesta de fatores, evitando redundÃ¢ncia entre ETFs correlacionados.
6. **ExclusÃ£o EWZ para BR:** Ativos brasileiros (WIN, WDO) excluem iSharesBrazil+ (EWZ) pois o ETF Ã© proxy da mesma bolsa â€” tautologia.


## 2. Componentes

### 2.1 `collector.py`

**Responsabilidade:** conectar sequencialmente aos 3 terminais MT5 (XP, Tickmill e Axi), coletar barras M5 de todos os sÃ­mbolos configurados, gravar em SQLite.

**SÃ­mbolos:**
- **XP:** `WIN$N`, `DOL$N`, `DI1$N`, `WDO$N` (targets + fatores locais)
- **Tickmill:** `US500`, `US30`, `USTEC`, `DE40`, `EURUSD`, `GBPUSD`, `USDJPY`, `AUDUSD`, `USDCAD`, `USDCHF`, `XAUUSD`, `BTCUSD`, `VIX`, `DXY`, `BRENT`, `CHINA50`, `USDMXN`, `AUDNZD`, `CADCHF`, `EURGBP`, `EURCHF`, `EURJPY`, `GBPJPY`, `EURAUD`
- **Axi:** `iSharesBrazil+`, `iSharesTreasury20+`, `iSharesTreasury10-20+`, `iSharesTreasury1-3+`, `iSharesUSEmerging+`, `iSharesCurrencyBond+` (fatores de calibraÃ§Ã£o apenas â€” nÃ£o sÃ£o alvos do dashboard)

**Ciclo de vida:**
1. No startup: `mt5.initialize(path=MT5_BR_PATH, login=..., password=..., server=...)`.
2. Registra job APScheduler: trigger cron `*/5 10-18 * * 1-5` (BRT), com offset `+3s` para garantir barra fechada.
3. A cada disparo:
   - Pega `mt5.copy_rates_from_pos(symbol, TIMEFRAME_M5, 0, 2)` â€” Ãºltimas 2 barras.
   - Converte timestamps pra UTC (MT5 retorna em server time, que tipicamente Ã© EET; ajustar via offset conhecido).
   - `INSERT OR IGNORE` no SQLite com `source='br'`.
4. Se `mt5.initialize()` falha ou `copy_rates_from_pos` retorna `None`, loga erro e agenda reconexÃ£o com backoff 5s â†’ 15s â†’ 30s â†’ 60s.

### 2.2 `worker_intl.py`

**Responsabilidade:** anÃ¡loga ao `worker_br.py`, mas para sÃ­mbolos internacionais.

**SÃ­mbolos:**
- Tickmill: `US500`, `US30`, `USTEC`, `EURUSD`, `GBPUSD`, `USDJPY`, `AUDUSD`, `USDCAD`, `USDCHF`, `XAUUSD`, `BTCUSD`, `VIX`, `DXY`, `BRENT`, `CHINA50`, `USDMXN`, `AUDNZD`, `CADCHF`

**DiferenÃ§as do worker BR:**
- SÃ­mbolos operam em janelas de atÃ© 24h (Forex, Crypto). Coleta contÃ­nua.
- Broker internacional usa server time EET (+2/+3).

### 2.3 `irai_api.py`

**Responsabilidade:** expor endpoints REST que leem do SQLite, calculam IRAI sob demanda, retornam JSON.

**Ciclo de vida:** servidor FastAPI Uvicorn stateless. Cache em memÃ³ria (`series_cache`) por `(target, date)` invalidado a cada `notify_update` do collector. Respostas HTTP instantÃ¢neas entre ciclos de coleta.

**Endpoints em Â§8.**

### 2.4 `calibrate_v2.py`

**Responsabilidade:** script offline, executado manualmente ou via cron, que lÃª dados diÃ¡rios histÃ³ricos agregados a partir de barras M5 e atualiza pesos/Î±/Ïƒ usando RegressÃ£o Ridge.

**Entrada:** Banco SQLite `irai.db`. Filtra retornos agregados de sessÃµes diÃ¡rias baseadas no horÃ¡rio de funcionamento exato de cada ativo (ex: 03h Ã s 22h para moedas).

**SaÃ­da:** atualizaÃ§Ã£o atÃ´mica da tabela `model_params` e `asset_models`.

### 2.5 Dashboard React (HÃ­brido)

**Responsabilidade:** Apresentar a UI interativa e limpa.
- **Modo Cloud (Firebase):** Quando configurado com `VITE_FIREBASE_URL`, consome o JSON hospedado via Firebase SSE (Server-Sent Events).
- **Modo Local:** HTTP polling a cada 60s em `localhost:8888` (WebSocket removido por estabilidade).
- **VisualizaÃ§Ãµes:** P_up com limiares compra/venda, grÃ¡fico NWE separado (preÃ§o + mÃ©dia + envelope com cor por inclinaÃ§Ã£o), Z-Score de divergÃªncia de preÃ§o.

### 2.6 `firebase_sync.py`

**Responsabilidade:** Expor o sistema na nuvem sem requerer infraestrutura pesada (zero custo).
LÃª a API local e faz upload de todo o payload do dashboard (Dates, Overview, Targets, Series e Summaries) consolidado para o Firebase via `PUT /db.json` a cada 30s.

---

## 3. Modelo de Dados

### 3.1 Schema SQLite

```sql
-- Barras brutas coletadas pelos workers
CREATE TABLE IF NOT EXISTS market_bars (
    symbol          TEXT NOT NULL,
    source          TEXT NOT NULL CHECK (source IN ('br', 'intl', 'axi')),
    timestamp_utc   TEXT NOT NULL,    -- ISO 8601 em UTC
    open            REAL NOT NULL,
    high            REAL NOT NULL,
    low             REAL NOT NULL,
    close           REAL NOT NULL,
    volume          REAL,
    received_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (symbol, timestamp_utc)
);

CREATE INDEX IF NOT EXISTS idx_market_bars_time ON market_bars(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_market_bars_symbol_time ON market_bars(symbol, timestamp_utc);

-- Cache de snapshots IRAI (opcional; pode ser recalculado sempre)
CREATE TABLE IF NOT EXISTS irai_snapshots (
    session_date    TEXT NOT NULL,          -- YYYY-MM-DD em BRT
    timestamp_utc   TEXT NOT NULL,
    bar_idx         INTEGER NOT NULL,       -- 0..95
    p_up            REAL NOT NULL,
    score           REAL NOT NULL,
    z_ewz           REAL, z_vix REAL, z_dxy REAL, z_us10y REAL,
    c_ewz           REAL, c_vix REAL, c_dxy REAL, c_us10y REAL,
    ibov_return     REAL,                   -- retorno % desde open
    stale_flags     TEXT,                   -- JSON array com fatores stale, ex '["vix"]'
    computed_at     TEXT NOT NULL,
    PRIMARY KEY (session_date, timestamp_utc)
);

-- ParÃ¢metros do modelo (versionados)
CREATE TABLE IF NOT EXISTS model_params (
    param_name      TEXT NOT NULL,
    value           REAL NOT NULL,
    effective_from  TEXT NOT NULL,          -- usado pra pegar versÃ£o vigente em timestamp X
    PRIMARY KEY (param_name, effective_from)
);

-- PreÃ§os de referÃªncia (open B3) por sessÃ£o
CREATE TABLE IF NOT EXISTS session_opens (
    session_date    TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    open_price      REAL NOT NULL,
    open_timestamp  TEXT NOT NULL,          -- pode nÃ£o ser 13:00 UTC exato se VIX
    PRIMARY KEY (session_date, symbol)
);
```

### 3.2 ParÃ¢metros vigentes

Exemplo de estado inicial em `model_params` (ex: modelo EURJPY):

| param_name        | value   | effective_from       |
|-------------------|---------|----------------------|
| eurjpy_w_gbpjpy   | +1.0189 | 2026-04-30T00:00:00Z |
| eurjpy_w_eurgbp   | +0.7114 | 2026-04-30T00:00:00Z |
| eurjpy_w_gbpusd   | -0.3094 | 2026-04-30T00:00:00Z |
| eurjpy_w_usdchf   | -0.2092 | 2026-04-30T00:00:00Z |
| eurjpy_w_eurchf   | +0.1871 | 2026-04-30T00:00:00Z |
| eurjpy_alpha      | 8.0363  | 2026-04-30T00:00:00Z |
| eurjpy_intercept  | -1.7168 | 2026-04-30T00:00:00Z |
| sigma_gbpjpy_daily| 0.00850 | 2026-04-30T00:00:00Z |
| sigma_eurgbp_daily| 0.00512 | 2026-04-30T00:00:00Z |

Consulta pra pegar parÃ¢metros vigentes em uma data:

```sql
SELECT param_name, value
FROM model_params
WHERE effective_from = (
    SELECT MAX(effective_from) FROM model_params mp2
    WHERE mp2.param_name = model_params.param_name
      AND mp2.effective_from <= :query_date
);
```

---

## 4. Fluxo de Dados

### 4.1 Fluxo intraday (evento tÃ­pico: barra de 10:05 BRT)

```
10:05:00 BRT â”‚ Barra M5 fecha na B3 e no MT5 INTL
10:05:03     â”‚ APScheduler dispara worker_br.on_bar_close()
10:05:03     â”‚ APScheduler dispara worker_intl.on_bar_close()
10:05:04     â”‚ worker_br insere IBOV, WIN em market_bars
10:05:05     â”‚ worker_intl insere EWZ, VIX, DXY, US10Y em market_bars
10:05:30     â”‚ Frontend faz poll em GET /api/v1/irai/current
10:05:30     â”‚ API calcula P_up(t=10:05), retorna JSON
10:05:30     â”‚ Dashboard renderiza nova barra no grÃ¡fico
```

### 4.2 Reset diÃ¡rio

NÃ£o hÃ¡ "reset" destrutivo â€” o modelo Ã© aditivo por sessÃ£o. O que muda Ã© a referÃªncia:

```
09:59 BRT â”‚ Sistema identifica prÃ³xima abertura B3 = hoje 10:00 BRT
10:00 BRT â”‚ Primeira barra pode ainda nÃ£o estar disponÃ­vel
10:05 BRT â”‚ Barra fechada 10:00-10:05 captura o open
10:05 BRT â”‚ Job dedicado `capture_session_open` insere em session_opens:
           â”‚   - IBOV: open da barra 10:00
           â”‚   - EWZ: Ãºltimo close disponÃ­vel (mercado americano abre 10:30)
           â”‚   - VIX: Ãºltimo close disponÃ­vel
           â”‚   - DXY, US10Y: Ãºltimo close disponÃ­vel
10:05 BRT â”‚ A partir daqui, todo z_i(t) usa P_i(open) de session_opens
```

### 4.3 CÃ¡lculo do IRAI (pseudo-cÃ³digo)

```python
def compute_irai(session_date: date, timestamp_utc: datetime) -> IraiSnapshot:
    params = load_params(effective_at=timestamp_utc)
    opens = load_session_opens(session_date)
    current = load_current_prices(timestamp_utc)

    # bar fraction: 0.01 para primeira barra, 1.0 para Ãºltima
    bar_idx = bars_since_open(timestamp_utc)
    t_fraction = (bar_idx + 1) / BARS_PER_SESSION  # 96

    z = {}
    stale = []
    for factor in ['ewz', 'vix', 'dxy', 'us10y']:
        if factor not in current or age_seconds(current[factor]) > 600:
            stale.append(factor)
            z[factor] = last_known_z.get(factor, 0.0)
            continue
        ret = (current[factor] - opens[factor]) / opens[factor]
        sigma_intraday = params[f'sigma_{factor}_daily'] * sqrt(t_fraction)
        z[factor] = ret / sigma_intraday

    contributions = {f: params[f'w_{f}'] * z[f] for f in z}
    score = sum(contributions.values())
    p_up = sigmoid(params['alpha'] * score) * 100

    ibov_return = (current['ibov'] - opens['ibov']) / opens['ibov']

    return IraiSnapshot(
        session_date=session_date,
        timestamp_utc=timestamp_utc,
        bar_idx=bar_idx,
        p_up=p_up,
        score=score,
        z=z,
        contributions=contributions,
        ibov_return=ibov_return,
        stale_flags=stale,
    )
```

---

## 5. Algoritmo IRAI

### 5.1 FormalizaÃ§Ã£o matemÃ¡tica

**Retorno intraday normalizado** (z-score) do fator i no instante t desde a abertura:

$$
z_i(t) = \frac{P_i(t) - P_i(\text{open})}{\sigma_i \cdot \sqrt{t/T}}
$$

Onde:
- $P_i(t)$ Ã© o preÃ§o do fator i no instante t.
- $P_i(\text{open})$ Ã© o preÃ§o de referÃªncia congelado em 10:00 BRT.
- $\sigma_i$ Ã© a volatilidade diÃ¡ria histÃ³rica do fator (escala decimal; ex: 0.018 = 1.8% ao dia).
- $T$ Ã© a duraÃ§Ã£o total da sessÃ£o em barras (96 para 5 min Ã— 8 horas).
- $t$ Ã© o nÃºmero de barras decorridas desde o open.

A raiz de $t/T$ aplica escalonamento por Brownian motion â€” a vol esperada em meio perÃ­odo Ã© $\sigma \sqrt{1/2}$, nÃ£o $\sigma/2$.

**Score composto:**

$$
S(t) = \sum_{i \in \{\text{EWZ, VIX, DXY, US10Y}\}} w_i \cdot z_i(t)
$$

Onde $w_i$ sÃ£o os pesos estimados via regressÃ£o linear multivariada (Â§6).

**Probabilidade de alta:**

$$
P_{\text{up}}(t) = \sigma(\alpha \cdot S(t)) \cdot 100
$$

Onde $\sigma(x) = 1/(1+e^{-x})$ Ã© a sigmoide logÃ­stica, e $\alpha$ Ã© um parÃ¢metro de calibraÃ§Ã£o que controla quÃ£o agressivamente o score Ã© mapeado pra probabilidade.

### 5.2 InterpretaÃ§Ã£o

- $P_{\text{up}}(t) = 50\%$ â‡” $S(t) = 0$ â‡” sem informaÃ§Ã£o lÃ­quida dos fatores.
- $P_{\text{up}}(t) = 70\%$ â‡” $S(t) \approx 0.70$ (com Î±=1.2) â‡” combinaÃ§Ã£o de fatores sugere probabilidade ~2x maior de alta vs. baixa.
- Banda 40â€“60% corresponde a $|S| < 0.34$ â‰ˆ "ruÃ­do".

### 5.3 Tratamento de dados faltantes

- Se fator i tem preÃ§o atrasado > 10 min: z_i Ã© congelado no Ãºltimo valor conhecido; flag `stale` ativada.
- Se fator i nunca teve cotaÃ§Ã£o na sessÃ£o (ex: VIX no prÃ©-open B3 antes das 10:30 BRT): z_i = 0 com flag `pre_market`.
- Se IBOV nÃ£o tem cotaÃ§Ã£o: cÃ¡lculo continua (IRAI nÃ£o depende do IBOV; ele Ã© apenas alvo de validaÃ§Ã£o visual).

---

### 6.1 Estimação dos pesos $w_i$ (Universal)

O motor Universal (`calibrate_universal.py`) faz um *brute-force* dinâmico para encontrar os melhores preditores para cada um dos 20 ativos a partir de um pool de 31 fatores candidatos (incluindo DE40 e iShares).

**Filtro de Correlação:** Apenas ativos com correlação mínima de 30% (ou restrições específicas) em relação ao fator mais forte do ativo são considerados.
**Regressão:** Usa-se a `Ridge` do `scikit-learn` para balancear a matriz de covariância e evitar explosão de pesos.
**Anti-Multicolinearidade:** Mínimo de 6 e máximo de 8 fatores por cesta, limitando ETFs correlacionados (ex: máximo 1 Treasury).
**Acurácia:** Todo modelo com ACC < 55% direcional é descartado sumariamente.

Os pesos resultantes sÃ£o gravados em `model_params` com prefixo por ativo (ex: `us500_w_vix`).

### 6.2 EstimaÃ§Ã£o de $\sigma_i$

$$
\sigma_i = \text{std}(\text{ret}_i^{\text{diÃ¡rio}}) \text{ sobre janela de 60 dias}
$$

Armazenado em `model_params` como `sigma_<fator>_daily` em escala decimal.

### 6.3 CalibraÃ§Ã£o de $\alpha$

Em dados intraday histÃ³ricos (se disponÃ­veis) ou diÃ¡rios (proxy):

1. Para cada dia t, calcular S(t) usando as barras do dia e os pesos.
2. Y = 1 se IBOV fechou acima do open, 0 caso contrÃ¡rio.
3. RegressÃ£o logÃ­stica: `logit(Y) = Î± Â· S(t) + Î²`.
4. Î± estimado vai pra model_params. Î² geralmente â‰ˆ 0 e Ã© ignorado.

### 6.4 ValidaÃ§Ã£o

O `calibrate.py` deve gerar `calibration_report_YYYYMMDD.md` com:

- Pesos estimados vs. vigentes (diff).
- RÂ² da regressÃ£o.
- p-valores individuais dos fatores.
- Reliability plot (bucket P_up Ã— frequÃªncia observada) em dados out-of-sample.
- Alerta se qualquer peso trocou de sinal.

---

## 7. ConexÃ£o Dual MT5

### 7.1 Setup fÃ­sico

Duas instÃ¢ncias completas do MetaTrader 5, cada uma em diretÃ³rio separado:

```
C:\Program Files\MetaTrader 5 BR\    â† instalaÃ§Ã£o normal, broker nacional
C:\Program Files\MetaTrader 5 INTL\  â† segunda instalaÃ§Ã£o (renomear pasta), broker offshore
```

Para instalar a segunda instÃ¢ncia, baixar o instalador do broker INTL e mudar o diretÃ³rio de destino durante o instalador.

### 7.2 ConexÃ£o Python

A biblioteca `MetaTrader5` aceita o argumento `path` em `initialize()` para apontar pro `terminal64.exe` especÃ­fico. **Cada processo Python** pode ter uma conexÃ£o ativa. Portanto:

```python
# worker_br.py
import MetaTrader5 as mt5
mt5.initialize(
    path=r"C:\Program Files\MetaTrader 5 BR\terminal64.exe",
    login=int(os.environ['MT5_BR_LOGIN']),
    password=os.environ['MT5_BR_PASSWORD'],
    server=os.environ['MT5_BR_SERVER'],
)
```

E em um **processo separado**:

```python
# worker_intl.py
import MetaTrader5 as mt5
mt5.initialize(
    path=r"C:\Program Files\MetaTrader 5 INTL\terminal64.exe",
    login=int(os.environ['MT5_INTL_LOGIN']),
    password=os.environ['MT5_INTL_PASSWORD'],
    server=os.environ['MT5_INTL_SERVER'],
)
```

**Importante:** rodar ambos no mesmo processo Python vai falhar silenciosamente â€” a segunda `initialize` derruba a primeira. Ã‰ por isso que precisam ser processos independentes.

### 7.3 Server time

Cada broker tem seu server time:

| Broker BR tÃ­pico | Server time = UTCâˆ’3 (BRT) |
| Broker INTL tÃ­pico | Server time = UTC+2/+3 (EET) |

Os `datetime` retornados por `copy_rates_from_pos` estÃ£o em server time. ConversÃ£o obrigatÃ³ria:

```python
from datetime import datetime, timezone, timedelta

BR_SERVER_OFFSET_HOURS = -3   # ajustar por broker
INTL_SERVER_OFFSET_HOURS = 3  # ajustar por broker

def to_utc(naive_dt: datetime, source: str) -> datetime:
    offset = BR_SERVER_OFFSET_HOURS if source == 'br' else INTL_SERVER_OFFSET_HOURS
    return (naive_dt - timedelta(hours=offset)).replace(tzinfo=timezone.utc)
```

O offset de cada broker Ã© configurÃ¡vel via `.env` e deve ser validado manualmente comparando `mt5.symbol_info_tick(symbol).time` com `time.time()` no primeiro setup.

---

## 8. API Contract

Base URL: `http://localhost:8000`

### 8.1 `GET /api/v1/health`

Status das conexÃµes e Ãºltimas barras recebidas.

```json
{
  "status": "ok",
  "mt5_br": {"connected": true, "last_bar_utc": "2026-04-23T17:00:00Z"},
  "mt5_intl": {"connected": true, "last_bar_utc": "2026-04-23T17:00:00Z"},
  "last_irai_compute": "2026-04-23T17:00:05Z"
}
```

### 8.2 `GET /api/v1/irai/current`

Snapshot mais recente.

```json
{
  "session_date": "2026-04-23",
  "timestamp_utc": "2026-04-23T17:00:00Z",
  "bar_idx": 84,
  "p_up": 67.3,
  "score": 0.587,
  "regime": "risk_on",
  "z_scores": {"ewz": 1.42, "vix": -0.88, "dxy": -0.31, "us10y": 0.15},
  "contributions": {"ewz": 0.639, "vix": 0.264, "dxy": 0.078, "us10y": 0.015},
  "ibov_return": 0.0112,
  "stale_flags": []
}
```

### 8.3 `GET /api/v1/irai/session?date=YYYY-MM-DD`

SÃ©rie completa da sessÃ£o. Sem parÃ¢metro, assume hoje.

```json
{
  "session_date": "2026-04-23",
  "bars": [
    {"bar_idx": 0, "timestamp_utc": "...", "p_up": 51.2, "score": 0.04, "z_scores": {...}, "contributions": {...}, "ibov_return": 0.0003},
    ...
  ]
}
```

### 8.4 `GET /api/v1/params`

ParÃ¢metros vigentes e histÃ³rico.

```json
{
  "current": {"w_ewz": 0.45, "w_vix": -0.30, ..., "effective_from": "2026-04-20"},
  "previous_calibrations": [
    {"effective_from": "2026-04-13", "w_ewz": 0.42, ...}
  ]
}
```

### 8.5 `GET /api/v1/bars?symbol=EWZ&from=...&to=...`

Debug endpoint â€” barras brutas.

### 8.6 PadrÃµes de erro

```json
{"error": "no_session_data", "detail": "PregÃ£o ainda nÃ£o abriu ou sessÃ£o vazia", "status": 404}
```

---

## 9. Scheduler & Reset DiÃ¡rio

### 9.1 Agenda dos workers

```python
# APScheduler cron
trigger = CronTrigger(
    day_of_week='mon-fri',
    hour='10-17',
    minute='0,5,10,15,20,25,30,35,40,45,50,55',
    second=3,
    timezone='America/Sao_Paulo',
)
```

A barra que fecha Ã s 10:00 BRT Ã© capturada no disparo de 10:05:03 (lÃª barra jÃ¡ fechada). A Ãºltima barra da sessÃ£o fecha 17:55 BRT e Ã© capturada 18:00:03.

### 9.2 Job de captura do session open

Roda uma vez por dia Ã s 10:05:30 BRT:

```python
def capture_session_open():
    today = date.today()
    for symbol in ALL_SYMBOLS:
        first_bar = get_first_bar_of_session(symbol, today)
        if first_bar is None:
            # Fator estrangeiro sem cotaÃ§Ã£o ainda â€” usar Ãºltimo close
            first_bar = get_last_close_before(symbol, today_open_utc)
        upsert_session_open(today, symbol, first_bar.open, first_bar.timestamp)
```

### 9.3 HorÃ¡rio de verÃ£o

B3 nÃ£o faz mais horÃ¡rio de verÃ£o desde 2019. Fuso BRT = UTCâˆ’3 ano inteiro. O broker internacional pode fazer DST â€” isso afeta a conversÃ£o server time â†’ UTC. O offset de cada server deve ser revalidado quando ocorrer mudanÃ§a de DST nos EUA/Europa (marÃ§o e novembro).

---

## 10. Error Handling & ResiliÃªncia

| CenÃ¡rio                             | Resposta                                                                 |
|-------------------------------------|--------------------------------------------------------------------------|
| MT5 nÃ£o conecta no startup          | Worker loga erro fatal, sai com exit code 1; process supervisor reinicia |
| MT5 desconecta no meio do dia       | `mt5.last_error()` logado; reconexÃ£o com backoff 5sâ†’15sâ†’30sâ†’60s          |
| `copy_rates_from_pos` retorna None  | Log warning, skip, prÃ³xima barra tenta de novo                           |
| PreÃ§o anÃ´malo (spike > 10Ïƒ)         | Log warning, inserir mesmo assim, flag `anomaly` no snapshot             |
| SQLite locked                       | WAL mode resolve em MVP; se persistir, retry com jitter                  |
| `model_params` vazio                | API retorna 503 "model_not_calibrated"; rodar `calibrate.py` seed        |
| Session opens faltantes             | API retorna P_up = 50% com flag `no_open_reference`                      |

---

## 11. Estrutura de Arquivos

```
irai/
â”œâ”€â”€ README.md
â”œâ”€â”€ PRD.md
â”œâ”€â”€ SPEC.md
â”œâ”€â”€ .env.example
â”œâ”€â”€ pyproject.toml
â”œâ”€â”€ requirements.txt
â”‚
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ config.py              # leitura .env, constantes (BARS_PER_SESSION etc.)
â”‚   â”œâ”€â”€ db.py                  # conexÃ£o SQLite + migrations
â”‚   â”œâ”€â”€ schemas.py             # Pydantic models
â”‚   â”œâ”€â”€ workers/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ worker_br.py
â”‚   â”‚   â”œâ”€â”€ worker_intl.py
â”‚   â”‚   â””â”€â”€ common.py          # helpers compartilhados (to_utc, retry, etc.)
â”‚   â”œâ”€â”€ api/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ main.py            # FastAPI app
â”‚   â”‚   â”œâ”€â”€ routes_irai.py
â”‚   â”‚   â”œâ”€â”€ routes_health.py
â”‚   â”‚   â””â”€â”€ routes_params.py
â”‚   â”œâ”€â”€ irai/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ compute.py         # funÃ§Ã£o compute_irai()
â”‚   â”‚   â”œâ”€â”€ params.py          # load_params()
â”‚   â”‚   â””â”€â”€ session.py         # helpers de open B3, reset, etc.
â”‚   â””â”€â”€ calibrate.py
â”‚
â”œâ”€â”€ frontend/
â”‚   â”œâ”€â”€ package.json
â”‚   â”œâ”€â”€ vite.config.ts
â”‚   â”œâ”€â”€ index.html
â”‚   â””â”€â”€ src/
â”‚       â”œâ”€â”€ main.tsx
â”‚       â”œâ”€â”€ App.tsx
â”‚       â”œâ”€â”€ IRAIDashboard.tsx  # adaptado do protÃ³tipo
â”‚       â””â”€â”€ api.ts             # fetch wrappers
â”‚
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ irai.db                # SQLite (gitignored)
â”‚   â””â”€â”€ reports/
â”‚       â””â”€â”€ calibration_*.md   # gerados por calibrate.py
â”‚
â””â”€â”€ scripts/
    â”œâ”€â”€ list_symbols.py        # helper pra descobrir sÃ­mbolos disponÃ­veis
    â”œâ”€â”€ seed_params.py         # popula model_params com defaults
    â””â”€â”€ validate_offsets.py    # valida server time offsets
```

---

## 12. Stack TÃ©cnico

| Camada      | Tecnologia            | VersÃ£o alvo | Justificativa                              |
|-------------|-----------------------|-------------|--------------------------------------------|
| MT5 client  | MetaTrader5 (pip)     | 5.0.45+     | Oficial, estÃ¡vel, suporta dual via path    |
| Scheduler   | APScheduler           | 3.10+       | Cron robusto, tolerante a restart          |
| DB          | SQLite                | 3.40+       | Zero setup, WAL suficiente pra MVP         |
| API         | FastAPI + Uvicorn     | 0.110+      | Stack padrÃ£o do Miqueias                   |
| Frontend    | React + Vite          | 18 / 5      | Consistente com dashboards anteriores      |
| Chart       | Recharts              | 2.12+       | JÃ¡ usado no protÃ³tipo                      |
| Python      | CPython               | 3.11+       | MetaTrader5 lib suporta atÃ© 3.12           |

---

## 13. Testes

### 13.1 UnitÃ¡rios

- `test_compute_irai.py` â€” casos sintÃ©ticos: todos z_i=0 â‡’ P_up=50%; z_ewz=1, resto=0 â‡’ P_up â‰ˆ 64% (com Î±=1.2, w_ewz=0.45).
- `test_time_conversion.py` â€” converte timestamps de ambos os brokers pra UTC.
- `test_session_open.py` â€” validaÃ§Ã£o de reset diÃ¡rio e tratamento de fatores sem cotaÃ§Ã£o.

### 13.2 IntegraÃ§Ã£o

- `test_full_session_replay.py` â€” alimenta banco com uma sessÃ£o histÃ³rica (CSV), roda API, compara sÃ©rie retornada vs. esperada.
- `test_dual_worker_isolation.py` â€” simula falha de um MT5, verifica que o outro continua e que o cÃ¡lculo marca stale.

### 13.3 Manual

- Checklist de setup de cada broker (ver README Â§Troubleshooting).
- ValidaÃ§Ã£o visual do dashboard contra TradingView em paralelo por 5 pregÃµes.

---

### 14.1 Deploy Windows Service (NSSM)

O sistema local Ã© configurado para iniciar automaticamente via script PowerShell (`scripts\install_nssm_services.ps1`) usando o NSSM (Non-Sucking Service Manager).
- `IRAI_API`
- `IRAI_Collector`
- `IRAI_FirebaseSync`

### 14.2 Cloud HÃ­brida (Zero Custo)

- MÃ¡quina Windows local (com MT5) opera o processamento pesado e o banco SQLite.
- `firebase_sync.py` publica o JSON resultante para o **Firebase Realtime Database**.
- O frontend React Ã© buildado (`npm run build`) e hospedado globalmente via **Firebase Hosting**.
- Isso elimina a necessidade de pagar VPS, mantendo o painel acessÃ­vel pelo celular 24/7.

---

## 15. Anexos

### 15.1 Valores tÃ­picos Ïƒ_i (referÃªncia inicial)

| Fator  | Ïƒ diÃ¡ria aprox. | ObservaÃ§Ã£o                              |
|--------|-----------------|-----------------------------------------|
| EWZ    | 1.8%            | ETF Brasil, vol alta                    |
| VIX    | 5.0%            | vol de vol, movimentos grandes normais  |
| DXY    | 0.4%            | Ã­ndice dÃ³lar, movimentos pequenos       |
| US10Y  | 2.0%            | yield, vol em pontos-base significativa |
| IBOV   | 1.2%            | sÃ³ para referÃªncia                      |

Estes sÃ£o valores *seed* â€” o primeiro `calibrate.py` substituirÃ¡ por estimativas empÃ­ricas.

### 15.2 GlossÃ¡rio

- **IRAI:** Intraday Risk Appetite Index (este projeto).
- **z-score normalizado:** retorno dividido pela vol esperada atÃ© o instante t; unidades em desvios-padrÃ£o.
- **Score S(t):** combinaÃ§Ã£o linear ponderada dos z-scores.
- **Sigmoide:** funÃ§Ã£o que mapeia â„ â†’ (0,1); usada para converter score em probabilidade.
- **Stale:** fator cujo Ãºltimo preÃ§o tem mais de 10 min de idade; indica dado potencialmente desatualizado.
- **Session open:** preÃ§o congelado Ã s 10:00 BRT usado como denominador de todos os z-scores do dia.
