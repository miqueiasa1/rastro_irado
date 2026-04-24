import MetaTrader5 as mt5
from datetime import datetime
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

mt5.initialize(path=r"C:\Program Files\Tickmill MT5 Terminal\terminal64.exe")
print(f"Tickmill: {mt5.terminal_info().company}")

for name in ["BTCUSD", "XBTUSD", "BTC", "BITCOIN"]:
    sym = mt5.symbol_info(name)
    if sym:
        t = mt5.symbol_info_tick(name)
        bid = t.bid if t and t.bid > 0 else 0
        print(f"  {name}: {sym.description} bid={bid:.2f}")
        for tf_n, tf, cnt in [("D1", mt5.TIMEFRAME_D1, 500), ("M5", mt5.TIMEFRAME_M5, 75000)]:
            r = mt5.copy_rates_from_pos(name, tf, 0, cnt)
            if r is not None and len(r) > 0:
                o = datetime.fromtimestamp(r[0][0], tz=datetime.now().astimezone().tzinfo)
                n = datetime.fromtimestamp(r[-1][0], tz=datetime.now().astimezone().tzinfo)
                d = (n - o).days
                print(f"    {tf_n}: {len(r)} barras | {o.strftime('%Y-%m-%d')} -> {n.strftime('%Y-%m-%d')} ({d}d)")
    else:
        print(f"  {name}: nao encontrado")

matches = mt5.symbols_get("BTC")
if matches:
    for s in matches[:10]:
        print(f"  Busca: {s.name} = {s.description}")
else:
    print("  Busca BTC: nenhum resultado")

mt5.shutdown()
