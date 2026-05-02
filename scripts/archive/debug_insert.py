"""Debug backfill insertion."""
import MetaTrader5 as mt5
import sqlite3
import time
from datetime import datetime, timezone

try:
    mt5.shutdown()
except:
    pass
time.sleep(1)

mt5.initialize(path=r"C:\Program Files\Axi MetaTrader 5 Terminal\terminal64.exe", timeout=30000)

sym = "iSharesBrazil+"
mt5.symbol_select(sym, True)
time.sleep(2)

bars = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 10)
print(f"Got {len(bars) if bars is not None else 0} bars from MT5")

if bars is not None and len(bars) > 0:
    # Show first bar structure
    bar = bars[0]
    print(f"Bar type: {type(bar)}, length: {len(bar)}")
    print(f"Bar[0]: {bar}")
    ts = datetime.fromtimestamp(bar[0], tz=timezone.utc)
    ts_iso = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    o, h, l, c = float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4])
    tv = float(bar[5]) if bar[5] else 0
    rv = float(bar[7]) if len(bar) > 7 and bar[7] else 0
    print(f"  ts={ts_iso}, o={o}, h={h}, l={l}, c={c}, tv={tv}, rv={rv}")
    
    # Try insertion
    conn = sqlite3.connect("data/irai.db")
    cursor = conn.cursor()
    
    # Check table structure
    schema = cursor.execute("SELECT sql FROM sqlite_master WHERE name='market_bars'").fetchone()
    print(f"\nTable schema:\n{schema[0]}")
    
    # Check unique constraint
    try:
        cursor.execute(
            """INSERT OR IGNORE INTO market_bars
               (symbol, source, timeframe, timestamp_utc, open, high, low, close,
                volume, real_volume, delta)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sym, "axi", "M5", ts_iso, o, h, l, c, tv, rv, 0.0),
        )
        print(f"rowcount after INSERT OR IGNORE: {cursor.rowcount}")
        conn.commit()
        
        # Verify
        check = cursor.execute(
            "SELECT COUNT(*) FROM market_bars WHERE symbol=?", (sym,)
        ).fetchone()
        print(f"Rows for {sym}: {check[0]}")
    except Exception as e:
        print(f"ERROR: {e}")
    
    conn.close()

mt5.shutdown()
