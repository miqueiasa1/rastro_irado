"""
IRAI — Backfill de Histórico para o Firebase Realtime Database.

Sincroniza séries, resumos, panoramas (overview) e volatilidades GARCH
para todas as datas disponíveis no SQLite local para o Firebase.

Estrutura no Firebase:
  /dates                              -> { dates: [ "YYYY-MM-DD", ... ] }
  /by_date/{YYYY-MM-DD}/series/{tgt}  -> Lista de barras do dia
  /by_date/{YYYY-MM-DD}/summaries/{tgt} -> Resumo do dia
  /by_date/{YYYY-MM-DD}/history/{tgt} -> Fechamentos históricos do dia
  /by_date/{YYYY-MM-DD}/garch/{tgt}   -> Dados GARCH do dia
  /by_date/{YYYY-MM-DD}/overview      -> Visão geral de todos alvos na data

Uso:
  python scripts/backfill_firebase_history.py [--limit 60]
"""

import os
import sys
import time
import argparse
import firebase_admin
from firebase_admin import credentials, db

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carregar variáveis de ambiente (.env)
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val.strip()

FIREBASE_URL = os.environ.get("FIREBASE_URL")
SERVICE_ACCOUNT_KEY = os.path.join(os.path.dirname(__file__), '..', 'serviceAccountKey.json')

if not FIREBASE_URL:
    print("Erro: FIREBASE_URL não está configurada no .env")
    sys.exit(1)

if not firebase_admin._apps:
    if os.path.exists(SERVICE_ACCOUNT_KEY):
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
    else:
        firebase_admin.initialize_app(options={'databaseURL': FIREBASE_URL})

import backend.api.main as api_main
from backend.db import DB_PATH, get_connection
from backend.irai.engine import IRAIEngine


def get_dates(limit=60):
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT date(timestamp_utc) as dt FROM market_bars WHERE timeframe='M5' ORDER BY dt DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [r["dt"] for r in rows if r["dt"]]


def clean_for_firebase(val):
    if isinstance(val, dict):
        new_dict = {}
        for k, v in val.items():
            safe_k = str(k).replace('$', '_').replace('.', '_').replace('#', '_').replace('[', '_').replace(']', '_').replace('/', '_')
            new_dict[safe_k] = clean_for_firebase(v)
        return new_dict
    elif isinstance(val, list):
        return [clean_for_firebase(x) for x in val]
    else:
        return val


