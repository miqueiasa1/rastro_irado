import json
import os

cache_dir = r"c:\Users\ryzen\Downloads\Antigravity\wdo win pair trading\gex\data"
target_map = {
    'win_walls_cache.json': 'WIN$N',
    'sp500_es_walls_cache.json': 'US500',
    'nasdaq_nq_walls_cache.json': 'USTEC',
    'btc_usd_walls_cache.json': 'BTCUSD',
    'usd_brl_walls_cache.json': 'WDO$N',
    'eur_usd_walls_cache.json': 'EURUSD',
    'gbp_usd_walls_cache.json': 'GBPUSD',
    'gold_xau_walls_cache.json': 'XAUUSD',
    'dow_us30_walls_cache.json': 'US30',
    'usd_jpy_walls_cache.json': 'USDJPY',
    'dax_de40_walls_cache.json': 'DE40',
    'russell_us2000_walls_cache.json': 'US2000',
    'nikkei_jp225_walls_cache.json': 'JP225',
    'china_fxi_walls_cache.json': 'CHINA50',
    'dxy_uup_walls_cache.json': 'DXY',
}

js_out = """/**
 * GEX (Gamma Exposure) Levels — Completo com MagicWalls, MidWalls e Níveis Críticos
 * Gerado automaticamente a partir dos caches GEX em 2026-07-23
 */

const GEX_LEVELS = {
"""

for fname, target in target_map.items():
    fpath = os.path.join(cache_dir, fname)
    if not os.path.exists(fpath):
        print(f"Aviso: {fname} não encontrado.")
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    walls = data.get('walls', [])
    js_out += f'  "{target}": [\n'
    for w in sorted(walls, key=lambda x: x.get('price', 0)):
        p = w.get('price')
        w_type = w.get('type')
        width = w.get('width', 1)
        style = 'dashed' if w_type == 'MidWall' else 'solid'
        
        if w_type == 'Wall':
            stars = '*' * width
            lbl = f'MAGICWALL {stars}'
            if 'strike_spy' in w:
                lbl += f' (Strike {w["strike_spy"]})'
            elif 'strike_ibov' in w:
                lbl += f' (IBOV {w["strike_ibov"]})'
            color = '#00e676'
            t_type = 'wall'
        elif w_type == 'MidWall':
            lbl = 'MIDLEWALL'
            color = '#90a4ae'
            t_type = 'mid_wall'
        elif w_type == 'GammaFlip':
            lbl = 'GAMMA FLIP (Pivot)'
            color = '#ffd600'
            t_type = 'gamma_flip'
        elif w_type == 'MaxGamma':
            lbl = 'MAX GAMMA (Teto)'
            color = '#00b0ff'
            t_type = 'max_gamma'
        elif w_type == 'MinGamma':
            lbl = 'MIN GAMMA (Piso)'
            color = '#ff1744'
            t_type = 'min_gamma'
        else:
            lbl = str(w_type)
            color = '#00e676'
            t_type = 'wall'
            
        js_out += f'    {{ price: {p}, label: "{lbl}", color: "{color}", width: {width}, style: "{style}", type: "{t_type}" }},\n'
    js_out += '  ],\n'

js_out += """};

export function getGexLevels(target) {
  if (!target) return [];
  return GEX_LEVELS[target] || [];
}

export default GEX_LEVELS;
"""

out_file = r"c:\Users\ryzen\Downloads\Antigravity\rastro_irado\frontend\src\gexLevels.js"
with open(out_file, 'w', encoding='utf-8') as f:
    f.write(js_out)

print(f"gexLevels.js atualizado com sucesso em {out_file}!")
