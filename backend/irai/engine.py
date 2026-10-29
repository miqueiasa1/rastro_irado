"""
IRAI Engine — Cálculo do P_up(t) em tempo real.

Carrega parâmetros calibrados do banco e computa z-scores,
contribuições e probabilidade a cada barra M5.
"""

import sqlite3
import math
import json
import numpy as np
from datetime import datetime, date, timezone, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional

import sys, os
import pandas as pd
import scipy.special as sp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.db import get_connection, DB_PATH, load_kalman_state, save_kalman_state
from backend.irai.kalman import KalmanFilterWrapper
from backend.irai.johansen import check_cointegration
from backend.irai.forex_basket import is_forex_pair, FOREX_28_PAIRS, compute_currency_basket_spread
from backend.timeconv import b3_session_bounds_broker, b3_bars_per_session


# ── Alias de símbolos ─────────────────────────────────────
SYMBOL_ALIASES = {"WIN$N_TOP8": "WIN$N"}

def resolve_symbol(sym: str) -> str:
    """Resolve alias para o símbolo real no banco."""
    return SYMBOL_ALIASES.get(sym, sym)

# Defaults para backward compat
TARGET = "WIN$N"
FACTOR_LABELS = {}  # carregado do DB
BARS_PER_SESSION = 108

# Normaliza??o temporal do z-score dos fatores.
# False (padr?o): z = ret / ?_sess?o. Coerente com a calibra??o (log?stica ajustada sobre o retorno do
#   preg?o inteiro): sob martingale, o retorno parcial ? a melhor estimativa do retorno final.
#   ? tamb?m o comportamento efetivo que o sistema sempre teve (o t_frac antigo saturava em 1.0
#   por contar as barras de warm-up).
# True: z = ret / (???t). Padroniza o retorno parcial, mas explode nos primeiros minutos da sess?o
#   (P(?) satura em 0/100 logo ap?s a abertura). S? ativar junto com uma recalibra??o que use o mesmo crit?rio.
Z_TIME_SCALING = False

# Piso de volatilidade dos res?duos de par/cesta, em % (res?duos em %): 0,01% = 1 bp.
# Evita z explosivo com mercado parado sem anular o sinal (o res?duo da cesta cambial ? ~0,01?0,03%).
MIN_RESIDUAL_SIGMA_PCT = 0.01


@dataclass
class FactorState:
    symbol: str
    label: str
    open_price: float = 0.0
    current_price: float = 0.0
    ret: float = 0.0
    z_score: float = 0.0
    contribution: float = 0.0
    weight: float = 0.0
    sigma: float = 0.0
    last_update: Optional[str] = None
    stale: bool = False


@dataclass
class IRAISnapshot:
    timestamp: str
    session_date: str
    bar_idx: int
    t_frac: float
    p_up: float
    score: float
    verdict: str
    verdict_color: str
    factors: dict = field(default_factory=dict)
    win_return: float = 0.0
    win_open: float = 0.0
    win_bar_open: float = 0.0
    win_high: float = 0.0
    win_low: float = 0.0
    win_current: float = 0.0
    stale_factors: list = field(default_factory=list)
    # Cumulative Delta
    bar_delta: float = 0.0
    cum_delta: float = 0.0
    cum_delta_norm: float = 0.0       # normalizado pelo volume médio
    flow_confirms: Optional[bool] = None  # True=confirma, False=diverge, None=neutro
    price_diverges: bool = False
    price_diverge_z: Optional[float] = None
    price_diverge_basket_z: Optional[float] = None  # Modo 1: Resíduo de Cesta (Pair Trading Basket)
    price_diverge_probit_z: Optional[float] = None  # Modo 2: Probit Normalizado (P_up vs Retorno Z)
    is_preview: bool = False  # True = preview pré-abertura (sem dados do target)
    is_pre_market: bool = False  # True = barra anterior à abertura da sessão do alvo (Regra 4)
    johansen_p_value: float = 1.0
    is_cointegrated: bool = True
    
    # Pairwise Signal (Dinâmico)
    pair_z: Optional[float] = None
    pair_factor: Optional[str] = None
    pair_beta: Optional[float] = None
    pair_signal: Optional[str] = None

    # Par Fixo (Z-SCORE WDO no Índice, Z-SCORE WIN no Dólar)
    pair_fixed_z: Optional[float] = None
    pair_fixed_factor: Optional[str] = None
    pair_fixed_beta: Optional[float] = None
    pair_fixed_signal: Optional[str] = None


def sigmoid(x: float) -> float:
    """Logistic sigmoid, numericamente estável."""
    if x >= 0:
        return 1.0 / (1.0 + np.exp(-x))
    else:
        ex = np.exp(x)
        return ex / (1.0 + ex)


