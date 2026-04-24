"""
Descoberta focada v2: confirmar EWZ (IC Trading), DI/DOL (BR), BRENT (Tickmill).
"""
import MetaTrader5 as mt5
import os, sys
from datetime import datetime

os.environ["PYTHONIOENCODING"] = "utf-8"

TERMINALS = [
    {
        "name": "BR (XP)",
        "path": r"C:\Program Files\MetaTrader 5 Terminal\terminal64.exe",
        "targets": ["WIN$N", "DOL$N", "DOL$", "DI1", "DI1F26", "DI1F27", "DI1F28",
                     "DI1$", "DI1$N", "DI1N26", "DI1J26"],
        "search": ["DI1", "DOL"],
    },
    {
        "name": "IC Trading",
        "path": r"C:\Program Files\IC Trading (MU) MT5 Terminal\terminal64.exe",
        "targets": ["EWZ", "EWZ.NYSE", "EWZ_KE", "EWZNYSE", "#EWZ"],
        "search": ["EWZ"],
    },
    {
        "name": "Tickmill",
        "path": r"C:\Program Files\Tickmill MT5 Terminal\terminal64.exe",
        "targets": ["BRENT", "BRNUSD", "XBRUSD", "UKOIL", "BRENT_OIL", "BRENT.OIL", "UKOUSD"],
        "search": ["BRENT", "BRN", "OIL", "UKO", "XBR", "CRUDE"],
    },
]


def check_depth(name):
    """Verifica profundidade M5 e D1 de um simbolo."""
    tick = mt5.symbol_info_tick(name)
    info = mt5.symbol_info(name)
    bid = tick.bid if tick and tick.bid > 0 else 0
    desc = info.description[:45] if info and info.description else ""
    live = "LIVE" if bid > 0 else "no-tick"

    print(f"    {name:<20} {desc:<45} bid={bid:<12.4f} {live}")

    for tf_name, tf, count in [("D1", mt5.TIMEFRAME_D1, 500), ("M5", mt5.TIMEFRAME_M5, 75000)]:
        rates = mt5.copy_rates_from_pos(name, tf, 0, count)
        if rates is not None and len(rates) > 0:
            oldest = datetime.fromtimestamp(rates[0][0], tz=datetime.now().astimezone().tzinfo)
            newest = datetime.fromtimestamp(rates[-1][0], tz=datetime.now().astimezone().tzinfo)
            days = (newest - oldest).days
            print(f"      {tf_name}: {len(rates):>6} barras | {oldest.strftime('%Y-%m-%d')} -> {newest.strftime('%Y-%m-%d')} ({days}d)")
        else:
            print(f"      {tf_name}: sem dados")


def main():
    print("IRAI - Descoberta Focada v2")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    for terminal in TERMINALS:
        print(f"\n{'='*80}")
        print(f"  {terminal['name']}")
        print(f"  Path: {terminal['path']}")
        print(f"{'='*80}")

        if not mt5.initialize(path=terminal["path"]):
            error = mt5.last_error()
            print(f"  FALHA: {error}")
            continue

        info = mt5.terminal_info()
        if info:
            print(f"  Conectado: {info.company} build {info.build}")

        # Busca direta
        print(f"\n  -- Alvos diretos --")
        for target in terminal["targets"]:
            sym = mt5.symbol_info(target)
            if sym:
                check_depth(target)
            else:
                print(f"    {target:<20} NAO ENCONTRADO")

        # Busca por wildcard
        if "search" in terminal:
            print(f"\n  -- Busca ampla --")
            seen = set()
            for kw in terminal["search"]:
                matches = mt5.symbols_get(kw)
                if matches:
                    count = 0
                    for s in matches:
                        if s.name in seen:
                            continue
                        seen.add(s.name)
                        tick = mt5.symbol_info_tick(s.name)
                        has_data = tick is not None and tick.bid > 0
                        desc = s.description[:35] if s.description else ""
                        bid_s = f"{tick.bid:.4f}" if tick and tick.bid > 0 else "---"
                        flag = "LIVE" if has_data else "   "
                        print(f"    {s.name:<20} {desc:<35} {bid_s:>12} {flag}")
                        count += 1
                        if count >= 20:
                            remaining = len(matches) - count
                            if remaining > 0:
                                print(f"    ... +{remaining} mais para '{kw}'")
                            break
                else:
                    print(f"    Nenhum resultado para '{kw}'")

        mt5.shutdown()

    print(f"\n{'='*80}")
    print("CONCLUIDO")


if __name__ == "__main__":
    main()
