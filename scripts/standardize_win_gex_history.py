"""
Auditoria e Padronização Histórica do WIN$N (Índice Futuro) na tabela `gex_levels`

Objetivo:
1. Auditar todas as coletas de WIN$N no banco `irai_live.db`.
2. Corrigir as 7 coletas anômalas (onde o vencimento sem liquidez foi pego antes do filtro MIN_CONTRACTS,
   ou onde o parser unificado do jumba_neologica misturou linhas de WDO com WIN).
3. Padronizar todas as coletas do período dinâmico (22/05/2026 a 06/08/2026) e divergências pontuais
   para a Metodologia Atualizada do Servidor:
   - Modo Ancorado de Custódia: `factor = (1 + r_anchored) ** (27 / 252)`
   - Respeitando a taxa Selic do início de cada ciclo de opções IBOV:
     * Ciclo Maio/Junho 2026 (até 17/06/2026): r = 14.50% -> factor = 1.01461346
     * Ciclo Julho/Agosto 2026 (18/06/2026 a 12/08/2026): r = 14.25% -> factor = 1.01437583
     * Ciclo Setembro/Outubro/Novembro 2026 (13/08/2026 em diante): r = 14.00% -> factor = 1.01413779
   - Garantindo rótulos completos `MAGICWALL * (IBOV <strike>)` em todas as coletas (incluindo Maio/2026).
"""
import os
import re
import sys
import json
import sqlite3

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IRAI_ROOT = os.path.dirname(SCRIPT_DIR)
GEX_REPO_ROOT = os.path.normpath(os.path.join(IRAI_ROOT, "..", "wdo win pair trading"))
DB_PATH = os.path.join(IRAI_ROOT, "data", "irai_live.db")

if GEX_REPO_ROOT not in sys.path:
    sys.path.insert(0, GEX_REPO_ROOT)

from gex.engine.b3_parser import _parse_single_csv
from gex.engine.walls_calculator import calculate_gex_profile


def get_anchored_selic_for_date(session_date: str, run_name: str) -> float:
    """
    Retorna a Selic ancorada (r_anchored) do início do ciclo de opções vigente na data:
    - Até 17/06/2026 (Ciclos Mai/26 e Jun/26): 14.50% (0.1450)
    - De 18/06/2026 até 12/08/2026 (Ciclos Jul/26 e Ago/26): 14.25% (0.1425)
    - De 13/08/2026 em diante (Ciclos Set/26, Out/26 e Nov/26): 14.00% (0.1400)
    """
    if session_date < "2026-06-18":
        return 0.1450
    elif session_date < "2026-08-13":
        return 0.1425
    else:
        return 0.1400


def get_anchored_factor(r_anchored: float) -> float:
    return (1.0 + r_anchored) ** (27.0 / 252.0)


def convert_walls_to_irai_format(walls):
    """Converte a saída do calculate_gex_profile para o schema JSON do gex_levels no IRAI."""
    out = []
    for w in sorted(walls, key=lambda x: x['price']):
        w_type = w['type']
        p = round(float(w['price']), 3)
        width = int(w.get('width', 1))
        if w_type == 'Wall':
            stars = '*' * width
            strike = int(w.get('strike_ibov', round(p / 1.014)))
            lbl = f"MAGICWALL {stars} (IBOV {strike})"
            col = "#00e676"
            st = "solid"
            t_type = "wall"
        elif w_type == 'MidWall':
            lbl = "MIDLEWALL"
            col = "#90a4ae"
            st = "dashed"
            t_type = "mid_wall"
        elif w_type == 'GammaFlip':
            lbl = "GAMMA FLIP (Pivot)"
            col = "#ffd600"
            st = "solid"
            t_type = "gamma_flip"
        elif w_type == 'MaxGamma':
            lbl = "MAX GAMMA (Teto)"
            col = "#00b0ff"
            st = "solid"
            t_type = "max_gamma"
        elif w_type == 'MinGamma':
            lbl = "MIN GAMMA (Piso)"
            col = "#ff1744"
            st = "solid"
            t_type = "min_gamma"
        else:
            continue
        out.append({
            "price": p,
            "label": lbl,
            "color": col,
            "width": width,
            "style": st,
            "type": t_type,
        })
    return out


