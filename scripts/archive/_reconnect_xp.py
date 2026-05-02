import MetaTrader5 as mt5, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import get_connection
from backend.workers.collector import collect_recent_bars

PATH = r"C:\Program Files\MetaTrader 5 Terminal - milhao - Copia\terminal64.exe"
mt5.shutdown()
time.sleep(1)
print(f"Conectando a {PATH} ...")
ok = mt5.initialize(path=PATH, timeout=20000)
if not ok:
    print(f"FALHA: {mt5.last_error()}")
    sys.exit(1)

info = mt5.terminal_info()
print(f"OK! Company: {info.company}, Connected: {info.connected}")

# Habilitar símbolos no Market Watch
for sym in ["WIN$N", "WDO$N", "DI1$N"]:
    si = mt5.symbol_info(sym)
    if si is None:
        print(f"  {sym}: simbolo NAO EXISTE neste terminal")
        continue
    if not si.visible:
        mt5.symbol_select(sym, True)
        print(f"  {sym}: adicionado ao Market Watch")
        time.sleep(0.5)

time.sleep(2)  # Esperar dados chegarem

conn = get_connection()
for sym in ["WIN$N", "WDO$N", "DI1$N"]:
    tick = mt5.symbol_info_tick(sym)
    if tick and tick.bid > 0:
        inserted = collect_recent_bars(sym, "br", conn, n_bars=10)
        print(f"  {sym}: bid={tick.bid:.2f}, +{inserted} barras")
    else:
        # Tentar copiar barras diretamente
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 3)
        if rates is not None and len(rates) > 0:
            print(f"  {sym}: sem tick mas tem {len(rates)} barras, last close={rates[-1][4]:.2f}")
            inserted = collect_recent_bars(sym, "br", conn, n_bars=10)
            print(f"         +{inserted} barras inseridas")
        else:
            print(f"  {sym}: sem dados")
conn.close()
mt5.shutdown()
print("Pronto!")
