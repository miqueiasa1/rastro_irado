"""
garch_ibov.py
=============
Calcula volatilidade condicional (GARCH) para o IBOV a partir de dados do MT5
e exporta uma serie temporal pronta para uso em dashboards (IRAI), GEX pipeline,
ou como input externo para indicadores em Profit Pro / MT5.

Requisitos:
    pip install MetaTrader5 arch pandas numpy

Uso:
    python garch_ibov.py --symbol IBOV --timeframe D1 --bars 1500 --horizon 5
"""

import argparse
import sys
import os
import json
from datetime import datetime

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from arch import arch_model


# ----------------------------------------------------------------------
# 1. Coleta de dados via MT5
# ----------------------------------------------------------------------
def fetch_ibov_data(symbol: str, timeframe: str, n_bars: int, terminal_path: str = None) -> pd.DataFrame:
    """Puxa OHLC do MT5 para o simbolo informado."""
    if mt5 is None:
        raise RuntimeError(
            "Pacote MetaTrader5 nao encontrado. Instale com: pip install MetaTrader5"
        )

    # Inicializa com o executavel especifico se fornecido
    if terminal_path:
        initialized = mt5.initialize(path=terminal_path, timeout=30000)
    else:
        initialized = mt5.initialize()

    if not initialized:
        raise RuntimeError(f"Falha ao iniciar MT5: {mt5.last_error()}")

    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    tf = tf_map.get(timeframe.upper())
    if tf is None:
        mt5.shutdown()
        raise ValueError(f"Timeframe invalido: {timeframe}. Opcoes: {list(tf_map)}")

    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n_bars)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        raise RuntimeError(
            f"Nenhum dado retornado para '{symbol}'. Verifique se o simbolo "
            "esta disponivel no Market Watch do seu terminal MT5."
        )

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    return df[["open", "high", "low", "close", "tick_volume"]]


# ----------------------------------------------------------------------
# 2. Preparacao dos retornos
# ----------------------------------------------------------------------
def compute_log_returns(df: pd.DataFrame, price_col: str = "close") -> pd.Series:
    """Retornos log em percentual (escala recomendada pela lib arch)."""
    returns = np.log(df[price_col] / df[price_col].shift(1)).dropna() * 100
    returns.name = "log_return_pct"
    return returns


# ----------------------------------------------------------------------
# 3. Ajuste do modelo GARCH
# ----------------------------------------------------------------------
def fit_garch(
    returns: pd.Series,
    p: int = 1,
    q: int = 1,
    dist: str = "t",
    vol_model: str = "Garch",
):
    """
    Ajusta um modelo GARCH(p,q).

    vol_model: 'Garch' (padrao), 'EGarch' (efeito alavancagem) ou 'Figarch'.
    dist: 't' (t-Student, recomendado p/ IBOV) ou 'skewt' (assimetrica).
    """
    model = arch_model(returns, mean="Constant", vol=vol_model, p=p, q=q, dist=dist)
    res = model.fit(disp="off")
    return res


# ----------------------------------------------------------------------
# 4. Previsao de volatilidade futura
# ----------------------------------------------------------------------
def forecast_volatility(res, horizon: int = 5) -> pd.DataFrame:
    """Retorna a volatilidade condicional prevista (desvio padrao, % ao dia)."""
    fc = res.forecast(horizon=horizon, reindex=False)
    variance = fc.variance.iloc[-1]
    vol_forecast = np.sqrt(variance)
    vol_forecast.index = [f"h+{i+1}" for i in range(horizon)]
    vol_forecast.name = "vol_forecast_pct"
    return vol_forecast.to_frame()


# ----------------------------------------------------------------------
# 5. Serie historica de volatilidade condicional (para plotar no grafico)
# ----------------------------------------------------------------------
def build_conditional_vol_series(res, returns: pd.Series) -> pd.DataFrame:
    """
    Serie historica (in-sample) de volatilidade condicional estimada pelo GARCH.
    Essa e a linha que voce plota junto com o preco (tipo um ATR "inteligente").
    """
    cond_vol = res.conditional_volatility
    out = pd.DataFrame(
        {
            "log_return_pct": returns,
            "garch_cond_vol_pct": cond_vol,
            # anualizada, caso queira comparar com IV das opcoes (252 dias uteis)
            "garch_cond_vol_annualized_pct": cond_vol * np.sqrt(252),
        }
    )
    return out