def recalculate_from_b3_csv(csv_filename, current_win, current_ibov, r_anchored, expiry_days=20):
    csv_path = os.path.join(GEX_REPO_ROOT, "gex", "data", csv_filename)
    df = _parse_single_csv(csv_path)
    if df.empty:
        raise RuntimeError(f"Empty DataFrame from {csv_path}")
    # Fix expiry year if b3_parser used datetime.now().month (10) on a historical CSV (e.g. June/July/August 2026)
    m_date = re.search(r"(\d{2})-(\d{2})-(\d{4})", csv_filename)
    if m_date:
        csv_day, csv_month, csv_year = int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3))
        csv_date_iso = f"{csv_year:04d}-{csv_month:02d}-{csv_day:02d}"
        def fix_exp(exp_str):
            y = int(exp_str[:4])
            m = int(exp_str[5:7])
            # If b3_parser bumped a 2026 month (>= csv_month) to 2027 because now().month is 10:
            if y == csv_year + 1 and m >= csv_month:
                from gex.engine.b3_parser import _get_ibov_expiration
                return _get_ibov_expiration(csv_year, m).isoformat()
            return exp_str
        df['expiry'] = df['expiry'].apply(fix_exp)
        df = df[df['expiry'].str[:10] > csv_date_iso].copy()
    # Filter out absurd strikes (< 100000) that caused the 49000 or 2000 strike bug
    df = df[df['strike'] >= 100000].copy()
    walls = calculate_gex_profile(
        options_df=df,
        current_win=current_win,
        current_ibov=current_ibov,
        iv=0.20,
        expiry_days=expiry_days,
        r=r_anchored,
        use_anchored_factor=True
    )
    return convert_walls_to_irai_format(walls)


