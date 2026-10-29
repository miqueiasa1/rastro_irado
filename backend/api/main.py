"""
IRAI — FastAPI Backend.

Endpoints:
  GET  /api/irai/current       → snapshot corrente (live ou última sessão)
  GET  /api/irai/series        → série completa de uma sessão (target=WIN$N|WDO$N)
  GET  /api/irai/dates         → datas disponíveis
  GET  /api/model/params       → parâmetros do modelo
  GET  /api/health             → status do sistema
  WS   /ws/irai                → push em tempo real (5s)
"""

import os
import math
import sys
import asyncio
import json
from datetime import date, datetime, timedelta
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.db import get_connection, DB_PATH, init_db, get_live_snapshots, save_live_snapshots
from backend.irai.engine import IRAIEngine, FACTOR_LABELS, TARGET

# ── Engine singleton ──────────────────────────────────────
engine: IRAIEngine = None
ws_clients: dict = {}
data_updated_event = asyncio.Event()

# ── Cache de resultados computados ─────────────────────
series_cache: dict = {}   # (target, date, version) → result dict
overview_cache_data: dict = {} # (date, version) → result dict


async def ws_broadcast_loop():
    """Push dados para todos os WebSocket clients quando ativado pelo collector."""
    while True:
        await data_updated_event.wait()
        data_updated_event.clear()
        
        if not ws_clients:
            continue
            
        try:
            # Usar a data mais recente do banco (mesma lógica do overview/dates)
            conn = get_connection()
            row = conn.execute("""
                SELECT DISTINCT substr(timestamp_utc, 1, 10) as d
                FROM market_bars WHERE timeframe='M5'
                ORDER BY d DESC LIMIT 1
            """).fetchone()
            conn.close()
            session_date = row["d"] if row else date.today().isoformat()

            overview_cache = None
            
            dead = set()
            for ws, config in ws_clients.copy().items():
                try:
                    target = config.get("target", "WIN$N")
                    version = config.get("version", "v1")
                    
                    ov_key = (session_date, version)
                    if ov_key not in overview_cache_data:
                        await irai_overview(session_date, version) # Isso vai popular o cache
                        
                    se_key = (target, session_date, version)
                    if se_key not in series_cache:
                        res = await irai_series(session_date, target, version)
                        if isinstance(res, JSONResponse):
                            series_cache[se_key] = {"error": "Sem dados"}
                        else:
                            series_cache[se_key] = res
                            
                    payload = json.dumps({
                        "type": "update",
                        "session_date": session_date,
                        "overview": overview_cache_data[ov_key],
                        "series": series_cache[se_key]
                    })
                    await ws.send_text(payload)
                except Exception:
                    dead.add(ws)
            for ws in dead:
                ws_clients.pop(ws, None)
        except Exception as e:
            print(f"WS broadcast error: {e}")




@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    init_db()  # Auto-heal schema no boot
    engine = IRAIEngine()
    print(f"IRAI Engine loaded: {len(engine.models)} models, {len(engine.registered_targets)} targets")
    task = asyncio.create_task(ws_broadcast_loop())
    yield
    task.cancel()
    print("IRAI Engine shutdown")


app = FastAPI(
    title="IRAI API",
    description="Intraday Risk Appetite Index — Cross-asset IBOV probability",
    version="1.0.0",
    lifespan=lifespan,
)

# A6 (auditoria): CORS restrito ao frontend local (Vite). O site público lê do Firebase, não desta API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5175", "http://127.0.0.1:5175",
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.post("/api/internal/notify_update")
async def notify_update(request: Request):
    """Chamado pelo collector.py após inserir novas barras.
    Apenas loopback (A6): antes qualquer host da LAN — ou página aberta no navegador — podia
    forçar recargas em loop. Também não faz mais importlib.reload do módulo (trocava o engine
    global no meio de requisições em andamento); apenas recarrega os parâmetros calibrados."""
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        return JSONResponse(status_code=403, content={"error": "forbidden"})
    try:
        engine._load_params()
    except Exception as e:
        print(f"Error reloading engine params: {e}")
    series_cache.clear()
    overview_cache_data.clear()
    data_updated_event.set()
    return {"status": "ok"}


