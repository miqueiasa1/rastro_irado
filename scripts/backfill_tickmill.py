"""
Backfill: Puxa histórico M5 de todos os símbolos novos do Tickmill.
Puxa 100.000 barras (~1 ano) para cada símbolo.
"""
import MetaTrader5 as mt5
import sqlite3
import sys
from datetime import datetime, timezone

TERMINAL = r"C:\Program Files\Tickmill MT5 Terminal\terminal64.exe"
DB_PATH = "data/irai.db"

# Símbolos para backfill (os que NÃO estão no DB)
SYMBOLS = [
    "USTEC", "US30", "XAUUSD",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
]

BARS = 100_000  # ~1 ano de M5

def compute_bar_delta(o, h, l, c, rv):
    bar_range = h - l
    if bar_range <= 0 or rv <= 0:
        return 0.0
    return rv * (2 * ((c - l) / bar_range) - 1)


def backfill_symbol(symbol, conn):
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, BARS)
    if rates is None or len(rates) == 0:
        print(f"  ❌ {symbol}: sem dados")
        return 0

    inserted = 0
    cursor = conn.cursor()
    for bar in rates:
        ts = datetime.fromtimestamp(bar[0], tz=timezone.utc)
        ts_iso = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        o, h, l, c = float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4])
        tv = float(bar[5]) if bar[5] else 0
        rv = float(bar[7]) if len(bar) > 7 and bar[7] else 0
        delta = compute_bar_delta(o, h, l, c, rv)

        try:
            cursor.execute(
                """INSERT OR IGNORE INTO market_bars
                   (symbol, source, timeframe, timestamp_utc, open, high, low, close,
                    volume, real_volume, delta)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (symbol, "tickmill", "M5", ts_iso, o, h, l, c, tv, rv, delta),
            )
            if cursor.rowcount > 0:
                inserted += 1
        except Exception:
            pass

    conn.commit()
    return inserted


def main():
    if not mt5.initialize(TERMINAL):
        print(f"FAIL: {mt5.last_error()}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    print(f"Backfilling {len(SYMBOLS)} symbols ({BARS:,} bars each)...")
    for sym in SYMBOLS:
        n = backfill_symbol(sym, conn)
        print(f"  ✅ {sym:10s}: {n:>8,d} bars inserted")

    conn.close()
    mt5.shutdown()
    print("\nDone!")


if __name__ == "__main__":
    main()
