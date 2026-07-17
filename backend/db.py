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

-- Cache de snapshots IRAI computados
CREATE TABLE IF NOT EXISTS irai_snapshots (
    session_date    TEXT NOT NULL,          -- YYYY-MM-DD em BRT
    timestamp_utc   TEXT NOT NULL,
    bar_idx         INTEGER NOT NULL,       -- 0..95
    p_up            REAL NOT NULL,
    score           REAL NOT NULL,
    z_dol           REAL, z_di REAL, z_vix REAL, z_dxy REAL,
    z_brent         REAL, z_us500 REAL, z_btcusd REAL,
    c_dol           REAL, c_di REAL, c_vix REAL, c_dxy REAL,
    c_brent         REAL, c_us500 REAL, c_btcusd REAL,
    win_return      REAL,                   -- retorno % WIN desde open
    stale_flags     TEXT,                   -- JSON array com fatores stale
    computed_at     TEXT NOT NULL,
    PRIMARY KEY (session_date, timestamp_utc)
);

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
"""

def get_connection(db_path=None):
    """Retorna conexão SQLite com WAL mode."""
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
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


def migrate_delta(db_path=None):
    """Adiciona colunas real_volume e delta se não existirem (migração)."""
    conn = get_connection(db_path)
    cursor = conn.execute("PRAGMA table_info(market_bars)")
    cols = {row["name"] for row in cursor}

    if "real_volume" not in cols:
        conn.execute("ALTER TABLE market_bars ADD COLUMN real_volume REAL DEFAULT 0")
        print("  + coluna real_volume adicionada")
    if "delta" not in cols:
        conn.execute("ALTER TABLE market_bars ADD COLUMN delta REAL DEFAULT 0")
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


def save_kalman_state(conn, slug: str, timeframe: str, session_date: str, state_mean, state_covariance, p_value: float, is_cointegrated: bool, timestamp_utc: str):
    """Salva o estado atual do filtro de Kalman e teste de Johansen com guard de timestamp."""
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
        
    conn.execute("""
        INSERT OR REPLACE INTO kalman_state 
        (slug, timeframe, session_date, state_mean, state_covariance, johansen_p_value, is_cointegrated, timestamp_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (slug, timeframe, session_date, json.dumps(state_mean), json.dumps(state_covariance), p_value, int(is_cointegrated), timestamp_utc))
    conn.commit()


def load_kalman_state(conn, slug: str, timeframe: str, session_date: str):
    """Carrega o último estado do filtro de Kalman para o ativo e timeframe anterior à data informada."""
    import json
    import numpy as np
    
    row = conn.execute("""
        SELECT state_mean, state_covariance, johansen_p_value, is_cointegrated, timestamp_utc
        FROM kalman_state
        WHERE slug = ? AND timeframe = ? AND session_date < ?
        ORDER BY session_date DESC LIMIT 1
    """, (slug, timeframe, session_date)).fetchone()
    
    if not row:
        return None
        
    return {
        "state_mean": np.array(json.loads(row["state_mean"])),
        "state_covariance": np.array(json.loads(row["state_covariance"])),
        "johansen_p_value": row["johansen_p_value"],
        "is_cointegrated": bool(row["is_cointegrated"]),
        "timestamp_utc": row["timestamp_utc"]
    }


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
        print("Adicionando coluna divergence_config à tabela asset_models...")
        try:
            conn.execute("ALTER TABLE asset_models ADD COLUMN divergence_config TEXT")
            conn.commit()
            print("Coluna divergence_config adicionada com sucesso!")
        except Exception as e:
            print(f"Erro ao adicionar coluna divergence_config: {e}")
    conn.close()


if __name__ == "__main__":
    init_db()
    migrate_delta()
    migrate_kalman_state()
    migrate_divergence_config()
