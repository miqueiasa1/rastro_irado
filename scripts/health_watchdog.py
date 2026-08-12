"""
IRAI Health Watchdog — adaptado para Windows.

Verifica 3 componentes de saúde do sistema:
1. Staleness das fontes de dados (Tickmill, Axi, BR)
2. Firebase sync liveness (last_update parado?)
3. Processos Windows (collector, API, firebase_sync rodando?)

Grava resultado em data/health_status.json para consumo pelo endpoint
GET /api/health/watchdog e pelo painel visual do frontend.

Uso standalone:  python scripts/health_watchdog.py
Embutido:        chamado automaticamente pelo collector.py a cada ~5 min
"""

import json
import os
import sys
import time
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Configuração ──────────────────────────────────────────
FIREBASE_LAST_UPDATE_URL = "https://rastromacro-default-rtdb.firebaseio.com/last_update.json"
LOCAL_API_URL = "http://localhost:8888"

STATUS_SNAPSHOT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "health_status.json"
)

# Limiares de defasagem (segundos)
STALENESS_THRESHOLD_S = {
    "tickmill": 15 * 60,    # Tickmill 24h — barra >15min é anomalia
    "axi": 15 * 60,         # Axi ETFs — só durante pregão americano
    "br": 15 * 60,          # B3 — só durante sessão 09h-18h BRT
}
FIREBASE_STALENESS_THRESHOLD_S = 5 * 60  # 5 min

# Sessões de mercado
BR_SESSION_START_H, BR_SESSION_END_H = 9, 18  # BRT
AXI_SESSION_START_UTC_H, AXI_SESSION_END_UTC_H = 13, 21  # UTC real (13:30 UTC = 10:30 BRT Abertura NY)

# Processos Windows que devem estar rodando
EXPECTED_PROCESSES = {
    "collector": "collector.py",
    "api": "main.py",
    "firebase_sync": "firebase_sync.py",
}


def _now_utc():
    return datetime.now(timezone.utc)


def _is_br_session_hours(now_utc):
    brt_now = now_utc - timedelta(hours=3)
    return brt_now.weekday() < 5 and BR_SESSION_START_H <= brt_now.hour < BR_SESSION_END_H


def _is_axi_session_hours(now_utc):
    return now_utc.weekday() < 5 and AXI_SESSION_START_UTC_H <= now_utc.hour < AXI_SESSION_END_UTC_H


def _parse_bar_dt(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)


_RESTART_COOLDOWNS = {}


