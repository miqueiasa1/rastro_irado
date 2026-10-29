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
    'dax': 'DE40',
    'jp': 'JP225',
    'rut': 'US2000',
    'china': 'CHINA50',
}





def parse_pine(filepath):
    import re
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    results = {}
    for prefix, target in PREFIX_TO_TARGET.items():
        results[target] = []

    current_target = None
    current_prices = []
    current_labels = []
    current_colors = []
    current_widths = []
    current_styles = []

    in_function = False

    def flush_levels():
        nonlocal current_target, current_prices, current_labels, current_colors, current_widths, current_styles
        if current_target:
            count = min(len(current_prices), len(current_labels), len(current_colors), len(current_widths), len(current_styles))
            for i in range(count):
                label = current_labels[i]
                level_type = 'wall'
                if 'MIN GAMMA' in label:
                    level_type = 'min_gamma'
                elif 'MAX GAMMA' in label:
                    level_type = 'max_gamma'
                elif 'GAMMA FLIP' in label:
                    level_type = 'gamma_flip'
                elif "MID" in label:
                    level_type = 'mid_wall'

                results[current_target].append({
                    'price': current_prices[i],
                    'label': label,
                    'color': current_colors[i],
                    'width': current_widths[i],
                    'style': current_styles[i],
                    'type': level_type,
                })
            # Clear buffers
            current_prices = []
            current_labels = []
            current_colors = []
            current_widths = []
            current_styles = []

    for line in lines:
        match = re.match(r'^\s*populate_([a-z]+)_\d+\(([^)]*)\)\s*=>', line)
        if match:
            flush_levels()
            prefix = match.group(1)
            if prefix in PREFIX_TO_TARGET:
                current_target = PREFIX_TO_TARGET[prefix]
                in_function = True
            else:
                current_target = None
                in_function = False
            continue

        if in_function:
            stripped = line.strip()
            if stripped == "":
                continue
            if line.startswith('    ') or line.startswith('\t'):
                # We are inside the function body. parse push lines
                m_pr = re.search(r'array\.push\(pr,\s*([\d.-]+)\)', stripped)
                if m_pr:
                    current_prices.append(float(m_pr.group(1)))
                    continue
                
                m_lb = re.search(r'array\.push\(lb,\s*"([^"]+)"\)', stripped)
                if m_lb:
                    current_labels.append(m_lb.group(1))
                    continue
                
                m_cl = re.search(r'array\.push\(cl,\s*color\.new\((#[0-9a-fA-F]+),\s*\d+\)\)', stripped)
                if m_cl:
                    current_colors.append(m_cl.group(1))
                    continue
                
                m_wd = re.search(r'array\.push\(wd,\s*(\d+)\)', stripped)
                if m_wd:
                    current_widths.append(int(m_wd.group(1)))
                    continue
                
                m_st = re.search(r'array\.push\(st,\s*"([^"]+)"\)', stripped)
                if m_st:
                    current_styles.append(m_st.group(1))
                    continue
            else:
                # Out of indentation
                flush_levels()
                current_target = None
                in_function = False

    flush_levels()
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
    lines.append('export function getGexLevels(target) {')
    lines.append('  return GEX_LEVELS[target] || [];')
    lines.append('}')
    lines.append('')
    lines.append('export default GEX_LEVELS;')
    lines.append('')

    return '\n'.join(lines)