@app.get("/api/health")
async def health():
    """Status do sistema."""
    from datetime import timezone
    conn = get_connection()
    bar_count = conn.execute("SELECT COUNT(*) as c FROM market_bars").fetchone()["c"]
    last_bar = conn.execute(
        "SELECT MAX(timestamp_utc) as ts FROM market_bars WHERE timeframe='M5'"
    ).fetchone()["ts"]

    from backend.timeconv import now_brt_wall, now_broker_wall, broker_wall_to_brt_wall
    now_utc = datetime.now(timezone.utc)
    now_brt = now_brt_wall()                # relógio de Brasília (naive)
    now_tickmill = now_broker_wall()        # relógio do broker NY+7 (mesma convenção do banco)

    # 1. B3 Status (WIN$N)
    b3_status = "CLOSED"
    b3_last = None
    b3_delay_min = 0

    row_b3 = conn.execute(
        "SELECT MAX(timestamp_utc) as ts FROM market_bars WHERE symbol='WIN$N' AND timeframe='M5'"
    ).fetchone()
    if row_b3 and row_b3["ts"]:
        b3_last = row_b3["ts"]
        try:
            # Banco em relógio do broker → converter para BRT antes de comparar com "agora" em BRT
            b3_dt = datetime.fromisoformat(b3_last.replace("Z", "+00:00")).replace(tzinfo=None)
            b3_dt = broker_wall_to_brt_wall(b3_dt)
            b3_last = b3_dt.strftime("%Y-%m-%dT%H:%M:%S")  # exibido no painel em BRT
            now_brt_naive = now_brt.replace(tzinfo=None)
            
            # Horário do pregão B3: Seg-Sex, 09:00 - 18:00 BRT
            is_b3_day = now_brt_naive.weekday() < 5
            is_b3_hours = 9 <= now_brt_naive.hour < 18
            
            if is_b3_day and is_b3_hours:
                diff = now_brt_naive - b3_dt
                b3_delay_min = int(diff.total_seconds() / 60)
                if b3_delay_min > 15:
                    b3_status = "DELAYED"
                else:
                    b3_status = "OK"
            else:
                b3_status = "CLOSED"
        except Exception as e:
            print(f"Error parsing B3 timestamp: {e}")

    # 2. Forex Status (EURUSD)
    forex_status = "CLOSED"
    forex_last = None
    forex_delay_min = 0

    row_forex = conn.execute(
        "SELECT MAX(timestamp_utc) as ts FROM market_bars WHERE symbol='EURUSD' AND timeframe='M5'"
    ).fetchone()
    if row_forex and row_forex["ts"]:
        forex_last = row_forex["ts"]
        try:
            forex_dt = datetime.fromisoformat(forex_last.replace("Z", "+00:00"))
            forex_dt = forex_dt.replace(tzinfo=None)  # naive
            now_tickmill_naive = now_tickmill.replace(tzinfo=None)
            
            # Forex mercado aberto: Dom 22:00 UTC até Sex 22:00 UTC
            day = now_utc.weekday()
            hour = now_utc.hour
            is_forex_open = True
            if day == 5:  # Sábado
                is_forex_open = False
            elif day == 6 and hour < 22:  # Domingo antes das 22h UTC
                is_forex_open = False
            elif day == 4 and hour >= 22:  # Sexta após as 22h UTC
                is_forex_open = False
                
            if is_forex_open:
                diff = now_tickmill_naive - forex_dt
                forex_delay_min = int(diff.total_seconds() / 60)
                if forex_delay_min > 15:
                    forex_status = "DELAYED"
                else:
                    forex_status = "OK"
            else:
                forex_status = "CLOSED"
        except Exception as e:
            print(f"Error parsing Forex timestamp: {e}")

    conn.close()

    return {
        "status": "ok",
        "bars_total": bar_count,
        "last_bar": last_bar,
        "models_loaded": len(engine.models),
        "targets": [t["target"] for t in engine.registered_targets],
        "b3_status": b3_status,
        "b3_last_bar": b3_last,
        "b3_delay_min": b3_delay_min,
        "global_status": forex_status,
        "global_last_bar": forex_last,
        "global_delay_min": forex_delay_min,
    }

@app.get("/api/health/sources")
async def health_sources():
    """Última barra M5 por fonte (br/tickmill/axi). Usado pelo watchdog para
    checar defasagem sem abrir o banco diretamente."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT source, MAX(timestamp_utc) as ts
            FROM market_bars
            WHERE timeframe = 'M5'
            GROUP BY source
        """).fetchall()
        return {"sources": {row["source"]: row["ts"] for row in rows}}
    finally:
        conn.close()


