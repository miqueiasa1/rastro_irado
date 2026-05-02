"""Debug Axi symbol access."""
import MetaTrader5 as mt5
import time
from datetime import datetime, timezone, timedelta

try:
    mt5.shutdown()
except:
    pass
time.sleep(1)

mt5.initialize(path=r"C:\Program Files\Axi MetaTrader 5 Terminal\terminal64.exe", timeout=30000)
info = mt5.terminal_info()
print(f"Terminal: {info.company}")

sym = "iSharesBrazil+"
sinfo = mt5.symbol_info(sym)
if sinfo:
    print(f"Symbol found: {sym}")
    print(f"  visible: {sinfo.visible}")
    print(f"  trade_mode: {sinfo.trade_mode}")
    print(f"  digits: {sinfo.digits}")
    
    # Force select
    ok = mt5.symbol_select(sym, True)
    print(f"  select: {ok}")
    time.sleep(3)  # longer wait
    
    # Check info again
    sinfo2 = mt5.symbol_info(sym)
    print(f"  visible after select: {sinfo2.visible}")
    
    # Try different approaches
    bars1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 10)
    count1 = len(bars1) if bars1 is not None else "None"
    print(f"  copy_rates_from_pos: {count1}")
    
    now = datetime.now(timezone.utc)
    bars2 = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, now - timedelta(days=7), now)
    count2 = len(bars2) if bars2 is not None else "None"
    print(f"  copy_rates_range (7d): {count2}")
    
    # Try with 50000 after warm-up
    bars3 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 50000)
    count3 = len(bars3) if bars3 is not None else "None"
    print(f"  copy_rates_from_pos (50k): {count3}")
else:
    print(f"Symbol NOT found: {sym}")
    all_syms = mt5.symbols_get()
    ishares = [s.name for s in all_syms if "iShare" in s.name][:10]
    print(f"Available iShares: {ishares}")

mt5.shutdown()
