"""Registra EURGBP, EURCHF, EURJPY, GBPJPY, EURAUD na tabela asset_models e verifica estrutura."""
import sqlite3, os

os.environ["PYTHONIOENCODING"] = "utf-8"

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "irai.db")
conn = sqlite3.connect(DB_PATH)

# Verificar colunas disponíveis
cols = [r[1] for r in conn.execute("PRAGMA table_info(asset_models)").fetchall()]
print("Colunas:", cols)

# Inserir os novos ativos
rows_to_insert = [
    ("EURGBP", "eurgbp", "EUR/GBP", 0, 24, 1, "tickmill"),
    ("EURCHF", "eurchf", "EUR/CHF", 0, 24, 1, "tickmill"),
    ("EURJPY", "eurjpy", "EUR/JPY", 0, 24, 1, "tickmill"),
    ("GBPJPY", "gbpjpy", "GBP/JPY", 0, 24, 1, "tickmill"),
    ("EURAUD", "euraud", "EUR/AUD", 0, 24, 1, "tickmill"),
]

for row in rows_to_insert:
    target, slug, display_name, s_start, s_end, active, source = row
    if "source" in cols:
        conn.execute(
            "INSERT OR IGNORE INTO asset_models (target, slug, display_name, session_start_h, session_end_h, active, source, factors, factor_labels) VALUES (?,?,?,?,?,?,?,?,?)",
            (target, slug, display_name, s_start, s_end, active, source, "[]", "{}")
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO asset_models (target, slug, display_name, session_start_h, session_end_h, active, factors, factor_labels) VALUES (?,?,?,?,?,?,?,?)",
            (target, slug, display_name, s_start, s_end, active, "[]", "{}")
        )

conn.commit()

# Confirmar
registered = conn.execute(
    "SELECT target, slug, display_name, session_start_h, session_end_h FROM asset_models WHERE target IN ('EURGBP', 'EURCHF', 'EURJPY', 'GBPJPY', 'EURAUD')"
).fetchall()
print("Registrados:")
for r in registered:
    print(" ", r)

total = conn.execute("SELECT COUNT(*) FROM asset_models WHERE active=1").fetchone()[0]
print(f"Total de ativos ativos: {total}")
conn.close()
print("OK")