@app.get("/api/health/watchdog")
async def health_watchdog_status():
    """Último ciclo do watchdog de saúde — leitura do instantâneo local
    gravado por scripts/health_watchdog.py a cada ~5 min."""
    from pathlib import Path
    snapshot_path = Path(DB_PATH).resolve().parent / "health_status.json"
    if not snapshot_path.exists():
        return {"available": False, "message": "Watchdog ainda não executou"}

    import json as _json
    with open(snapshot_path, encoding="utf-8") as f:
        snapshot = _json.load(f)

    # Verificar se está defasado (>15 min sem atualização)
    generated_at = snapshot.get("generated_at", "")
    age_s = 0
    try:
        gen_dt = datetime.fromisoformat(generated_at)
        from datetime import timezone
        age_s = (datetime.now(timezone.utc) - gen_dt).total_seconds()
    except Exception:
        pass

    return {
        "available": True,
        "healthy": snapshot.get("healthy"),
        "stale": age_s > 15 * 60,
        "generated_at": generated_at,
        "age_seconds": round(age_s),
        "components": snapshot.get("components", []),
    }

@app.get("/api/gex")
async def get_gex(target: str = Query(...), date: str = Query(...), run: str = Query(None)):
    """Retorna os niveis de GEX para um ativo, data e run especificos."""
    conn = get_connection()
    try:
        effective_date = date
        runs = [r[0] for r in conn.execute(
            "SELECT DISTINCT run_name FROM gex_levels WHERE target = ? AND session_date = ? ORDER BY run_name DESC",
            (target, effective_date)
        ).fetchall()]

        if not runs:
            latest_row = conn.execute(
                "SELECT session_date FROM gex_levels WHERE target = ? AND session_date <= ? ORDER BY session_date DESC LIMIT 1",
                (target, date)
            ).fetchone()
            if latest_row:
                effective_date = latest_row["session_date"]
                runs = [r[0] for r in conn.execute(
                    "SELECT DISTINCT run_name FROM gex_levels WHERE target = ? AND session_date = ? ORDER BY run_name DESC",
                    (target, effective_date)
                ).fetchall()]

        if not runs:
            return {"target": target, "date": date, "levels": [], "available_runs": [], "selected_run": None}

        selected_run = run if (run and run in runs) else runs[0]

        row = conn.execute(
            "SELECT levels_json FROM gex_levels WHERE target = ? AND session_date = ? AND run_name = ?",
            (target, effective_date, selected_run)
        ).fetchone()

        if row:
            return {
                "target": target,
                "date": date,
                "effective_gex_date": effective_date,
                "selected_run": selected_run,
                "available_runs": runs,
                "levels": json.loads(row["levels_json"])
            }
    except Exception as e:
        print(f"Error querying gex_levels: {e}")
    finally:
        conn.close()
    return {"target": target, "date": date, "levels": [], "available_runs": [], "selected_run": None}


@app.get("/api/gex/pine")
def get_gex_pine(key: str = Query(...)):
    """Retorna o c?digo do indicador TradingView (jumba_tradingview.pine).
    Exige `key` = sha256('<PINE_SALT>:<PINE_PASSWORD>') ? mesma chave do cofre RTDB."""
    import hashlib, hmac, os
    from pathlib import Path
    from fastapi import HTTPException
    root_dir = Path(DB_PATH).resolve().parent.parent
    env = {}
    env_path = root_dir / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                env[k] = v.strip()
    password = os.environ.get("PINE_PASSWORD") or env.get("PINE_PASSWORD")
    salt = os.environ.get("PINE_SALT") or env.get("PINE_SALT")
    if not password or not salt:
        raise HTTPException(status_code=503, detail="Cofre do Pine n?o configurado")
    expected = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    if not hmac.compare_digest(expected, key.strip().lower()):
        raise HTTPException(status_code=403, detail="Senha incorreta")

    path = root_dir.parent / "wdo win pair trading" / "gex" / "docs" / "jumba_tradingview.pine"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo jumba_tradingview.pine n?o encontrado")
    content = path.read_text(encoding="utf-8")
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    date_str = mtime.strftime("%Y-%m-%d")
    return {
        "content": content,
        "date": date_str,
        "run_name": mtime.strftime("%H:%M"),
        "updated_at": mtime.strftime("%Y-%m-%d %H:%M:%S"),
        "filename": f"jumba_tradingview_{date_str}.pine",
    }


