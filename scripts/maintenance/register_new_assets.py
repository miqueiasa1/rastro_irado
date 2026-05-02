"""Registra CADCHF e AUDNZD na tabela asset_models e verifica estrutura."""
import sqlite3, os, sys

os.environ["PYTHONIOENCODING"] = "utf-8"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "irai.db")
conn = sqlite3.connect(DB_PATH)

# Verificar colunas disponíveis
cols = [r[1] for r in conn.execute("PRAGMA table_info(asset_models)").fetchall()]
print("Colunas:", cols)

# Inserir os dois novos ativos
rows_to_insert = [
    ("CADCHF", "cadchf", "CAD/CHF", 3, 22, 1, "tickmill"),
    ("AUDNZD", "audnzd", "AUD/NZD", 3, 22, 1, "tickmill"),
]

for row in rows_to_insert:
    target, slug, display_name, s_start, s_end, active, source = row
    # Build insert dinamicamente com colunas que existem
    if "source" in cols:
        conn.execute(
            "INSERT OR IGNORE INTO asset_models (target, slug, display_name, session_start_h, session_end_h, active, source) VALUES (?,?,?,?,?,?,?)",
            (target, slug, display_name, s_start, s_end, active, source)
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO asset_models (target, slug, display_name, session_start_h, session_end_h, active) VALUES (?,?,?,?,?,?)",
            (target, slug, display_name, s_start, s_end, active)
        )

conn.commit()

# Confirmar
registered = conn.execute(
    "SELECT target, slug, display_name, session_start_h, session_end_h FROM asset_models WHERE target IN ('CADCHF','AUDNZD')"
).fetchall()
print("Registrados:")
for r in registered:
    print(" ", r)

total = conn.execute("SELECT COUNT(*) FROM asset_models WHERE active=1").fetchone()[0]
print(f"Total ativos ativos: {total}")
conn.close()
print("OK")
