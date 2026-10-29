"""
Migração única: converte o histórico B3 (source='br') de BRT para o relógio do broker.

Contexto (auditoria 28/10/2026):
  - Até 28/07/2026 o collector gravava barras da B3 em horário de Brasília (09:00–18:30).
  - A partir de 08/08/2026 passou a gravar no relógio do broker (NY+7), somando +6h fixo.
  - Entre 29/07 e 07/08 as duas versões rodaram juntas (dias "misturados").
  - Os fatores (Tickmill/Axi) sempre estiveram no relógio do broker → o histórico B3 em BRT
    ficava desalinhado 5–6h dos fatores (afeta calibração, Kalman e z-scores históricos).

Regras:
  - Dias < 2026-07-29: todas as barras são BRT → converter com offset dinâmico
    (+6h no verão americano, +5h no inverno americano). Ver backend/timeconv.py.
  - Dias 2026-07-29..2026-08-07 (misturados), por horário gravado:
      * 09:00–14:55            → BRT (o relógio do broker nunca grava a B3 nesse intervalo)
      * 18:35–23:55, 00:00–00:30 → já no relógio do broker
      * 15:00–18:30 (ambíguo)  → é cópia no relógio do broker se o OHLC for idêntico ao da barra
                                  BRT de 6h antes; caso contrário, é BRT
  - Dias >= 2026-08-08: já no relógio do broker → não mexe.
  - D1 não é alterado (semântica de data).
  - Colisões após conversão: INSERT OR IGNORE, priorizando as linhas que já estavam no relógio do broker.

Uso:
  python scripts/migrate_b3_broker_time.py --db data/irai_live.db            # dry-run (não grava)
  python scripts/migrate_b3_broker_time.py --db data/irai_live.db --apply    # aplica (faça BACKUP antes)
"""
import argparse
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.timeconv import brt_wall_to_broker_wall

MIXED_START = "2026-07-29"
BROKER_ERA_START = "2026-08-08"
TIMEFRAMES = ("M1", "M2", "M5", "M15", "M30", "H1")
# Apenas s?mbolos com hist?rico 100% no padr?o BRT (verificado). A??es e IV_ATM t?m poucas linhas
# e padr?o amb?guo ? ficam como est?o.
SYMBOLS = ("WIN$N", "WDO$N", "DI1$N", "DOL$N")
COLS = ("symbol", "source", "timeframe", "timestamp_utc", "open", "high", "low", "close",
        "volume", "real_volume", "delta")


def _parse(ts):
    return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")


def _fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_broker(ts):
    return _fmt(brt_wall_to_broker_wall(_parse(ts)))


def _ohlc(r):
    return (r["open"], r["high"], r["low"], r["close"])


def plan_symbol_tf(rows):
    """Retorna (broker_origin, brt_converted, stats) — listas de dicts com timestamp final."""
    stats = Counter()
    by_ts = {r["timestamp_utc"][:19]: r for r in rows}
    broker_origin, brt_converted = [], []
    for r in rows:
        ts = r["timestamp_utc"]
        day, hhmm = ts[:10], ts[11:16]
        if day < MIXED_START:
            brt_converted.append({**r, "timestamp_utc": _to_broker(ts)})
            stats["brt_era"] += 1
            continue
        # Dia misturado
        if "09:00" <= hhmm <= "14:55":
            brt_converted.append({**r, "timestamp_utc": _to_broker(ts)})
            stats["mixed_brt"] += 1
        elif hhmm >= "18:35" or hhmm <= "00:30":
            broker_origin.append(dict(r))
            stats["mixed_broker"] += 1
        else:
            twin = by_ts.get(_fmt(_parse(ts) - timedelta(hours=6))[:19])
            if twin is not None and _ohlc(twin) == _ohlc(r):
                broker_origin.append(dict(r))
                stats["mixed_ambig_broker"] += 1
            else:
                brt_converted.append({**r, "timestamp_utc": _to_broker(ts)})
                stats["mixed_ambig_brt"] += 1
    return broker_origin, brt_converted, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")

    total = Counter()
    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            rows = [dict(r) for r in conn.execute(
                f"SELECT rowid AS _rid, {', '.join(COLS)} FROM market_bars "
                "WHERE source='br' AND symbol=? AND timeframe=? AND timestamp_utc < ? "
                "ORDER BY timestamp_utc", (sym, tf, BROKER_ERA_START))]
            if not rows:
                continue
            broker_origin, brt_converted, stats = plan_symbol_tf(rows)
            total.update(stats)
            if not args.apply:
                continue
            with conn:
                conn.executemany("DELETE FROM market_bars WHERE rowid=?", [(r["_rid"],) for r in rows])
                placeholders = ",".join("?" * len(COLS))
                inserted = 0
                for batch in (broker_origin, brt_converted):
                    cur = conn.executemany(
                        f"INSERT OR IGNORE INTO market_bars ({', '.join(COLS)}) VALUES ({placeholders})",
                        [tuple(r[c] for c in COLS) for r in batch])
                    inserted += cur.rowcount
                total["inserted"] += inserted
                total["dropped_dupes"] += len(rows) - inserted
        print(f"  {sym}: ok", flush=True)

    print("\nResumo:", dict(total))
    if not args.apply:
        print("DRY-RUN: nada foi gravado. Use --apply após fazer backup do banco.")
    conn.close()


if __name__ == "__main__":
    main()
