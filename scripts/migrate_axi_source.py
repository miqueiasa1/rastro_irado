"""
Migração: Adicionar 'axi' como source válido na tabela market_bars.
SQLite não permite ALTER CHECK, então recriamos a tabela preservando dados.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "irai.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Check current constraint
    schema = conn.execute("SELECT sql FROM sqlite_master WHERE name='market_bars'").fetchone()
    current = schema[0]
    
    if "'axi'" in current:
        print("Constraint already includes 'axi' - nothing to do")
        conn.close()
        return
    
    print(f"Current schema:\n{current}\n")
    print("Migrating to include 'axi' source...")
    
    conn.executescript("""
        -- 1. Renomear tabela atual
        ALTER TABLE market_bars RENAME TO market_bars_old;
        
        -- 2. Criar tabela nova com constraint atualizada
        CREATE TABLE market_bars (
            symbol          TEXT NOT NULL,
            source          TEXT NOT NULL CHECK (source IN ('br', 'tickmill', 'axi')),
            timeframe       TEXT NOT NULL CHECK (timeframe IN ('M5', 'D1')),
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
        );
        
        -- 3. Copiar dados
        INSERT INTO market_bars 
            SELECT symbol, source, timeframe, timestamp_utc, open, high, low, close,
                   volume, real_volume, delta, received_at
            FROM market_bars_old;
        
        -- 4. Recriar indices
        CREATE INDEX IF NOT EXISTS idx_bars_sym_tf_time ON market_bars(symbol, timeframe, timestamp_utc);
        CREATE INDEX IF NOT EXISTS idx_bars_time ON market_bars(timestamp_utc);
        
        -- 5. Drop tabela antiga
        DROP TABLE market_bars_old;
    """)
    
    conn.commit()
    
    # Verify
    new_schema = conn.execute("SELECT sql FROM sqlite_master WHERE name='market_bars'").fetchone()
    count = conn.execute("SELECT COUNT(*) FROM market_bars").fetchone()[0]
    print(f"\nNew schema:\n{new_schema[0]}")
    print(f"\nRows preserved: {count:,}")
    
    conn.close()
    print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
