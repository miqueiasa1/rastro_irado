"""
Gera `tests/fixtures/eval_baseline_fixture.db.gz` (fixture reduzida da fase 15).

Fonte: a extração somente leitura usada na auditoria de 10/11/2026
(`%TEMP%\\irai_audit\\irai_extract.db`). Copia só as colunas e linhas que o harness usa:
snapshots M5 não-ghost de WIN$N/WDO$N (sessões 2026-08-01 a 2026-11-10) e barras M5 dos mesmos
símbolos a partir de 2026-07-29. Uso:

  python tests/fixtures/make_eval_fixture.py <caminho_da_extracao>
"""

import gzip
import os
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "eval_baseline_fixture.db.gz")
SNAP_COLS = ["target", "timeframe", "session_date", "timestamp_utc", "p_up", "is_ghost", "created_at",
             "price_diverge_z", "pair_z"]


def main(src: str) -> None:
    uri = "file:" + os.path.abspath(src).replace("\\", "/") + "?mode=ro"
    s = sqlite3.connect(uri, uri=True)
    tmp = os.path.join(tempfile.mkdtemp(), "fixture.db")
    d = sqlite3.connect(tmp)
    d.execute("CREATE TABLE irai_live_snapshots (target TEXT, timeframe TEXT, session_date TEXT, timestamp_utc TEXT, "
              "p_up REAL, is_ghost INTEGER, created_at TEXT, price_diverge_z REAL, pair_z REAL, "
              "PRIMARY KEY (target, timeframe, session_date, timestamp_utc))")
    d.execute("CREATE TABLE market_bars (symbol TEXT, timeframe TEXT, timestamp_utc TEXT, open REAL, close REAL, "
              "PRIMARY KEY (symbol, timeframe, timestamp_utc))")
    rows = s.execute(f"SELECT {', '.join(SNAP_COLS)} FROM irai_live_snapshots WHERE target IN ('WIN$N','WDO$N') "
                     "AND timeframe='M5' AND is_ghost = 0 AND session_date BETWEEN '2026-08-01' AND '2026-11-10'").fetchall()
    d.executemany(f"INSERT INTO irai_live_snapshots VALUES ({','.join('?' * len(SNAP_COLS))})", rows)
    bars = s.execute("SELECT symbol, timeframe, timestamp_utc, open, close FROM market_bars WHERE symbol IN "
                     "('WIN$N','WDO$N') AND timeframe='M5' AND timestamp_utc >= '2026-07-29'").fetchall()
    d.executemany("INSERT INTO market_bars VALUES (?,?,?,?,?)", bars)
    d.commit()
    d.execute("VACUUM")
    d.close()
    s.close()
    with open(tmp, "rb") as fi, gzip.GzipFile(OUT, "wb", mtime=0) as fo:
        shutil.copyfileobj(fi, fo)
    print(f"{len(rows)} snapshots, {len(bars)} barras -> {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main(sys.argv[1])
