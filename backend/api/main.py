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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.db import get_connection, DB_PATH
from backend.irai.engine import IRAIEngine, FACTOR_LABELS, TARGET

# ── Engine singleton ──────────────────────────────────────
engine: IRAIEngine = None
ws_clients: dict = {}
data_updated_event = asyncio.Event()

# ── Cache de resultados computados ─────────────────────
series_cache: dict = {}   # (target, date) → result dict
overview_cache_data = {"date": None, "result": None}


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
                    
                    if overview_cache is None:
                        overview_cache = await irai_overview(session_date)
                        
                    if target not in series_cache:
                        res = await irai_series(session_date, target)
                        if isinstance(res, JSONResponse):
                            series_cache[target] = {"error": "Sem dados"}
                        else:
                            series_cache[target] = res
                            
                    payload = json.dumps({
                        "type": "update",
                        "session_date": session_date,
                        "overview": overview_cache,
                        "series": series_cache[target]
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
    series_cache.clear()
    overview_cache_data["date"] = None
    overview_cache_data["result"] = None
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
                "session_hours": f"{t['session_start_h']:02d}h-{t['session_end_h']:02d}h",
            }
            for t in engine.registered_targets
        ]
    }


@app.get("/api/irai/overview")
async def irai_overview(
    session_date: str = Query(None, description="Data YYYY-MM-DD (default: hoje)"),
):
    """Snapshot atual de TODOS os targets calibrados."""
    if session_date is None:
        # Usar último dia com dados (qualquer símbolo — inclui internacional no fim de semana)
        conn = get_connection()
        row = conn.execute("""
            SELECT DISTINCT substr(timestamp_utc, 1, 10) as d
            FROM market_bars WHERE timeframe='M5'
            ORDER BY d DESC LIMIT 1
        """).fetchone()
        conn.close()
        if row:
            session_date = row["d"]
        else:
            session_date = date.today().isoformat()

    # Return cached overview if available for the same date
    if overview_cache_data["date"] == session_date and overview_cache_data["result"]:
        return overview_cache_data["result"]

    results = []
    for t in engine.registered_targets:
        if not t.get("accuracy"):
            continue  # Skip não-calibrados

        try:
            snapshots = engine.compute_from_db(session_date, target=t["target"])
            if not snapshots:
                continue
            last = snapshots[-1]
            # Sparkline: P_up de cada barra
            sparkline = [round(s.p_up, 1) for s in snapshots[-24:]]  # últimas 2h
            # Flow confirms (already present in snap)
            flow_confirms = getattr(last, "flow_confirms", None)
            
            # Price diverges — baseado em z-score do retorno do target
            # Lógica: IRAI sinaliza direção X mas o preço se move
            # significativamente na direção oposta (z-score > limiar)
            price_diverges = False
            price_diverge_z = None
            try:
                slug = t["slug"]
                m = engine.models.get(slug, {})
                div_cfg = m.get("divergence_config", {"sigma": 0.005, "threshold": 0.5})
                target_div_sigma = div_cfg.get("sigma", 0.005)
                target_div_threshold = div_cfg.get("threshold", 0.5)
                
                if target_div_sigma > 0 and last.t_frac > 0:
                    # z-score do retorno atual do target
                    ret_frac = last.win_return / 100.0  # % → fração
                    ret_z = ret_frac / (target_div_sigma * math.sqrt(last.t_frac))
                    price_diverge_z = round(ret_z, 2)
                    
                    if last.p_up > 55 and ret_z < -target_div_threshold:
                        price_diverges = True
                    elif last.p_up < 45 and ret_z > target_div_threshold:
                        price_diverges = True
            except Exception:
                pass

            # NWE - calcula apenas para os dois últimos pontos O(N)
            nwe_slope = 0.0
            try:
                if len(snapshots) >= 2:
                    h = 8  # NWE_BW default
                    n = len(snapshots)
                    vals = [s.win_return for s in snapshots]
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
                
            results.append({
                "target": t["target"],
                "slug": t["slug"],
                "display_name": t["display_name"],
                "icon": t["icon"],
                "p_up": round(last.p_up, 1),
                "score": round(last.score, 4),
                "verdict": last.verdict,
                "win_return": round(last.win_return, 4),
                "bars": len(snapshots),
                "accuracy": t.get("accuracy"),
                "sparkline": sparkline,
                "flow_confirms": flow_confirms,
                "price_diverges": price_diverges,
                "price_diverge_z": price_diverge_z,
                "nwe_slope": nwe_slope,
                "is_preview": getattr(last, "is_preview", False),
            })
        except Exception as e:
            print(f"Overview error for {t['target']}: {e}")

    result = {
        "session_date": session_date,
        "targets": results,
    }
    overview_cache_data["date"] = session_date
    overview_cache_data["result"] = result
    return result


