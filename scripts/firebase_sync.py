import os
import time
import json
import urllib.request
import urllib.error

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

if not FIREBASE_URL:
    print("Erro: FIREBASE_URL não está configurada no .env")
    exit(1)

# Ensure URL ends with /db.json
if not FIREBASE_URL.endswith("db.json"):
    FIREBASE_URL = FIREBASE_URL.rstrip("/") + "/db.json"

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
    
    # 2. Puxar Overview para dados em tempo real dos cards
    overview_data = fetch_json(f"{LOCAL_API}/api/irai/overview")
    
    # 3. Puxar lista de targets
    targets_data = fetch_json(f"{LOCAL_API}/api/irai/targets")
    targets = targets_data.get("targets", []) if targets_data else []
    
    # 4. Puxar a série de cada target calibrado
    series_map = {}
    summaries_map = {}
    for target_obj in targets:
        target = target_obj['target']
        safe_target = target.replace('$', '_').replace('.', '_')
        if not target_obj.get('calibrated'):
            continue
            
        import urllib.parse
        target_encoded = urllib.parse.quote(target)
        series_data = fetch_json(f"{LOCAL_API}/api/irai/series?session_date={current_date}&target={target_encoded}")
        if series_data:
            series_map[safe_target] = series_data.get("series", [])
            summaries_map[safe_target] = series_data.get("summary", {})
    
    # 5. Montar payload
    payload = {
        "dates": dates_data,
        "overview": overview_data,
        "targets": targets_data,
        "series": series_map,
        "summaries": summaries_map,
        "last_update": time.time()
    }
    
    # 6. Enviar para o Firebase
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(FIREBASE_URL, data=data, method='PUT')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                print("  [Sucesso] Payload enviado ao Firebase.")
            else:
                print(f"  [Aviso] Status {response.status} ao enviar ao Firebase.")
    except Exception as e:
        print(f"  [Erro] Falha ao enviar para o Firebase: {e}")

if __name__ == "__main__":
    print(f"Iniciando Sincronizador Firebase")
    print(f"Alvo: {FIREBASE_URL}")
    while True:
        sync()
        time.sleep(30)
