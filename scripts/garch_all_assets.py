import sys
import os
import sqlite3
import json
import traceback
from datetime import datetime
import pandas as pd
import numpy as np

# Garante o root no path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Importa as funcoes matematicas de modelagem
from scripts.garch_ibov import (
    compute_log_returns,
    fit_garch,
    build_conditional_vol_series,
    forecast_volatility,
    mt5
)

# Caminho do banco
DB_PATH = os.path.join(PROJECT_ROOT, "data", "irai_live.db")

# Mapeamento de terminais e simbolos
TERMINAL_MAPPING = {
    "br": {
        "paths": [
            r"C:\Program Files\MetaTrader 5\terminal64.exe",
            r"C:\Program Files\MetaTrader 5 Terminal\terminal64.exe",
        ],
        "symbols": ["WIN$N", "WDO$N", "IBOV"]
    },
    "tickmill": {
        "paths": [
            r"C:\Program Files\Tickmill MT5 Terminal\terminal64.exe",
            r"C:\Program Files\Tickmill MT5 Terminal - Copia\terminal64.exe",
            r"C:\Program Files\Tickmill MT5 Terminal - Copia - Copia\terminal64.exe",
        ],
        "symbols": [
            "BTCUSD", "US500", "US30", "USTEC", "XAUUSD",
            "EURUSD", "GBPUSD", "USDJPY"
        ]
    }
}

def fetch_data_with_fallback_terminals(symbol: str, n_bars: int, paths: list) -> pd.DataFrame:
    """Tenta conectar em cada terminal da lista ate conseguir os dados de D1."""
    if mt5 is None:
        raise RuntimeError("MetaTrader5 python package not available.")

    last_error = None
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            print(f"  Conectando ao terminal: {path} ...")
            if mt5.initialize(path=path, timeout=20000):
                # Registra o simbolo no Market Watch
                mt5.symbol_select(symbol, True)
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, n_bars)
                mt5.shutdown()
                
                if rates is not None and len(rates) > 0:
                    df = pd.DataFrame(rates)
                    df["time"] = pd.to_datetime(df["time"], unit="s")
                    df.set_index("time", inplace=True)
                    return df[["open", "high", "low", "close", "tick_volume"]]
                else:
                    last_error = f"Sem taxas/barras D1 retornadas para {symbol}."
            else:
                last_error = f"Erro de inicializacao: {mt5.last_error()}"
        except Exception as e:
            last_error = str(e)
            try:
                mt5.shutdown()
            except:
                pass
    
    raise RuntimeError(f"Impossivel obter dados de {symbol}. Ultimo erro: {last_error}")

def run_garch_for_symbol(symbol: str, paths: list):
    try:
        print(f"\n>>> Calculando GARCH(1,1) para {symbol} ...")
        
        # 1. Obter dados
        df = fetch_data_with_fallback_terminals(symbol, 1500, paths)
        
        # 2. Log-retornos
        returns = compute_log_returns(df)
        
        # 3. Ajustar GARCH
        try:
            res = fit_garch(returns, dist="t")
        except Exception as e:
            print(f"  [GARCH WARN] Falha com t-dist ({e}). Tentando normal...")
            res = fit_garch(returns, dist="normal")
            
        # 4. Previsoes e series
        hist = build_conditional_vol_series(res, returns)
        fc = forecast_volatility(res, horizon=5)
        
        # 5. Formatar JSON
        hist_data = []
        for idx, row in hist.iterrows():
            hist_data.append({
                "time": idx.strftime("%Y-%m-%d"),
                "log_return_pct": float(row["log_return_pct"]) if not pd.isna(row["log_return_pct"]) else 0.0,
                "garch_cond_vol_pct": float(row["garch_cond_vol_pct"]) if not pd.isna(row["garch_cond_vol_pct"]) else 0.0,
                "garch_cond_vol_annualized_pct": float(row["garch_cond_vol_annualized_pct"]) if not pd.isna(row["garch_cond_vol_annualized_pct"]) else 0.0
            })

        fc_data = []
        for idx, row in fc.iterrows():
            fc_data.append({
                "step": idx,
                "vol_forecast_pct": float(row["vol_forecast_pct"]) if not pd.isna(row["vol_forecast_pct"]) else 0.0
            })

        # 6. Salvar SQLite irai_live.db
        session_date = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT OR REPLACE INTO garch_volatility (session_date, symbol, history_json, forecast_json, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (session_date, symbol, json.dumps(hist_data), json.dumps(fc_data)))
        conn.commit()
        conn.close()
        print(f"  [DB SUCCESS] Salvo GARCH de {symbol} para a data {session_date}")
        return True
    except Exception as e:
        print(f"  [GARCH ERROR] {symbol} falhou: {e}")
        return False

def main():
    success_count = 0
    fail_count = 0
    
    all_symbols = []
    for category, config in TERMINAL_MAPPING.items():
        for symbol in config["symbols"]:
            all_symbols.append((symbol, config["paths"]))

    print(f"Calculadora de Volatilidade GARCH para todos os ativos no painel")
    print(f"Total de ativos para processar: {len(all_symbols)}")
    
    for symbol, paths in all_symbols:
        success = run_garch_for_symbol(symbol, paths)
        if success:
            success_count += 1
        else:
            fail_count += 1
            
    print(f"\n==================================================")
    print(f"CONCLUIDO!")
    print(f"Sucessos: {success_count}")
    print(f"Falhas: {fail_count}")
    print(f"==================================================")

if __name__ == "__main__":
    main()
