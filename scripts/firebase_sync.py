import os
import time
import json
import urllib.request
import urllib.parse
import firebase_admin
from firebase_admin import credentials, db

# Load environment variables manually
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val

FIREBASE_URL = os.environ.get("FIREBASE_URL")
LOCAL_API = "http://localhost:8889"

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
    
    # 4. Puxar a série de cada target calibrado
    series_map = {}
    summaries_map = {}
    history_map = {}
    for target_obj in targets:
        target = target_obj['target']
        safe_target = target.replace('$', '_').replace('.', '_')
        if not target_obj.get('calibrated'):
            continue
            
        target_encoded = urllib.parse.quote(target)
        # Sincroniza a versão correspondente para o Firebase
        series_data = fetch_json(f"{LOCAL_API}/api/irai/series?session_date={current_date}&target={target_encoded}&version={used_version}")
        if series_data:
            raw_series = series_data.get("series", [])
            lean_series = []
            for i, bar in enumerate(raw_series):
                # Mantemos o objeto completo (com "factors", etc.) APENAS na última barra (atual)
                # para que os cards e a tabela lateral exibam os fatores em tempo real normalmente.
                if i == len(raw_series) - 1:
                    lean_series.append(bar)
                else:
                    # Removemos os campos pesados (não utilizados nos gráficos históricos) das barras anteriores
                    lean_bar = {k: v for k, v in bar.items() if k not in ("factors", "stale_factors")}
                    lean_series.append(lean_bar)
            series_map[safe_target] = lean_series
            summaries_map[safe_target] = series_data.get("summary", {})
            history_map[safe_target] = series_data.get("history_closes", [])
    
    # 5. Montar payload flat para atualização atômica via SDK
    update_payload = {
        "dates": dates_data,
        "overview": overview_data,
        "targets": targets_data,
        "last_update": time.time()
    }
    
    for safe_target, target_series in series_map.items():
        update_payload[f"series/{safe_target}"] = target_series
        
    for safe_target, target_summary in summaries_map.items():
        update_payload[f"summaries/{safe_target}"] = target_summary

    for safe_target, target_history in history_map.items():
        update_payload[f"history/{safe_target}"] = target_history
    
    # 6. Gravar usando SDK do Firebase Admin (garante autenticação nativa)
    try:
        ref = db.reference('/')
        ref.update(update_payload)
        print("  [Sucesso] Payload enviado ao Firebase.")
    except Exception as e:
        print(f"  [Erro] Falha ao enviar para o Firebase: {e}")

if __name__ == "__main__":
    print(f"Iniciando Sincronizador Firebase (SDK de Produção)")
    print(f"Alvo: {FIREBASE_URL}")
    while True:
        sync()
        time.sleep(60)
