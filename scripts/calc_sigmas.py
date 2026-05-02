import sqlite3
import pandas as pd
import numpy as np
import json

conn = sqlite3.connect('data/irai.db')

# Pegar targets ativos
targets = pd.read_sql_query('SELECT target, slug, data_proxy FROM asset_models WHERE active=1', conn)

updates = []

for _, row in targets.iterrows():
    target = row['target']
    slug = row['slug']
    data_proxy = row['data_proxy'] if pd.notna(row['data_proxy']) else target
    
    # Carregar dados do ativo
    df = pd.read_sql_query(f"SELECT timestamp_utc, open, close FROM market_bars WHERE symbol='{data_proxy}' AND timeframe='M5' ORDER BY timestamp_utc", conn)
    
    if df.empty:
        print(f"Skipping {target}: df.empty")
        continue
        
    df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])
    df['session_date'] = df['timestamp_utc'].dt.date
    
    # Pegar o first open e last close por dia
    daily_returns = []
    
    grouped = df.groupby('session_date')
    for date, group in grouped:
        first_open = group.iloc[0]['open']
        last_close = group.iloc[-1]['close']
        
        if first_open > 0:
            ret = (last_close - first_open) / first_open
            daily_returns.append(ret)
            
    if len(daily_returns) < 5:
        print(f"Skipping {target}: daily_returns = {len(daily_returns)}")
        continue
        
    daily_returns = np.array(daily_returns)
    sigma = np.std(daily_returns)
    
    # Arredondar para 4 casas decimais
    sigma = round(float(sigma), 4)
    
    # Definir threshold (vamos usar 1.0 como default, significa 1 desvio padrão inteiro para configurar divergência forte)
    # Mas para manter compatibilidade com "z_score", se o z_score chega a 1.0, o preço andou 1 desvio padrão
    # O threshold anterior era 0.5 (meio desvio padrão). Vamos usar 0.75 para não acionar à toa.
    threshold = 0.75
    
    config = {"sigma": sigma, "threshold": threshold}
    updates.append((json.dumps(config), slug))
    
    print(f"Ativo: {target} (proxy: {data_proxy})")
    print(f"  Sessoes: {len(daily_returns)}")
    print(f"  Sigma Intraday (StdDev do Retorno): {sigma:.4f} ({(sigma*100):.2f}%)")
    print(f"  Threshold Sugerido: {threshold}")
    print()

for config_json, slug in updates:
    conn.execute('UPDATE asset_models SET divergence_config = ? WHERE slug = ?', (config_json, slug))

conn.commit()
print("Banco de dados atualizado com os novos sigmas!")
conn.close()
