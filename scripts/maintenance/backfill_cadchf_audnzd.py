"""
Backfill histórico para CADCHF e AUDNZD via Tickmill MT5.
Baixa ~250 sessões (barras M5 dos últimos ~60 dias) para ter dados suficientes para calibração.
"""
import MetaTrader5 as mt5
import sqlite3
import os
import sys
import time
from datetime import datetime, timezone, timedelta

os.environ["PYTHONIOENCODING"] = "utf-8"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "irai.db")
TICKMILL_PATH = r"C:\Program Files\Tickmill MT5 Terminal\terminal64.exe"

NEW_SYMBOLS = ["CADCHF", "AUDNZD"]
N_BARS = 80000  # ~277 dias de M5 (288 barras/dia × 277) — suficiente para o calibrador


def compute_bar_delta(open_p, high, low, close, real_volume):
    bar_range = high - low
    if bar_range <= 0 or real_volume <= 0:
        return 0.0
    close_pct = (close - low) / bar_range
    return real_volume * (2 * close_pct - 1)


def backfill_symbol(symbol, conn, n_bars=N_BARS):
    print(f"\n  Baixando {n_bars} barras M5 de {symbol}...")
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, n_bars)

    if rates is None or len(rates) == 0:
        err = mt5.last_error()
        print(f"  ERRO: sem dados para {symbol} — {err}")
        return 0

    inserted = 0
    cursor = conn.cursor()

    for bar in rates:
        ts = datetime.fromtimestamp(bar[0], tz=timezone.utc)
        ts_iso = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        o, h, l, c = float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4])
        tick_vol = float(bar[5]) if bar[5] else 0
        real_vol = float(bar[7]) if len(bar) > 7 and bar[7] else 0
        delta = compute_bar_delta(o, h, l, c, real_vol)

        try:
            cursor.execute(
                """INSERT OR IGNORE INTO market_bars
                   (symbol, source, timeframe, timestamp_utc, open, high, low, close,
                    volume, real_volume, delta)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (symbol, "tickmill", "M5", ts_iso, o, h, l, c, tick_vol, real_vol, delta),
            )
            if cursor.rowcount > 0:
                inserted += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    print(f"  OK: {inserted} barras novas inseridas ({len(rates)} recebidas)")
    return inserted


def main():
    print("=" * 60)
    print("  Backfill: CADCHF + AUDNZD via Tickmill")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)

    print(f"\nConectando ao Tickmill MT5...")
    if not mt5.initialize(path=TICKMILL_PATH, timeout=20000):
        print(f"ERRO ao conectar: {mt5.last_error()}")
        conn.close()
        return

    print(f"Conectado. Versão: {mt5.version()}")

    total = 0
    for sym in NEW_SYMBOLS:
        # Verificar se o símbolo existe
        info = mt5.symbol_info(sym)
        if info is None:
            print(f"\n  AVISO: {sym} nao encontrado no Tickmill. Verifique o nome do simbolo.")
            continue
        print(f"\n  {sym}: encontrado (digits={info.digits}, spread={info.spread})")
        n = backfill_symbol(sym, conn)
        total += n

    mt5.shutdown()
    conn.close()

    print(f"\n{'=' * 60}")
    print(f"  Total: {total} barras inseridas para {NEW_SYMBOLS}")
    print("  Pronto para calibracao.")
    print("=" * 60)


if __name__ == "__main__":
    main()