class IRAIEngine:
    """Motor de cálculo do IRAI — suporta N targets via DB."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        # Modelo por slug: {slug: {weights, sigmas, alpha, intercept, factors, labels, session_h}}
        self.models: dict[str, dict] = {}
        # Target → slug mapping
        self.target_slugs: dict[str, str] = {}
        # All registered targets
        self.registered_targets: list[dict] = []

        self.session_opens: dict[str, float] = {}
        self.factor_states: dict[str, FactorState] = {}
        self.alpha: float = 1.0
        self.intercept: float = 0.0
        self._load_params()

    def _load_params(self):
        """Carrega configs de asset_models + params de model_params."""
        conn = get_connection(self.db_path)

        self.registered_targets = []

        # 1) Carregar asset_models
        try:
            rows = conn.execute(
                "SELECT target, slug, display_name, icon, factors, factor_labels, "
                "session_start_h, session_end_h, data_proxy, accuracy, r_squared, active, divergence_config "
                "FROM asset_models WHERE active=1 ORDER BY target"
            ).fetchall()
        except Exception:
            rows = []

        for row in rows:
            target = row["target"]
            slug = row["slug"]
            factors = json.loads(row["factors"]) if row["factors"] else []
            factor_labels = json.loads(row["factor_labels"]) if row["factor_labels"] else {}
            divergence_config = json.loads(row["divergence_config"]) if row["divergence_config"] else {"sigma": 0.005, "threshold": 2.0}
            
            self.target_slugs[target] = slug
            self.registered_targets.append({
                "target": target, "slug": slug,
                "display_name": row["display_name"], "icon": row["icon"],
                "factors": factors, "factor_labels": factor_labels,
                "session_start_h": row["session_start_h"] or 0,
                "session_end_h": row["session_end_h"] or 24,
                "data_proxy": row["data_proxy"],
                "accuracy": row["accuracy"], "r_squared": row["r_squared"],
                "divergence_config": divergence_config,
            })

            # Determinar prefixo dos params
            prefix = f"{slug}_"

            # 2) Carregar model_params para este slug
            # Usar MAX(effective_from) POR param_name para pegar a versão mais recente
            # de cada parâmetro individualmente (evita bug onde calibrações de outros
            # assets com mesmo prefixo sobrescrevem os params corretos).
            params_cursor = conn.execute("""
                SELECT mp.param_name, mp.value FROM model_params mp
                INNER JOIN (
                    SELECT param_name, MAX(effective_from) as max_eff
                    FROM model_params
                    WHERE param_name LIKE ?
                    GROUP BY param_name
                ) latest ON mp.param_name = latest.param_name
                         AND mp.effective_from = latest.max_eff
                WHERE mp.param_name LIKE ?
            """, (f"{prefix}%", f"{prefix}%"))

            weights, sigmas = {}, {}
            alpha, intercept = 1.0, 0.0

            for p in params_cursor:
                name = p["param_name"]
                value = p["value"]
                # Strip prefix
                clean = name[len(prefix):] if prefix and name.startswith(prefix) else name
                if clean.startswith("w_"):
                    weights[clean] = value
                elif clean.startswith("sigma_"):
                    label = clean.replace("sigma_", "").replace("_session", "").replace("_daily", "")
                    sigmas[label] = value
                elif clean == "alpha":
                    alpha = value
                elif clean == "intercept":
                    intercept = value

            self.models[slug] = {
                "weights": weights, "sigmas": sigmas,
                "alpha": alpha, "intercept": intercept,
                "factors": factors, "factor_labels": factor_labels,
                "prefix": prefix,
                "session_start_h": row["session_start_h"] or 0,
                "session_end_h": row["session_end_h"] or 24,
                "data_proxy": row["data_proxy"],
                "divergence_config": divergence_config,
            }

        conn.close()

        # Backward compat: set default FACTOR_LABELS from WIN model
        global FACTOR_LABELS
        if "win" in self.models:
            FACTOR_LABELS = self.models["win"]["factor_labels"]

    def _get_model_config(self, target: str):
        """Retorna weights, sigmas, alpha, intercept, cfg para o target."""
        slug = self.target_slugs.get(target)
        if slug and slug in self.models:
            m = self.models[slug]
            return m["weights"], m["sigmas"], m["alpha"], m["intercept"], {
                "factors": m["factors"],
                "labels": m["factor_labels"],
                "param_prefix": m["prefix"],
                "session_start_h": m["session_start_h"],
                "session_end_h": m["session_end_h"],
                "data_proxy": m["data_proxy"],
                "divergence_config": m["divergence_config"],
                "use_johansen": m["divergence_config"].get("use_johansen", True),
            }
        # Fallback WIN
        if "win" in self.models:
            m = self.models["win"]
            return m["weights"], m["sigmas"], m["alpha"], m["intercept"], {
                "factors": m["factors"], "labels": m["factor_labels"],
                "param_prefix": "", "session_start_h": 12, "session_end_h": 21,
                "data_proxy": None,
                "divergence_config": m.get("divergence_config", {"sigma": 0.009, "threshold": 2.0}),
                "use_johansen": m.get("divergence_config", {}).get("use_johansen", True),
            }
        return {}, {}, 1.0, 0.0, {"factors": [], "labels": {}, "param_prefix": "",
                                    "session_start_h": 0, "session_end_h": 24, "data_proxy": None, "divergence_config": {"sigma": 0.005, "threshold": 2.0}, "use_johansen": True}

    def set_session_opens(self, opens: dict[str, float], factor_states: dict = None):
        """Define preços de abertura da sessão."""
        fs = factor_states if factor_states is not None else self.factor_states
        self.session_opens = opens
        for label, state in fs.items():
            # Resolver alias de símbolos (atualmente vazio — WDO$N tem barras próprias)
            db_sym = resolve_symbol(state.symbol)
            if db_sym in opens and opens[db_sym] > 0:
                state.open_price = opens[db_sym]
            elif state.symbol in opens and opens[state.symbol] > 0:
                state.open_price = opens[state.symbol]

    def update_price(self, symbol: str, price: float, timestamp: str = None, factor_states: dict = None):
        """Atualiza o preço corrente de um fator."""
        fs = factor_states if factor_states is not None else self.factor_states
        # Procurar nos factor_states pelo símbolo lógico
        for label, state in fs.items():
            if state.symbol == symbol:
                state.current_price = price
                state.last_update = timestamp or datetime.now().isoformat()
                state.stale = False
                return

    def compute(self, bar_idx: int, win_current: float = 0, win_open: float = 0,
                win_bar_open: float = None, win_high: float = None, win_low: float = None,
                session_date: str = None, stale_threshold_sec: int = 600,
                bars_per_session: int = BARS_PER_SESSION, factor_states: dict = None,
                alpha: float = None, intercept: float = None,
                is_cointegrated: bool = True, johansen_p_value: float = 1.0) -> IRAISnapshot:
        """
        Computa P_up(t) para a barra corrente.

        Args:
            bar_idx: Índice da barra na sessão (0..95)
            win_current: Preço corrente do WIN
            win_open: Preço de abertura do WIN
            session_date: Data da sessão (YYYY-MM-DD)
            stale_threshold_sec: Segundos para considerar um fator stale
            bars_per_session: Quantidade de barras na sessão (default: 108)
            factor_states: Dicionário local opcional de factor_states
            alpha: Alpha local opcional
            intercept: Intercept local opcional
        """
        t_frac = (bar_idx + 1) / bars_per_session
        if t_frac > 1.0:
            t_frac = 1.0
        
        sqrt_t = np.sqrt(t_frac) if Z_TIME_SCALING else 1.0
        now_str = datetime.now().isoformat()
        session_date = session_date or date.today().isoformat()

        # Computar z-scores e contribuições
        score = 0.0
        stale_factors = []
        
        fs = factor_states if factor_states is not None else self.factor_states
        a = alpha if alpha is not None else self.alpha
        i_cept = intercept if intercept is not None else self.intercept

        for label, state in fs.items():
            # Retorno desde open
            if state.open_price > 0 and state.current_price > 0:
                state.ret = (state.current_price - state.open_price) / state.open_price
            else:
                state.ret = 0.0
                state.stale = True

            # Z-score normalizado por tempo
            if state.sigma > 0:
                state.z_score = state.ret / (state.sigma * sqrt_t)
            else:
                state.z_score = 0.0

            # Contribuição
            state.contribution = state.weight * state.z_score
            score += state.contribution

            # Check stale
            if state.stale:
                stale_factors.append(label)

        # P_up via sigmoid
        p_up = sigmoid(a * score + i_cept) * 100.0

        # WIN return
        win_return = 0.0
        if win_open > 0 and win_current > 0:
            win_return = (win_current - win_open) / win_open * 100.0

        # Verdict
        if p_up > 65:
            verdict, verdict_color = "RISK-ON", "#6FB38A"
        elif p_up < 35:
            verdict, verdict_color = "RISK-OFF", "#C25C5C"
        elif p_up > 55:
            verdict, verdict_color = "levemente comprador", "#6FB38A"
        elif p_up < 45:
            verdict, verdict_color = "levemente vendedor", "#C25C5C"
        else:
            verdict, verdict_color = "indeciso", "#7A7F8A"

        # Guardrail Johansen
        if not is_cointegrated:
            # Em vez de forçar p_up = 50.0 (o que causa quedas verticais agressivas no gráfico),
            # apenas marcamos o veredito como indeciso, mas deixamos o P(↑) fluir matematicamente.
            verdict, verdict_color = "indeciso (Sem Coint)", "#7A7F8A"

        return IRAISnapshot(
            timestamp=now_str,
            session_date=session_date,
            bar_idx=bar_idx,
            t_frac=t_frac,
            p_up=round(p_up, 2),
            score=round(score, 4),
            verdict=verdict,
            verdict_color=verdict_color,
            johansen_p_value=round(johansen_p_value, 4),
            is_cointegrated=is_cointegrated,

            factors={
                label: {
                    "symbol": state.symbol,
                    "z_score": round(state.z_score, 4),
                    "contribution": round(state.contribution, 4),
                    "ret": round(state.ret * 100, 4),
                    "weight": round(state.weight, 4),
                    "current_price": round(state.current_price, 4),
                    "open_price": round(state.open_price, 4),
                    "stale": state.stale,
                }
                for label, state in fs.items()
            },
            win_return=round(win_return, 4),
            win_open=win_open,
            win_bar_open=win_bar_open if (win_bar_open is not None and win_bar_open > 0) else win_current,
            win_high=win_high if (win_high is not None and win_high > 0) else win_current,
            win_low=win_low if (win_low is not None and win_low > 0) else win_current,
            win_current=win_current,
            stale_factors=stale_factors,
        )

    def compute_from_db(self, session_date: str = None, target: str = None, version: str = "v1", timeframe: str = "M5", persist_state: bool = True) -> list[IRAISnapshot]:
        """Computa série IRAI completa para uma sessão a partir do banco.
        
        Args:
            session_date: Data YYYY-MM-DD
            target: Símbolo alvo (WIN$N, WDO$N). Default: WIN$N
            version: 'v1' para regressão estática, 'v2' para Kalman dinâmico
            timeframe: Timeframe para os dados ('M1', 'M2', 'M5', 'M15', 'M30', 'H1'). Default: M5
        """
        session_date = session_date or date.today().isoformat()
        target = target or TARGET

        # Carregar modelo correto para o target
        t_weights, t_sigmas, t_alpha, t_intercept, cfg = self._get_model_config(target)
        active_factors = cfg["factors"]
        active_labels = cfg["labels"]

        # Setup factor states para este target
        local_factor_states = {}
        for symbol, label in active_labels.items():
            local_factor_states[label] = FactorState(
                symbol=symbol,
                label=label,
                weight=t_weights.get(f"w_{label}", 0.0),
                sigma=t_sigmas.get(label, 0.01),
            )
        
        local_alpha = t_alpha
        local_intercept = t_intercept

        # Resolver aliases: símbolo lógico → símbolo no banco
        data_target = cfg.get("data_proxy") or resolve_symbol(target)
        # Mapear fatores lógicos → símbolos no banco
        factor_to_db = {f: resolve_symbol(f) for f in active_factors}
        db_factors = list(set(factor_to_db.values()))
        # Reverso: DB symbol → fator lógico (para update_price)
        db_to_factor = {v: k for k, v in factor_to_db.items()}

        conn = get_connection(self.db_path)

        # Pegar barras da sessão (usa símbolos do banco)
        is_target_forex = is_forex_pair(target)
        if is_target_forex:
            all_symbols = list(set([data_target] + db_factors + FOREX_28_PAIRS))
        else:
            all_symbols = list(set([data_target] + db_factors))
        placeholders = ",".join(["?"] * len(all_symbols))
        
        # 1. Verificar/carregar barras de hoje
        query_today = f"""
            SELECT symbol, source, timestamp_utc, open, high, low, close, real_volume, delta
            FROM market_bars
            WHERE timeframe = ?
              AND symbol IN ({placeholders})
              AND timestamp_utc >= ? AND timestamp_utc < ?
            ORDER BY timestamp_utc
        """
        # Convenção do banco: relógio do broker (NY+7). Ver backend/timeconv.py.
        is_b3 = cfg.get("session_start_h", 0) != 0
        day_start_utc = datetime.fromisoformat(session_date).replace(tzinfo=timezone.utc)
        end_dt = day_start_utc + timedelta(days=1)
        if is_b3:
            # Pregão B3 definido no relógio de Brasília (09:00–18:30 BRT), convertido p/ broker
            # com offset dinâmico (+6h no verão americano, +5h no inverno).
            b3_open_utc, b3_close_utc = b3_session_bounds_broker(session_date)
            if b3_close_utc + timedelta(minutes=5) > end_dt:
                end_dt = b3_close_utc + timedelta(minutes=5)
        start = day_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        end = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        rows_today = conn.execute(query_today, [timeframe] + all_symbols + [start, end]).fetchall()
        
        if not rows_today:
            conn.close()
            return []

        # 2. Carregar barras de aquecimento (warm-up) das últimas 150 barras antes de hoje por ativo
        rows_warmup = []
        for sym in all_symbols:
            sym_warmup = conn.execute(f"""
                SELECT symbol, source, timestamp_utc, open, high, low, close, real_volume, delta
                FROM market_bars
                WHERE timeframe = ? AND symbol = ? AND timestamp_utc < ?
                ORDER BY timestamp_utc DESC
                LIMIT 150
            """, [timeframe, sym, start]).fetchall()
            rows_warmup.extend(sym_warmup)

        rows_raw = rows_warmup + rows_today
        
        # Load previous Kalman state if valid
        slug = cfg.get("slug", self.target_slugs.get(target, "win"))
        saved_state = load_kalman_state(conn, slug, timeframe, session_date, expected_dim=1 + len(active_factors))
        
        conn.close()

        # Detectar sessão via config do modelo (is_b3 já definido acima)
        session_start = cfg.get("session_start_h", 0)

        # Converter sqlite3.Row para dicts com timestamp parsed e hora extraída
        rows = []
        for r in rows_raw:
            d = dict(r)
            ts_str = d["timestamp_utc"]
            ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            d["timestamp"] = ts_dt
            d["hour"] = d["timestamp"].hour
            rows.append(d)

        # Detectar sessão via config do modelo
        session_start = cfg.get("session_start_h", 0)
        session_end = cfg.get("session_end_h", 24)

        duration_h = session_end - session_start
        if duration_h <= 0:
            duration_h += 24
        
        bars_per_hour = 12
        if timeframe == "M1":
            bars_per_hour = 60
        elif timeframe == "M2":
            bars_per_hour = 30
        elif timeframe == "M5":
            bars_per_hour = 12
        elif timeframe == "M15":
            bars_per_hour = 4
        elif timeframe == "M30":
            bars_per_hour = 2
        elif timeframe == "H1":
            bars_per_hour = 1

        target_bars_per_session = int(duration_h * bars_per_hour)
        if is_b3:
            # Pregão regular B3: 09:00–18:30 BRT (independe do DST americano)
            target_bars_per_session = b3_bars_per_session(timeframe)
        if target_bars_per_session <= 0:
            target_bars_per_session = BARS_PER_SESSION

        target_rows = [r for r in rows if r["symbol"] == data_target]
        is_preview_mode = len(target_rows) == 0

        if is_preview_mode:
            # ── Preview pré-abertura ──────────────────────────────────────
            conn2 = get_connection(self.db_path)
            last_row = conn2.execute("""
                SELECT close FROM market_bars
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp_utc DESC LIMIT 1
            """, (data_target, timeframe)).fetchone()
            conn2.close()

            if not last_row:
                return []

            target_last_close = float(last_row["close"])

            factor_rows = [r for r in rows if r["symbol"] in db_factors]
            if not factor_rows:
                return []

            all_timestamps = sorted(set(r["timestamp"] for r in factor_rows))

            opens = {}
            for sym in db_factors:
                sym_bars = sorted([r for r in rows if r["symbol"] == sym], key=lambda r: r["timestamp"])
                if sym_bars:
                    opens[sym] = float(sym_bars[0]["open"])
            opens[data_target] = target_last_close

            self.set_session_opens(opens, factor_states=local_factor_states)

            factor_prices = {}
            for factor in active_factors:
                db_sym = factor_to_db.get(factor, factor)
                fb = sorted([r for r in rows if r["symbol"] == db_sym], key=lambda r: r["timestamp"])
                factor_prices[factor] = [(r["timestamp"], float(r["close"])) for r in fb] if fb else []

            factor_cursors = {f: 0 for f in active_factors}
            snapshots = []

            for bar_idx, ts in enumerate(all_timestamps):
                for factor in active_factors:
                    prices = factor_prices[factor]
                    cursor = factor_cursors[factor]
                    while cursor < len(prices) - 1 and prices[cursor + 1][0] <= ts:
                        cursor += 1
                    factor_cursors[factor] = cursor
                    if cursor < len(prices) and prices[cursor][0] <= ts:
                        self.update_price(factor, prices[cursor][1], ts.isoformat() if hasattr(ts, 'isoformat') else str(ts), factor_states=local_factor_states)

                snap = self.compute(
                    bar_idx=bar_idx,
                    win_current=target_last_close,
                    win_open=target_last_close,
                    session_date=session_date,
                    bars_per_session=target_bars_per_session,
                    factor_states=local_factor_states,
                    alpha=local_alpha,
                    intercept=local_intercept,
                )
                snap.win_bar_open = target_last_close
                snap.win_high = target_last_close
                snap.win_low = target_last_close
                snap.timestamp = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
                snap.is_preview = True
                snap.is_ghost = True
                snap.flow_confirms = None
                snapshots.append(snap)

            return snapshots

        # ── Modo normal (target tem barras) ───────────────────────────────
        # Filter by session removed to allow 24/7 continuous timeline

        # Opens = primeira barra de cada símbolo da sessão atual (hoje)
        # day_start_utc = 00:00 do broker (início do dia para fatores e ativos globais)
        # target_session_open_utc = início da sessão do TARGET:
        #   - B3: 09:00 BRT convertido (o after-market de ontem, 18:00–18:30 BRT, cai após 00:00 do
        #     broker e NÃO pode virar a "abertura de hoje" — Regra 4 / Zero-Repainting)
        #   - Globais: 00:00 do broker
        session_start_utc = day_start_utc
        target_session_open_utc = b3_open_utc if is_b3 else day_start_utc
        # Para alvos B3 a calibração (scripts/calibrate_universal.py) mede o retorno dos FATORES na
        # mesma janela do pregão B3. O motor online precisa usar a mesma base: open dos fatores =
        # primeira barra a partir da abertura da B3. Para alvos globais, a base é 00:00 do broker.
        factor_session_start_utc = target_session_open_utc if is_b3 else session_start_utc
        opens = {}
        # Primeira barra de sessão de cada símbolo. Antes dela o símbolo "ainda não abriu":
        # retorno = 0 (Regra 4 — evita que o forward-fill do fechamento de ontem gere ret = −gap).
        first_session_ts = {}
        for sym in all_symbols:
            sym_session_start = target_session_open_utc if sym == data_target else factor_session_start_utc
            session_bars = sorted([r for r in rows if r["symbol"] == sym and r["timestamp"] >= sym_session_start], key=lambda r: r["timestamp"])
            if session_bars:
                opens[sym] = float(session_bars[0]["open"])
                first_session_ts[sym] = session_bars[0]["timestamp"]
            else:
                # Se o ativo AINDA NÃO ABRIU na sessão atual (sem barras hoje):
                # Usar o último fechamento conhecido como abertura de referência.
                # Isso garante ret = 0.0, z_score = 0.0 e impede repainting/distorções antes da abertura oficial.
                sym_bars = sorted([r for r in rows if r["symbol"] == sym and r["timestamp"] < sym_session_start], key=lambda r: r["timestamp"])
                if sym_bars:
                    opens[sym] = float(sym_bars[-1]["close"])

        if data_target not in opens:
            return []

        self.set_session_opens(opens, factor_states=local_factor_states)

        # Pré-indexar preços dos fatores por timestamp (O(n) em vez de O(n²))
        factor_prices = {}
        for factor in active_factors:
            db_sym = factor_to_db.get(factor, factor)
            fb = sorted([r for r in rows if r["symbol"] == db_sym], key=lambda r: r["timestamp"])
            factor_prices[factor] = [(r["timestamp"], float(r["close"])) for r in fb] if fb else []

        # Pré-indexar preços de forex para o cálculo de Cesta Cambial (Forex Basket Spread)
        forex_pair_prices = {}
        if is_target_forex:
            for f_sym in FOREX_28_PAIRS:
                fb = sorted([r for r in rows if r["symbol"] == f_sym], key=lambda r: r["timestamp"])
                forex_pair_prices[f_sym] = [(r["timestamp"], float(r["close"])) for r in fb] if fb else []
        forex_cursors = {f_sym: 0 for f_sym in FOREX_28_PAIRS}
        recent_forex_basket_spreads = []

        # Iterar sobre barras do target e alinhar com todas as timestamps para forward-fill
        target_bars = sorted([r for r in rows if r["symbol"] == data_target], key=lambda r: r["timestamp"])
        all_timestamps = sorted(set(r["timestamp"] for r in rows))
        n_bars = len(all_timestamps)
        snapshots = []
        cum_delta = 0.0
        cum_real_vol = 0.0
        session_volume_bars = 0
        target_cursor = 0
        tf_seconds = {"M1": 60, "M2": 120, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600}.get(timeframe, 300)
        
        # --- Kalman Filter Setup ---
        kf = None
        if version in ("v2", "both"):
            n_dim_state = 1 + len(active_factors) # Intercept + Factors
            initial_state_mean = np.zeros(n_dim_state)
            initial_state_mean[0] = local_intercept
            for i, factor in enumerate(active_factors):
                label = active_labels.get(factor, factor)
                initial_state_mean[i+1] = t_weights.get(f"w_{label}", 0.0)
                
            trans_cov = float(t_sigmas.get("kalman_trans_cov", 1e-5))
            obs_cov = float(t_sigmas.get("kalman_obs_cov", 1e-3))
            
            kf = KalmanFilterWrapper(
                n_dim_state=n_dim_state,
                n_dim_obs=1,
                transition_covariance=trans_cov,
                observation_covariance=obs_cov,
                initial_state_mean=initial_state_mean
            )
            
            if saved_state:
                if len(saved_state["state_mean"]) == n_dim_state:
                    clean_mean = np.array(saved_state["state_mean"])
                    for i, factor in enumerate(active_factors):
                        label = active_labels.get(factor, factor)
                        sw = t_weights.get(f"w_{label}", 0.0)
                        if sw < 0:
                            clean_mean[i+1] = np.clip(clean_mean[i+1], 3.0 * sw, 0.0)
                        elif sw > 0:
                            clean_mean[i+1] = np.clip(clean_mean[i+1], 0.0, 3.0 * sw)
                    kf.set_state(clean_mean, saved_state["state_covariance"])
                    # Inicializar pesos locais com o estado dinâmico sanitizado do Kalman
                    for i, factor in enumerate(active_factors):
                        label = active_labels.get(factor, factor)
                        local_factor_states[label].weight = clean_mean[i+1]
                else:
                    print(f"[Kalman Warning] Discarding saved state for {slug} due to dimension mismatch ({len(saved_state['state_mean'])} != {n_dim_state})")
        
        
        # --- Johansen Setup ---
        johansen_lookback = int(t_sigmas.get("johansen_lookback", 50))
        price_history = []

        factor_cursors = {f: 0 for f in active_factors}

        div_cfg = cfg.get("divergence_config", {"sigma": 0.005, "threshold": 2.0})
        use_johansen = cfg.get("use_johansen", True)
        target_div_sigma = div_cfg.get("sigma", 0.005)
        target_div_threshold = div_cfg.get("threshold", 2.0)
        
        pair_sigma_fallback = div_cfg.get("pair_sigma", 0.005)
        pair_threshold = div_cfg.get("pair_threshold", 2.0)
        
        cum_basket_residual = 0.0
        cum_pair_residual = 0.0
        recent_basket_spreads = []
        recent_pair_spreads = []
        factor_spread_history = { f_key: [] for f_key in active_factors }
        recent_fixed_pair_spreads = []
        factor_activity_window = { f_key: [] for f_key in active_factors }

        # Set de timestamps reais do target para detecção precisa de ghost bars
        target_ts_set = set(r["timestamp"] for r in target_bars)

        # Último preço conhecido do target ANTES da abertura da sessão (inclui after-market de ontem)
        pre_session_bars = [r for r in target_bars if r["timestamp"] < target_session_open_utc]
        if pre_session_bars:
            pre_market_close = float(pre_session_bars[-1]["close"])
        else:
            conn_prev = get_connection(self.db_path)
            prev_close_row = conn_prev.execute("""
                SELECT close FROM market_bars
                WHERE symbol = ? AND timeframe = ? AND timestamp_utc < ?
                ORDER BY timestamp_utc DESC LIMIT 1
            """, (data_target, timeframe, target_session_open_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))).fetchone()
            conn_prev.close()
            pre_market_close = float(prev_close_row["close"]) if prev_close_row else opens.get(data_target, 0)
        pre_market_open = pre_market_close  # Open = last known close for ghost bars

        for bar_idx, ts in enumerate(all_timestamps):
            while target_cursor < len(target_bars) - 1 and target_bars[target_cursor + 1]["timestamp"] <= ts:
                target_cursor += 1
                
            # Pré-sessão: B3 antes das 09:00 BRT; globais antes das 00:00 do broker (= barras de warm-up).
            # Em pré-sessão: retorno do alvo = 0, Kalman NÃO é atualizado e os históricos de resíduo
            # não são alimentados (A1 — antes o warm-up de ontem era reaplicado contra o open de HOJE).
            is_pre_market = (ts < target_session_open_utc)
            # Índice da barra DENTRO da sessão (relógio), base do t_frac = √t (C6 — antes contava o warm-up)
            session_bar_idx = int((ts - target_session_open_utc).total_seconds() // tf_seconds)
            
            if target_cursor < len(target_bars) and target_bars[target_cursor]["timestamp"] <= ts:
                row = target_bars[target_cursor]
                is_ghost_bar = (ts not in target_ts_set)
            else:
                # Pré-mercado: target ainda não tem barras para este timestamp
                # Criar barra sintética com o último close conhecido
                row = {"close": pre_market_close, "open": pre_market_open, "delta": 0, "real_volume": 0, "timestamp": ts}
                is_ghost_bar = True

            for factor in active_factors:
                prices = factor_prices[factor]
                cursor = factor_cursors[factor]
                while cursor < len(prices) - 1 and prices[cursor + 1][0] <= ts:
                    cursor += 1
                factor_cursors[factor] = cursor
                if cursor < len(prices) and prices[cursor][0] <= ts:
                    self.update_price(factor, prices[cursor][1], ts.isoformat(), factor_states=local_factor_states)
                f_first = first_session_ts.get(factor_to_db.get(factor, factor))
                if f_first is None or ts < f_first:
                    # Fator ainda não negociou na sessão: preço = open de referência → ret 0
                    f_state = local_factor_states.get(active_labels.get(factor, factor))
                    if f_state is not None and f_state.open_price > 0:
                        f_state.current_price = f_state.open_price

            # Atualizar preços e retornos de todos os pares Forex para o cálculo de Cesta Cambial
            current_forex_rets = {}
            if is_target_forex:
                for f_sym, p_list in forex_pair_prices.items():
                    if not p_list:
                        continue
                    cursor = forex_cursors[f_sym]
                    while cursor < len(p_list) - 1 and p_list[cursor + 1][0] <= ts:
                        cursor += 1
                    forex_cursors[f_sym] = cursor
                    f_first = first_session_ts.get(f_sym)
                    if cursor < len(p_list) and p_list[cursor][0] <= ts and f_first is not None and ts >= f_first:
                        f_close = p_list[cursor][1]
                        f_open = opens.get(f_sym, 0.0)
                        if f_open > 0:
                            # Em % (mesma unidade de win_ret) — A2: antes ia em fração e a cesta era ignorada
                            current_forex_rets[f_sym] = (f_close - f_open) / f_open * 100.0

            is_coint = True
            p_val = 0.01

            if version in ("v2", "both"):
                # Preparar dados para Johansen (Preços)
                if use_johansen:
                    basket_prices = {"target": float(row["close"])}
                    for factor in active_factors:
                        label = active_labels.get(factor, factor)
                        basket_prices[label] = local_factor_states[label].current_price
                    price_history.append(basket_prices)
                    
                    if len(price_history) > johansen_lookback:
                        price_history.pop(0)
                        
                    if len(price_history) >= 20 and bar_idx == len(all_timestamps) - 1:
                        df_basket = pd.DataFrame(price_history)
                        p_val, is_coint = check_cointegration(df_basket)
                
                # Preparar dados para Kalman (Retornos em Porcentagem)
                win_ret = 0.0
                if opens[data_target] > 0 and not is_pre_market:
                    win_ret = ((float(row["close"]) - opens[data_target]) / opens[data_target]) * 100.0
                
                obs_matrix = [1.0] # Intercept
                for factor in active_factors:
                    label = active_labels.get(factor, factor)
                    state = local_factor_states[label]
                    f_ret = 0.0
                    if state.open_price > 0 and state.current_price > 0:
                        f_ret = ((state.current_price - state.open_price) / state.open_price) * 100.0
                    obs_matrix.append(f_ret)
                    
                    # Rastrear atividade recente do fator para filtragem de mercado aberto
                    f_wins = factor_activity_window.setdefault(factor, [])
                    f_wins.append(f_ret)
                    if len(f_wins) > 20:
                        f_wins.pop(0)
                    
                # Capture PRIOR betas (before observation update) for innovation residual calculation
                prior_betas, _ = kf.get_state()

                # Update Kalman ONLY if the target market is actually trading
                if not is_ghost_bar and not is_pre_market:
                    kf.update(observation=win_ret, observation_matrix=np.array([obs_matrix]))
                    current_betas, _ = kf.get_state()
                    
                    # Update local weights based on Kalman
                    # NOTE: We deliberately do NOT update local_intercept here.
                    # current_betas[0] is a linear return intercept (usually ~0),
                    # whereas local_intercept is a logistic regression intercept used in sigmoid().
                    for i, factor in enumerate(active_factors):
                        label = active_labels.get(factor, factor)
                        # Camada 1: Weight Clamping com preservação de sinal econômico
                        static_weight = t_weights.get(f"w_{label}", 0.0)
                        if static_weight < 0:
                            clamped = float(np.clip(current_betas[i+1], 3.0 * static_weight, 0.0))
                        elif static_weight > 0:
                            clamped = float(np.clip(current_betas[i+1], 0.0, 3.0 * static_weight))
                        else:
                            clamped = float(np.clip(current_betas[i+1], -0.5, 0.5))
                        local_factor_states[label].weight = clamped
                        current_betas[i+1] = clamped
            else:
                # V1: Garantir que os pesos sejam os estáticos (default setup at the start)
                pass

            snap = self.compute(
                bar_idx=max(session_bar_idx, 0),
                win_current=float(row["close"]),
                win_bar_open=float(row.get("open", row["close"])),
                win_high=float(row.get("high", row["close"])),
                win_low=float(row.get("low", row["close"])),
                win_open=opens[data_target],
                session_date=session_date,
                bars_per_session=target_bars_per_session,
                factor_states=local_factor_states,
                alpha=local_alpha,
                intercept=local_intercept,
                is_cointegrated=is_coint,
                johansen_p_value=p_val
            )

            # Camada 2: Fallback V2→V1 — se Kalman divergiu demais, usar score estático
            if version in ("v2", "both"):
                v1_score = sum(
                    t_weights.get(f"w_{active_labels.get(f, f)}", 0.0) *
                    local_factor_states[active_labels.get(f, f)].z_score
                    for f in active_factors
                )
                if abs(snap.score - v1_score) > 3.0:
                    p_up_v1 = sigmoid(local_alpha * v1_score + local_intercept) * 100.0
                    snap.p_up = round(p_up_v1, 2)
                    snap.score = round(v1_score, 4)
                    # Recalcular verdict
                    if snap.p_up > 65:
                        snap.verdict, snap.verdict_color = "RISK-ON", "#6FB38A"
                    elif snap.p_up < 35:
                        snap.verdict, snap.verdict_color = "RISK-OFF", "#C25C5C"
                    elif snap.p_up > 55:
                        snap.verdict, snap.verdict_color = "levemente comprador", "#6FB38A"
                    elif snap.p_up < 45:
                        snap.verdict, snap.verdict_color = "levemente vendedor", "#C25C5C"
                    else:
                        snap.verdict, snap.verdict_color = "indeciso", "#7A7F8A"
            snap.win_bar_open = float(row.get("open", row["close"]))
            snap.win_high = float(row.get("high", row["close"]))
            snap.win_low = float(row.get("low", row["close"]))
            snap.timestamp = ts.isoformat()
            snap.is_ghost = is_ghost_bar
            snap.is_pre_market = is_pre_market
            
            if is_pre_market:
                snap.win_return = 0.0

            # Cumulative Delta
            # Delta acumulado zera na abertura da sessão (C6 — antes somava o warm-up de ontem)
            in_session_bar = (not is_ghost_bar) and (not is_pre_market)
            bar_d = float(row.get("delta") or 0) if in_session_bar else 0.0
            rv = float(row.get("real_volume") or 0) if in_session_bar else 0.0
            cum_delta += bar_d
            cum_real_vol += rv
            if in_session_bar:
                session_volume_bars += 1

            snap.bar_delta = round(bar_d, 0)
            snap.cum_delta = round(cum_delta, 0)

            avg_vol = cum_real_vol / session_volume_bars if session_volume_bars > 0 else 0
            if avg_vol > 0:
                snap.cum_delta_norm = round(cum_delta / avg_vol, 3)
            else:
                snap.cum_delta_norm = 0.0

            if snap.p_up > 55 and cum_delta > 0:
                snap.flow_confirms = True
            elif snap.p_up < 45 and cum_delta < 0:
                snap.flow_confirms = True
            elif snap.p_up > 55 and cum_delta < 0:
                snap.flow_confirms = False
            elif snap.p_up < 45 and cum_delta > 0:
                snap.flow_confirms = False
            # Multi-Factor Basket Arbitrage Z-Score & Pairwise Signal (v2 Kalman Only)
            if version in ("v2", "both") and kf is not None and len(active_factors) > 0 and snap.t_frac > 0 and not is_ghost_bar and not is_pre_market:
                # 1. Z-Score Rastro (Cálculo dos 2 Modos: Cesta Multi-Fatorial vs. Probit P_up)
                # Modo A: Cesta Multi-Fatorial (Pair Trading Spread vs Basket Macro Ponderado)
                predicted_macro_ret = sum(prior_betas[idx + 1] * obs_matrix[idx + 1] for idx in range(len(active_factors)))
                residuo_basket = win_ret - predicted_macro_ret
                recent_basket_spreads.append(residuo_basket)
                if len(recent_basket_spreads) > 100:
                    recent_basket_spreads.pop(0)

                if len(recent_basket_spreads) >= 6:
                    past_basket = recent_basket_spreads[:-1]
                    basket_sigma = float(np.std(past_basket))
                    min_basket_sigma = MIN_RESIDUAL_SIGMA_PCT
                    if basket_sigma < min_basket_sigma:
                        basket_sigma = min_basket_sigma
                    basket_z = (residuo_basket - 0.0) / basket_sigma
                    snap.price_diverge_basket_z = round(float(basket_z), 2)
                else:
                    snap.price_diverge_basket_z = None

                # Modo B: Probabilístico / Probit (Z Price Realizado vs Z Macro Probit)
                sqrt_t = (np.sqrt(snap.t_frac) if snap.t_frac > 0 else 1.0) if Z_TIME_SCALING else 1.0
                target_sigma_denom = (target_div_sigma * 100.0 * sqrt_t) if sqrt_t > 0 else 0.1
                if target_sigma_denom < 0.1:
                    target_sigma_denom = 0.1
                win_z_normalized = (win_ret / target_sigma_denom) if target_sigma_denom > 0 else 0.0
                
                p_clamped = max(0.001, min(0.999, snap.p_up / 100.0))
                z_macro = float(sp.ndtri(p_clamped))
                price_div_probit = win_z_normalized - z_macro
                snap.price_diverge_probit_z = round(float(price_div_probit), 2)

                # Por padrão do backend: usa o Resíduo de Cesta se disponível, senão Probit
                snap.price_diverge_z = snap.price_diverge_basket_z if snap.price_diverge_basket_z is not None else snap.price_diverge_probit_z
                snap.price_diverges = bool(abs(snap.price_diverge_z or 0.0) >= 2.0)

                # 2. Pairwise Signal (Forex Basket Spread para moedas, Fator Único Dominante para outros ativos)
                if is_target_forex:
                    basket_res = compute_currency_basket_spread(
                        target=target,
                        target_return=win_ret,
                        current_pair_returns=current_forex_rets,
                        recent_spread_history=recent_forex_basket_spreads,
                        min_sigma=MIN_RESIDUAL_SIGMA_PCT,  # retornos em %
                        threshold=pair_threshold,
                    )
                    snap.pair_z = basket_res["pair_z"]
                    snap.pair_factor = basket_res["pair_factor"]
                    snap.pair_beta = basket_res["pair_beta"]
                    snap.pair_signal = basket_res["pair_signal"]
                else:
                    active_candidate_indices = []
                    for idx, f_key in enumerate(active_factors):
                        recent_f_rets = factor_activity_window.get(f_key, [])
                        # Fator considerado ativo se teve movimentação recente (retorno diferente do valor estático nas últimas 15 barras)
                        if len(recent_f_rets) >= 3 and any(abs(r - recent_f_rets[0]) > 1e-6 for r in recent_f_rets[-15:]):
                            active_candidate_indices.append(idx)

                    if len(active_candidate_indices) == 0:
                        active_candidate_indices = list(range(len(active_factors)))

                    # Rastrear histórico de resíduo de TODOS os fatores individualmente (Isolamento de histórico por par)
                    for idx, f_key in enumerate(active_factors):
                        b_f = prior_betas[idx + 1]
                        r_f = obs_matrix[idx + 1]
                        res_f = win_ret - (b_f * r_f)
                        f_hist = factor_spread_history.setdefault(f_key, [])
                        f_hist.append(res_f)
                        if len(f_hist) > 100:
                            f_hist.pop(0)

                    betas_candidates = [(idx, abs(prior_betas[idx + 1])) for idx in active_candidate_indices]
                    betas_candidates.sort(key=lambda x: x[1], reverse=True)
                    max_idx = betas_candidates[0][0]

                    beta_max = prior_betas[max_idx + 1]
                    f_ret_max = obs_matrix[max_idx + 1]
                    
                    pair_factor_key = active_factors[max_idx]
                    pair_label = active_labels.get(pair_factor_key, pair_factor_key)
                    
                    # Resíduo do Par Dominante utilizando SOMENTE o histórico limpo do fator escolhido
                    recent_pair_spreads = factor_spread_history.get(pair_factor_key, [])
                    residuo = win_ret - (beta_max * f_ret_max)
                        
                    if len(recent_pair_spreads) >= 6:
                        past_pair_spreads = recent_pair_spreads[:-1]
                        pair_sigma = float(np.std(past_pair_spreads))
                        # M5 spread noise floor: 0,1% (resíduos em %)
                        min_pair_sigma = MIN_RESIDUAL_SIGMA_PCT
                        if pair_sigma < min_pair_sigma:
                            pair_sigma = min_pair_sigma
                        
                        residuo_mean = 0.0
                        pair_z = (residuo - residuo_mean) / pair_sigma
                        snap.pair_z = round(float(pair_z), 2)
                    else:
                        pair_z = 0.0
                        snap.pair_z = None
                    snap.pair_factor = pair_label
                    snap.pair_beta = round(float(beta_max), 3)
                    
                    if pair_z is not None:
                        if pair_z < -pair_threshold:
                            snap.pair_signal = "buy"
                        elif pair_z > pair_threshold:
                            snap.pair_signal = "sell"
                        else:
                            snap.pair_signal = None

                # 3. Fixed Pairwise Signal (Z-SCORE WDO no Índice, Z-SCORE WIN no Dólar)
                target_pair_key = None
                if target == "WIN$N":
                    target_pair_key = "WDO$N"
                elif target == "WDO$N":
                    target_pair_key = "WIN$N"

                if target_pair_key and target_pair_key in active_factors:
                    fixed_idx = active_factors.index(target_pair_key)
                    beta_fixed = prior_betas[fixed_idx + 1]
                    f_ret_fixed = obs_matrix[fixed_idx + 1]
                    fixed_label = "WDO" if target_pair_key == "WDO$N" else ("WIN" if target_pair_key == "WIN$N" else active_labels.get(target_pair_key, target_pair_key))
                    
                    residuo_fixed = win_ret - (beta_fixed * f_ret_fixed)
                    recent_fixed_pair_spreads.append(residuo_fixed)
                    if len(recent_fixed_pair_spreads) > 100:
                        recent_fixed_pair_spreads.pop(0)

                    if len(recent_fixed_pair_spreads) >= 6:
                        past_fixed = recent_fixed_pair_spreads[:-1]
                        fixed_sigma = float(np.std(past_fixed))
                        # M5 spread noise floor: 0,1% (resíduos em %)
                        min_pair_sigma = MIN_RESIDUAL_SIGMA_PCT
                        if fixed_sigma < min_pair_sigma:
                            fixed_sigma = min_pair_sigma

                        fixed_mean = 0.0
                        fixed_z = (residuo_fixed - fixed_mean) / fixed_sigma
                        snap.pair_fixed_z = round(float(fixed_z), 2)
                    else:
                        fixed_z = 0.0
                        snap.pair_fixed_z = None
                    snap.pair_fixed_factor = fixed_label
                    snap.pair_fixed_beta = round(float(beta_fixed), 3)

                    if snap.pair_fixed_z is not None:
                        if snap.pair_fixed_z < -pair_threshold:
                            snap.pair_fixed_signal = "buy"
                        elif snap.pair_fixed_z > pair_threshold:
                            snap.pair_fixed_signal = "sell"
                        else:
                            snap.pair_fixed_signal = None
            else:
                # Fallback se V1 ou pré-mercado
                if is_pre_market or is_ghost_bar:
                    snap.price_diverge_z = 0.0
                    snap.price_diverges = False
                elif target_div_sigma > 0:
                    W = 60
                    idx_prev = max(0, target_cursor - W)
                    price_prev = float(target_bars[idx_prev]["close"]) if idx_prev < len(target_bars) else float(row["close"])
                    price_curr = float(row["close"])
                    ret_rolling = ((price_curr - price_prev) / price_prev) * 100.0 if price_prev > 0 else 0.0
                    sigma_w = target_div_sigma * math.sqrt(W / target_bars_per_session)
                    ret_z = (ret_rolling / 100.0) / sigma_w if sigma_w > 0 else 0.0
                    snap.price_diverge_z = round(ret_z, 2)
                    snap.price_diverges = (abs(ret_z) >= 2.0)

            if ts >= session_start_utc:
                snapshots.append(snap)
            
        # Salvar o último estado do Kalman no banco
        if snapshots and version in ("v2", "both") and kf is not None and persist_state:
            last_ts = snapshots[-1].timestamp
            last_p = snapshots[-1].johansen_p_value
            last_coint = snapshots[-1].is_cointegrated
            s_mean, s_cov = kf.get_state()
            conn2 = get_connection(self.db_path)
            save_kalman_state(conn2, slug, timeframe, session_date, s_mean, s_cov, last_p, last_coint, last_ts)
            conn2.close()

        return snapshots


# ── Teste rápido ──────────────────────────────────────────
if __name__ == "__main__":
    engine = IRAIEngine()
    print(f"Params carregados:")
    print(f"  Weights: {engine.weights}")
    print(f"  Sigmas: {engine.sigmas}")
    print(f"  Alpha: {engine.alpha}")
    print(f"  Intercept: {engine.intercept}")

    # Testar com última sessão do banco
    conn = get_connection()
    last_date = conn.execute("""
        SELECT DISTINCT substr(timestamp_utc, 1, 10) as d
        FROM market_bars
        WHERE symbol = 'WIN$N' AND timeframe = 'M5'
        ORDER BY d DESC LIMIT 2
    """).fetchall()
    conn.close()

    if last_date and len(last_date) > 1:
        test_date = last_date[1]["d"]  # penúltimo dia (mais completo)
        print(f"\nComputando sessao {test_date}...")
        snaps = engine.compute_from_db(test_date)
        if snaps:
            print(f"  Barras: {len(snaps)}")
            print(f"  P_up range: {min(s.p_up for s in snaps):.1f}% - {max(s.p_up for s in snaps):.1f}%")
            print(f"  Final: P_up={snaps[-1].p_up:.1f}% | score={snaps[-1].score:.4f} | {snaps[-1].verdict}")
            print(f"  WIN: {snaps[-1].win_open:.0f} -> {snaps[-1].win_current:.0f} ({snaps[-1].win_return:+.2f}%)")
            for label, f in snaps[-1].factors.items():
                print(f"    {label:<8} z={f['z_score']:>+7.3f}  contrib={f['contribution']:>+7.4f}  ret={f['ret']:>+6.3f}%")