def _kill_stale_service_process(script_name):
    """Encerra processos Python obsoletos rodando o mesmo script antes de reiniciar."""
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    if any(script_name in str(arg) for arg in cmdline):
                        print(f"[watchdog] Matando processo obsoleto PID {proc.info['pid']} ({script_name})...", flush=True)
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        if sys.platform == "win32":
            try:
                subprocess.run(
                    f'wmic process where "name=\'python.exe\' and commandline like \'%{script_name}%\'" call terminate',
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception:
                pass


def _normalize_age_seconds(raw_age_s):
    """Ajusta o fuso horário para calcular a diferença real entre BRT, UTC e MT5 Server Time (+3h)."""
    # Se a diferença estiver em torno de -3h (-14400s a -7200s), o timestamp da barra
    # veio com offset de +3h do servidor MT5/BRT. Adicionamos 3h para obter a idade real.
    if -14400 <= raw_age_s <= -7200:
        return raw_age_s + 3 * 3600
    elif 7200 <= raw_age_s <= 14400:
        return raw_age_s - 3 * 3600
    elif raw_age_s < 0:
        return abs(raw_age_s)
    return raw_age_s


def _try_restart_service(service_name):
    """Reinicia automaticamente um serviço desativado (com cooldown de 60s), matando instâncias travadas."""
    now = time.time()
    last_restart = _RESTART_COOLDOWNS.get(service_name, 0)
    if now - last_restart < 60:
        return

    _RESTART_COOLDOWNS[service_name] = now
    root_dir = Path(__file__).resolve().parent.parent

    cmd_map = {
        "collector": ([sys.executable, str(root_dir / "backend" / "workers" / "collector.py"), "--interval", "20", "--force"], "collector.py"),
        "api": ([sys.executable, "-m", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8888"], "main.py"),
        "firebase_sync": ([sys.executable, str(root_dir / "scripts" / "firebase_sync.py")], "firebase_sync.py"),
    }

    item = cmd_map.get(service_name)
    if not item:
        return

    cmd, script_name = item

    try:
        print(f"[watchdog] AUTO-RESTART: Reiniciando serviço {service_name}...", flush=True)
        _kill_stale_service_process(script_name)
        time.sleep(1.0)

        if sys.platform == "win32":
            subprocess.Popen(
                cmd,
                cwd=str(root_dir),
                creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
                close_fds=True,
            )
        else:
            subprocess.Popen(cmd, cwd=str(root_dir), close_fds=True)
    except Exception as e:
        print(f"[watchdog] ERRO ao reiniciar {service_name}: {e}", flush=True)


# ── Check 1: Staleness das Fontes ─────────────────────────
def check_source_staleness(now_utc):
    """Verifica defasagem das fontes via HTTP na API local."""
    problems = []
    try:
        req = urllib.request.Request(f"{LOCAL_API_URL}/api/health/sources")
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        sources = payload.get("sources", {})
    except Exception as exc:
        message = f"API local indisponível: {exc}"
        problems.append(("source:tickmill", message, False))
        if _is_br_session_hours(now_utc):
            problems.append(("source:br", message, False))
        if _is_axi_session_hours(now_utc):
            problems.append(("source:axi", message, False))
        return problems

    # Tickmill (24h)
    ts = sources.get("tickmill")
    if ts is None:
        problems.append(("source:tickmill", "Nenhuma barra M5 encontrada", False))
    else:
        raw_age_s = (now_utc - _parse_bar_dt(ts)).total_seconds()
        age_s = _normalize_age_seconds(raw_age_s)
        if age_s > STALENESS_THRESHOLD_S["tickmill"]:
            problems.append(("source:tickmill", f"Última barra há {age_s / 60:.0f} min", False))
        else:
            problems.append(("source:tickmill", f"OK ({age_s / 60:.0f} min)", True))

    # BR (só durante sessão B3)
    if _is_br_session_hours(now_utc):
        ts = sources.get("br")
        if ts is None:
            problems.append(("source:br", "Sem barra M5 durante sessão B3", False))
        else:
            raw_age_s = (now_utc - _parse_bar_dt(ts)).total_seconds()
            age_s = _normalize_age_seconds(raw_age_s)
            if age_s > STALENESS_THRESHOLD_S["br"]:
                problems.append(("source:br", f"Última barra há {age_s / 60:.0f} min", False))
            else:
                problems.append(("source:br", f"OK ({age_s / 60:.0f} min)", True))
    else:
        problems.append(("source:br", "Fora do horário B3", True))

    # Axi (só durante pregão americano)
    if _is_axi_session_hours(now_utc):
        ts = sources.get("axi")
        if ts is None:
            problems.append(("source:axi", "Sem barra M5 durante pregão americano", False))
        else:
            raw_age_s = (now_utc - _parse_bar_dt(ts)).total_seconds()
            age_s = _normalize_age_seconds(raw_age_s)
            if age_s > STALENESS_THRESHOLD_S["axi"]:
                problems.append(("source:axi", f"Última barra há {age_s / 60:.0f} min", False))
            else:
                problems.append(("source:axi", f"OK ({age_s / 60:.0f} min)", True))
    else:
        problems.append(("source:axi", "Fora do horário do pregão americano", True))

    return problems


# ── Check 2: Firebase Liveness ────────────────────────────
def check_firebase_liveness(now_utc):
    """Verifica se o firebase_sync está atualizando o RTDB."""
    try:
        with urllib.request.urlopen(FIREBASE_LAST_UPDATE_URL, timeout=10) as resp:
            raw = resp.read().decode("utf-8").strip()
        last_update = float(raw)
    except Exception as exc:
        return [("firebase", f"Não consegui ler Firebase: {exc}", False)]

    age_s = abs(now_utc.timestamp() - last_update)
    if age_s > FIREBASE_STALENESS_THRESHOLD_S:
        return [("firebase", f"Parado há {age_s / 60:.0f} min (limiar: {FIREBASE_STALENESS_THRESHOLD_S / 60:.0f} min)", False)]
    return [("firebase", f"OK (atualizado há {age_s / 60:.0f} min)", True)]


# ── Check 3: Serviços Locais ──────────────────────────────
def check_local_services():
    """Verifica se os serviços IRAI estão respondendo e reinicia automaticamente se necessário."""
    results = []

    # API: tenta HTTP na porta 8888
    try:
        req = urllib.request.Request(f"{LOCAL_API_URL}/api/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == "ok":
            models = data.get("models_loaded", "?")
            results.append(("service:api", f"OK ({models} modelos)", True))
        else:
            results.append(("service:api", "Resposta inesperada", False))
            _try_restart_service("api")
    except Exception as exc:
        results.append(("service:api", f"Offline: {exc}", False))
        _try_restart_service("api")

    # Collector: verifica se a última barra M5 é recente (< 2 min)
    try:
        req = urllib.request.Request(f"{LOCAL_API_URL}/api/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        last_bar = data.get("last_bar")
        if last_bar:
            bar_dt = _parse_bar_dt(last_bar)
            age = _normalize_age_seconds((_now_utc() - bar_dt).total_seconds())
            if age < 120:  # Barra recente = collector ativo
                results.append(("service:collector", f"OK (ultima barra ha {age:.0f}s)", True))
            else:
                is_ok = age < 600
                results.append(("service:collector", f"Ultima barra ha {age/60:.0f} min", is_ok))
                if not is_ok:
                    _try_restart_service("collector")
        else:
            results.append(("service:collector", "Sem barras no DB", False))
            _try_restart_service("collector")
    except Exception:
        results.append(("service:collector", "API offline", False))
        _try_restart_service("collector")

    return results


# ── Gravar Snapshot Local ─────────────────────────────────
def write_status_snapshot(now_utc, component_reports):
    """Grava JSON em data/health_status.json para o dashboard ler.
    Usa write-then-rename para evitar JSON truncado em caso de crash."""
    payload = {
        "generated_at": now_utc.isoformat(),
        "healthy": all(healthy for _, _, healthy in component_reports),
        "components": [
            {"endpoint": endpoint, "message": message, "healthy": healthy}
            for endpoint, message, healthy in component_reports
        ],
    }
    os.makedirs(os.path.dirname(STATUS_SNAPSHOT_PATH), exist_ok=True)
    tmp_path = f"{STATUS_SNAPSHOT_PATH}.tmp{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp_path, STATUS_SNAPSHOT_PATH)


# ── Main ──────────────────────────────────────────────────
def run_health_check():
    """Executa todos os checks e grava o snapshot. Retorna o payload."""
    now_utc = _now_utc()

    component_reports = (
        check_source_staleness(now_utc)
        + check_firebase_liveness(now_utc)
        + check_local_services()
    )

    write_status_snapshot(now_utc, component_reports)

    healthy = all(h for _, _, h in component_reports)
    status = "OK" if healthy else "PROBLEMAS DETECTADOS"
    print(f"[watchdog] {status} -- {now_utc.strftime('%H:%M:%S')} UTC", flush=True)
    for endpoint, message, ok in component_reports:
        icon = "OK" if ok else "!!"
        print(f"  [{icon}] {endpoint}: {message}", flush=True)

    return component_reports


if __name__ == "__main__":
    run_health_check()
