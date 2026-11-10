"""
IRAI Database — Schema e inicialização do SQLite.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "irai_live.db")

SCHEMA = """
-- Barras brutas coletadas pelos workers (M5 e D1)
CREATE TABLE IF NOT EXISTS market_bars (
    symbol          TEXT NOT NULL,
    source          TEXT NOT NULL CHECK (source IN ('br', 'tickmill', 'axi')),
    timeframe       TEXT NOT NULL CHECK (timeframe IN ('M1', 'M2', 'M5', 'M15', 'M30', 'H1', 'D1')),
    timestamp_utc   TEXT NOT NULL,    -- ISO 8601 em UTC
    open            REAL NOT NULL,
    high            REAL NOT NULL,
    low             REAL NOT NULL,
    close           REAL NOT NULL,
    volume          REAL,
    real_volume     REAL DEFAULT 0,
    delta           REAL DEFAULT 0,
    received_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (symbol, timeframe, timestamp_utc)
);

CREATE INDEX IF NOT EXISTS idx_bars_sym_tf_time ON market_bars(symbol, timeframe, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_bars_time ON market_bars(timestamp_utc);

-- Parâmetros do modelo (versionados)
CREATE TABLE IF NOT EXISTS model_params (
    param_name      TEXT NOT NULL,
    value           REAL NOT NULL,
    effective_from  TEXT NOT NULL,
    PRIMARY KEY (param_name, effective_from)
);

-- Preços de referência (open B3) por sessão
CREATE TABLE IF NOT EXISTS session_opens (
    session_date    TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    open_price      REAL NOT NULL,
    open_timestamp  TEXT NOT NULL,
    PRIMARY KEY (session_date, symbol)
);

-- Log de calibrações
CREATE TABLE IF NOT EXISTS calibration_log (
    calibration_date TEXT NOT NULL PRIMARY KEY,
    window_days      INTEGER NOT NULL,
    r_squared        REAL,
    params_json      TEXT NOT NULL,         -- JSON com todos os pesos
    notes            TEXT
);

-- Configuração de modelos por ativo
CREATE TABLE IF NOT EXISTS asset_models (
    target          TEXT PRIMARY KEY,          -- 'US500', 'XAUUSD', etc.
    slug            TEXT NOT NULL UNIQUE,      -- 'us500' (prefixo no model_params)
    display_name    TEXT NOT NULL,             -- 'S&P 500'
    icon            TEXT DEFAULT '📊',
    factors         TEXT NOT NULL,             -- JSON: ["DXY","VIX","BTCUSD"]
    factor_labels   TEXT NOT NULL,             -- JSON: {"DXY":"dxy","VIX":"vix"}
    session_start_h INTEGER DEFAULT 0,        -- hora UTC início sessão
    session_end_h   INTEGER DEFAULT 24,       -- hora UTC fim sessão (0-24 = 24h)
    data_proxy      TEXT,                     -- símbolo no banco se diferente (DOL$N para WDO$N)
    accuracy        REAL,                     -- última acurácia direcional calibrada
    r_squared       REAL,                     -- último R²
    n_sessions      INTEGER,                  -- sessões usadas na calibração
    calibrated_at   TEXT,                     -- timestamp última calibração
    active          INTEGER DEFAULT 1,         -- 1=ativo, 0=inativo
    divergence_config TEXT                     -- JSON config para desvios de preço e Johansen
);
-- Estado Dinâmico (Kalman Filter & Johansen)
CREATE TABLE IF NOT EXISTS kalman_state (
    slug             TEXT NOT NULL,
    timeframe        TEXT NOT NULL DEFAULT 'M5',
    session_date     TEXT NOT NULL,
    state_mean       TEXT NOT NULL,         -- JSON array
    state_covariance TEXT NOT NULL,         -- JSON 2D array
    johansen_p_value REAL,
    is_cointegrated  INTEGER DEFAULT 1,     -- 1=sim, 0=não
    timestamp_utc    TEXT NOT NULL,
    PRIMARY KEY (slug, timeframe, session_date)
);

-- Barreiras de GEX históricas por data e ativo
CREATE TABLE IF NOT EXISTS gex_levels (
    session_date    TEXT NOT NULL,
    target          TEXT NOT NULL,
    run_name        TEXT NOT NULL DEFAULT 'default',
    levels_json     TEXT NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (session_date, target, run_name)
);

-- Volatilidade condicional GARCH histórica e previsão
CREATE TABLE IF NOT EXISTS garch_volatility (
    session_date     TEXT NOT NULL,
    symbol           TEXT NOT NULL,
    history_json     TEXT NOT NULL,
    forecast_json    TEXT NOT NULL,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (session_date, symbol)
);

-- Snapshots imutáveis em tempo real (Zero-Repainting Live Mode)
CREATE TABLE IF NOT EXISTS irai_live_snapshots (
    target          TEXT NOT NULL,
    timeframe       TEXT NOT NULL DEFAULT 'M5',
    session_date    TEXT NOT NULL,
    timestamp_utc   TEXT NOT NULL,
    bar_idx         INTEGER NOT NULL,
    p_up            REAL NOT NULL,
    score           REAL NOT NULL,
    verdict         TEXT NOT NULL,
    verdict_color   TEXT NOT NULL,
    price_diverge_z REAL,
    price_diverges  INTEGER,
    pair_z          REAL,
    pair_factor     TEXT,
    pair_beta       REAL,
    pair_signal     TEXT,
    win_return      REAL,
    win_current     REAL,
    win_open        REAL,
    win_bar_open    REAL,
    win_high        REAL,
    win_low         REAL,
    cum_delta       REAL,
    cum_delta_norm  REAL,
    nwe_center_price REAL,
    nwe_upper_price  REAL,
    nwe_lower_price  REAL,
    nwe_slope        REAL,
    nwe_up_price     REAL,
    nwe_down_price   REAL,
    is_ghost        INTEGER DEFAULT 0,
    is_live_captured INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (target, timeframe, session_date, timestamp_utc)
);

CREATE INDEX IF NOT EXISTS idx_live_snaps_lookup ON irai_live_snapshots(target, session_date, timeframe);
"""

def get_connection(db_path=None):
    """Retorna conexão SQLite com WAL mode e resiliência de concorrência."""
    path = db_path or DB_PATH
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    """Cria schema se não existir."""
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    print(f"Database initialized: {db_path or DB_PATH}")
    conn.close()

    # Rodar migrações
    migrate_delta(db_path)
    migrate_kalman_state(db_path)
    migrate_gex_levels(db_path)
    migrate_garch_volatility(db_path)
    migrate_timeframe_constraint(db_path)
    migrate_kalman_state_timeframe(db_path)
    migrate_divergence_config(db_path)
    migrate_live_snapshots(db_path)
    migrate_drop_snapshots(db_path)
    migrate_win_top8_asset(db_path)


def migrate_win_top8_asset(db_path=None):
    """Garante que WIN$N_TOP8 fique desativado em asset_models."""
    conn = get_connection(db_path)
    conn.execute("UPDATE asset_models SET active = 0 WHERE target = 'WIN$N_TOP8'")
    conn.commit()
    conn.close()


def _add_column(conn, sql):
    """Executa ALTER TABLE ADD COLUMN de forma idempotente.

    Captura 'duplicate column' silenciosamente para suportar
    inicialização concorrente (API + Collector em boot simultâneo).
    Retorna True se a coluna foi adicionada, False se já existia.
    """
    try:
        conn.execute(sql)
        return True
    except sqlite3.OperationalError as exc:
        if "duplicate column" not in str(exc).lower():
            raise
        return False


def migrate_delta(db_path=None):
    """Adiciona colunas real_volume e delta se não existirem (migração)."""
    conn = get_connection(db_path)
    cursor = conn.execute("PRAGMA table_info(market_bars)")
    cols = {row["name"] for row in cursor}

    if "real_volume" not in cols:
        if _add_column(conn, "ALTER TABLE market_bars ADD COLUMN real_volume REAL DEFAULT 0"):
            print("  + coluna real_volume adicionada")
    if "delta" not in cols:
        if _add_column(conn, "ALTER TABLE market_bars ADD COLUMN delta REAL DEFAULT 0"):
            print("  + coluna delta adicionada")

    conn.commit()
    conn.close()


def migrate_kalman_state(db_path=None):
    """Adiciona a tabela kalman_state se não existir (migração Fase 6)."""
    conn = get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kalman_state (
            slug             TEXT NOT NULL,
            timeframe        TEXT NOT NULL DEFAULT 'M5',
            session_date     TEXT NOT NULL,
            state_mean       TEXT NOT NULL,         -- JSON array
            state_covariance TEXT NOT NULL,         -- JSON 2D array
            johansen_p_value REAL,
            is_cointegrated  INTEGER DEFAULT 1,     -- 1=sim, 0=não
            timestamp_utc    TEXT NOT NULL,
            PRIMARY KEY (slug, timeframe, session_date)
        )
    """)
    conn.commit()
    print("  + tabela kalman_state garantida")
    conn.close()


