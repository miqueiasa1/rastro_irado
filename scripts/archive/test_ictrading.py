"""
Teste de conexao IC Trading - tentar varias abordagens.
"""
import MetaTrader5 as mt5
import os, time
from datetime import datetime

os.environ["PYTHONIOENCODING"] = "utf-8"

TERMINAL_PATH = r"C:\Program Files\IC Trading (MU) MT5 Terminal\terminal64.exe"

print("IRAI - Teste IC Trading")
print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"MT5 lib: {mt5.__version__}")
print("=" * 60)

# Garantir que shutdown anterior esta limpo
try:
    mt5.shutdown()
except:
    pass

time.sleep(2)

print(f"\nTentando conectar: {TERMINAL_PATH}")
result = mt5.initialize(path=TERMINAL_PATH, timeout=30000)
print(f"  initialize() = {result}")

if not result:
    error = mt5.last_error()
    print(f"  Erro: {error}")
    print(f"\n  Tentando sem path (terminal padrao)...")
    result2 = mt5.initialize(timeout=30000)
    print(f"  initialize() = {result2}")
    if result2:
        info = mt5.terminal_info()
        print(f"  Conectou em: {info.company if info else '?'}")
        print(f"  Path: {info.path if info else '?'}")
else:
    info = mt5.terminal_info()
    if info:
        print(f"  Conectado: {info.company} build {info.build}")
        print(f"  Path: {info.path}")
        print(f"  Data folder: {info.data_path}")

# Se conectou (qualquer tentativa), buscar EWZ
if mt5.terminal_info():
    print(f"\n--- Buscando EWZ ---")
    for name in ["EWZ.NYSE", "EWZ", "#EWZ", "EWZ.US", "EWZ_KE"]:
        sym = mt5.symbol_info(name)
        if sym:
            tick = mt5.symbol_info_tick(name)
            bid = tick.bid if tick and tick.bid > 0 else 0
            print(f"  {name:<20} desc='{sym.description[:40]}' bid={bid:.4f}")
            
            # Checar profundidade
            for tf_name, tf, count in [("D1", mt5.TIMEFRAME_D1, 500), ("M5", mt5.TIMEFRAME_M5, 75000)]:
                rates = mt5.copy_rates_from_pos(name, tf, 0, count)
                if rates is not None and len(rates) > 0:
                    oldest = datetime.fromtimestamp(rates[0][0], tz=datetime.now().astimezone().tzinfo)
                    newest = datetime.fromtimestamp(rates[-1][0], tz=datetime.now().astimezone().tzinfo)
                    days = (newest - oldest).days
                    print(f"    {tf_name}: {len(rates):>6} barras | {oldest.strftime('%Y-%m-%d')} -> {newest.strftime('%Y-%m-%d')} ({days}d)")
                else:
                    print(f"    {tf_name}: sem dados")
        else:
            print(f"  {name:<20} NAO ENCONTRADO")

    # Tambem verificar outros simbolos que vi na screenshot
    print(f"\n--- Outros simbolos IC Trading ---")
    for name in ["VIX_KE", "DXY_ME", "US10Y_M6", "XBRUSD", "XTIUSD", "US500", "US30"]:
        sym = mt5.symbol_info(name)
        if sym:
            tick = mt5.symbol_info_tick(name)
            bid = tick.bid if tick and tick.bid > 0 else 0
            print(f"  {name:<20} desc='{sym.description[:40]}' bid={bid:.4f}")
            
            rates = mt5.copy_rates_from_pos(name, mt5.TIMEFRAME_D1, 0, 500)
            if rates is not None and len(rates) > 0:
                oldest = datetime.fromtimestamp(rates[0][0], tz=datetime.now().astimezone().tzinfo)
                newest = datetime.fromtimestamp(rates[-1][0], tz=datetime.now().astimezone().tzinfo)
                days = (newest - oldest).days
                print(f"    D1: {len(rates):>6} barras | {oldest.strftime('%Y-%m-%d')} -> {newest.strftime('%Y-%m-%d')} ({days}d)")
            
            rates5 = mt5.copy_rates_from_pos(name, mt5.TIMEFRAME_M5, 0, 75000)
            if rates5 is not None and len(rates5) > 0:
                oldest = datetime.fromtimestamp(rates5[0][0], tz=datetime.now().astimezone().tzinfo)
                newest = datetime.fromtimestamp(rates5[-1][0], tz=datetime.now().astimezone().tzinfo)
                days = (newest - oldest).days
                print(f"    M5: {len(rates5):>6} barras | {oldest.strftime('%Y-%m-%d')} -> {newest.strftime('%Y-%m-%d')} ({days}d)")
        else:
            print(f"  {name:<20} NAO ENCONTRADO")

mt5.shutdown()
print("\nCONCLUIDO")
