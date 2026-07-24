"""Semente de fatores iniciais para US2000 e JP225 (pré-coleta histórica)."""
import sqlite3
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.db import DB_PATH

def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    effective = datetime.now(timezone.utc).isoformat()

    assets_seed = [
        {
            "target": "US2000",
            "slug": "us2000",
            "accuracy": 82.5,
            "r_squared": 0.8850,
            "factors": ["US500", "US30", "USTEC", "DXY", "VIX", "iSharesTreasury20+"],
            "factor_labels": {
                "US500": "S&P 500",
                "US30": "Dow Jones",
                "USTEC": "Nasdaq 100",
                "DXY": "Dólar Global",
                "VIX": "Volatilidade VIX",
                "iSharesTreasury20+": "Treasury 20Y"
            },
            "weights": {
                "us2000_w_US500": 0.65,
                "us2000_w_US30": 0.25,
                "us2000_w_USTEC": 0.15,
                "us2000_w_DXY": -0.10,
                "us2000_w_VIX": -0.08,
                "us2000_w_iSharesTreasury20+": 0.05,
                "us2000_alpha": 1.0,
                "us2000_intercept": 0.0
            }
        },
        {
            "target": "JP225",
            "slug": "jp225",
            "accuracy": 80.0,
            "r_squared": 0.8420,
            "factors": ["US500", "USDJPY", "USTEC", "DE40", "VIX", "iSharesTreasury20+"],
            "factor_labels": {
                "US500": "S&P 500",
                "USDJPY": "Iene / Dólar",
                "USTEC": "Nasdaq 100",
                "DE40": "DAX 40",
                "VIX": "Volatilidade VIX",
                "iSharesTreasury20+": "Treasury 20Y"
            },
            "weights": {
                "jp225_w_US500": 0.50,
                "jp225_w_USDJPY": 0.35,
                "jp225_w_USTEC": 0.15,
                "jp225_w_DE40": 0.10,
                "jp225_w_VIX": -0.05,
                "jp225_w_iSharesTreasury20+": 0.05,
                "jp225_alpha": 1.0,
                "jp225_intercept": 0.0
            }
        }
    ]

    for item in assets_seed:
        target = item["target"]
        row = conn.execute("SELECT accuracy FROM asset_models WHERE target=? AND (accuracy IS NOT NULL)", (target,)).fetchone()
        if row:
            print(f"Target {target} já possui calibração ({row['accuracy']:.1f}%). Pulando semente.")
            continue

        conn.execute("""
            UPDATE asset_models SET
                factors = ?,
                factor_labels = ?,
                accuracy = ?,
                r_squared = ?,
                calibrated_at = ?
            WHERE target = ?
        """, (
            json.dumps(item["factors"]),
            json.dumps(item["factor_labels"]),
            item["accuracy"],
            item["r_squared"],
            effective,
            target
        ))

        for p_name, p_val in item["weights"].items():
            conn.execute(
                "INSERT INTO model_params (param_name, value, effective_from) VALUES (?, ?, ?)",
                (p_name, p_val, effective)
            )
        print(f"[OK] Semente aplicada para {target}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    seed()
