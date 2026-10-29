"""
IRAI — Worker de coleta em tempo real.

Conecta sequencialmente aos terminais MT5 (XP e Tickmill) a cada
intervalo configurado, coleta barras M5 mais recentes e insere no SQLite.

Projetado para rodar como serviço persistente durante o pregão B3.

Uso: python backend/workers/collector.py [--interval 60] [--once]
"""

import MetaTrader5 as mt5
import sqlite3
import os
import sys
import time
import re
import argparse
import logging
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.db import get_connection, DB_PATH, init_db, save_live_snapshots
from backend.timeconv import brt_epoch_to_broker_epoch, now_broker_wall

TIMEFRAME_SECONDS = {"M1": 60, "M2": 120, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600}

os.environ["PYTHONIOENCODING"] = "utf-8"

# ── Configuração ──────────────────────────────────────────
TERMINALS = [
    {
        "name": "BR (XP)",
        "paths": [
            r"C:\Program Files\MetaTrader 5 Terminal\terminal64.exe",
            r"C:\Program Files\MetaTrader 5\terminal64.exe",
        ],
        "source": "br",
        "symbols": [
            "WIN$N", "WDO$N", "DI1$N",
            "VALE3", "PETR4", "ITUB4", "BBDC4", "ELET3", "WEGE3", "ABEV3", "B3SA3",
        ],
    },
    {
        "name": "Tickmill",
        "path": r"C:\Program Files\Tickmill MT5 Terminal\terminal64.exe",
        "source": "tickmill",
        "symbols": [
            # Macro, Índices Globais & Commodities
            "DXY", "BRENT", "CHINA50", "USDMXN", "VIX", "BTCUSD",
            "US500", "US30", "USTEC", "DE40", "US2000", "JP225", "XAUUSD",
            # Matriz Completa Forex (28 Pares das 8 Moedas Principais)
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
            "EURGBP", "EURCHF", "EURJPY", "EURAUD", "EURCAD", "EURNZD",
            "GBPJPY", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD",
            "AUDNZD", "AUDCAD", "AUDCHF", "AUDJPY",
            "NZDCAD", "NZDCHF", "NZDJPY",
            "CADCHF", "CADJPY",
            "CHFJPY",
        ],
    },
    {
        "name": "Axi",
        "path": r"C:\Program Files\Axi MetaTrader 5 Terminal\terminal64.exe",
        "source": "axi",
        "symbols": [
            # iShares — apenas fatores de calibracao, nao entram no painel
            "iSharesBrazil+",       # EWZ
            "iSharesTreasury20+",   # TLT (20+y)
            "iSharesTreasury10-20+",# TLH (10-20y)
            "iSharesTreasury1-3+",  # SHY (1-3y)
            "iSharesUSEmerging+",   # EMB
            "iSharesCurrencyBond+", # LEMB
        ],
    },
]

# Controle de status offline para redução de ruído de logs
OFFLINE_TERMINALS = {}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("collector")


def compute_bar_delta(open_p, high, low, close, real_volume):
    """Aproximação de delta por posição de close na barra."""
    bar_range = high - low
    if bar_range <= 0 or real_volume <= 0:
        return 0.0
    close_pct = (close - low) / bar_range  # 0..1
    return real_volume * (2 * close_pct - 1)