def _read_env_value(name):
    """Lê uma variável do ambiente ou do .env na raiz do projeto."""
    val = os.environ.get(name)
    if val:
        return val.strip()
    env_path = os.path.join(PROJECT_ROOT, '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as ef:
            for line in ef:
                if line.strip().startswith(f"{name}="):
                    return line.strip().split("=", 1)[1].strip()
    return None


def pine_vault_key():
    """Chave do cofre do Pine no RTDB: sha256('<salt>:<senha>') em hex.
    Deve bater com o cálculo feito no frontend (PineDownloadModal.jsx)."""
    import hashlib
    password = _read_env_value("PINE_PASSWORD")
    salt = _read_env_value("PINE_SALT")
    if not password or not salt:
        return None
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


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

    # SEGURANÇA: o .pine NUNCA deve ir para frontend/public (seria servido sem senha pelo Hosting).
    # Remove cópia legada, se existir.
    legacy_public_pine = os.path.join(PROJECT_ROOT, "frontend", "public", "jumba_tradingview.pine")
    if os.path.exists(legacy_public_pine):
        os.remove(legacy_public_pine)
        print(f"Removida cópia pública legada: {legacy_public_pine}")

    # Ler conteúdo integral do .pine para publicação diária na nuvem
    with open(pine_path, 'r', encoding='utf-8') as pf:
        pine_raw_content = pf.read()

    # Persistir no banco de dados SQLite
    import json
    sys.path.insert(0, PROJECT_ROOT)
    from backend.db import get_connection

    session_date = datetime.now().strftime("%Y-%m-%d")
    run_name = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%H:%M")
    print(f"Persistindo niveis GEX no SQLite (Coleta: {run_name}) para a data {session_date}...")

    conn = get_connection()
    try:
        for target, levels in data.items():
            if levels:
                levels_json = json.dumps(levels)
                conn.execute(
                    "INSERT OR REPLACE INTO gex_levels (session_date, target, run_name, levels_json) VALUES (?, ?, ?, ?)",
                    (session_date, target, run_name, levels_json)
                )
        conn.commit()
        print("Níveis GEX salvos com sucesso no SQLite!")
    except Exception as e:
        print(f"Erro ao salvar níveis GEX no banco: {e}")
    finally:
        conn.close()

    # Publicar diretamente no Firebase RTDB (/summaries/gex e /gex_pine) para atualização imediata no painel web
    try:
        import firebase_admin
        from firebase_admin import credentials, db as fb_db

        env_path = os.path.join(PROJECT_ROOT, '.env')
        fb_url = os.environ.get("FIREBASE_URL")
        if not fb_url and os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as ef:
                for line in ef:
                    if line.strip().startswith("FIREBASE_URL="):
                        fb_url = line.strip().split("=", 1)[1].strip()
        sa_key = os.path.join(PROJECT_ROOT, 'serviceAccountKey.json')
        if fb_url and os.path.exists(sa_key):
            if not firebase_admin._apps:
                cred = credentials.Certificate(sa_key)
                firebase_admin.initialize_app(cred, {'databaseURL': fb_url})
            fb_batch = {}
            for target, levels in data.items():
                if levels:
                    safe_target = target.replace('$', '_').replace('.', '_')
                    payload = {
                        "target": target,
                        "date": session_date,
                        "selected_run": run_name,
                        "available_runs": [run_name],
                        "levels": levels,
                    }
                    fb_batch[f"summaries/gex/{session_date}/{safe_target}"] = payload
                    fb_batch[f"summaries/gex/{safe_target}"] = payload

            pine_payload = {
                "content": pine_raw_content,
                "date": session_date,
                "run_name": run_name,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "filename": f"jumba_tradingview_{session_date}.pine",
                "total_levels": total,
                "assets_count": len([k for k, v in data.items() if v]),
            }
            # Nó admin-only (regras RTDB: leitura negada ao público)
            fb_batch["gex_pine"] = pine_payload
            # Cofre: caminho = sha256(salt:senha). Só quem conhece a senha consegue ler.
            # Substitui o nó inteiro para invalidar chaves antigas quando a senha muda.
            vault_key = pine_vault_key()
            if vault_key:
                fb_batch["pine_vault"] = {vault_key: pine_payload}
            else:
                print("Aviso: PINE_PASSWORD/PINE_SALT ausentes no .env; cofre do Pine não publicado.")

            if fb_batch:
                fb_db.reference('/').update(fb_batch)
                print(f"Níveis GEX ({len(data)} ativos) e Pine Script ({len(pine_raw_content)} bytes) publicados no Firebase RTDB!")
    except Exception as e:
        print(f"Aviso ao publicar GEX no Firebase RTDB: {e}")
