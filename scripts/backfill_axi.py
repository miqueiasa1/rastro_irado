"""
Backfill: Puxa histórico M5 dos iShares da Axi (EWZ, Treasuries, etc).
Estes ativos servem como fatores candidatos para recalibração — não entram no painel.
"""
import MetaTrader5 as mt5
import sqlite3
import sys
import time
from datetime import datetime, timezone

TERMINAL = r"C:\Program Files\Axi MetaTrader 5 Terminal\terminal64.exe"
DB_PATH = "data/irai.db"

# Símbolos iShares da Axi para backfill como fatores de calibração
SYMBOLS = [
    "iSharesBrazil+",       # EWZ - MSCI Brazil ETF
    "iSharesTreasury20+",   # TLT - 20+ Year Treasury
    "iSharesTreasury10-20+",# TLH - 10-20 Year Treasury  
    "iSharesTreasury1-3+",  # SHY - 1-3 Year Treasury
    "iSharesUSEmerging+",   # EMB - USD EM Bond
    "iSharesCurrencyBond+", # LEMB - EM Local Currency Bond
]

BARS = 50_000  # Axi retorna ~40k max por símbolo


def compute_bar_delta(o, h, l, c, rv):
    bar_range = h - l
    if bar_range <= 0 or rv <= 0:
        return 0.0
    return rv * (2 * ((c - l) / bar_range) - 1)


def backfill_symbol(symbol, conn):
    mt5.symbol_select(symbol, True)
    time.sleep(1)  # aguardar dados do símbolo carregarem
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, BARS)
    if rates is None or len(rates) == 0:
        print(f"  [FAIL] {symbol}: sem dados")
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
                (symbol, "axi", "M5", ts_iso, o, h, l, c, tv, rv, delta),
            )
            if cursor.rowcount > 0:
                inserted += 1
        except Exception:
            pass

    conn.commit()
    
    if inserted > 0:
        first = datetime.fromtimestamp(rates[0][0], tz=timezone.utc)
        last = datetime.fromtimestamp(rates[-1][0], tz=timezone.utc)
        first_str = first.strftime("%Y-%m-%d")
        last_str = last.strftime("%Y-%m-%d")
        print(f"  [OK] {symbol:28s}: {inserted:>8,d} bars ({first_str} -> {last_str})")
    else:
        print(f"  [SKIP] {symbol:28s}: 0 new bars (already backfilled?)")
    
    return inserted


def main():
    # Desconectar qualquer terminal MT5 anterior
    try:
        mt5.shutdown()
    except Exception:
        pass
    time.sleep(1)

    if not mt5.initialize(path=TERMINAL, timeout=30000):
        print(f"FAIL: {mt5.last_error()}")
        sys.exit(1)
    
    info = mt5.terminal_info()
    print(f"Terminal: {info.company} ({info.path})")

    conn = sqlite3.connect(DB_PATH)

    print(f"Backfilling {len(SYMBOLS)} iShares from Axi ({BARS:,} bars max each)...")
    print()
    
    total = 0
    for sym in SYMBOLS:
        n = backfill_symbol(sym, conn)
        total += n

    print(f"\n{'='*60}")
    print(f"  Total: {total:,} bars inserted")
    print(f"{'='*60}")

    conn.close()
    mt5.shutdown()


if __name__ == "__main__":
    main()