def resolve_symbol(symbol: str) -> str:
    """
    Mapeia símbolos contínuos (WIN$N, WDO$N, DI1$N) para os contratos futuros ativos reais
    caso o terminal conectado não ofereça suporte direto a eles (ex: contas de simulação/demo).
    """
    # 1. Removido o suporte ao contrato contínuo nativo (bug no MT5 no dia de rolagem).
    # Sempre resolvemos dinamicamente para o contrato futuro vigente.

    # 2. Caso contrário, resolvemos dinamicamente para o contrato futuro vigente
    now = time.time()
    all_symbols = mt5.symbols_get()
    if not all_symbols:
        return symbol

    if symbol == "WIN$N":
        # WIN expira em meses pares: G(Fev), J(Abr), M(Jun), Q(Ago), V(Out), Z(Dez)
        pattern = re.compile(r"^WIN[GJKMQVUZ]\d{2}$")
        candidates = []
        for s in all_symbols:
            if pattern.match(s.name):
                if s.expiration_time == 0 or s.expiration_time > now:
                    candidates.append(s)
        if candidates:
            candidates.sort(key=lambda x: (x.expiration_time if x.expiration_time > 0 else float('inf'), -x.session_volume))
            resolved = candidates[0].name
            mt5.symbol_select(resolved, True)
            log.info(f"Mapeamento dinâmico: {symbol} -> {resolved} (Conta Demo/Simulação)")
            return resolved

    elif symbol == "WDO$N":
        # WDO expira todo mês: F, G, H, J, K, M, N, Q, U, V, X, Z
        pattern = re.compile(r"^WDO[FGHJKMNQUVXZ]\d{2}$")
        candidates = []
        for s in all_symbols:
            if pattern.match(s.name):
                if s.expiration_time == 0 or s.expiration_time > now:
                    candidates.append(s)
        if candidates:
            candidates.sort(key=lambda x: (x.expiration_time if x.expiration_time > 0 else float('inf'), -x.session_volume))
            resolved = candidates[0].name
            mt5.symbol_select(resolved, True)
            log.info(f"Mapeamento dinâmico: {symbol} -> {resolved} (Conta Demo/Simulação)")
            return resolved

    elif symbol == "DI1$N":
        # DI1 expira mensalmente/trimestralmente, mas apenas os contratos de Janeiro (F) possuem liquidez
        # relevante para servir como benchmark ativo.
        pattern = re.compile(r"^DI1F\d{2}$")
        candidates = []
        for s in all_symbols:
            if pattern.match(s.name):
                if s.expiration_time == 0 or s.expiration_time > now:
                    candidates.append(s)
        if candidates:
            candidates.sort(key=lambda x: (x.expiration_time if x.expiration_time > 0 else float('inf'), -x.session_volume))
            resolved = candidates[0].name
            mt5.symbol_select(resolved, True)
            log.info(f"Mapeamento dinâmico: {symbol} -> {resolved} (Conta Demo/Simulação)")
            return resolved

    return symbol


