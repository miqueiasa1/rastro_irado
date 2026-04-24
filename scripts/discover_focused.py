"""
Descoberta focada: só os símbolos que importam para o IRAI.
Testa profundidade histórica D1 e M5.
"""

import MetaTrader5 as mt5
import sys, os
from datetime import datetime, timedelta

os.environ["PYTHONIOENCODING"] = "utf-8"

TERMINALS = [
    {
        "name": "BR (MetaTrader 5)",
        "path": r"C:\Program Files\MetaTrader 5 Terminal\terminal64.exe",
        "targets": ["IBOV", "WIN$N", "WIN$", "WINM26", "IND$", "INDFUT", "IBOVESPA"],
    },
    {
        "name": "IC Trading",
        "path": r"C:\Program Files\IC Trading (MU) MT5 Terminal\terminal64.exe",
        "targets": ["EWZ", "EWZ.US", "iShares MSCI Brazil"],
    },
    {
        "name": "Tickmill",
        "path": r"C:\Program Files\Tickmill MT5 Terminal\terminal64.exe",
        "targets": ["VIX", "DXY", "US10Y", "US10", "TNX", "TLT", "US30", "US500", "USTEC", "USDX", "USIDX"],
    },
]


def check_symbol(name, timeframes=None):
    """Verifica um simbolo: bid, profundidade M5 e D1."""
    if timeframes is None:
        timeframes = [
            ("D1", mt5.TIMEFRAME_D1, 500),
            ("M5", mt5.TIMEFRAME_M5, 75000),
        ]

    tick = mt5.symbol_info_tick(name)
    info = mt5.symbol_info(name)
    has_data = tick is not None and tick.bid > 0

    desc = info.description if info and hasattr(info, 'description') else ""
    bid = tick.bid if tick and tick.bid > 0 else 0

    print(f"    {name:<20} desc='{desc[:40]}' bid={bid:.4f} live={'YES' if has_data else 'NO'}")

    for tf_name, tf, count in timeframes:
        rates = mt5.copy_rates_from_pos(name, tf, 0, count)
        if rates is not None and len(rates) > 0:
            oldest = datetime.utcfromtimestamp(rates[0][0])
            newest = datetime.utcfromtimestamp(rates[-1][0])
            days = (newest - oldest).days
            print(f"      {tf_name}: {len(rates)} barras | {oldest.strftime('%Y-%m-%d')} -> {newest.strftime('%Y-%m-%d')} ({days}d)")
        else:
            print(f"      {tf_name}: sem dados")


def main():
    print("IRAI - Descoberta Focada de Simbolos")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    for terminal in TERMINALS:
        print(f"\n--- {terminal['name']} ---")
        print(f"    Path: {terminal['path']}")

        if not mt5.initialize(path=terminal["path"]):
            error = mt5.last_error()
            print(f"    FALHA: {error}")
            print(f"    -> Abra o terminal e logue antes de rodar.")
            continue

        info = mt5.terminal_info()
        if info:
            print(f"    Conectado: {info.company} build {info.build}")

        # Testar cada target
        for target in terminal["targets"]:
            # Tentar buscar exato
            sym = mt5.symbol_info(target)
            if sym:
                check_symbol(target)
            else:
                # Buscar por wildcard
                matches = mt5.symbols_get(target)
                if matches:
                    # Mostrar apenas os 5 primeiros que tem dados
                    shown = 0
                    for s in matches:
                        if shown >= 5:
                            remaining = len(matches) - shown
                            if remaining > 0:
                                print(f"    ... +{remaining} resultados para '{target}'")
                            break
                        tick = mt5.symbol_info_tick(s.name)
                        if tick and tick.bid > 0:
                            check_symbol(s.name)
                            shown += 1
                    if shown == 0:
                        # Mostrar os primeiros 3 mesmo sem dados
                        for s in matches[:3]:
                            check_symbol(s.name)
                else:
                    print(f"    {target:<20} NAO ENCONTRADO")

        mt5.shutdown()

    print("\n" + "=" * 60)
    print("CONCLUIDO")


if __name__ == "__main__":
    main()
