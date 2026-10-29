"""
Backfill GEX Historical Levels into IRAI SQLite Database (irai_live.db)

Scans the git commit history of `wdo win pair trading/gex/` (both `jumba_tradingview.pine`
in its legacy and modern formats, and `jumba_neologica` for the earliest May 2026 runs)
and populates `gex_levels` in `irai_live.db` with all historical runs.
"""
import os
import re
import json
import sqlite3
import subprocess
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IRAI_ROOT = os.path.dirname(SCRIPT_DIR)
GEX_REPO_ROOT = os.path.normpath(os.path.join(IRAI_ROOT, "..", "wdo win pair trading"))
DB_PATH = os.path.join(IRAI_ROOT, "data", "irai_live.db")

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


def parse_pine_universal(text):
    """
    Parses both the modern `populate_<prefix>_<idx>(pr, lb, cl, wd, st)` format
    and the legacy `array.push(<prefix>_prices, ...)` format from jumba_tradingview.pine.
    """
    lines = text.splitlines()
    results = {target: [] for target in PREFIX_TO_TARGET.values()}

    has_populate = any(re.match(r'^\s*populate_([a-z]+)_\d+\(', l) for l in lines)

    if has_populate:
        current_target = None
        current_prices, current_labels, current_colors, current_widths, current_styles = [], [], [], [], []
        in_function = False

        def flush_levels():
            nonlocal current_target, current_prices, current_labels, current_colors, current_widths, current_styles
            if current_target:
                count = min(
                    len(current_prices), len(current_labels),
                    len(current_colors), len(current_widths), len(current_styles)
                )
                for i in range(count):
                    label = current_labels[i]
                    level_type = 'wall'
                    if 'MIN GAMMA' in label:
                        level_type = 'min_gamma'
                    elif 'MAX GAMMA' in label:
                        level_type = 'max_gamma'
                    elif 'GAMMA FLIP' in label:
                        level_type = 'gamma_flip'
                    elif 'MID' in label:
                        level_type = 'mid_wall'
                    results[current_target].append({
                        'price': current_prices[i],
                        'label': label,
                        'color': current_colors[i],
                        'width': current_widths[i],
                        'style': current_styles[i],
                        'type': level_type,
                    })
                current_prices, current_labels, current_colors, current_widths, current_styles = [], [], [], [], []

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
                    flush_levels()
                    current_target = None
                    in_function = False
        flush_levels()
    else:
        buffers = {p: {'pr': [], 'lb': [], 'cl': [], 'wd': [], 'st': []} for p in PREFIX_TO_TARGET}
        for line in lines:
            stripped = line.strip()
            m_pr = re.search(r'array\.push\(([a-z]+)_prices,\s*([\d.-]+)\)', stripped)
            if m_pr and m_pr.group(1) in buffers:
                buffers[m_pr.group(1)]['pr'].append(float(m_pr.group(2)))
                continue
            m_lb = re.search(r'array\.push\(([a-z]+)_labels,\s*"([^"]+)"\)', stripped)
            if m_lb and m_lb.group(1) in buffers:
                buffers[m_lb.group(1)]['lb'].append(m_lb.group(2))
                continue
            m_cl = re.search(r'array\.push\(([a-z]+)_colors,\s*color\.new\((#[0-9a-fA-F]+),\s*\d+\)\)', stripped)
            if m_cl and m_cl.group(1) in buffers:
                buffers[m_cl.group(1)]['cl'].append(m_cl.group(2))
                continue
            m_wd = re.search(r'array\.push\(([a-z]+)_widths,\s*(\d+)\)', stripped)
            if m_wd and m_wd.group(1) in buffers:
                buffers[m_wd.group(1)]['wd'].append(int(m_wd.group(2)))
                continue
            m_st = re.search(r'array\.push\(([a-z]+)_styles,\s*"([^"]+)"\)', stripped)
            if m_st and m_st.group(1) in buffers:
                buffers[m_st.group(1)]['st'].append(m_st.group(2))
                continue

        for prefix, target in PREFIX_TO_TARGET.items():
            b = buffers[prefix]
            count = min(len(b['pr']), len(b['lb']), len(b['cl']), len(b['wd']), len(b['st']))
            for i in range(count):
                label = b['lb'][i]
                level_type = 'wall'
                if 'MIN GAMMA' in label:
                    level_type = 'min_gamma'
                elif 'MAX GAMMA' in label:
                    level_type = 'max_gamma'
                elif 'GAMMA FLIP' in label:
                    level_type = 'gamma_flip'
                elif 'MID' in label:
                    level_type = 'mid_wall'
                results[target].append({
                    'price': b['pr'][i],
                    'label': label,
                    'color': b['cl'][i],
                    'width': b['wd'][i],
                    'style': b['st'][i],
                    'type': level_type,
                })

    return {k: v for k, v in results.items() if v}