@app.get("/api/garch")
async def get_garch(symbol: str = Query("IBOV"), date: str = Query(None)):
    """Retorna a volatilidade condicional GARCH e forecast para um símbolo."""
    conn = get_connection()
    try:
        if date:
            row = conn.execute(
                "SELECT history_json, forecast_json, updated_at FROM garch_volatility WHERE symbol = ? AND session_date = ?",
                (symbol, date)
            ).fetchone()
            if row:
                return {
                    "symbol": symbol,
                    "session_date": date,
                    "history": json.loads(row["history_json"]),
                    "forecast": json.loads(row["forecast_json"]),
                    "updated_at": row["updated_at"]
                }
        
        # Fallback to the latest run for this symbol
        row = conn.execute(
            "SELECT session_date, history_json, forecast_json, updated_at FROM garch_volatility WHERE symbol = ? ORDER BY session_date DESC LIMIT 1",
            (symbol,)
        ).fetchone()

        if row:
            return {
                "symbol": symbol,
                "session_date": row["session_date"],
                "history": json.loads(row["history_json"]),
                "forecast": json.loads(row["forecast_json"]),
                "updated_at": row["updated_at"]
            }
    except Exception as e:
        print(f"Error querying garch_volatility: {e}")
    finally:
        conn.close()
    return {"symbol": symbol, "session_date": date, "history": [], "forecast": [], "updated_at": None}


@app.get("/api/irai/targets")
async def irai_targets():
    """Lista todos os targets disponíveis com status."""
    try:
        engine._load_params()
    except Exception as e:
        print(f"Error refreshing engine params: {e}")
    return {
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
            for t in engine.registered_targets
        ]
    }


def _enrich_top8_overlay(conn, series_list, target, session_date, timeframe, mode):
    if target not in ("WIN$N", "WIN$N_TOP8"):
        return
    other_target = "WIN$N_TOP8" if target == "WIN$N" else "WIN$N"
    other_map = {}
    if mode == "live":
        other_snaps = get_live_snapshots(conn, other_target, session_date, timeframe=timeframe)
        if other_snaps:
            for s in other_snaps:
                ts = s.get("timestamp_utc") or s.get("timestamp")
                if ts:
                    other_map[ts] = {
                        "p_up": s.get("p_up"),
                        "price_diverge_z": s.get("price_diverge_z"),
                        "price_diverge_basket_z": s.get("price_diverge_basket_z"),
                        "price_diverge_probit_z": s.get("price_diverge_probit_z"),
                    }
    if not other_map:
        try:
            other_snaps = engine.compute_from_db(session_date, target=other_target, version="v2", timeframe=timeframe, persist_state=False)
            if other_snaps:
                for s in other_snaps:
                    other_map[s.timestamp] = {
                        "p_up": s.p_up,
                        "price_diverge_z": s.price_diverge_z,
                        "price_diverge_basket_z": getattr(s, "price_diverge_basket_z", None),
                        "price_diverge_probit_z": getattr(s, "price_diverge_probit_z", None),
                    }
        except Exception:
            pass

    for s in series_list:
        ts = s.get("timestamp_utc") or s.get("timestamp")
        info = other_map.get(ts, {})
        if target == "WIN$N":
            s["p_up_top8"] = info.get("p_up")
            s["price_diverge_top8_z"] = info.get("price_diverge_z")
            s["price_diverge_top8_basket_z"] = info.get("price_diverge_basket_z")
            s["price_diverge_top8_probit_z"] = info.get("price_diverge_probit_z")
        elif target == "WIN$N_TOP8":
            s["p_up_top8"] = s.get("p_up")
            s["price_diverge_top8_z"] = s.get("price_diverge_z")
            s["price_diverge_top8_basket_z"] = s.get("price_diverge_basket_z")
            s["price_diverge_top8_probit_z"] = s.get("price_diverge_probit_z")
            s["p_up_macro"] = info.get("p_up")
            s["price_diverge_macro_z"] = info.get("price_diverge_z")
            s["price_diverge_macro_basket_z"] = info.get("price_diverge_basket_z")
            s["price_diverge_macro_probit_z"] = info.get("price_diverge_probit_z")