def backfill_history(limit=60):
    print("=" * 70)
    print("  IRAI — Sincronização de Histórico para o Firebase")
    print(f"  Firebase URL: {FIREBASE_URL}")
    print("=" * 70)

    engine = IRAIEngine(db_path=DB_PATH)
    api_main.engine = engine
    targets_list = engine.registered_targets
    print(f"Alvos registrados no Engine: {len(targets_list)}")

    dates = get_dates(limit=limit)
    if not dates:
        print("Nenhuma data encontrada no SQLite!")
        return

    print(f"Datas a processar ({len(dates)}): {dates[0]} até {dates[-1]}")

    # Atualizar /dates e /targets
    dates_payload = clean_for_firebase({"dates": dates})
    targets_payload = clean_for_firebase({
        "targets": [
            {
                "target": t["target"],
                "slug": t["slug"],
                "display_name": t["display_name"],
                "icon": t["icon"],
                "accuracy": t.get("accuracy"),
                "r_squared": t.get("r_squared"),
                "calibrated": t.get("accuracy") is not None,
                "session_start_h": t.get("session_start_h", 0),
                "session_hours": f"{t['session_start_h']:02d}h-{t['session_end_h']:02d}h",
                "divergence_config": t.get("divergence_config"),
            }
            for t in targets_list
        ]
    })

    ref = db.reference('/')
    ref.child('dates').set(dates_payload)
    ref.child('targets').set(targets_payload)
    ref.child('last_update').set(time.time())
    print("[SUCESSO] /dates e /targets atualizados no Firebase.")

    for idx, session_date in enumerate(dates):
        print(f"\n[{idx+1}/{len(dates)}] Processando sessão {session_date}...")
        
        # 1. Compute overview for date
        try:
            raw_overview = api_main._get_overview_data_sync(session_date, "v2")
            overview_data = clean_for_firebase(raw_overview)
        except Exception as e:
            print(f"  Erro ao gerar overview para {session_date}: {e}")
            overview_data = None

        series_map = {}
        summaries_map = {}
        history_map = {}
        garch_map = {}
        gex_map = {}

        for t in targets_list:
            target = t["target"]
            if not t.get("accuracy"):
                continue
            safe_target = target.replace('$', '_').replace('.', '_')
            
            try:
                series_data = api_main._get_series_data_sync(target, session_date, "v2")
                if series_data and "error" not in series_data:
                    raw_series = series_data.get("series", [])
                    lean_series = []
                    for i, bar in enumerate(raw_series):
                        if i == len(raw_series) - 1:
                            lean_series.append(bar)
                        else:
                            lean_bar = {k: v for k, v in bar.items() if k not in ("factors", "stale_factors")}
                            lean_series.append(lean_bar)
                    
                    series_map[safe_target] = clean_for_firebase(lean_series)
                    summaries_map[safe_target] = clean_for_firebase(series_data.get("summary", {}))
                    history_map[safe_target] = clean_for_firebase(series_data.get("history_closes", []))
            except Exception as e:
                print(f"  Erro série {target} em {session_date}: {e}")

            # GARCH data for date
            try:
                garch_symbol = 'IBOV' if target == 'WIN$N' else target
                conn = get_connection()
                row = conn.execute(
                    "SELECT history_json, forecast_json, updated_at FROM garch_volatility WHERE symbol = ? AND session_date = ?",
                    (garch_symbol, session_date)
                ).fetchone()
                conn.close()
                if row:
                    import json
                    garch_data = {
                        "symbol": garch_symbol,
                        "session_date": session_date,
                        "history": json.loads(row["history_json"]),
                        "forecast": json.loads(row["forecast_json"]),
                        "updated_at": row["updated_at"]
                    }
                    garch_map[safe_target] = clean_for_firebase(garch_data)
            except Exception as e:
                pass

            # GEX data for date (with fallback to latest <= session_date)
            try:
                import json
                conn = get_connection()
                eff_gex_date = session_date
                runs = [r[0] for r in conn.execute(
                    "SELECT DISTINCT run_name FROM gex_levels WHERE target = ? AND session_date = ? ORDER BY run_name DESC",
                    (target, eff_gex_date)
                ).fetchall()]
                if not runs:
                    l_row = conn.execute(
                        "SELECT session_date FROM gex_levels WHERE target = ? AND session_date <= ? ORDER BY session_date DESC LIMIT 1",
                        (target, session_date)
                    ).fetchone()
                    if l_row:
                        eff_gex_date = l_row["session_date"]
                        runs = [r[0] for r in conn.execute(
                            "SELECT DISTINCT run_name FROM gex_levels WHERE target = ? AND session_date = ? ORDER BY run_name DESC",
                            (target, eff_gex_date)
                        ).fetchall()]
                if runs:
                    g_row = conn.execute(
                        "SELECT levels_json FROM gex_levels WHERE target = ? AND session_date = ? AND run_name = ?",
                        (target, eff_gex_date, runs[0])
                    ).fetchone()
                    if g_row:
                        gex_payload = {
                            "target": target,
                            "date": session_date,
                            "effective_gex_date": eff_gex_date,
                            "selected_run": runs[0],
                            "available_runs": runs,
                            "levels": json.loads(g_row["levels_json"])
                        }
                        gex_map[safe_target] = clean_for_firebase(gex_payload)
                        if safe_target in summaries_map and isinstance(summaries_map[safe_target], dict):
                            summaries_map[safe_target]["gex"] = clean_for_firebase(gex_payload)
                conn.close()
            except Exception as e:
                pass

        # 2. Upload under allowed top-level paths: /series/{session_date}/{safe_target}, /summaries/{session_date}/{safe_target}, etc.
        if overview_data:
            ref.child(f'overview/{session_date}').set(overview_data)

        for safe_target, t_series in series_map.items():
            ref.child(f'series/{session_date}/{safe_target}').set(t_series)
        for safe_target, t_summary in summaries_map.items():
            ref.child(f'summaries/{session_date}/{safe_target}').set(t_summary)
        for safe_target, t_history in history_map.items():
            ref.child(f'history/{session_date}/{safe_target}').set(t_history)
        for safe_target, t_garch in garch_map.items():
            ref.child(f'garch/{session_date}/{safe_target}').set(t_garch)
        for safe_target, t_gex in gex_map.items():
            ref.child(f'summaries/gex/{session_date}/{safe_target}').set(t_gex)

        # 3. If latest date, also set top-level /series/{safe_target} for backward compatibility & live polling
        if idx == 0:
            if overview_data:
                ref.child('overview').set(overview_data)
            for safe_target, t_series in series_map.items():
                ref.child(f'series/{safe_target}').set(t_series)
            for safe_target, t_summary in summaries_map.items():
                ref.child(f'summaries/{safe_target}').set(t_summary)
            for safe_target, t_history in history_map.items():
                ref.child(f'history/{safe_target}').set(t_history)
            for safe_target, t_garch in garch_map.items():
                ref.child(f'garch/{safe_target}').set(t_garch)
            for safe_target, t_gex in gex_map.items():
                ref.child(f'summaries/gex/{safe_target}').set(t_gex)

        print(f"  [OK] Sessão {session_date} enviada ({len(series_map)} ativos).")

    print("\n" + "=" * 70)
    print("  [CONCLUÍDO] Backfill de histórico enviado com sucesso para o Firebase!")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IRAI - Backfill de Historico Firebase")
    parser.add_argument("--limit", type=int, default=60, help="Limite de dias passados a enviar")
    args = parser.parse_args()

    backfill_history(limit=args.limit)