def migrate_gex_levels(db_path=None):
    """Garante que a tabela gex_levels suporta múltiplas coletas (run_name)."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(gex_levels)")
    cols = [r[1] for r in cursor.fetchall()]
    if cols and "run_name" not in cols:
        print("Migrando tabela gex_levels para suportar múltiplas coletas...")
        cursor.execute("DROP TABLE IF EXISTS gex_levels")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gex_levels (
            session_date    TEXT NOT NULL,
            target          TEXT NOT NULL,
            run_name        TEXT NOT NULL DEFAULT 'default',
            levels_json     TEXT NOT NULL,
            updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (session_date, target, run_name)
        )
    """)
    conn.commit()

    # Audit log: contagem de registros por estado
    try:
        total = conn.execute("SELECT COUNT(*) FROM gex_levels").fetchone()[0]
        sessions = conn.execute("SELECT COUNT(DISTINCT session_date) FROM gex_levels").fetchone()[0]
        print(f"  + tabela gex_levels ok ({total} registros em {sessions} sessões)")
    except Exception:
        print("  + tabela gex_levels ok (vazia)")

    conn.close()


def migrate_garch_volatility(db_path=None):
    """Adiciona a tabela garch_volatility se não existir (migração GARCH)."""
    conn = get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS garch_volatility (
            session_date     TEXT NOT NULL,
            symbol           TEXT NOT NULL,
            history_json     TEXT NOT NULL,
            forecast_json    TEXT NOT NULL,
            updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (session_date, symbol)
        )
    """)
    conn.commit()
    print("  + tabela garch_volatility garantida")
    conn.close()


def _has_column(conn, table: str, column: str) -> bool:
    """True se a coluna existe (usado para gravar campos da fase 16 só após a migração)."""
    try:
        return any(r[1] == column for r in conn.execute(f"PRAGMA table_info({table})").fetchall())
    except sqlite3.Error:
        return False


def save_kalman_state(conn, slug: str, timeframe: str, session_date: str, state_mean, state_covariance, p_value: float, is_cointegrated: bool, timestamp_utc: str, model_version: str = None):
    """Salva o estado atual do filtro de Kalman e teste de Johansen com guard de timestamp.

    Fase 16 (REQ-P05): com a migração aplicada, grava também a versão de modelo do estado.
    """
    import json
    import numpy as np
    
    # Guard de timestamp: só atualizar se o novo timestamp_utc for estritamente mais recente
    row = conn.execute("""
        SELECT timestamp_utc FROM kalman_state
        WHERE slug = ? AND timeframe = ? AND session_date = ?
    """, (slug, timeframe, session_date)).fetchone()
    if row:
        existing_ts = row["timestamp_utc"]
        if timestamp_utc <= existing_ts:
            return
            
    # Converter numpy arrays para listas para serialização JSON
    if isinstance(state_mean, np.ndarray):
        state_mean = state_mean.tolist()
    if isinstance(state_covariance, np.ndarray):
        state_covariance = state_covariance.tolist()
        
    if model_version is not None and _has_column(conn, "kalman_state", "model_version"):
        conn.execute("""
            INSERT OR REPLACE INTO kalman_state 
            (slug, timeframe, session_date, state_mean, state_covariance, johansen_p_value, is_cointegrated, timestamp_utc, model_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (slug, timeframe, session_date, json.dumps(state_mean), json.dumps(state_covariance), p_value, int(is_cointegrated), timestamp_utc, model_version))
    else:
        conn.execute("""
            INSERT OR REPLACE INTO kalman_state 
            (slug, timeframe, session_date, state_mean, state_covariance, johansen_p_value, is_cointegrated, timestamp_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (slug, timeframe, session_date, json.dumps(state_mean), json.dumps(state_covariance), p_value, int(is_cointegrated), timestamp_utc))
    conn.commit()


def load_kalman_state(conn, slug: str, timeframe: str, session_date: str, expected_dim: int = None,
                      model_version: str = None, accept_untagged: bool = False):
    """Carrega o último estado do filtro de Kalman para o ativo e timeframe anterior à data informada.

    Fase 16 (REQ-P05): com ``model_version`` informado (e a migração aplicada), o estado mais recente
    só é aceito se for da MESMA versão. Troca de versão = estado reinicializado de forma explícita
    (retorna None e registra no log). ``accept_untagged`` aceita estados gravados antes da migração
    (model_version NULL) — usado só pela versão adotada do legado, para não mudar o comportamento ao vivo.
    """
    import json
    import numpy as np
    import logging
    
    versioned = model_version is not None and _has_column(conn, "kalman_state", "model_version")
    row = conn.execute(f"""
        SELECT state_mean, state_covariance, johansen_p_value, is_cointegrated, timestamp_utc
               {", model_version" if versioned else ""}
        FROM kalman_state
        WHERE slug = ? AND timeframe = ? AND session_date < ?
        ORDER BY session_date DESC LIMIT 1
    """, (slug, timeframe, session_date)).fetchone()
    
    if not row:
        return None

    if versioned:
        saved_version = row["model_version"]
        if saved_version != model_version and not (saved_version is None and accept_untagged):
            logging.warning(
                f"[Kalman Versioning] Estado de {slug}/{timeframe} descartado: versão salva="
                f"{saved_version or 'legado'} vs vigente={model_version}. Estado reinicializado com os pesos da versão."
            )
            return None
        
    try:
        state_mean = np.array(json.loads(row["state_mean"]))
        state_covariance = np.array(json.loads(row["state_covariance"]))
        
        # Guard de dimensão: descartar estado incompatível se o modelo foi recalibrado com outro número de fatores
        if expected_dim is not None and len(state_mean) != expected_dim:
            logging.warning(
                f"[Kalman Robustness] Estado salvo descartado para {slug}/{timeframe}: "
                f"dim={len(state_mean)} vs esperado={expected_dim}"
            )
            return None
            
        return {
            "state_mean": state_mean,
            "state_covariance": state_covariance,
            "johansen_p_value": row["johansen_p_value"],
            "is_cointegrated": bool(row["is_cointegrated"]),
            "timestamp_utc": row["timestamp_utc"]
        }
    except Exception as e:
        logging.error(f"[Kalman Error] Falha ao carregar estado para {slug}/{timeframe}: {e}")
        return None


def migrate_timeframe_constraint(db_path=None):
    """Migra o check constraint de timeframe em market_bars para suportar novos timeframes."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='market_bars'").fetchone()
    if not row:
        conn.close()
        return

    sql = row["sql"]
    if "'M1'" in sql or '"M1"' in sql:
        conn.close()
        return
        
    print("Iniciando migração do CHECK constraint em market_bars para suportar novos timeframes...")
    
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN TRANSACTION")
        conn.execute("ALTER TABLE market_bars RENAME TO _market_bars_old")
        
        conn.execute("""
        CREATE TABLE market_bars (
            symbol          TEXT NOT NULL,
            source          TEXT NOT NULL CHECK (source IN ('br', 'tickmill', 'axi')),
            timeframe       TEXT NOT NULL CHECK (timeframe IN ('M1', 'M2', 'M5', 'M15', 'M30', 'H1', 'D1')),
            timestamp_utc   TEXT NOT NULL,
            open            REAL NOT NULL,
            high            REAL NOT NULL,
            low             REAL NOT NULL,
            close           REAL NOT NULL,
            volume          REAL,
            real_volume     REAL DEFAULT 0,
            delta           REAL DEFAULT 0,
            received_at     TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (symbol, timeframe, timestamp_utc)
        )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bars_sym_tf_time ON market_bars(symbol, timeframe, timestamp_utc)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bars_time ON market_bars(timestamp_utc)")
        
        conn.execute("INSERT INTO market_bars SELECT * FROM _market_bars_old")
        conn.execute("DROP TABLE _market_bars_old")
        conn.execute("COMMIT")
        print("Migração do CHECK constraint concluída com sucesso!")
    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"Erro durante migração: {e}")
        raise e
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()


def migrate_kalman_state_timeframe(db_path=None):
    """Migra kalman_state para incluir timeframe na chave primária."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='kalman_state'").fetchone()
    if not row:
        conn.close()
        return

    sql = row["sql"]
    if "timeframe" in sql:
        conn.close()
        return
        
    print("Iniciando migração da tabela kalman_state para incluir coluna timeframe...")
    
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN TRANSACTION")
        conn.execute("ALTER TABLE kalman_state RENAME TO _kalman_state_old")
        
        conn.execute("""
        CREATE TABLE kalman_state (
            slug             TEXT NOT NULL,
            timeframe        TEXT NOT NULL DEFAULT 'M5',
            session_date     TEXT NOT NULL,
            state_mean       TEXT NOT NULL,
            state_covariance TEXT NOT NULL,
            johansen_p_value REAL,
            is_cointegrated  INTEGER DEFAULT 1,
            timestamp_utc    TEXT NOT NULL,
            PRIMARY KEY (slug, timeframe, session_date)
        )
        """)
        
        conn.execute("""
            INSERT INTO kalman_state (slug, timeframe, session_date, state_mean, state_covariance, johansen_p_value, is_cointegrated, timestamp_utc)
            SELECT slug, 'M5', session_date, state_mean, state_covariance, johansen_p_value, is_cointegrated, timestamp_utc FROM _kalman_state_old
        """)
        
        conn.execute("DROP TABLE _kalman_state_old")
        conn.execute("COMMIT")
        print("Migração da tabela kalman_state concluída com sucesso!")
    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"Erro durante migração de kalman_state: {e}")
        raise e
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()