def parse_neologica(text):
    """
    Parses early jumba_neologica files (before jumba_tradingview.pine existed) for WIN$N.
    """
    prices, colors, widths, styles = {}, {}, {}, {}
    for line in text.splitlines():
        s = line.strip()
        m_p = re.match(r'^line(\d+)\s*:=\s*([\d.]+);', s)
        if m_p:
            prices[int(m_p.group(1))] = float(m_p.group(2))
            continue
        m_c = re.match(r'^line(\d+)Color\s*:=\s*(\w+);', s)
        if m_c:
            colors[int(m_c.group(1))] = m_c.group(2)
            continue
        m_w = re.match(r'^line(\d+)Width\s*:=\s*(\d+);', s)
        if m_w:
            widths[int(m_w.group(1))] = int(m_w.group(2))
            continue
        m_s = re.match(r'^line(\d+)Style\s*:=\s*(\w+);', s)
        if m_s:
            styles[int(m_s.group(1))] = m_s.group(2)
            continue

    levels = []
    for idx in sorted(prices.keys()):
        p = prices[idx]
        c_var = colors.get(idx, 'clWall')
        w = widths.get(idx, 1)
        if c_var == 'clMinGamma':
            l_type, label, col, st = 'min_gamma', 'MIN GAMMA (Piso)', '#ff1744', 'solid'
        elif c_var == 'clMaxGamma':
            l_type, label, col, st = 'max_gamma', 'MAX GAMMA (Teto)', '#00b0ff', 'solid'
        elif c_var == 'clFlip':
            l_type, label, col, st = 'gamma_flip', 'GAMMA FLIP (Pivot)', '#ffd600', 'solid'
        elif c_var in ('clMidWall', 'clMidWallFibo'):
            l_type, label, col, st = 'mid_wall', 'MIDLEWALL', '#90a4ae', 'dashed'
        else:
            l_type, label, col, st = 'wall', f"MAGICWALL {'*' * w}", '#00e676', 'solid'
        levels.append({
            'price': p,
            'label': label,
            'color': col,
            'width': w,
            'style': st,
            'type': l_type,
        })
    return {'WIN$N': levels} if levels else {}


def run_backfill():
    commits = subprocess.check_output(
        ["git", "log", "--format=%H|%ai|%s", "--reverse", "--", "gex/"],
        cwd=GEX_REPO_ROOT, text=True, encoding="utf-8", errors="replace"
    ).strip().splitlines()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT COUNT(*), COUNT(DISTINCT session_date), MIN(session_date), MAX(session_date), COUNT(DISTINCT target) FROM gex_levels")
    print("Before backfill:", c.fetchone())

    c.execute("SELECT session_date, run_name, target FROM gex_levels")
    existing_keys = set(c.fetchall())

    c.execute("SELECT DISTINCT session_date, run_name FROM gex_levels")
    existing_date_runs = {}
    for sd, rn in c.fetchall():
        existing_date_runs.setdefault(sd, []).append(rn)

    inserted_runs = 0
    inserted_rows = 0

    for line in commits:
        h, dt, msg = line.split("|", 2)
        session_date = dt[:10]
        run_name = dt[11:16]

        try:
            dt_obj = datetime.strptime(dt.strip(), "%Y-%m-%d %H:%M:%S %z")
            updated_at_utc = dt_obj.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            updated_at_utc = dt[:19]

        files = subprocess.check_output(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", h, "--", "gex/"],
            cwd=GEX_REPO_ROOT, text=True, encoding="utf-8", errors="replace"
        ).strip().splitlines()

        data = {}
        if "gex/docs/jumba_tradingview.pine" in files:
            try:
                pine_txt = subprocess.check_output(
                    ["git", "show", f"{h}:gex/docs/jumba_tradingview.pine"],
                    cwd=GEX_REPO_ROOT, text=True, encoding="utf-8", errors="replace"
                )
                data = parse_pine_universal(pine_txt)
            except Exception as e:
                print(f"Error parsing pine at {h}: {e}")
        elif "gex/docs/jumba_neologica" in files:
            try:
                neo_txt = subprocess.check_output(
                    ["git", "show", f"{h}:gex/docs/jumba_neologica"],
                    cwd=GEX_REPO_ROOT, text=True, encoding="utf-8", errors="replace"
                )
                data = parse_neologica(neo_txt)
            except Exception as e:
                print(f"Error parsing neo at {h}: {e}")

        if not data:
            continue

        has_close = False
        for ex_r in existing_date_runs.get(session_date, []):
            try:
                m1 = int(run_name[:2]) * 60 + int(run_name[3:5])
                m2 = int(ex_r[:2]) * 60 + int(ex_r[3:5])
                if abs(m1 - m2) <= 5:
                    has_close = True
                    break
            except Exception:
                pass

        if has_close:
            continue

        run_added = False
        for target, levels in data.items():
            if levels and (session_date, run_name, target) not in existing_keys:
                levels_json = json.dumps(levels, ensure_ascii=False)
                c.execute(
                    "INSERT OR REPLACE INTO gex_levels (session_date, target, run_name, levels_json, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (session_date, target, run_name, levels_json, updated_at_utc)
                )
                existing_keys.add((session_date, run_name, target))
                inserted_rows += 1
                run_added = True

        if run_added:
            inserted_runs += 1
            existing_date_runs.setdefault(session_date, []).append(run_name)

    conn.commit()

    c.execute("SELECT COUNT(*), COUNT(DISTINCT session_date), MIN(session_date), MAX(session_date), COUNT(DISTINCT target) FROM gex_levels")
    print(f"Inserted {inserted_runs} runs ({inserted_rows} target-rows).")
    print("After backfill:", c.fetchone())
    conn.close()


if __name__ == "__main__":
    run_backfill()
