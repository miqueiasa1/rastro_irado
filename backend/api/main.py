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

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.db import get_connection, DB_PATH
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
    import backend
    import backend.api.main
    import backend.irai.engine
    print("SYS PATH IN API:", sys.path, flush=True)
    print("BACKEND FILE IN API:", backend.__file__, flush=True)
    print("API MAIN FILE IN API:", backend.api.main.__file__, flush=True)
    print("ENGINE FILE IN API:", backend.irai.engine.__file__, flush=True)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/internal/notify_update")
async def notify_update():
    """Chamado pelo collector.py após inserir novas barras."""
    global engine
    try:
        if engine:
            engine._load_params()
    except Exception as e:
        print(f"Error reloading model parameters: {e}")
    series_cache.clear()
    overview_cache_data.clear()
    data_updated_event.set()
    return {"status": "ok"}


@app.get("/api/health")
async def health():
    """Status do sistema."""
    conn = get_connection()
    bar_count = conn.execute("SELECT COUNT(*) as c FROM market_bars").fetchone()["c"]
    last_bar = conn.execute(
        "SELECT MAX(timestamp_utc) as ts FROM market_bars WHERE timeframe='M5'"
    ).fetchone()["ts"]
    conn.close()
    return {
        "status": "ok",
        "bars_total": bar_count,
        "last_bar": last_bar,
        "models_loaded": len(engine.models),
        "targets": [t["target"] for t in engine.registered_targets],
    }


@app.get("/api/irai/targets")
async def irai_targets():
    """Lista todos os targets disponíveis com status."""
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
            }
            for t in engine.registered_targets
        ]
    }


def _get_series_data_sync(target: str, session_date: str, version: str, timeframe: str = "M5") -> dict:
    is_today = (session_date == date.today().isoformat())
    cache_key = (target, session_date, version, timeframe)
    if not is_today and cache_key in series_cache:
        print(f"[CACHE HIT] {cache_key}", flush=True)
        return series_cache[cache_key]
    print(f"[CACHE MISS] {cache_key} - computing...", flush=True)

    conn = get_connection()
    target_db = next((t["data_proxy"] for t in engine.registered_targets if t["target"] == target), target)
    if not target_db: target_db = target
    prev_rows = conn.execute("""
        SELECT close FROM market_bars
        WHERE symbol = ? AND timeframe = ? AND timestamp_utc < ?
        ORDER BY timestamp_utc DESC LIMIT 95
    """, (target_db, timeframe, f"{session_date}T00:00:00Z")).fetchall()
    conn.close()
    history_closes = [r["close"] for r in reversed(prev_rows)]

    snapshots = engine.compute_from_db(session_date, target=target, version=version, timeframe=timeframe, persist_state=is_today)
    if not snapshots:
        return {"error": f"Sem dados para sessão {session_date}"}

    target_info = next((t for t in engine.registered_targets if t["target"] == target), {})
    is_b3 = target_info.get("session_start_h", 0) != 0
    
    series_data = [_snap_to_dict(s) for s in snapshots]
    try:
        from backend.irai.nwe import compute_nwe
        series_data = compute_nwe(series_data, history_closes)
    except Exception as e:
        print(f"Error computing NWE in API: {e}", flush=True)

    result = {
        "session_date": session_date,
        "target": target,
        "display_name": target_info.get("display_name", target),
        "icon": target_info.get("icon", "📊"),
        "bars": len(snapshots),
        "series": series_data,
        "history_closes": history_closes,
        "is_b3": is_b3,
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
    is_today = (session_date == date.today().isoformat())
    cache_key = (session_date, version, timeframe)
    if not is_today and cache_key in overview_cache_data:
        return overview_cache_data[cache_key]

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
            is_preview = last_dict["is_preview"]
            is_cointegrated = last_dict["is_cointegrated"]
            johansen_p_value = last_dict["johansen_p_value"]

            sparkline = [round(s["p_up"], 1) for s in series_list[-24:]]
            flow_confirms = last_dict.get("flow_confirms")

            price_diverges = False
            price_diverge_z = None
            try:
                slug = t["slug"]
                m = engine.models.get(slug, {})
                div_cfg = m.get("divergence_config", {"sigma": 0.005, "threshold": 0.5})
                target_div_sigma = div_cfg.get("sigma", 0.005)
                target_div_threshold = div_cfg.get("threshold", 0.5)

                t_frac = last_dict.get("t_frac", 0.0)
                if target_div_sigma > 0 and t_frac > 0:
                    ret_frac = win_return / 100.0
                    ret_z = ret_frac / (target_div_sigma * math.sqrt(t_frac))
                    price_diverge_z = round(ret_z, 2)

                    if p_up > 55 and ret_z < -target_div_threshold:
                        price_diverges = True
                    elif p_up < 45 and ret_z > target_div_threshold:
                        price_diverges = True
            except Exception:
                pass

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
):
    """Série IRAI completa para uma sessão. Suporta multi-target."""
    if session_date is None:
        session_date = date.today().isoformat()

    result = await run_in_threadpool(_get_series_data_sync, target, session_date, version, timeframe=timeframe)
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
        "win_bar_open": getattr(snap, "win_bar_open", snap.win_current),
        "win_high": getattr(snap, "win_high", snap.win_current),
        "win_low": getattr(snap, "win_low", snap.win_current),
        "win_current": snap.win_current,
        "stale_factors": snap.stale_factors,
        "bar_delta": snap.bar_delta,
        "cum_delta": snap.cum_delta,
        "cum_delta_norm": snap.cum_delta_norm,
        "flow_confirms": snap.flow_confirms,
        "price_diverges": snap.price_diverges,
        "price_diverge_z": snap.price_diverge_z,
        "pair_z": getattr(snap, "pair_z", None),
        "pair_factor": getattr(snap, "pair_factor", None),
        "pair_beta": getattr(snap, "pair_beta", None),
        "pair_signal": getattr(snap, "pair_signal", None),
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
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=8888, reload=True)
