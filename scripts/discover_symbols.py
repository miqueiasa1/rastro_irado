"""
Descoberta de símbolos nos 3 terminais MT5 para o projeto IRAI.

Conecta sequencialmente a cada terminal (MT5 lib aceita só 1 conexão por processo),
busca símbolos relevantes e gera relatório.

Uso: python scripts/discover_symbols.py
"""

import MetaTrader5 as mt5
import sys
from datetime import datetime

# ── Terminais ──────────────────────────────────────────────
TERMINALS = {
    "BR (MetaTrader 5)": {
        "path": r"C:\Program Files\MetaTrader 5 Terminal\terminal64.exe",
        "keywords": ["IBOV", "WIN", "WINFUT", "BOVA", "IND", "INDFUT", "PETR", "VALE", "B3SA"],
        "role": "Dados Brasil (IBOV, WIN)",
    },
    "IC Trading (INTL)": {
        "path": r"C:\Program Files\IC Trading (MU) MT5 Terminal\terminal64.exe",
        "keywords": ["EWZ", "BRAZ", "BRL", "IBOV"],
        "role": "EWZ (ETF Brasil na NYSE)",
    },
    "Tickmill": {
        "path": r"C:\Program Files\Tickmill MT5 Terminal\terminal64.exe",
        "keywords": ["VIX", "UVIX", "DXY", "USDX", "DX", "US10", "TNX", "TLT", "UST",
                      "US30", "US500", "US100", "USTEC", "SPX", "SPY", "NDX", "NAS",
                      "DOW", "DJ30", "USIDX"],
        "role": "VIX, DXY, US10Y, índices US",
    },
}

# Keywords adicionais para busca ampla
BROAD_KEYWORDS = ["VIX", "DXY", "USDX", "EWZ", "US10", "TNX", "TLT", "IBOV", "WIN",
                   "SPX", "SPY", "NAS", "NDX", "US500", "US100", "US30", "USTEC",
                   "DOW", "DJ30"]


def discover_terminal(name: str, config: dict) -> dict:
    """Conecta a um terminal e busca símbolos relevantes."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  Path: {config['path']}")
    print(f"  Role: {config['role']}")
    print(f"{'='*60}")

    # Inicializar
    if not mt5.initialize(path=config["path"]):
        error = mt5.last_error()
        print(f"  ✗ Falha ao conectar: {error}")
        print(f"  → Verifique se o terminal está aberto e logado.")
        return {"status": "error", "error": str(error), "symbols": []}

    info = mt5.terminal_info()
    if info:
        print(f"  ✓ Conectado: {info.company} | Build {info.build}")
        print(f"  Server: {info.name if hasattr(info, 'name') else 'N/A'}")

    # Buscar todos os símbolos
    all_symbols = mt5.symbols_get()
    if not all_symbols:
        print(f"  ✗ Nenhum símbolo encontrado")
        mt5.shutdown()
        return {"status": "empty", "symbols": []}

    print(f"  Total de símbolos no terminal: {len(all_symbols)}")

    # Filtrar por keywords
    results = []
    seen = set()

    for kw in config["keywords"] + BROAD_KEYWORDS:
        matches = mt5.symbols_get(kw)
        if matches:
            for s in matches:
                if s.name not in seen:
                    seen.add(s.name)
                    # Pegar info de spread e cotação
                    tick = mt5.symbol_info_tick(s.name)
                    has_data = tick is not None and tick.bid > 0

                    results.append({
                        "name": s.name,
                        "description": s.description if hasattr(s, 'description') else "",
                        "path": s.path if hasattr(s, 'path') else "",
                        "currency_base": s.currency_base if hasattr(s, 'currency_base') else "",
                        "spread": s.spread if hasattr(s, 'spread') else 0,
                        "has_live_data": has_data,
                        "bid": tick.bid if tick and tick.bid > 0 else 0,
                        "ask": tick.ask if tick and tick.ask > 0 else 0,
                        "matched_keyword": kw,
                    })

    # Ordenar por nome
    results.sort(key=lambda x: x["name"])

    # Exibir
    if results:
        print(f"\n  Símbolos relevantes encontrados: {len(results)}")
        print(f"  {'─'*56}")
        print(f"  {'Símbolo':<20} {'Descrição':<30} {'Bid':>10} {'Data?'}")
        print(f"  {'─'*56}")
        for r in results:
            data_flag = "✓" if r["has_live_data"] else "✗"
            bid_str = f"{r['bid']:.4f}" if r["bid"] > 0 else "—"
            desc = r["description"][:28] if r["description"] else "—"
            print(f"  {r['name']:<20} {desc:<30} {bid_str:>10} {data_flag}")
    else:
        print(f"\n  Nenhum símbolo relevante encontrado com as keywords.")

    # Verificar barras históricas 5min disponíveis para os principais
    print(f"\n  Verificando profundidade histórica (M5)...")
    for r in results[:15]:  # Limitar a 15 para não demorar
        rates = mt5.copy_rates_from_pos(r["name"], mt5.TIMEFRAME_M5, 0, 1)
        if rates is not None and len(rates) > 0:
            # Tentar puxar 1 ano (~75000 barras M5)
            rates_deep = mt5.copy_rates_from_pos(r["name"], mt5.TIMEFRAME_M5, 0, 75000)
            if rates_deep is not None and len(rates_deep) > 0:
                oldest = datetime.utcfromtimestamp(rates_deep[0][0])
                newest = datetime.utcfromtimestamp(rates_deep[-1][0])
                days_span = (newest - oldest).days
                print(f"    {r['name']:<20} {len(rates_deep):>6} barras M5 | {oldest.strftime('%Y-%m-%d')} → {newest.strftime('%Y-%m-%d')} ({days_span}d)")
            else:
                print(f"    {r['name']:<20} sem histórico M5")
        else:
            print(f"    {r['name']:<20} sem dados M5")

    mt5.shutdown()
    return {"status": "ok", "symbols": results}


def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  IRAI — Descoberta de Símbolos MT5                          ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\nData: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"MetaTrader5 lib version: {mt5.__version__}")

    all_results = {}

    for name, config in TERMINALS.items():
        try:
            result = discover_terminal(name, config)
            all_results[name] = result
        except Exception as e:
            print(f"\n  ✗ Erro inesperado em {name}: {e}")
            all_results[name] = {"status": "error", "error": str(e), "symbols": []}
            try:
                mt5.shutdown()
            except:
                pass

    # ── Resumo ──────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  RESUMO")
    print(f"{'='*60}")

    for name, result in all_results.items():
        status = result["status"]
        count = len(result.get("symbols", []))
        if status == "ok":
            print(f"  ✓ {name}: {count} símbolos relevantes")
        else:
            print(f"  ✗ {name}: {result.get('error', 'falha')}")

    print(f"\n  Próximo passo: usar os nomes exatos acima no .env")
    print(f"  e rodar o script de coleta histórica.")


if __name__ == "__main__":
    main()
