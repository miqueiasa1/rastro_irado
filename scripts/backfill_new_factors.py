"""Popular historico de CHINA50, USDMXN, DE40 no irai.db."""
import MetaTrader5 as mt5
import sqlite3
import os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import DB_PATH

TICKMILL = r"C:\Program Files\Tickmill MT5 Terminal\terminal64.exe"
SYMBOLS = ["CHINA50", "USDMXN", "DE40"]

mt5.initialize(path=TICKMILL, timeout=15000)
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

for sym in SYMBOLS:
    mt5.symbol_select(sym, True)
    bars = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 100000)
    if bars is None or len(bars) == 0:
        print(f"{sym}: SEM DADOS")
        continue
    
    count = 0
    for b in bars:
        ts = datetime.utcfromtimestamp(b["time"]).strftime("%Y-%m-%dT%H:%M:%SZ")
        cursor.execute(
            """INSERT OR IGNORE INTO market_bars
               (symbol, source, timeframe, timestamp_utc, open, high, low, close,
                volume, real_volume, delta)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sym, "tickmill", "M5", ts,
             float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"]),
             int(b["tick_volume"]), int(b["real_volume"]), 0),
        )
        count += 1
    
    conn.commit()
    print(f"{sym}: {count} barras inseridas")

conn.close()
mt5.shutdown()
print("Pronto!")