def migrate_divergence_config(db_path=None):
    """Adiciona a coluna divergence_config na tabela asset_models se não existir."""
    conn = get_connection(db_path)
    cursor = conn.execute("PRAGMA table_info(asset_models)")
    cols = {row["name"] for row in cursor}

    if "divergence_config" not in cols:
        if _add_column(conn, "ALTER TABLE asset_models ADD COLUMN divergence_config TEXT"):
            print("  + coluna divergence_config adicionada")

    conn.commit()
    conn.close()


def migrate_live_snapshots(db_path=None):
    """Garante que a tabela irai_live_snapshots existe com schema e índices atualizados."""
    conn = get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS irai_live_snapshots (
            target          TEXT NOT NULL,
            timeframe       TEXT NOT NULL DEFAULT 'M5',
            session_date    TEXT NOT NULL,
            timestamp_utc   TEXT NOT NULL,
            bar_idx         INTEGER NOT NULL,
            p_up            REAL NOT NULL,
            score           REAL NOT NULL,
            verdict         TEXT NOT NULL,
            verdict_color   TEXT NOT NULL,
            price_diverge_z REAL,
            price_diverges  INTEGER,
            pair_z          REAL,
            pair_factor     TEXT,
            pair_beta       REAL,
            pair_signal     TEXT,
            pair_fixed_z    REAL,
            pair_fixed_factor TEXT,
            pair_fixed_beta REAL,
            pair_fixed_signal TEXT,
            win_return      REAL,
            win_current     REAL,
            win_open        REAL,
            win_bar_open    REAL,
            win_high        REAL,
            win_low         REAL,
            cum_delta       REAL,
            cum_delta_norm  REAL,
            nwe_center_price REAL,
            nwe_upper_price  REAL,
            nwe_lower_price  REAL,
            nwe_slope        REAL,
            nwe_up_price     REAL,
            nwe_down_price   REAL,
            is_ghost        INTEGER DEFAULT 0,
            is_live_captured INTEGER DEFAULT 1,
            created_at      TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (target, timeframe, session_date, timestamp_utc)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_live_snaps_lookup ON irai_live_snapshots(target, session_date, timeframe)")
    
    # Migrar colunas se faltarem em bancos existentes
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(irai_live_snapshots)")
    cols = [col[1] for col in cursor.fetchall()]
    for col_name, col_type in [("win_bar_open", "REAL"), ("win_high", "REAL"), ("win_low", "REAL"), ("pair_fixed_z", "REAL"), ("pair_fixed_factor", "TEXT"), ("pair_fixed_beta", "REAL"), ("pair_fixed_signal", "TEXT")]:
        if col_name not in cols:
            try:
                cursor.execute(f"ALTER TABLE irai_live_snapshots ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

    conn.commit()
    conn.close()


def save_live_snapshots(conn_or_path, target: str, session_date: str, snapshots: list, timeframe: str = "M5", is_live_captured: int = 1):
    """Salva snapshots no SQLite com política Zero-Repainting:
    
    - Barras fechadas (0..N-1): INSERT OR IGNORE — uma vez gravadas, são IMUTÁVEIS.
      Isso impede que recálculos futuros do engine (ex: troca de fator dominante às 10h30)
      sobrescrevam valores históricos de pair_z, pair_factor, NWE etc.
    - Última barra (N): INSERT OR REPLACE — é a barra em formação, atualizada a cada ciclo.
    """
    if not snapshots:
        return 0

    should_close = False
    if isinstance(conn_or_path, (str, type(None))):
        conn = get_connection(conn_or_path)
        should_close = True
    else:
        conn = conn_or_path

    def _snap_to_tuple(s):
        d = s if isinstance(s, dict) else (s.__dict__ if hasattr(s, '__dict__') else s)
        return (
            target,
            timeframe,
            session_date,
            d.get("timestamp_utc") or d.get("timestamp"),
            d.get("bar_idx", 0),
            d.get("p_up", 50.0),
            d.get("score", 0.0),
            d.get("verdict", "indeciso"),
            d.get("verdict_color", "#7A7F8A"),
            d.get("price_diverge_z"),
            1 if d.get("price_diverges") else 0,
            d.get("pair_z"),
            d.get("pair_factor"),
            d.get("pair_beta"),
            d.get("pair_signal"),
            d.get("pair_fixed_z"),
            d.get("pair_fixed_factor"),
            d.get("pair_fixed_beta"),
            d.get("pair_fixed_signal"),
            d.get("win_return", 0.0),
            d.get("win_current", 0.0),
            d.get("win_open", 0.0),
            d.get("win_bar_open", d.get("win_current", 0.0)),
            d.get("win_high", d.get("win_current", 0.0)),
            d.get("win_low", d.get("win_current", 0.0)),
            d.get("cum_delta", 0.0),
            d.get("cum_delta_norm", 0.0),
            d.get("nwe_center_price"),
            d.get("nwe_upper_price"),
            d.get("nwe_lower_price"),
            d.get("nwe_slope"),
            d.get("nwe_up_price"),
            d.get("nwe_down_price"),
            1 if d.get("is_ghost") else 0,
            is_live_captured
        ) + ((d.get("model_version"),) if with_version else ())

    # Fase 16 (REQ-P03): model_version só é gravado depois da migração (coluna existente).
    with_version = _has_column(conn, "irai_live_snapshots", "model_version")
    extra_cols = ", model_version" if with_version else ""
    n_cols = 35 + (1 if with_version else 0)
    COLUMNS_SQL = f"""(
                target, timeframe, session_date, timestamp_utc, bar_idx,
                p_up, score, verdict, verdict_color, price_diverge_z, price_diverges,
                pair_z, pair_factor, pair_beta, pair_signal,
                pair_fixed_z, pair_fixed_factor, pair_fixed_beta, pair_fixed_signal,
                win_return, win_current, win_open, win_bar_open, win_high, win_low,
                cum_delta, cum_delta_norm, nwe_center_price, nwe_upper_price,
                nwe_lower_price, nwe_slope, nwe_up_price, nwe_down_price, is_ghost, is_live_captured{extra_cols}
            ) VALUES ({", ".join(["?"] * n_cols)})"""

    try:
        # Barras fechadas (0..N-1): IMUTÁVEIS — INSERT OR IGNORE preserva valores originais
        closed_bars = [_snap_to_tuple(s) for s in snapshots[:-1]]
        if closed_bars:
            conn.executemany(
                f"INSERT OR IGNORE INTO irai_live_snapshots {COLUMNS_SQL}",
                closed_bars
            )

        # Última barra (N): MUTÁVEL — INSERT OR REPLACE atualiza a barra em formação
        open_bar = [_snap_to_tuple(snapshots[-1])]
        conn.executemany(
            f"INSERT OR REPLACE INTO irai_live_snapshots {COLUMNS_SQL}",
            open_bar
        )

        conn.commit()
        return len(snapshots)
    finally:
        if should_close:
            conn.close()


def get_live_snapshots(conn_or_path, target: str, session_date: str, timeframe: str = "M5") -> list[dict]:
    """Recupera a série imutável de snapshots gravados para o ativo e sessão."""
    should_close = False
    if isinstance(conn_or_path, (str, type(None))):
        conn = get_connection(conn_or_path)
        should_close = True
    else:
        conn = conn_or_path

    try:
        rows = conn.execute("""
            SELECT * FROM irai_live_snapshots
            WHERE target = ? AND session_date = ? AND timeframe = ?
            ORDER BY timestamp_utc ASC
        """, (target, session_date, timeframe)).fetchall()
        return [dict(r) for r in rows]
    finally:
        if should_close:
            conn.close()


def migrate_drop_snapshots(db_path=None):
    """Remove a tabela antiga irai_snapshots que não é mais utilizada."""
    conn = get_connection(db_path)
    try:
        conn.execute("DROP TABLE IF EXISTS irai_snapshots")
        conn.commit()
        print("  - tabela antiga irai_snapshots removida/ausente")
    except Exception as e:
        print(f"Erro ao remover tabela irai_snapshots: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Todas as migrações aplicadas com sucesso.")