def _get_series_data_sync(target: str, session_date: str, version: str, timeframe: str = "M5", mode: str = "live") -> dict:
    from backend.timeconv import is_current_session_date
    series_cache.clear()
    overview_cache_data.clear()
    is_today = is_current_session_date(session_date)
    cache_key = (target, session_date, version, timeframe, mode)
    if not is_today and cache_key in series_cache:
        print(f"[CACHE HIT] {cache_key}", flush=True)
        return series_cache[cache_key]
    print(f"[CACHE MISS] {cache_key} - mode={mode}...", flush=True)

    conn = get_connection()
    target_info = next((t for t in engine.registered_targets if t["target"].lower() == target.lower() or (t.get("data_proxy") and t["data_proxy"].lower() == target.lower())), {})
    target_real = target_info.get("target") or target
    target_db = target_info.get("data_proxy") or target_real

    tf_query = "M5" if timeframe == "both" else timeframe
    prev_rows = conn.execute("""
        SELECT close FROM market_bars
        WHERE symbol = ? AND timeframe = ? AND timestamp_utc < ?
        ORDER BY timestamp_utc DESC LIMIT 190
    """, (target_db, tf_query, f"{session_date}T00:00:00Z")).fetchall()
    
    is_b3 = target_info.get("session_start_h", 0) != 0
    div_cfg = target_info.get("divergence_config", {})
    divergence_threshold = div_cfg.get("threshold", 2.0)
    history_closes = [r["close"] for r in reversed(prev_rows)]

    if mode == "live":
        live_snaps = get_live_snapshots(conn, target_real, session_date, timeframe=tf_query)
        if live_snaps and len(live_snaps) > 0:
            for s in live_snaps:
                ts_str = s.get("timestamp_utc") or s.get("timestamp")
                if ts_str and "T" in ts_str:
                    s["time"] = ts_str.split("T")[1][:5]
                elif ts_str:
                    s["time"] = ts_str

            _enrich_top8_overlay(conn, live_snaps, target_real, session_date, tf_query, mode)
            conn.close()

            result = {
                "session_date": session_date,
                "target": target,
                "display_name": target_info.get("display_name", target),
                "icon": target_info.get("icon", "📊"),
                "bars": len(live_snaps),
                "series": live_snaps,
                "history_closes": history_closes,
                "is_b3": is_b3,
                "divergence_threshold": divergence_threshold,
                "is_live_mode": True,
                "summary": {
                    "p_up_min": min(s["p_up"] for s in live_snaps),
                    "p_up_max": max(s["p_up"] for s in live_snaps),
                    "p_up_final": live_snaps[-1]["p_up"],
                    "score_final": live_snaps[-1]["score"],
                    "verdict": live_snaps[-1]["verdict"],
                    "win_return": live_snaps[-1]["win_return"],
                    "timestamp": live_snaps[-1].get("timestamp_utc") or live_snaps[-1].get("timestamp"),
                    "accuracy": target_info.get("accuracy"),
                }
            }
            if not is_today:
                series_cache[cache_key] = result
            return result

    snapshots = engine.compute_from_db(session_date, target=target, version=version, timeframe=timeframe, persist_state=is_today)
    if not snapshots:
        conn.close()
        return {"error": f"Sem dados para sessão {session_date}"}

    series_data = [_snap_to_dict(s) for s in snapshots]
    conn.close()

    try:
        from backend.irai.nwe import compute_nwe
        series_data = compute_nwe(series_data, history_closes)
    except Exception as e:
        print(f"Error computing NWE in API: {e}", flush=True)

    if mode == "live" and is_today:
        save_live_snapshots(DB_PATH, target, session_date, series_data, timeframe=tf_query, is_live_captured=0)

    result = {
        "session_date": session_date,
        "target": target,
        "display_name": target_info.get("display_name", target),
        "icon": target_info.get("icon", "📊"),
        "bars": len(snapshots),
        "series": series_data,
        "history_closes": history_closes,
        "is_b3": is_b3,
        "divergence_threshold": divergence_threshold,
        "is_live_mode": False,
        "summary": {
            "p_up_min": min(s.p_up for s in snapshots),
            "p_up_max": max(s.p_up for s in snapshots),
            "p_up_final": snapshots[-1].p_up,
            "score_final": snapshots[-1].score,
            "verdict": snapshots[-1].verdict,
            "win_return": snapshots[-1].win_return,
            "timestamp": snapshots[-1].timestamp,
            "accuracy": target_info.get("accuracy"),
        }
    }
    if not is_today:
        series_cache[cache_key] = result
        print(f"[CACHE WRITE] {cache_key}", flush=True)
    return result


