import os
import sys
import time
import json
import urllib.request
import urllib.parse
import firebase_admin
from firebase_admin import credentials, db

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables manually
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val

FIREBASE_URL = os.environ.get("FIREBASE_URL")
LOCAL_API = "http://localhost:8888"

# Path to service account key in the root folder
SERVICE_ACCOUNT_KEY = os.path.join(os.path.dirname(__file__), '..', 'serviceAccountKey.json')

if not FIREBASE_URL:
    print("Erro: FIREBASE_URL não está configurada no .env")
    exit(1)

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    if os.path.exists(SERVICE_ACCOUNT_KEY):
        print(f"[{time.strftime('%H:%M:%S')}] Usando autenticação de Conta de Serviço: {SERVICE_ACCOUNT_KEY}")
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY)
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_URL
        })
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Aviso: Arquivo '{SERVICE_ACCOUNT_KEY}' não encontrado.")
        print("                  Tentando acesso sem autenticação (as regras do Firebase precisam estar públicas)...")
        firebase_admin.initialize_app(options={
            'databaseURL': FIREBASE_URL
        })

def clean_for_firebase(val):
    if isinstance(val, dict):
        new_dict = {}
        for k, v in val.items():
            safe_k = str(k).replace('$', '_').replace('.', '_').replace('#', '_').replace('[', '_').replace(']', '_').replace('/', '_').replace(':', '_')
            new_dict[safe_k] = clean_for_firebase(v)
        return new_dict
    elif isinstance(val, list):
        return [clean_for_firebase(x) for x in val]
    elif isinstance(val, float):
        import math
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    else:
        return val

from backend.public_payload import build_lean_series  # noqa: E402  (fase 19A, REQ-S01)


def fetch_json(url):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"  [Erro] Falha ao puxar {url}: {e}")
        return None

