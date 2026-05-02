"""
Dump current calibration from irai.db for FACTOR_MAP.md generation.
Reads asset_models and model_params, plus computes correlations.
"""
import sqlite3, json, os, sys
import numpy as np
import pandas as pd

os.environ["PYTHONIOENCODING"] = "utf-8"

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "irai.db")

def main():
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Read asset_models
    cur = conn.execute(
        "SELECT target, factors, accuracy, r_squared, session_start_h, session_end_h "
        "FROM asset_models WHERE active=1 ORDER BY accuracy DESC"
    )
    models = []
    for row in cur:
        target, fj, acc, r2, sh, eh = row
        factors = json.loads(fj) if fj else []
        models.append({
            "target": target,
            "factors": factors,
            "acc": acc,
            "r2": r2,
            "session": f"{sh:02d}-{eh:02d}",
            "n_factors": len(factors),
        })
    
    # 2. Read model_params for weights, sigmas, alpha, intercept
    for m in models:
        prefix = m["target"].replace("$", "").lower() + "_"
        params = {}
        cur2 = conn.execute("SELECT param_name, value FROM model_params WHERE param_name LIKE ?", (prefix + "%",))
        for pname, val in cur2:
            short = pname[len(prefix):]
            params[short] = val
        m["params"] = params
        m["alpha"] = params.get("alpha", 0)
        m["intercept"] = params.get("intercept", 0)
    
    # 3. Compute correlations between each target and its factors
    df = pd.read_sql_query(
        "SELECT symbol, timestamp_utc, open, close FROM market_bars WHERE timeframe='M5'",
        conn,
    )
    df["timestamp"] = pd.to_datetime(df["timestamp_utc"])
    df["date"] = df["timestamp"].dt.date
    
    daily = df.groupby(["symbol", "date"]).agg(
        open_price=("open", "first"),
        close_price=("close", "last"),
    ).reset_index()
    daily["ret"] = (daily["close_price"] - daily["open_price"]) / daily["open_price"]
    pivot = daily.pivot_table(index="date", columns="symbol", values="ret")
    
    for m in models:
        t = m["target"]
        corrs = {}
        if t in pivot.columns:
            for f in m["factors"]:
                if f in pivot.columns:
                    valid = pivot[[t, f]].dropna()
                    if len(valid) > 20:
                        c = valid[t].corr(valid[f])
                        corrs[f] = round(c, 4)
        m["correlations"] = corrs
    
    conn.close()
    
    # 4. Print as markdown
    print("# IRAI Multi-Asset — Mapa de Fatores por Ativo")
    print()
    print("> [!NOTE]")
    print("> **20 modelos recalibrados** (Calibração Universal 2026-04-30). Regras aplicadas:")
    print("> 1. Mínimo **6 fatores** por cesta (máximo 8) — força robustez e reduz overfitting.")
    print("> 2. **DE40** incluído na pool global de fatores candidatos (31 totais).")
    print("> 3. Ativos internacionais **não** utilizam ativos BR (WIN, WDO, DI1).")
    print("> 4. Índices americanos (US500, US30, USTEC) **não** utilizam outros índices americanos.")
    print("> 5. Filtros anti-multicolinearidade: max 1 Treasury + 1 EM Bond por cesta; EWZ excluído para BR.")
    print("> 6. Exclusão cruzada para pares correlatos (ex: EURJPY e GBPJPY não se usam).")
    print("> 7. **Coluna Corr** = correlação Pearson diária entre o fator e o ativo-alvo.")
    print("> Última calibração: 2026-05-01")
    print()
    print("---")
    print()
    print("## Ranking por Acurácia (Pós-Calibração Universal)")
    print()
    print("| # | Ativo | ACC | R² | Sessão | #Fats | Fator Principal | DE40? |")
    print("|---|---|---|---|---|---|---|---|")
    for i, m in enumerate(models, 1):
        weights = {}
        for f in m["factors"]:
            w_key = f"w_{f.replace('$', '').lower()}"
            weights[f] = m["params"].get(w_key, 0)
        main_f = max(weights, key=lambda k: abs(weights[k])) if weights else "?"
        main_w = weights.get(main_f, 0)
        has_de40 = "✅" if "DE40" in m["factors"] else "❌"
        # Emoji formatting
        target_display = f"**{m['target']}**"
        if m['target'] == "BTCUSD": target_display = f"₿ {target_display}"
        if m['target'] == "XAUUSD": target_display = f"🥇 {target_display}"
        print(f"| {i} | {target_display} | **{m['acc']:.1f}%** | **{m['r2']:.4f}** | {m['session']} UTC | {m['n_factors']} | {main_f} ({main_w:+.3f}) | {has_de40} |")
    
    print()
    print("---")
    print()
    print("## Detalhamento Completo por Ativo")
    
    for i, m in enumerate(models, 1):
        sess_label = "09h-18h BRT" if m["session"] == "09-18" else "00h-24h UTC"
        print(f"\n### {i}. {m['target']} - ACC {m['acc']:.1f}% | R2={m['r2']:.4f} | Sessao: {sess_label}")
        print("```")
        print(f"α={m['alpha']:.4f}, intercept={m['intercept']:.4f}")
        print()
        print(f"  {'Fator':<22s} {'Peso':>10s}    {'Corr':>6s}  {'Direção'}")
        print(f"  {'─'*22}  {'─'*10}    {'─'*6}  {'─'*9}")
        
        # Sort factors by absolute weight for better reading
        sorted_factors = sorted(m["factors"], key=lambda f: abs(m["params"].get(f"w_{f.replace('$', '').lower()}", 0)), reverse=True)

        for f in sorted_factors:
            w_key = f"w_{f.replace('$', '').lower()}"
            w = m["params"].get(w_key, 0)
            corr = m["correlations"].get(f, None)
            corr_str = f"{corr:+.4f}" if corr is not None else "  N/A "
            direction = "↑ COMPRA" if w > 0 else "↓ VENDA"
            print(f"  {f:<22s} {w:+10.6f}    {corr_str:>6s}  {direction}")
        print("```")

if __name__ == "__main__":
    main()
