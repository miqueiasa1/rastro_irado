"""
Features causais do Rastro (fase 18, SPEC §4) e valor justo da cesta.

Ideia central (intenção do owner, 10/11/2026): usar a cesta já coletada (DI, dólar, índices
externos, commodities) para estimar onde o preço do alvo DEVERIA estar (valor justo) e comparar
com onde ele ESTÁ. O descolamento (gap) padronizado é a candidata a oportunidade de entrada.

Regras de causalidade (REQ-F02, REQ-N01):
- Tudo no instante da barra k usa só barras com abertura ≤ k da sessão e sessões anteriores.
- Escalas (σ) vêm de sessões ANTERIORES (janela trailing), nunca da amostra inteira (R1).
- Retornos parciais são normalizados por √(k+1) (R2).
- Fator que ainda não negociou na sessão contribui 0; forward-fill máximo de 12 barras (R3).
- γ (pesos do valor justo) é reajustado por sessão só com sessões anteriores (walk-forward).

Unidades: retornos em log (fração). Relógio do banco = broker (NY+7); sessão B3 em BRT,
barras M5 com abertura em [09:00, 18:25).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backend.eval.data import broker_wall_to_brt

SESSION_OPEN_MIN = 9 * 60
SESSION_END_MIN = 18 * 60 + 25
FFILL_MAX_BARS = 12
BAR_MIN = 5

# Cestas fixas e econômicas (SPEC §4.2; sem força bruta)
BASKETS = {
    "WIN$N": ["WDO$N", "DI1$N", "US500", "USTEC", "VIX", "DXY", "USDMXN", "XAUUSD", "BRENT", "CHINA50"],
    "WDO$N": ["WIN$N", "DI1$N", "US500", "DXY", "USDMXN", "VIX", "EURUSD", "XAUUSD", "BRENT", "USDJPY"],
}
PAIR_OF = {"WIN$N": "WDO$N", "WDO$N": "WIN$N"}


def _norm(sym: str) -> str:
    return sym.replace("$", "").replace("+", "p").replace("-", "_")


# ── Painel por sessão ──────────────────────────────────────────────────────

def load_symbol_bars(conn, symbol: str, start: str, end: str) -> pd.DataFrame:
    lo = (pd.Timestamp(start) - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
    hi = (pd.Timestamp(end) + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    b = pd.read_sql_query(
        "SELECT timestamp_utc, open, close FROM market_bars "
        "WHERE symbol = ? AND timeframe = 'M5' AND timestamp_utc >= ? AND timestamp_utc < ? "
        "ORDER BY timestamp_utc", conn, params=(symbol, lo, hi))
    if b.empty:
        return b.assign(ts_brt=pd.Series(dtype="datetime64[ns, America/Sao_Paulo]"))
    b["ts_brt"] = broker_wall_to_brt(b["timestamp_utc"])
    b = b.dropna(subset=["ts_brt"]).drop_duplicates("ts_brt").sort_values("ts_brt").reset_index(drop=True)
    return b


def _in_session(ts: pd.Series) -> pd.Series:
    m = ts.dt.hour * 60 + ts.dt.minute
    return (m >= SESSION_OPEN_MIN) & (m < SESSION_END_MIN)


@dataclass
class Panel:
    """Uma linha por barra de pregão do alvo. Colunas de fator em `factor_cols`."""
    target: str
    factors: list
    df: pd.DataFrame
    factor_cols: dict = field(default_factory=dict)   # símbolo -> coluna de retorno acumulado


def build_panel(conn, target: str, factors: list, start: str, end: str,
                min_bars: int = 60) -> Panel:
    """Painel causal: retorno acumulado (log) do alvo e de cada fator desde a abertura da B3.

    Fator: âncora = abertura da 1ª barra do fator com abertura ≥ 09:00 BRT da sessão; antes disso
    contribui 0. Valor na barra k = último fechamento do fator com abertura ≤ k (forward-fill
    máximo de 12 barras; além disso, retorno congelado e `stale_<f>`=1).
    """
    t = load_symbol_bars(conn, target, start, end)
    prev_close = t[["ts_brt", "close"]].rename(columns={"close": "prev_any_close"})
    t = t[_in_session(t.ts_brt)].copy()
    t["sess"] = t.ts_brt.dt.strftime("%Y-%m-%d")
    t = t[(t.sess >= start) & (t.sess <= end)]
    n = t.groupby("sess").close.transform("size")
    t = t[n >= min_bars].copy().reset_index(drop=True)
    t["k"] = ((t.ts_brt.dt.hour * 60 + t.ts_brt.dt.minute - SESSION_OPEN_MIN) // BAR_MIN).astype(int)
    g = t.groupby("sess")
    t["o0"] = g.open.transform("first")
    t["rT"] = np.log(t.close / t.o0)
    # último fechamento antes da abertura do pregão (para gap noturno)
    first_ts = g.ts_brt.transform("first")
    pc = pd.merge_asof(t[["ts_brt"]].assign(q=first_ts - pd.Timedelta(minutes=BAR_MIN)).sort_values("q"),
                       prev_close.sort_values("ts_brt"), left_on="q", right_on="ts_brt",
                       direction="backward", suffixes=("", "_p"))
    t["prev_close"] = pc.sort_values("ts_brt")["prev_any_close"].to_numpy()
    cols = {}
    for f in factors:
        fb = load_symbol_bars(conn, f, start, end)
        c = "rf_" + _norm(f)
        cols[f] = c
        if fb.empty:
            t[c] = 0.0
            t["stale_" + _norm(f)] = 1
            continue
        fb = fb[_in_session(fb.ts_brt)].copy()
        fb["sess"] = fb.ts_brt.dt.strftime("%Y-%m-%d")
        anchor = fb.groupby("sess").agg(f_o0=("open", "first"), f_first=("ts_brt", "first"))
        m = pd.merge_asof(t[["ts_brt", "sess"]], fb[["ts_brt", "close", "sess"]].rename(
            columns={"ts_brt": "f_ts", "sess": "f_sess"}), left_on="ts_brt", right_on="f_ts",
            direction="backward")
        m = m.join(anchor, on="sess")
        ok = (m.f_sess == m.sess) & m.f_first.notna() & (m.f_ts >= m.f_first)
        age = (m.ts_brt - m.f_ts).dt.total_seconds() / 60.0 / BAR_MIN
        r = np.where(ok, np.log(m.close / m.f_o0), 0.0)
        r = pd.Series(r, index=t.index)
        stale = (ok & (age > FFILL_MAX_BARS)).astype(int)
        # além de 12 barras sem negócio: congela no último valor dentro do limite
        r = r.where(stale == 0).groupby(t.sess).ffill().fillna(0.0)
        t[c] = r.to_numpy()
        t["stale_" + _norm(f)] = stale.to_numpy()
    return Panel(target=target, factors=list(factors), df=t, factor_cols=cols)


# ── Valor justo da cesta (walk-forward por sessão) ─────────────────────────

@dataclass(frozen=True)
class FairValueConfig:
    window_sessions: int = 60        # janela trailing do ajuste de γ
    step_bars: int = 6               # incrementos não sobrepostos de 30 min no ajuste
    ridge: float = 1e-3              # λ relativo (× traço/p) — só estabiliza
    sigma_sessions: int = 60         # janela trailing do perfil σ_k do gap
    min_sessions: int = 20           # mínimo de sessões anteriores para ter z
    factors: tuple | None = None     # None = cesta padrão do alvo


def _increments(cum: np.ndarray, k: np.ndarray, step: int) -> np.ndarray:
    """Incrementos não sobrepostos de `step` barras do acumulado (o 1º parte de 0 na abertura)."""
    sel = np.flatnonzero((k + 1) % step == 0)
    if len(sel) == 0:
        return np.empty((0,) + cum.shape[1:])
    v = cum[sel]
    prev = np.vstack([np.zeros((1,) + cum.shape[1:]), v[:-1]]) if v.ndim > 1 else np.concatenate([[0.0], v[:-1]])
    return v - prev


def fit_gamma(X: np.ndarray, y: np.ndarray, ridge: float = 1e-3) -> np.ndarray:
    """OLS sem intercepto (retornos desde a abertura partem de 0) com ridge relativo pequeno."""
    if len(y) < X.shape[1] + 5:
        return np.full(X.shape[1], np.nan)
    xtx = X.T @ X
    lam = ridge * np.trace(xtx) / max(X.shape[1], 1)
    return np.linalg.solve(xtx + lam * np.eye(X.shape[1]), X.T @ y)


def fair_value(panel: Panel, cfg: FairValueConfig = FairValueConfig(), pair_only: bool = False,
               ) -> pd.DataFrame:
    """Gap do alvo contra o valor justo da cesta, padronizado de forma causal.

    Para cada sessão s:
      γ_s = OLS(incrementos de 30 min do alvo ~ incrementos dos fatores) nas `window_sessions`
            sessões anteriores (nunca a própria sessão);
      fv(s,k) = Σ γ_s,f · r_f(s,k)  (retorno "justo" desde a abertura);
      gap(s,k) = r_T(s,k) − fv(s,k)  (log; > 0 = alvo caro frente à cesta);
      σ_k(s)  = RMS de gap(s',k) nas `sigma_sessions` sessões anteriores (perfil por horário);
      z(s,k)  = gap / σ_k(s).
    `pair_only=True`: cesta = só o par (WIN↔WDO) — é o β OLS de N pregões do spread.
    """
    df = panel.df
    facs = list(cfg.factors) if cfg.factors else list(panel.factors)
    if pair_only:
        facs = [PAIR_OF[panel.target]]
    cols = [panel.factor_cols[f] for f in facs]
    sessions = sorted(df.sess.unique())
    idx_of = {s: np.flatnonzero(df.sess.to_numpy() == s) for s in sessions}
    X_all = df[cols].to_numpy(float)
    y_all = df.rT.to_numpy(float)
    k_all = df.k.to_numpy(int)
    incr = {}
    for s in sessions:
        ii = idx_of[s]
        incr[s] = (_increments(X_all[ii], k_all[ii], cfg.step_bars), _increments(y_all[ii], k_all[ii], cfg.step_bars))
    fv = np.full(len(df), np.nan)
    gammas = {}
    for j, s in enumerate(sessions):
        prev = sessions[max(0, j - cfg.window_sessions):j]
        if len(prev) < cfg.min_sessions:
            continue
        X = np.vstack([incr[p][0] for p in prev])
        y = np.concatenate([incr[p][1] for p in prev])
        gmm = fit_gamma(X, y, cfg.ridge)
        if not np.all(np.isfinite(gmm)):
            continue
        gammas[s] = gmm
        ii = idx_of[s]
        fv[ii] = X_all[ii] @ gmm
    gap = y_all - fv
    out = pd.DataFrame({"sess": df.sess.to_numpy(), "k": k_all, "fv": fv, "gap": gap})
    # perfil σ_k trailing (sessões anteriores apenas)
    kmax = int(k_all.max()) + 1 if len(k_all) else 1
    G = np.full((len(sessions), kmax), np.nan)
    for j, s in enumerate(sessions):
        ii = idx_of[s]
        G[j, k_all[ii]] = gap[ii]
    z = np.full(len(df), np.nan)
    sig = np.full(len(df), np.nan)
    for j, s in enumerate(sessions):
        lo = max(0, j - cfg.sigma_sessions)
        past = G[lo:j]
        if np.isfinite(past).any(axis=1).sum() < cfg.min_sessions:
            continue
        cnt = np.isfinite(past).sum(axis=0)
        ms = np.where(cnt >= cfg.min_sessions, np.nanmean(np.where(np.isfinite(past), past ** 2, np.nan), axis=0), np.nan)
        prof = np.sqrt(ms)
        # suaviza o perfil e preenche horários raros com a forma c·√(k+1)
        kk = np.arange(kmax)
        okp = np.isfinite(prof)
        if okp.sum() >= 5:
            c = np.nanmedian(prof[okp] / np.sqrt(kk[okp] + 1))
            prof = np.where(okp, prof, c * np.sqrt(kk + 1))
        else:
            continue
        ii = idx_of[s]
        sig[ii] = prof[k_all[ii]]
        z[ii] = gap[ii] / sig[ii]
    out["gap_sigma"] = sig
    out["z"] = z
    out.attrs["gammas"] = {s: g.tolist() for s, g in gammas.items()}
    out.attrs["factors"] = facs
    return out


def legacy_like_z(gap: np.ndarray, sess: np.ndarray, min_n: int = 5, floor: float = 1e-4) -> np.ndarray:
    """Padronização do engine atual (para comparação): nível / desvio dos níveis anteriores do dia,
    média fixada em 0 (janela até 99), piso de 1 bp. Reproduz a construção que dá |z|>2 em ~31%."""
    z = np.full(len(gap), np.nan)
    start = 0
    for i in range(1, len(gap) + 1):
        if i == len(gap) or sess[i] != sess[start]:
            seg = gap[start:i]
            for j in range(len(seg)):
                past = seg[max(0, j - 99):j]
                past = past[np.isfinite(past)]
                if len(past) >= min_n and np.isfinite(seg[j]):
                    z[start + j] = seg[j] / max(float(np.std(past)), floor)
            start = i
    return z


def rolling_z(gap: np.ndarray, sess: np.ndarray, win: int = 40, min_n: int = 10) -> np.ndarray:
    """z do desvio do gap em relação à própria média móvel (janela no dia, só barras passadas)."""
    s = pd.Series(gap)
    g = s.groupby(pd.Series(sess))
    m = g.transform(lambda x: x.shift(1).rolling(win, min_periods=min_n).mean())
    sd = g.transform(lambda x: x.shift(1).rolling(win, min_periods=min_n).std())
    return ((s - m) / sd).to_numpy()


# ── Features do modelo de 60 min (SPEC §4.2) ──────────────────────────────

def _trailing_session_stat(values: pd.Series, sess: pd.Series, fn, window: int = 60, min_s: int = 20) -> pd.Series:
    """Estatística por sessão calculada com as `window` sessões ANTERIORES (R1)."""
    per = values.groupby(sess).apply(lambda x: x.to_numpy())
    keys = list(per.index)
    res = {}
    for j, s in enumerate(keys):
        prev = keys[max(0, j - window):j]
        if len(prev) < min_s:
            res[s] = np.nan
            continue
        res[s] = fn(np.concatenate([per[p] for p in prev]))
    return sess.map(res)


def nwe_center_mae(close: np.ndarray, sess: np.ndarray, o0: np.ndarray, prev_close: np.ndarray,
                   lookback: int = 95, bw: float = 8.0) -> tuple[np.ndarray, np.ndarray]:
    """NWE causal (kernel gaussiano unilateral, bw 8, lookback 95) sobre a série contínua com o gap
    noturno removido (mesma fórmula de `backend/irai/nwe.py`)."""
    n = len(close)
    adj = close.astype(float).copy()
    shift = 0.0
    off = np.zeros(n)
    for i in range(n):
        if i > 0 and sess[i] != sess[i - 1]:
            if np.isfinite(prev_close[i]) and prev_close[i] > 0:
                shift += o0[i] - prev_close[i]
        off[i] = shift
    adj = adj - off  # série "costurada": em nível da 1ª sessão
    w = np.exp(-np.arange(lookback) ** 2 / (2 * bw * bw))
    center = np.empty(n)
    for t in range(n):
        l = min(t, lookback - 1)
        center[t] = np.dot(w[:l + 1], adj[t - l:t + 1][::-1]) / w[:l + 1].sum()
    err = np.abs(adj - center)
    mae = pd.Series(err).rolling(lookback, min_periods=1).mean().to_numpy()
    return center + off, mae


def forecast_features(panel: Panel, fv: pd.DataFrame | None = None, pair_fv: pd.DataFrame | None = None,
                      sigma_window: int = 60) -> pd.DataFrame:
    """Matriz de features causais por barra (SPEC §4.2 + valor justo da cesta)."""
    df = panel.df
    sess = df.sess
    g = df.groupby("sess")
    lr1 = g.close.transform(lambda x: np.log(x).diff())
    lr1 = lr1.where(df.k > 0, np.log(df.close / df.o0))
    sig5 = _trailing_session_stat(lr1, sess, lambda a: float(np.nanstd(a)), sigma_window)
    k1 = df.k + 1
    F = pd.DataFrame({"sess": sess.to_numpy(), "k": df.k.to_numpy()}, index=df.index)
    F["own_rtd_z"] = df.rT / (sig5 * np.sqrt(k1))
    rv24 = lr1.groupby(sess).transform(lambda x: x.rolling(24, min_periods=6).std())
    rv24 = rv24.fillna(sig5)
    logc = np.log(df.close)
    for h in (1, 3, 6, 12):
        rh = logc - logc.groupby(sess).shift(h)
        rh = rh.fillna(df.rT)  # no começo do pregão: desde a abertura
        F[f"own_r{h}"] = rh / (rv24 * np.sqrt(h))
    for f, c in panel.factor_cols.items():
        r = df[c]
        inc = r.groupby(sess).diff().fillna(r)
        s5 = _trailing_session_stat(inc, sess, lambda a: float(np.nanstd(a)), sigma_window)
        F[f"f_rtd_z_{_norm(f)}"] = (r / (s5 * np.sqrt(k1))).replace([np.inf, -np.inf], 0).fillna(0)
        r3 = r - r.groupby(sess).shift(3).fillna(0)
        F[f"f_r3_{_norm(f)}"] = (r3 / s5).replace([np.inf, -np.inf], 0).fillna(0)
    if fv is not None:
        F["fv_gap_z"] = fv.z.to_numpy()
    if pair_fv is not None:
        F["pair_gap_z"] = pair_fv.z.to_numpy()
    center, mae = nwe_center_mae(df.close.to_numpy(), sess.to_numpy(), df.o0.to_numpy(), df.prev_close.to_numpy())
    F["nwe_pos"] = (df.close.to_numpy() - center) / (3 * np.maximum(mae, 1e-12))
    F["rvol"] = rv24 / sig5
    F["tod"] = df.k * BAR_MIN / 565.0
    F["tod2"] = F.tod ** 2
    dret = np.log(df.close / df.o0)
    daily = dret.groupby(sess).last()
    dsig = {}
    keys = list(daily.index)
    for j, s in enumerate(keys):
        prev = daily.iloc[max(0, j - sigma_window):j]
        dsig[s] = float(prev.std()) if len(prev) >= 20 else np.nan
    F["gap_z"] = (np.log(df.o0 / df.prev_close) / sess.map(dsig)).replace([np.inf, -np.inf], np.nan)
    return F


def forward_targets(panel: Panel, horizons=(3, 6, 12)) -> pd.DataFrame:
    """Retornos futuros (log) no mesmo pregão: h barras e até o último fechamento (SPEC §3)."""
    df = panel.df
    g = df.groupby("sess")
    out = pd.DataFrame(index=df.index)
    lc = np.log(df.close)
    for h in horizons:
        out[f"y{h * BAR_MIN}"] = g.close.shift(-h).pipe(np.log) - lc
    out["yclose"] = np.log(g.close.transform("last")) - lc
    out.loc[g.cumcount(ascending=False) == 0, "yclose"] = np.nan
    return out