def _get_overview_data_sync(session_date: str, version: str, timeframe: str = "M5") -> dict:
    from backend.timeconv import is_current_session_date
    is_today = is_current_session_date(session_date)
    cache_key = (session_date, version, timeframe)
    if not is_today and cache_key in overview_cache_data:
        cached_targets = overview_cache_data[cache_key].get("targets", [])
        if len(cached_targets) >= len(engine.registered_targets):
            return overview_cache_data[cache_key]

    try:
        engine._load_params()
    except Exception:
        pass

    results = []
    for t in engine.registered_targets:
        if not t.get("accuracy"):
            continue

        try:
            series_data = _get_series_data_sync(t["target"], session_date, version, timeframe=timeframe)
            if "error" in series_data:
                continue

            series_list = series_data["series"]
            if not series_list:
                continue

            last_dict = series_list[-1]
            p_up = last_dict["p_up"]
            score = last_dict["score"]
            verdict = last_dict["verdict"]
            win_return = last_dict["win_return"]
            is_preview = last_dict.get("is_preview", False)
            is_cointegrated = last_dict.get("is_cointegrated", True)
            johansen_p_value = last_dict.get("johansen_p_value", 0.05)

            sparkline = [round(s["p_up"], 1) for s in series_list[-24:]]
            flow_confirms = last_dict.get("flow_confirms")

            price_diverges = last_dict.get("price_diverges", False)
            price_diverge_z = last_dict.get("price_diverge_z")

            nwe_slope = 0.0
            try:
                if len(series_list) >= 2:
                    h = 8
                    n = len(series_list)
                    vals = [s["win_return"] for s in series_list]
                    def get_center(i_idx):
                        sum_w = 0.0
                        sum_y = 0.0
                        for j in range(n):
                            w = math.exp(-((i_idx - j) ** 2) / (2 * h * h))
                            sum_w += w
                            sum_y += w * vals[j]
                        return sum_y / sum_w if sum_w > 0 else vals[i_idx]

                    c_last = get_center(n - 1)
                    c_prev = get_center(n - 2)
                    nwe_slope = round(c_last - c_prev, 6)
            except Exception:
                pass

            res_obj = {
                "target": t["target"],
                "slug": t["slug"],
                "display_name": t["display_name"],
                "icon": t["icon"],
                "win_return": round(win_return, 4),
                "bars": len(series_list),
                "accuracy": t.get("accuracy"),
                "flow_confirms": flow_confirms,
                "price_diverges": price_diverges,
                "price_diverge_z": price_diverge_z,
                "pair_z": last_dict.get("pair_z"),
                "pair_factor": last_dict.get("pair_factor"),
                "pair_beta": last_dict.get("pair_beta"),
                "pair_fixed_z": last_dict.get("pair_fixed_z"),
                "pair_fixed_factor": last_dict.get("pair_fixed_factor"),
                "pair_fixed_beta": last_dict.get("pair_fixed_beta"),
                "nwe_slope": nwe_slope,
                "is_preview": is_preview,
                "is_cointegrated": is_cointegrated,
                "johansen_p_value": johansen_p_value,
                "p_up": round(p_up, 1),
                "score": round(score, 4),
                "verdict": verdict,
                "sparkline": sparkline,
                "win_current": last_dict.get("win_current"),
                "nwe_upper_price": last_dict.get("nwe_upper_price"),
                "nwe_lower_price": last_dict.get("nwe_lower_price"),
            }
            results.append(res_obj)
        except Exception as e:
            print(f"Overview error for {t['target']}: {e}")

    result = {
        "session_date": session_date,
        "version": version,
        "targets": results,
    }
    if not is_today:
        overview_cache_data[cache_key] = result
    return result


