"""Test Axi MT5 history depth for iShares symbols."""
import MetaTrader5 as mt5
from datetime import datetime, timezone

mt5.initialize(path=r"C:\Program Files\Axi MetaTrader 5 Terminal\terminal64.exe", timeout=15000)

targets = [
    "iSharesBrazil+",
    "iSharesTreasury20+",
    "iSharesTreasury10-20+",
    "iSharesTreasury1-3+",
    "iSharesCurrencyBond+",
    "iSharesUSEmerging+",
]

for name in targets:
    mt5.symbol_select(name, True)
    
    for n in [10, 100, 500, 1000, 5000, 10000, 50000]:
        bars = mt5.copy_rates_from_pos(name, mt5.TIMEFRAME_M5, 0, n)
        if bars is not None and len(bars) > 0:
            first = datetime.fromtimestamp(bars[0][0], tz=timezone.utc)
            last = datetime.fromtimestamp(bars[-1][0], tz=timezone.utc)
            first_str = first.strftime("%Y-%m-%d %H:%M")
            last_str = last.strftime("%Y-%m-%d %H:%M")
            print(f"  {name} n={n:>6}: got {len(bars):>6} bars | {first_str} -> {last_str}")
        else:
            err = mt5.last_error()
            print(f"  {name} n={n:>6}: NO DATA | error: {err}")
            break
    print()

mt5.shutdown()