# ----------------------------------------------------------------------
# 6. Pipeline principal
# ----------------------------------------------------------------------
def run(symbol: str, timeframe: str, n_bars: int, horizon: int, dist: str, vol_model: str, out_csv: str, terminal_path: str):
    print(f"[1/4] Buscando {n_bars} barras de {symbol} ({timeframe}) via MT5...")
    df = fetch_ibov_data(symbol, timeframe, n_bars, terminal_path)

    print("[2/4] Calculando retornos log...")
    returns = compute_log_returns(df)

    print(f"[3/4] Ajustando {vol_model}(1,1) com distribuicao '{dist}'...")
    res = fit_garch(returns, dist=dist, vol_model=vol_model)
    print(res.summary())

    print(f"[4/4] Gerando serie historica + forecast de {horizon} passos...")
    hist = build_conditional_vol_series(res, returns)
    fc = forecast_volatility(res, horizon=horizon)

    # Salva arquivos locais
    hist.to_csv(out_csv)
    fc_path = out_csv.replace(".csv", "_forecast.csv")
    fc.to_csv(fc_path)

    print(f"\nSerie historica salva em: {out_csv}")
    print(f"Forecast salvo em: {fc_path}")
    print("\nUltimos 5 valores de volatilidade condicional:")
    print(hist.tail(5))

    # Persistir no banco de dados SQLite
    try:
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, PROJECT_ROOT)
        from backend.db import get_connection

        # Converter histórico
        hist_data = []
        for idx, row in hist.iterrows():
            hist_data.append({
                "time": idx.strftime("%Y-%m-%d"),
                "log_return_pct": float(row["log_return_pct"]) if not pd.isna(row["log_return_pct"]) else 0.0,
                "garch_cond_vol_pct": float(row["garch_cond_vol_pct"]) if not pd.isna(row["garch_cond_vol_pct"]) else 0.0,
                "garch_cond_vol_annualized_pct": float(row["garch_cond_vol_annualized_pct"]) if not pd.isna(row["garch_cond_vol_annualized_pct"]) else 0.0
            })

        # Converter forecast
        fc_data = []
        for idx, row in fc.iterrows():
            fc_data.append({
                "step": idx,
                "vol_forecast_pct": float(row["vol_forecast_pct"]) if not pd.isna(row["vol_forecast_pct"]) else 0.0
            })

        session_date = datetime.now().strftime("%Y-%m-%d")
        conn = get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO garch_volatility (session_date, symbol, history_json, forecast_json, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (session_date, symbol, json.dumps(hist_data), json.dumps(fc_data)))
        conn.commit()
        conn.close()
        print(f"\n[DB SUCCESS] Persistido GARCH no SQLite para {symbol} na data {session_date}.")
    except Exception as e:
        print(f"\n[DB ERROR] Erro ao persistir no SQLite: {e}")

    return hist, fc, res


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GARCH de volatilidade para o IBOV via MT5")
    parser.add_argument("--symbol", default="IBOV", help="Simbolo no MT5 (ex: IBOV, WINQ25, IND$)")
    parser.add_argument("--timeframe", default="D1", help="M1, M5, M15, H1, H4, D1")
    parser.add_argument("--bars", type=int, default=1500, help="Numero de barras historicas")
    parser.add_argument("--horizon", type=int, default=5, help="Passos a frente para o forecast")
    parser.add_argument("--dist", default="t", choices=["normal", "t", "skewt"], help="Distribuicao dos residuos")
    parser.add_argument("--vol-model", default="Garch", choices=["Garch", "EGarch", "Figarch"], help="Variante do modelo")
    parser.add_argument("--out", default="garch_ibov.csv", help="Caminho do CSV de saida")
    parser.add_argument("--terminal", default=r"C:\Program Files\MetaTrader 5 Terminal\terminal64.exe", help="Caminho do terminal MT5")

    args = parser.parse_args()

    try:
        run(
            symbol=args.symbol,
            timeframe=args.timeframe,
            n_bars=args.bars,
            horizon=args.horizon,
            dist=args.dist,
            vol_model=args.vol_model,
            out_csv=args.out,
            terminal_path=args.terminal,
        )
    except Exception as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)