def _get_current_data_sync(version: str) -> dict:
    today = date.today().isoformat()
    snapshots = engine.compute_from_db(today, version=version)
    if not snapshots:
        conn = get_connection()
        row = conn.execute("""
            SELECT DISTINCT substr(timestamp_utc, 1, 10) as d
            FROM market_bars
            WHERE symbol = ? AND timeframe = 'M5'
            ORDER BY d DESC LIMIT 1
        """, [TARGET]).fetchone()
        conn.close()
        if row:
            snapshots = engine.compute_from_db(row["d"], version=version)
    if not snapshots:
        return {"error": "Sem dados"}
    return _snap_to_dict(snapshots[-1])


@app.get("/api/irai/overview")
async def irai_overview(
    session_date: str = Query(None, description="Data YYYY-MM-DD (default: hoje)"),
    version: str = Query("v2", description="Versão do motor (v1=estático, v2=dinâmico)"),
    timeframe: str = Query("M5", description="Timeframe do gráfico"),
):
    """Snapshot atual de TODOS os targets calibrados."""
    if session_date is None:
        conn = get_connection()
        row = conn.execute("""
            SELECT DISTINCT substr(timestamp_utc, 1, 10) as d
            FROM market_bars WHERE timeframe = ?
            ORDER BY d DESC LIMIT 1
        """, [timeframe]).fetchone()
        conn.close()
        if row:
            session_date = row["d"]
        else:
            session_date = date.today().isoformat()

    return await run_in_threadpool(_get_overview_data_sync, session_date, version, timeframe=timeframe)


@app.get("/api/irai/dates")
async def irai_dates(
    target: str = Query(None, description="Filtrar datas por target específico"),
):
    """Datas com dados disponíveis."""
    # This query runs very fast (<1ms), so we can run it inline, or in a threadpool. Let's run in threadpool to be safe.
    def get_dates_sync():
        conn = get_connection()
        if target:
            rows = conn.execute("""
                SELECT DISTINCT substr(timestamp_utc, 1, 10) as d
                FROM market_bars
                WHERE symbol = ? AND timeframe = 'M5'
                ORDER BY d DESC
                LIMIT 60
            """, [target]).fetchall()
        else:
            rows = conn.execute("""
                SELECT DISTINCT substr(timestamp_utc, 1, 10) as d
                FROM market_bars
                WHERE timeframe = 'M5'
                ORDER BY d DESC
                LIMIT 60
            """).fetchall()
        conn.close()
        return {"dates": [r["d"] for r in rows]}

    return await run_in_threadpool(get_dates_sync)


@app.get("/api/irai/series")
async def irai_series(
    session_date: str = Query(None, description="Data YYYY-MM-DD (default: hoje)"),
    target: str = Query("WIN$N", description="Target: WIN$N ou WDO$N"),
    version: str = Query("v2", description="Versão do motor (v1=estático, v2=dinâmico)"),
    timeframe: str = Query("M5", description="Timeframe do gráfico (M1, M2, M5, M15, M30, H1)"),
    mode: str = Query("live", description="Modo de consulta (live=imutável em tempo real, recalculated=recalculado)"),
):
    """Série IRAI completa para uma sessão. Suporta multi-target e modo imutável live."""
    if session_date is None:
        from backend.timeconv import current_session_date
        t_info = next((t for t in engine.registered_targets if t["target"] == target), {})
        session_date = current_session_date(t_info.get("session_start_h", 0) != 0)

    result = await run_in_threadpool(_get_series_data_sync, target, session_date, version, timeframe=timeframe, mode=mode)
    if "error" in result:
        return JSONResponse(status_code=404, content=result)
    return result


@app.get("/api/irai/current")
async def irai_current(version: str = Query("v1")):
    """Snapshot mais recente (última barra processada)."""
    result = await run_in_threadpool(_get_current_data_sync, version)
    if "error" in result:
        return JSONResponse(status_code=404, content=result)
    return result


@app.get("/api/model/params")
async def model_params(target: str = Query("WIN$N")):
    """Parâmetros do modelo calibrado para um target."""
    slug = engine.target_slugs.get(target, "win")
    m = engine.models.get(slug, {})
    return {
        "target": target,
        "slug": slug,
        "weights": m.get("weights", {}),
        "sigmas": m.get("sigmas", {}),
        "alpha": m.get("alpha", 1.0),
        "intercept": m.get("intercept", 0.0),
        "factors": list(m.get("factor_labels", {}).values()),
    }


