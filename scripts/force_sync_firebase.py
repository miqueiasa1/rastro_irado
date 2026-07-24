"""Força a sincronização completa de todos os 24 ativos diretamente para o Firebase sem depender do servidor local."""
import os
import sys
import time
import json
import urllib.parse
import firebase_admin
from firebase_admin import credentials, db

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env vars
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val

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

def get_dates():
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT date(timestamp_utc) as dt FROM market_bars ORDER BY dt DESC LIMIT 30").fetchall()
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

def main():
    print("=== Sincronização Direta de 14 Ativos para o Firebase ===")
    engine = IRAIEngine(db_path=DB_PATH)
    api_main.engine = engine
    targets_list = engine.registered_targets
    print(f"Total alvos no Engine: {len(targets_list)}")

    dates = get_dates()
    if not dates:
        print("Sem datas no banco!")
        return
    current_date = dates[0]
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

    overview_data = clean_for_firebase(api_main._get_overview_data_sync(current_date, "v2"))

    series_map = {}
    summaries_map = {}
    history_map = {}

    for t in targets_list:
        target = t["target"]
        if not t.get("accuracy"):
            continue
        safe_target = target.replace('$', '_').replace('.', '_')
        series_data = api_main._get_series_data_sync(target, current_date, "v2")
        if series_data:
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

    print(f"Enviando atualização de {len(targets_list)} alvos ao Firebase ({FIREBASE_URL})...")
    ref = db.reference('/')
    ref.child('dates').set(dates_payload)
    ref.child('overview').set(overview_data)
    ref.child('targets').set(targets_payload)
    ref.child('last_update').set(time.time())

    for safe_target, target_series in series_map.items():
        ref.child(f'series/{safe_target}').set(target_series)

    for safe_target, target_summary in summaries_map.items():
        ref.child(f'summaries/{safe_target}').set(target_summary)

    for safe_target, target_history in history_map.items():
        ref.child(f'history/{safe_target}').set(target_history)

    print("[SUCESSO] Firebase totalmente atualizado com os 14 ativos!")
    print("[SUCESSO] Firebase totalmente atualizado com os novos ativos!")

if __name__ == "__main__":
    main()
