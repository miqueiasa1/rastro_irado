"""
Script de Repopulação e Higienização do Banco de Dados IRAI.
1. Purga barras e snapshots desalinhados de hoje (2026-08-10).
2. Executa um ciclo completo de coleta limpa no collector.py.
3. Recalcula os snapshots no fuso Tickmill UTC+3 e verifica continuidade.
"""
import os
import sys
import sqlite3
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_connection, DB_PATH
from backend.workers.collector import run_collection_cycle, persist_live_snapshots_cycle

def repopulate_today():
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"=== REPOPULAÇÃO E HIGIENIZAÇÃO DE DADOS ({today_str}) ===")

    conn = get_connection(DB_PATH)
    
    # 1. Purgar snapshots de hoje
    deleted_snaps = conn.execute("DELETE FROM irai_live_snapshots WHERE session_date = ?", (today_str,)).rowcount
    print(f"  - Snapshots expurgados hoje: {deleted_snaps}")

    # 2. Purgar barras B3 (source='br') gravadas no fuso antigo de hoje
    deleted_bars = conn.execute("DELETE FROM market_bars WHERE timestamp_utc LIKE ? AND source = 'br'", (f"{today_str}%",)).rowcount
    print(f"  - Barras B3 expurgadas hoje: {deleted_bars}")

    conn.commit()

    # 3. Executar ciclo de coleta com alinhamento Tickmill UTC+3
    print("  - Executando ciclo de coleta limpa no MT5...")
    results = run_collection_cycle(conn, skip_br=False, cycle_num=1)
    
    print(f"  - Coleta finalizada para {len(results)} símbolos.")

    # 4. Recalcular e persistir snapshots ao vivo
    print("  - Recalculando snapshots de sessão...")
    persist_live_snapshots_cycle(DB_PATH)

    # 5. Diagnóstico de verificação
    snaps_count = conn.execute("SELECT COUNT(*) FROM irai_live_snapshots WHERE session_date = ?", (today_str,)).fetchone()[0]
    bars_count = conn.execute("SELECT COUNT(*) FROM market_bars WHERE timestamp_utc LIKE ?", (f"{today_str}%",)).fetchone()[0]
    
    print(f"=== HIGIENIZAÇÃO CONCLUÍDA ===")
    print(f"  - Total de Barras em market_bars (hoje): {bars_count}")
    print(f"  - Total de Snapshots em irai_live_snapshots (hoje): {snaps_count}")

    conn.close()

if __name__ == "__main__":
    repopulate_today()