def collect_recent_bars(symbol: str, source: str, conn: sqlite3.Connection, timeframe: str, mt5_timeframe, n_bars: int = 5, resolved_symbol: str = None) -> int:
    """Coleta barras de um símbolo no timeframe informado com alinhamento de fuso e backfill dinâmico."""
    query_symbol = resolved_symbol if resolved_symbol else symbol

    # Backfill dinâmico: se n_bars é pequeno (ciclo normal), verifica lacuna desde a última barra gravada
    if n_bars <= 10:
        try:
            last_row = conn.execute("""
                SELECT MAX(timestamp_utc) as max_ts FROM market_bars
                WHERE symbol = ? AND timeframe = ?
            """, (symbol, timeframe)).fetchone()
            if last_row and last_row[0]:
                last_dt = datetime.fromisoformat(last_row[0].replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
                # O banco usa o relógio do broker (NY+7): comparar com "agora" no mesmo relógio
                now_dt = now_broker_wall()
                diff_sec = (now_dt - last_dt).total_seconds()
                tf_sec = TIMEFRAME_SECONDS.get(timeframe, 300)
                missing_bars = int(max(diff_sec, 0) / tf_sec) + 3
                n_bars = max(n_bars, min(missing_bars, 300))
        except Exception as e:
            log.debug(f"Backfill check falhou para {symbol} {timeframe}: {e}")

    rates = mt5.copy_rates_from_pos(query_symbol, mt5_timeframe, 0, n_bars)

    if rates is None or len(rates) == 0:
        return 0

    inserted = 0
    cursor = conn.cursor()

    for i, bar in enumerate(rates):
        bar_timestamp = float(bar[0])
        # Unificação no relógio do broker (Tickmill/Axi = NY+7: GMT+3 no verão americano, GMT+2 no inverno).
        # O terminal XP entrega a B3 em BRT: converter com offset dinâmico (+6h ou +5h).
        if source == "br":
            bar_timestamp = brt_epoch_to_broker_epoch(bar_timestamp)

        ts = datetime.fromtimestamp(bar_timestamp, tz=timezone.utc)
        ts_iso = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

        o, h, l, c = float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4])
        tick_vol = float(bar[5]) if bar[5] else 0
        real_vol = float(bar[7]) if len(bar) > 7 and bar[7] else 0
        delta = compute_bar_delta(o, h, l, c, real_vol)

        # Barras recentes (últimas 2) → REPLACE para capturar OHLC final correto
        is_recent_bar = (i >= len(rates) - 2)
        verb = "INSERT OR REPLACE" if is_recent_bar else "INSERT OR IGNORE"

        try:
            cursor.execute(
                f"""{verb} INTO market_bars
                   (symbol, source, timeframe, timestamp_utc, open, high, low, close,
                    volume, real_volume, delta)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (symbol, source, timeframe, ts_iso, o, h, l, c,
                 tick_vol, real_vol, delta),
            )
            if cursor.rowcount > 0:
                inserted += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    return inserted


def is_b3_session() -> bool:
    """Verifica se está dentro do horário do pregão B3 Futuros/Ações (08:50–18:30 BRT, Seg-Sex)."""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    h, m = now.hour, now.minute
    # Futuros B3 (WIN/WDO/DI1): abertura às 09:00 (pré-abertura 08:55). Coleta inicia às 08:50 BRT.
    if h < 8 or (h == 8 and m < 50):
        return False
    if h > 18 or (h == 18 and m > 30):
        return False
    return True


def run_collection_cycle(conn: sqlite3.Connection, skip_br: bool = False, cycle_num: int = 1) -> dict:
    """Executa um ciclo de coleta em todos os terminais."""
    results = {}

    TIMEFRAME_MAP = {
        "M1": mt5.TIMEFRAME_M1,
        "M2": mt5.TIMEFRAME_M2,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
    }

    for terminal in TERMINALS:
        # Pular terminal BR fora do horário
        if skip_br and terminal.get("source") == "br":
            for sym in terminal["symbols"]:
                results[sym] = {"status": "skipped", "error": "B3 fechada"}
            continue

        # Obter caminhos a tentar
        paths_to_try = terminal.get("paths")
        if not paths_to_try:
            paths_to_try = [terminal.get("path")]

        connected = False
        last_error = None
        active_path = None

        for path in paths_to_try:
            try:
                mt5.shutdown()
            except Exception:
                pass
            time.sleep(0.5)

            timeout_ms = 25000
            if mt5.initialize(path=path, timeout=timeout_ms):
                connected = True
                active_path = path
                break
            else:
                last_error = mt5.last_error()
                # Loga o fallback apenas no primeiro ciclo offline para não poluir
                if OFFLINE_TERMINALS.get(terminal['name'], 0) == 0:
                    log.info(f"{terminal['name']}: Falha ao conectar em {path} ({last_error}). Tentando fallback...")

        if terminal['name'] not in OFFLINE_TERMINALS:
            OFFLINE_TERMINALS[terminal['name']] = 0

        if not connected:
            offline_count = OFFLINE_TERMINALS[terminal['name']]
            OFFLINE_TERMINALS[terminal['name']] += 1

            if offline_count == 0:
                log.warning(f"{terminal['name']}: Todas as tentativas de conexão falharam (último erro: {last_error}). Suprimindo logs repetidos até reconectar.")
            elif offline_count % 30 == 0:
                log.warning(f"{terminal['name']}: Continua offline há {offline_count} ciclos (último erro: {last_error}).")

            for sym in terminal["symbols"]:
                results[sym] = {"status": "error", "error": str(last_error)}
            continue

        offline_count = OFFLINE_TERMINALS[terminal['name']]
        if offline_count > 0:
            log.info(f"{terminal['name']}: Reconectado com sucesso após {offline_count} ciclos offline usando {active_path}")
        else:
            log.info(f"{terminal['name']}: Conectado com sucesso usando {active_path}")

        OFFLINE_TERMINALS[terminal['name']] = 0

        for sym in terminal["symbols"]:
            resolved_sym = resolve_symbol(sym)
            total_inserted = 0
            for tf_name, mt5_tf in TIMEFRAME_MAP.items():
                n_bars = 5
                if cycle_num == 1:
                    # History pre-fill sizes
                    if tf_name == "M1": n_bars = 600
                    elif tf_name == "M2": n_bars = 300
                    elif tf_name == "M5": n_bars = 150
                    elif tf_name == "M15": n_bars = 100
                    elif tf_name == "M30": n_bars = 100
                    elif tf_name == "H1": n_bars = 50

                inserted = collect_recent_bars(sym, terminal["source"], conn, tf_name, mt5_tf, n_bars, resolved_symbol=resolved_sym)
                total_inserted += inserted

            tick = mt5.symbol_info_tick(resolved_sym)
            bid = tick.bid if tick and tick.bid > 0 else 0
            results[sym] = {
                "status": "ok",
                "inserted": total_inserted,
                "bid": bid,
                "source": terminal["source"],
            }

        mt5.shutdown()

    return results


def persist_live_snapshots_cycle(db_path):
    """Calcula e persiste snapshots ao vivo para os alvos ativos no ciclo atual."""
    try:
        from backend.irai.engine import IRAIEngine
        from backend.irai.nwe import compute_nwe
        from datetime import date

        from backend.api.main import _snap_to_dict
        from backend.db import get_connection as _get_conn
        from backend.timeconv import current_session_date
        engine = IRAIEngine(db_path)
        
        saved_count = 0
        for t_info in engine.registered_targets:
            target = t_info["target"]
            # B3: dia de Brasília. Globais: dia do broker (vira às 17:00 NY) — evita ~6h/noite sem snapshots.
            today_str = current_session_date(t_info.get("session_start_h", 0) != 0)
            snapshots = engine.compute_from_db(today_str, target=target, version="v2", timeframe="M5", persist_state=True)
            if snapshots:
                series_data = [_snap_to_dict(s) for s in snapshots]

                # Buscar history_closes do dia anterior para warm-up das bandas NWE
                target_db = t_info.get("data_proxy") or target
                if not target_db:
                    target_db = target
                try:
                    conn_hist = _get_conn(db_path)
                    prev_rows = conn_hist.execute("""
                        SELECT close FROM market_bars
                        WHERE symbol = ? AND timeframe = 'M5' AND timestamp_utc < ?
                        ORDER BY timestamp_utc DESC LIMIT 190
                    """, (target_db, f"{today_str}T00:00:00Z")).fetchall()
                    conn_hist.close()
                    history_closes = [r["close"] for r in reversed(prev_rows)]
                except Exception:
                    history_closes = []

                series_data = compute_nwe(series_data, history_closes)
                count = save_live_snapshots(db_path, target, today_str, series_data, timeframe="M5", is_live_captured=1)
                saved_count += count
        log.info(f"  [Live Snapshots] {saved_count} snapshots persistidos com sucesso")
    except Exception as e:
        log.warning(f"  [Live Snapshots] Erro ao persistir: {e}")


def main():
    parser = argparse.ArgumentParser(description="IRAI - Collector worker")
    parser.add_argument("--interval", type=int, default=20, help="Intervalo em segundos (default: 20)")
    parser.add_argument("--once", action="store_true", help="Executa apenas um ciclo")
    parser.add_argument("--force", action="store_true", help="Ignora verificacao de horario")
    parser.add_argument("--db", default=DB_PATH, help="Caminho do banco SQLite")
    args = parser.parse_args()

    log.info("=" * 50)
    log.info("IRAI Collector v1.0")
    log.info(f"Intervalo: {args.interval}s | DB: {args.db}")
    log.info("=" * 50)

    init_db(args.db)  # Auto-heal schema no boot

    cycle = 0
    HEALTH_CHECK_EVERY = 15  # A cada 15 ciclos (~5 min com interval=20s)

    while True:
        cycle += 1
        conn = None
        try:
            conn = get_connection(args.db)

            b3_open = args.force or is_b3_session()

            log.info(f"--- Ciclo {cycle} {'(B3 aberta)' if b3_open else '(apenas internacional)'} ---")
            results = run_collection_cycle(conn, skip_br=not b3_open, cycle_num=cycle)

            for sym, r in results.items():
                if r.get("status") == "skipped":
                    continue  # Silencioso para ativos fora do horário
                if r["status"] == "ok":
                    log.info(f"  {sym:<12} bid={r['bid']:<12.2f} +{r['inserted']} barras")
                else:
                    log.warning(f"  {sym:<12} ERRO: {r.get('error', '?')}")

            persist_live_snapshots_cycle(args.db)

            # Health Watchdog embutido — roda a cada ~5 min
            if cycle % HEALTH_CHECK_EVERY == 0 or cycle == 1:
                try:
                    from scripts.health_watchdog import run_health_check
                    run_health_check()
                except Exception as e:
                    log.warning(f"  [Health Watchdog] Erro: {e}")

            # Notificar API sobre novos dados para push via WebSocket
            try:
                import requests
                requests.post("http://127.0.0.1:8888/api/internal/notify_update", timeout=1.0)
            except Exception as e:
                log.debug(f"Falha ao notificar API local: {e}")

        except Exception as e:
            log.error(f"Erro no ciclo {cycle} do Collector: {e}. Recuperando no próximo ciclo...", exc_info=True)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        if args.once:
            break

        log.info(f"  Proximo ciclo em {args.interval}s...")
        time.sleep(args.interval)

    log.info("Collector encerrado.")


if __name__ == "__main__":
    main()