@app.get("/api/irai/dates")
async def irai_dates(
    target: str = Query(None, description="Filtrar datas por target específico"),
):
    """Datas com dados disponíveis."""
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


@app.get("/api/irai/series")
async def irai_series(
    session_date: str = Query(None, description="Data YYYY-MM-DD (default: hoje)"),
    target: str = Query("WIN$N", description="Target: WIN$N ou WDO$N"),
):
    """Série IRAI completa para uma sessão. Suporta multi-target."""
    if session_date is None:
        session_date = date.today().isoformat()

    # Check cache first
    cache_key = (target, session_date)
    if cache_key in series_cache:
        return series_cache[cache_key]

    snapshots = engine.compute_from_db(session_date, target=target)

    if not snapshots:
        return JSONResponse(
            status_code=404,
            content={"error": f"Sem dados para sessão {session_date}"}
        )

    # Lookup display info
    target_info = next((t for t in engine.registered_targets if t["target"] == target), {})
    result = {
        "session_date": session_date,
        "target": target,
        "display_name": target_info.get("display_name", target),
        "icon": target_info.get("icon", "📊"),
        "bars": len(snapshots),
        "series": [_snap_to_dict(s) for s in snapshots],
        "summary": {
            "p_up_min": min(s.p_up for s in snapshots),
            "p_up_max": max(s.p_up for s in snapshots),
            "p_up_final": snapshots[-1].p_up,
            "score_final": snapshots[-1].score,
            "verdict": snapshots[-1].verdict,
            "return": snapshots[-1].win_return,
        },
    }
    # Cache result
    series_cache[(target, session_date)] = result
    return result


@app.get("/api/irai/current")
async def irai_current():
    """Snapshot mais recente (última barra processada)."""
    # Tentar sessão de hoje, senão último dia disponível
    today = date.today().isoformat()
    snapshots = engine.compute_from_db(today)

    if not snapshots:
        # Pegar último dia com dados
        conn = get_connection()
        row = conn.execute("""
            SELECT DISTINCT substr(timestamp_utc, 1, 10) as d
            FROM market_bars
            WHERE symbol = ? AND timeframe = 'M5'
            ORDER BY d DESC LIMIT 1
        """, [TARGET]).fetchone()
        conn.close()

        if row:
            snapshots = engine.compute_from_db(row["d"])

    if not snapshots:
        return JSONResponse(status_code=404, content={"error": "Sem dados"})

    last = snapshots[-1]
    return _snap_to_dict(last)


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
        "win_current": snap.win_current,
        "stale_factors": snap.stale_factors,
        "bar_delta": snap.bar_delta,
        "cum_delta": snap.cum_delta,
        "cum_delta_norm": snap.cum_delta_norm,
        "flow_confirms": snap.flow_confirms,
        "price_diverges": snap.price_diverges,
        "price_diverge_z": snap.price_diverge_z,
        "is_preview": getattr(snap, "is_preview", False),
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
    ws_clients[ws] = {"target": "WIN$N"} # Default
    print(f"WS client connected ({len(ws_clients)} total)")
    
    # Enviar o estado atual imediatamente na conexão
    try:
        today = date.today().isoformat()
        ov = await irai_overview(today)
        se = await irai_series(today, "WIN$N")
        if isinstance(se, JSONResponse): se = {"error": "Sem dados"}
        await ws.send_text(json.dumps({"type": "update", "overview": ov, "series": se}))
    except Exception as e:
        print(f"Initial WS send error: {e}")
        
    try:
        while True:
            # Recebe mensagens de configuração (mudança de target)
            data = await ws.receive_json()
            if data and "target" in data:
                ws_clients[ws]["target"] = data["target"]
                # Força um envio imediato com o novo target
                today = date.today().isoformat()
                ov = await irai_overview(today)
                se = await irai_series(today, data["target"])
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