def _snap_to_dict(snap) -> dict:
    """Converte snapshot para dict serializável."""
    return {
        "timestamp": snap.timestamp,
        "is_pre_market": getattr(snap, "is_pre_market", False),
        "session_date": snap.session_date,
        "bar_idx": snap.bar_idx,
        "t_frac": snap.t_frac,
        "p_up": snap.p_up,
        "score": snap.score,
        "verdict": snap.verdict,
        "verdict_color": snap.verdict_color,
        "factors": snap.factors,
        "win_return": snap.win_return,
        "win_open": snap.win_open,
        "win_bar_open": getattr(snap, "win_bar_open", None) or snap.win_current,
        "win_high": getattr(snap, "win_high", None) or snap.win_current,
        "win_low": getattr(snap, "win_low", None) or snap.win_current,
        "win_current": snap.win_current,
        "stale_factors": snap.stale_factors,
        "bar_delta": snap.bar_delta,
        "cum_delta": snap.cum_delta,
        "cum_delta_norm": snap.cum_delta_norm,
        "flow_confirms": snap.flow_confirms,
        "price_diverges": snap.price_diverges,
        "price_diverge_z": snap.price_diverge_z,
        "price_diverge_basket_z": getattr(snap, "price_diverge_basket_z", None),
        "price_diverge_probit_z": getattr(snap, "price_diverge_probit_z", None),
        "pair_z": getattr(snap, "pair_z", None),
        "pair_factor": getattr(snap, "pair_factor", None),
        "pair_beta": getattr(snap, "pair_beta", None),
        "pair_signal": getattr(snap, "pair_signal", None),
        "pair_fixed_z": getattr(snap, "pair_fixed_z", None),
        "pair_fixed_factor": getattr(snap, "pair_fixed_factor", None),
        "pair_fixed_beta": getattr(snap, "pair_fixed_beta", None),
        "pair_fixed_signal": getattr(snap, "pair_fixed_signal", None),
        "is_preview": getattr(snap, "is_preview", False),
        "is_ghost": getattr(snap, "is_ghost", False),
        "is_cointegrated": getattr(snap, "is_cointegrated", True),
        "johansen_p_value": getattr(snap, "johansen_p_value", 1.0),
    }


def _bar_time(bar_idx: int) -> str:
    """Converte índice de barra para horário BRT."""
    total_min = 10 * 60 + bar_idx * 5
    h = total_min // 60
    m = total_min % 60
    return f"{h:02d}:{m:02d}"


@app.websocket("/ws/irai")
async def websocket_irai(ws: WebSocket):
    """WebSocket push: envia série IRAI atualizada baseada no target."""
    await ws.accept()
    ws_clients[ws] = {"target": "WIN$N", "version": "both", "timeframe": "M5"} # Default
    print(f"WS client connected ({len(ws_clients)} total)")
    
    # Enviar o estado atual imediatamente na conexão
    try:
        today = date.today().isoformat()
        ov = await irai_overview(today, "both", timeframe="M5")
        se = await irai_series(today, "WIN$N", "both", timeframe="M5")
        if isinstance(se, JSONResponse): se = {"error": "Sem dados"}
        await ws.send_text(json.dumps({"type": "update", "overview": ov, "series": se}))
    except Exception as e:
        print(f"Initial WS send error: {e}")
        
    try:
        while True:
            # Recebe mensagens de configuração (mudança de target)
            data = await ws.receive_json()
            if data:
                if "target" in data:
                    ws_clients[ws]["target"] = data["target"]
                if "version" in data:
                    ws_clients[ws]["version"] = data["version"]
                if "timeframe" in data:
                    ws_clients[ws]["timeframe"] = data["timeframe"]
                
                # Força um envio imediato com as novas configurações
                today = date.today().isoformat()
                t = ws_clients[ws]["target"]
                v = ws_clients[ws]["version"]
                tf = ws_clients[ws].get("timeframe", "M5")
                ov = await irai_overview(today, v, timeframe=tf)
                se = await irai_series(today, t, v, timeframe=tf)
                if isinstance(se, JSONResponse): se = {"error": "Sem dados"}
                await ws.send_text(json.dumps({"type": "update", "overview": ov, "series": se}))
    except WebSocketDisconnect:
        ws_clients.pop(ws, None)
        print(f"WS client disconnected ({len(ws_clients)} total)")
    except Exception:
        ws_clients.pop(ws, None)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.main:app", host="127.0.0.1", port=8888)
