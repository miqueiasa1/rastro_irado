"""Registra os 4 novos índices globais (DE40, US2000, JP225, CHINA50) na tabela asset_models."""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.db import DB_PATH

NEW_ASSETS = [
    {
        "target": "DE40",
        "slug": "de40",
        "display_name": "DAX 40",
        "icon": "DE",
        "session_start_h": 0,
        "session_end_h": 24,
        "source": "tickmill",
        "data_proxy": None
    },
    {
        "target": "US2000",
        "slug": "us2000",
        "display_name": "Russell 2000",
        "icon": "US",
        "session_start_h": 0,
        "session_end_h": 24,
        "source": "tickmill",
        "data_proxy": None
    },
    {
        "target": "JP225",
        "slug": "jp225",
        "display_name": "Nikkei 225",
        "icon": "JP",
        "session_start_h": 0,
        "session_end_h": 24,
        "source": "tickmill",
        "data_proxy": None
    },
    {
        "target": "CHINA50",
        "slug": "china50",
        "display_name": "China A50",
        "icon": "CN",
        "session_start_h": 0,
        "session_end_h": 24,
        "source": "tickmill",
        "data_proxy": None
    },
]

def main():
    if not os.path.exists(DB_PATH):
        print(f"Erro: Banco de dados não encontrado em {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cols = [r[1] for r in conn.execute("PRAGMA table_info(asset_models)").fetchall()]
    has_source = "source" in cols

    for asset in NEW_ASSETS:
        if has_source:
            conn.execute("""
                INSERT INTO asset_models (target, slug, display_name, icon, session_start_h, session_end_h, active, source, data_proxy, factors, factor_labels)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, '[]', '{}')
                ON CONFLICT(target) DO UPDATE SET
                    slug=excluded.slug,
                    display_name=excluded.display_name,
                    icon=excluded.icon,
                    session_start_h=excluded.session_start_h,
                    session_end_h=excluded.session_end_h,
                    active=1,
                    source=excluded.source;
            """, (asset["target"], asset["slug"], asset["display_name"], asset["icon"], asset["session_start_h"], asset["session_end_h"], asset["source"], asset["data_proxy"]))
        else:
            conn.execute("""
                INSERT INTO asset_models (target, slug, display_name, icon, session_start_h, session_end_h, active, data_proxy, factors, factor_labels)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, '[]', '{}')
                ON CONFLICT(target) DO UPDATE SET
                    slug=excluded.slug,
                    display_name=excluded.display_name,
                    icon=excluded.icon,
                    session_start_h=excluded.session_start_h,
                    session_end_h=excluded.session_end_h,
                    active=1;
            """, (asset["target"], asset["slug"], asset["display_name"], asset["icon"], asset["session_start_h"], asset["session_end_h"], asset["data_proxy"]))
        print(f"[OK] Cadastrado/Atualizado: {asset['target']} ({asset['display_name']})")

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM asset_models WHERE active=1").fetchone()[0]
    print(f"\nSucesso: {len(NEW_ASSETS)} ativos registrados. Total de ativos ativos no banco: {total}")
    conn.close()

if __name__ == "__main__":
    main()
