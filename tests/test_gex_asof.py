"""Fase 20 — escolha do GEX as-of (CSV oficial + fallback gex_levels antes de 09:00)."""
import json
import os
import sqlite3
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.irai import gex_asof as G  # noqa: E402


def _csv(tmp_path):
    p = tmp_path / "h.csv"
    p.write_text("session_date;type;price;width\n"
                 "2026-01-02;Wall;100.0;1\n2026-01-02;MidWall;105.0;1\n2026-01-02;Wall;110.0;2\n"
                 "2026-01-02;Wall;120.0;3\n2026-01-02;MaxGamma;130.0;3\n2026-01-02;MinGamma;90.0;3\n"
                 "2026-01-02;GammaFlip;110.0;2\n2026-05-23;Wall;100.0;3\n", encoding="utf-8")
    return str(p)


def _db(rows):
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE gex_levels (session_date TEXT, target TEXT, run_name TEXT, levels_json TEXT, updated_at TEXT)")
    for r in rows:
        c.execute("INSERT INTO gex_levels VALUES (?,?,?,?,?)", r)
    return c


def test_csv_types_and_widths(tmp_path):
    d = G.load_gex_csv(_csv(tmp_path))
    assert set(d) == {"2026-01-02", "2026-05-23"}
    types = {x["type"] for x in d["2026-01-02"]}
    assert types == {"wall", "mid_wall", "max_gamma", "min_gamma", "gamma_flip"}
    with pytest.raises(ValueError):
        G.norm_type("CallWall")


def test_db_first_run_before_open_only():
    lv = lambda p: json.dumps([{"price": p, "type": "gamma_flip", "width": 2}])
    c = _db([("2026-06-01", "WIN$N", "07:30", lv(1), "2026-06-01 10:30:00"),
             ("2026-06-01", "WIN$N", "08:15", lv(2), "2026-06-01 11:15:00"),
             ("2026-06-01", "WIN$N", "18:05", lv(3), "2026-06-01 21:05:00"),
             ("2026-06-02", "WIN$N", "09:13", lv(4), "2026-06-02 12:13:00"),
             ("2026-06-03", "WIN$N", "default", lv(5), "2026-06-03 10:00:00")])
    d = G.load_gex_db_preopen(c, "WIN$N")
    assert d["2026-06-01"]["run_name"] == "07:30" and d["2026-06-01"]["levels"][0]["price"] == 1
    assert "2026-06-02" not in d          # só run depois da abertura → sai
    assert "2026-06-03" not in d          # run sem horário não serve


def test_history_prefers_csv_and_excludes_weekends(tmp_path):
    csvl = G.load_gex_csv(_csv(tmp_path))
    db = {"2026-01-02": {"run_name": "07:00", "levels": [{"type": "wall", "price": 1.0, "width": 3}]},
          "2026-06-01": {"run_name": "07:30", "levels": [{"type": "wall", "price": 2.0, "width": 3}]}}
    h = G.build_gex_history(csvl, db, exclude=("2026-05-23",))
    assert h["2026-01-02"]["source"] == "csv"
    assert h["2026-06-01"]["source"] == "db"
    assert "2026-05-23" not in h          # sábado / excluído
    assert G.is_weekend("2026-05-23")


def test_primary_levels_and_merge(tmp_path):
    lv = G.load_gex_csv(_csv(tmp_path))["2026-01-02"]
    p = G.primary_levels(lv, 2)
    assert [x["price"] for x in p] == [90.0, 110.0, 120.0, 130.0]     # 100 (1★) e mid fora; 110 duplicado → 1
    m = G.merge_levels(p, h_ref=3.0, open_price=111.0)
    assert len(m) == 4
    m2 = G.merge_levels(p, h_ref=6.0, open_price=111.0)            # 110–120–130 em cadeia (≤ 12) → um grupo
    assert [x["price"] for x in m2] == [90.0, 120.0]                # maior width (3★), empate → mais perto da abertura
    assert m2[1]["merged"] == 3
    assert G.grid_spacing(lv) == 5.0