def sync():
    print(f"[{time.strftime('%H:%M:%S')}] Iniciando sincronização com Firebase...")
    
    # 1. Puxar as datas ativas
    dates_data = fetch_json(f"{LOCAL_API}/api/irai/dates")
    if not dates_data or not dates_data.get('dates'):
        print("  Sem datas disponíveis.")
        return
    
    current_date = dates_data['dates'][0]
    
    # 2. Puxar Overview para dados em tempo real dos cards (usando V2 com fallback para V1 se vier vazio)
    overview_data = fetch_json(f"{LOCAL_API}/api/irai/overview?version=v2")
    used_version = "v2"
    if not overview_data or not overview_data.get("targets"):
        print("  [Fallback] Overview V2 vazio ou falhou. Tentando versão V1 (estática)...")
        overview_data = fetch_json(f"{LOCAL_API}/api/irai/overview?version=v1")
        used_version = "v1"
    
    # 3. Puxar lista de targets
    targets_data = fetch_json(f"{LOCAL_API}/api/irai/targets")
    targets = targets_data.get("targets", []) if targets_data else []
    
    # Se o API local retornar menos de 20 alvos (servidor antigo em memória), força recarga via engine
    try:
        from backend.db import DB_PATH, get_connection
        from backend.irai.engine import IRAIEngine
        engine = IRAIEngine(db_path=DB_PATH)
        db_targets = engine.registered_targets
        if len(targets) < len(db_targets):
            print(f"  [Fallback Direct Engine] API retornou {len(targets)} alvos, mas o banco possui {len(db_targets)}. Sincronizando todos os {len(db_targets)} ativos.")
            import backend.api.main as api_main
            api_main.engine = engine
            targets_data = {
                "targets": [
                    {
                        "target": t["target"],
                        "slug": t["slug"],
                        "display_name": t["display_name"],
                        "icon": t["icon"],
                        "accuracy": t.get("accuracy"),
                        "r_squared": t.get("r_squared"),
                        "calibrated": bool(t.get("calibrated", t.get("accuracy") is not None)),
                        "model_version": t.get("model_version"),
                        "forecast_mode": t.get("forecast_mode", "off"),
                        "forecast_ui": t.get("forecast_ui", "off"),
                        "session_start_h": t.get("session_start_h", 0),
                        "session_hours": f"{t['session_start_h']:02d}h-{t['session_end_h']:02d}h",
                        "divergence_config": t.get("divergence_config"),
                    }
                    for t in db_targets
                ]
            }
            targets = targets_data["targets"]
            overview_data = api_main._get_overview_data_sync(current_date, "v2")
    except Exception as e:
        print(f"  [Warning Engine Fallback]: {e}")

    health_data = fetch_json(f"{LOCAL_API}/api/health")
    
    # 4. Puxar a série de cada target calibrado
    series_map = {}
    summaries_map = {}
    history_map = {}
    garch_map = {}
    gex_map = {}
    for target_obj in targets:
        target = target_obj['target']
        safe_target = target.replace('$', '_').replace('.', '_')
        if not target_obj.get('calibrated'):
            continue
            
        target_encoded = urllib.parse.quote(target)
        series_data = fetch_json(f"{LOCAL_API}/api/irai/series?session_date={current_date}&target={target_encoded}&version={used_version}")
        if not series_data or "error" in series_data:
            # Fix 13/11/2026: sem fallback no proprio processo (o engine da API nao existe aqui e o
            # calculo local disputaria o lock de escrita do SQLite com o collector). Pula o ativo neste
            # ciclo; o Firebase mantem o ultimo valor bom e o proximo ciclo (60 s) tenta de novo.
            # Pula so a serie (series/summaries/history); GARCH e GEX do ativo continuam sendo publicados.
            print(f"  [Skip] Serie indisponivel para {target} em {current_date}; tenta de novo no proximo ciclo (GARCH/GEX seguem).")
            series_data = None
        if series_data:
            series_map[safe_target] = build_lean_series(series_data.get("series", []))
            summaries_map[safe_target] = series_data.get("summary", {})
            history_map[safe_target] = series_data.get("history_closes", [])
        
        # Puxar dados de GARCH para o alvo
        garch_symbol = 'IBOV' if target == 'WIN$N' else target
        garch_data = fetch_json(f"{LOCAL_API}/api/garch?symbol={urllib.parse.quote(garch_symbol)}&date={current_date}")
        if garch_data and not garch_data.get("error"):
            garch_map[safe_target] = garch_data
            if safe_target in summaries_map and isinstance(summaries_map[safe_target], dict):
                summaries_map[safe_target]["garch"] = garch_data

        # Puxar dados de GEX para o alvo
        gex_data = fetch_json(f"{LOCAL_API}/api/gex?target={target_encoded}&date={current_date}")
        if gex_data and isinstance(gex_data.get("levels"), list) and len(gex_data["levels"]) > 0:
            gex_map[safe_target] = gex_data
            if safe_target in summaries_map and isinstance(summaries_map[safe_target], dict):
                summaries_map[safe_target]["gex"] = gex_data
    
    # 5. Montar payload flat para atualização atômica via SDK
    update_payload = {
        "dates": clean_for_firebase(dates_data),
        "overview": clean_for_firebase(overview_data),
        "targets": clean_for_firebase(targets_data),
        "last_update": time.time()
    }
    if health_data:
        update_payload["health"] = clean_for_firebase(health_data)

    # Health Watchdog status (from local JSON file)
    try:
        import json as _json
        from pathlib import Path
        watchdog_path = Path(__file__).resolve().parent.parent / "data" / "health_status.json"
        if watchdog_path.exists():
            with open(watchdog_path, encoding="utf-8") as f:
                watchdog_data = _json.load(f)
            # Calculate age
            generated_at = watchdog_data.get("generated_at", "")
            age_s = 0
            try:
                from datetime import datetime as _dt, timezone as _tz
                gen_dt = _dt.fromisoformat(generated_at)
                age_s = (_dt.now(_tz.utc) - gen_dt).total_seconds()
            except Exception:
                pass
            update_payload["health_watchdog"] = clean_for_firebase({
                "available": True,
                "healthy": watchdog_data.get("healthy"),
                "stale": age_s > 15 * 60,
                "generated_at": generated_at,
                "age_seconds": round(age_s),
                "components": watchdog_data.get("components", []),
            })
    except Exception as e:
        print(f"  [Watchdog] Não consegui ler health_status.json: {e}")
    
    for safe_target, target_series in series_map.items():
        update_payload[f"series/{current_date}/{safe_target}"] = clean_for_firebase(target_series)
        update_payload[f"series/{safe_target}"] = clean_for_firebase(target_series)
        
    for safe_target, target_summary in summaries_map.items():
        update_payload[f"summaries/{current_date}/{safe_target}"] = clean_for_firebase(target_summary)
        update_payload[f"summaries/{safe_target}"] = clean_for_firebase(target_summary)

    for safe_target, target_history in history_map.items():
        update_payload[f"history/{current_date}/{safe_target}"] = clean_for_firebase(target_history)
        update_payload[f"history/{safe_target}"] = clean_for_firebase(target_history)
    
    for safe_target, target_garch in garch_map.items():
        update_payload[f"garch/{current_date}/{safe_target}"] = clean_for_firebase(target_garch)
        update_payload[f"garch/{safe_target}"] = clean_for_firebase(target_garch)

    for safe_target, target_gex in gex_map.items():
        update_payload[f"summaries/gex/{current_date}/{safe_target}"] = clean_for_firebase(target_gex)
        update_payload[f"summaries/gex/{safe_target}"] = clean_for_firebase(target_gex)

    if overview_data:
        update_payload[f"overview/{current_date}"] = clean_for_firebase(overview_data)

    # Fase 21A (deploy aprovado pelo owner em 16/11/2026): eval/<target> com a assertividade fora da
    # amostra (ultimos 20 pregoes) para o ReliabilityCard do site publico. Leitura publica pela regra
    # eval/$target; escrita so pelo Admin SDK. Desligavel com IRAI_DISABLE_EVAL_SYNC=1.
    if os.environ.get("IRAI_DISABLE_EVAL_SYNC") != "1":
        for eval_target in ("WIN$N", "WDO$N"):
            eval_data = fetch_json(f"{LOCAL_API}/api/eval/assertividade?target={urllib.parse.quote(eval_target)}&window=20")
            if eval_data and eval_data.get("available"):
                safe_eval = eval_target.replace('$', '_').replace('.', '_')
                update_payload[f"eval/{safe_eval}"] = clean_for_firebase(eval_data)

    # Pine Script: publicado apenas pelo sync diário (scripts/sync_gex_to_irai.py → pine_vault).
    # Não reenviar aqui a cada 60s (desperdício de banda e sobrescreve metadados).
    
    # 6. Gravar usando SDK do Firebase Admin (garante autenticação nativa)
    # Pré-sanitização: garantir que o payload inteiro é JSON-serializável
    import math
    def _deep_sanitize(obj):
        if isinstance(obj, dict):
            return {k: _deep_sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_deep_sanitize(v) for v in obj]
        elif isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, (int, bool, str, type(None))):
            return obj
        else:
            return str(obj)  # numpy, Decimal, etc.
    
    update_payload = _deep_sanitize(update_payload)
    
    # Enviar em lotes de no máximo BATCH_SIZE chaves (payload gigante falha no Firebase)
    BATCH_SIZE = 30
    keys = list(update_payload.keys())
    total_ok = 0
    total_err = 0
    
    for i in range(0, len(keys), BATCH_SIZE):
        batch_keys = keys[i:i + BATCH_SIZE]
        batch = {k: update_payload[k] for k in batch_keys}
        try:
            db.reference('/').update(batch)
            total_ok += len(batch_keys)
        except Exception as e:
            print(f"  [Aviso] Lote {i//BATCH_SIZE + 1} falhou ({e}), enviando individualmente...")
            for key in batch_keys:
                try:
                    db.reference(f'/{key}').set(update_payload[key])
                    total_ok += 1
                except Exception as e2:
                    print(f"    [!!] {key}: {e2}")
                    total_err += 1
    
    if total_err == 0:
        print(f"  [Sucesso] {total_ok} chaves enviadas ao Firebase.")
    else:
        print(f"  [Parcial] {total_ok} OK, {total_err} erros.")

if __name__ == "__main__":
    print(f"Iniciando Sincronizador Firebase (SDK de Produção)")
    print(f"Alvo: {FIREBASE_URL}")
    failures = 0
    while True:
        try:
            sync()
            failures = 0
        except Exception as e:
            failures += 1
            print(f"[{time.strftime('%H:%M:%S')}] [Erro Crítico Loop #{failures}]: {e}")
        # Backoff exponencial em falhas consecutivas (60s → 120s → 240s … até 15 min)
        time.sleep(min(60 * (2 ** min(failures, 4)), 900) if failures else 60)