def standardize_win_levels():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. Remove the two broken intermediate commit runs that were immediately superseded minutes later:
    # - 2026-06-24 13:00 (commit 2be3a971 which only unified WDO+WIN in jumba_neologica; 12:54 already has the full 10-asset run)
    # - 2026-07-28 08:30 (commit c2820669 which had unformatted raw levels; 07:34 and 16:47 have the full runs)
    c.execute("DELETE FROM gex_levels WHERE session_date = '2026-06-24' AND run_name = '13:00'")
    c.execute("DELETE FROM gex_levels WHERE session_date = '2026-07-28' AND run_name = '08:30'")

    # 2. Recalculate the 5 expiry-rollover / outlier-strike runs from the official B3 CSVs using the updated anchored methodology:
    recalc_specs = [
        # (session_date, run_name, b3_csv_name, win_spot, ibov_spot, expiry_days)
        ("2026-06-18", "07:33", "Posições em aberto-17-06-2026.csv", 169500.0, 168000.0, 21),
        ("2026-07-16", "18:03", "Posições em aberto-15-07-2026.csv", 174500.0, 173000.0, 21),
        ("2026-07-17", "07:31", "Posições em aberto-15-07-2026.csv", 174500.0, 173000.0, 21),
        ("2026-08-13", "07:37", "Posições em aberto-12-08-2026.csv", 167000.0, 165000.0, 22),
        ("2026-09-29", "07:43", "Posições em aberto-28-09-2026.csv", 182500.0, 180000.0, 12),
    ]
    for s_date, r_name, csv_name, f_win, s_ibov, exp_d in recalc_specs:
        r_anc = get_anchored_selic_for_date(s_date, r_name)
        new_levels = recalculate_from_b3_csv(csv_name, f_win, s_ibov, r_anc, exp_d)
        c.execute(
            "UPDATE gex_levels SET levels_json = ? WHERE session_date = ? AND run_name = ? AND target = 'WIN$N'",
            (json.dumps(new_levels, ensure_ascii=False), s_date, r_name)
        )
        print(f"[RECALC CSV] {s_date} {r_name} recalculado com sucesso ({len(new_levels)} niveis, r={r_anc*100:.2f}%).")

    # 3. Rescale all remaining WIN$N runs to the exact Anchored Custody Factor of their respective Selic cycle
    c.execute("SELECT session_date, run_name, levels_json FROM gex_levels WHERE target = 'WIN$N' ORDER BY session_date ASC, run_name ASC")
    rows = c.fetchall()

    rescaled_count = 0
    labels_upgraded_count = 0

    for session_date, run_name, levels_json in rows:
        levels = json.loads(levels_json)
        walls = [l for l in levels if l.get('type') == 'wall']

        r_target = get_anchored_selic_for_date(session_date, run_name)
        f_target = get_anchored_factor(r_target)

        # Infer current factor from walls
        factors = []
        for w in walls:
            lbl = w.get('label', '')
            m = re.search(r'IBOV\s+(\d+)', lbl)
            if m:
                s = int(m.group(1))
                if s >= 100000:
                    factors.append(float(w['price']) / s)

        if not factors and len(walls) >= 2:
            diffs = [
                walls[i+1]['price'] - walls[i]['price']
                for i in range(len(walls) - 1)
                if 990 < (walls[i+1]['price'] - walls[i]['price']) < 1050
            ]
            if diffs:
                factors.append(sum(diffs) / len(diffs) / 1000.0)

        if not factors:
            continue

        old_f = sum(factors) / len(factors)
        needs_factor_update = abs(old_f - f_target) > 1e-5
        needs_label_update = any('IBOV' not in w.get('label', '') or w.get('label', '').startswith('WALL ') for w in walls)

        if not needs_factor_update and not needs_label_update:
            continue

        # Update walls first so MidWalls can be exact midpoints
        new_levels = []
        updated_walls = []

        for l in levels:
            l_copy = dict(l)
            l_type = l_copy.get('type')
            old_p = float(l_copy['price'])

            if l_type == 'wall':
                lbl = l_copy.get('label', '')
                m = re.search(r'IBOV\s+(\d+)', lbl)
                if m:
                    strike_ibov = int(m.group(1))
                else:
                    strike_ibov = int(round((old_p / old_f) / 1000.0) * 1000)

                new_p = round(strike_ibov * f_target, 3)
                l_copy['price'] = new_p
                stars = '*' * int(l_copy.get('width', 1))
                l_copy['label'] = f"MAGICWALL {stars} (IBOV {strike_ibov})"
                updated_walls.append(l_copy)
                new_levels.append(l_copy)
            elif l_type in ('gamma_flip', 'max_gamma', 'min_gamma'):
                # Scale exact IBOV equivalent by (f_target / old_f)
                new_p = round(old_p * (f_target / old_f), 3)
                l_copy['price'] = new_p
                new_levels.append(l_copy)

        # Recompute MidWalls as exact midpoints between consecutive sorted walls
        updated_walls.sort(key=lambda x: x['price'])
        for i in range(len(updated_walls) - 1):
            mid_p = round((updated_walls[i]['price'] + updated_walls[i+1]['price']) / 2.0, 3)
            new_levels.append({
                "price": mid_p,
                "label": "MIDLEWALL",
                "color": "#90a4ae",
                "width": 1,
                "style": "dashed",
                "type": "mid_wall",
            })

        new_levels.sort(key=lambda x: x['price'])

        c.execute(
            "UPDATE gex_levels SET levels_json = ? WHERE session_date = ? AND run_name = ? AND target = 'WIN$N'",
            (json.dumps(new_levels, ensure_ascii=False), session_date, run_name)
        )
        if needs_factor_update:
            rescaled_count += 1
        elif needs_label_update:
            labels_upgraded_count += 1

    conn.commit()
    print(f"\nPadronizacao concluida:")
    print(f"  - Coletas reescaladas do modo dinamico/divergente para Ancorado (27d): {rescaled_count}")
    print(f"  - Coletas de Maio/2026 com rotulos IBOV padronizados: {labels_upgraded_count}")
    conn.close()


if __name__ == "__main__":
    standardize_win_levels()
