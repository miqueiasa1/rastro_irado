"""
Sync GEX Levels: Pine Script → IRAI Frontend

Parseia o jumba_tradingview.pine e gera gexLevels.js no frontend IRAI.
Chamado automaticamente pelo GEX_DAILY_ALL.bat após gerar o Pine.

Uso: python scripts/sync_gex_to_irai.py
"""
import re
import os
import sys
from datetime import datetime

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PINE_PATH = os.path.join(PROJECT_ROOT, "..", "wdo win pair trading", "gex", "docs", "jumba_tradingview.pine")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "frontend", "src", "gexLevels.js")

# Map Pine array prefixes to IRAI target names
PREFIX_TO_TARGET = {
    'win': 'WIN$N',
    'us': 'US500',
    'nq': 'USTEC',
    'btc': 'BTCUSD',
    'dol': 'WDO$N',
    'eur': 'EURUSD',
    'gbp': 'GBPUSD',
    'gold': 'XAUUSD',
    'dow': 'US30',
    'jpy': 'USDJPY',
    'dxy': 'DXY',
}


def parse_pine(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    results = {}

    for prefix, target in PREFIX_TO_TARGET.items():
        results[target] = []

        prices = re.findall(rf'array\.push\({prefix}_prices,\s*([\d.]+)\)', content)
        labels = re.findall(rf'array\.push\({prefix}_labels,\s*"([^"]+)"\)', content)
        colors = re.findall(rf'array\.push\({prefix}_colors,\s*color\.new\((#[0-9a-fA-F]+),\s*\d+\)\)', content)
        widths = re.findall(rf'array\.push\({prefix}_widths,\s*(\d+)\)', content)
        styles = re.findall(rf'array\.push\({prefix}_styles,\s*"([^"]+)"\)', content)

        count = min(len(prices), len(labels), len(colors), len(widths), len(styles))

        for i in range(count):
            label = labels[i]
            level_type = 'wall'
            if 'MIN GAMMA' in label:
                level_type = 'min_gamma'
            elif 'MAX GAMMA' in label:
                level_type = 'max_gamma'
            elif 'GAMMA FLIP' in label:
                level_type = 'gamma_flip'
            elif label == "MID WALL":
                level_type = 'mid_wall'

            results[target].append({
                'price': float(prices[i]),
                'label': label,
                'color': colors[i],
                'width': int(widths[i]),
                'style': styles[i],
                'type': level_type,
            })

    return results


def generate_js(data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        '/**',
        ' * GEX (Gamma Exposure) Levels — Extraídos do jumba_tradingview.pine',
        f' * Atualizado em: {now}',
        ' * ',
        ' * Tipos: wall, mid_wall, min_gamma, gamma_flip, max_gamma',
        ' */',
        '',
        'const GEX_LEVELS = {',
    ]

    for target, levels in data.items():
        lines.append(f'  "{target}": [')
        for lvl in levels:
            lines.append(
                f'    {{ price: {lvl["price"]}, label: "{lvl["label"]}", '
                f'color: "{lvl["color"]}", width: {lvl["width"]}, '
                f'style: "{lvl["style"]}", type: "{lvl["type"]}" }},'
            )
        lines.append('  ],')

    lines.append('};')
    lines.append('')
    lines.append('export default GEX_LEVELS;')
    lines.append('')

    return '\n'.join(lines)


if __name__ == '__main__':
    # Resolve path
    pine_path = os.path.normpath(PINE_PATH)
    if not os.path.exists(pine_path):
        print(f"ERRO: Pine nao encontrado em {pine_path}")
        sys.exit(1)

    print(f"Parsing: {pine_path}")
    data = parse_pine(pine_path)

    total = sum(len(v) for v in data.values())
    for target, levels in data.items():
        print(f"  {target}: {len(levels)} niveis")
    print(f"  Total: {total} niveis")

    js = generate_js(data)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(js)

    print(f"Salvo em: {OUTPUT_PATH}")
