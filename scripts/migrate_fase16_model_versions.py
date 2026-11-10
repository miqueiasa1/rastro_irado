"""
Migração da fase 16 (v2.0): registro imutável de versões de modelo + anti-repaint.

Aditiva e idempotente: só CREATE TABLE/INDEX/TRIGGER IF NOT EXISTS e ALTER TABLE ADD COLUMN.
Nenhum DROP, DELETE ou UPDATE de dados existentes. Em seguida adota os parâmetros atuais
(caminho legado) como a primeira versão 'active' de cada alvo ativo (bootstrap).

Tudo roda em UMA transação: ou aplica tudo, ou nada (``--dry-run`` sempre faz ROLLBACK).

Uso:
    python scripts/migrate_fase16_model_versions.py --db %TEMP%\\copia.db            # cópia
    python scripts/migrate_fase16_model_versions.py --db data\\irai_live.db --dry-run --confirm-live
    python scripts/migrate_fase16_model_versions.py --db data\\irai_live.db --confirm-live   # produção (com aprovação)

Reverter (se necessário): os objetos novos podem ser removidos manualmente
(DROP TRIGGER trg_*; DROP TABLE model_versions, model_version_events). As colunas novas
ficam (NULL) e são ignoradas pelo código antigo.
"""
import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import DB_PATH
from backend.irai import model_registry


def _counts(conn) -> dict:
    out = {}
    for t in ("model_params", "asset_models", "kalman_state", "irai_live_snapshots",
              "model_versions", "model_version_events"):
        if model_registry.table_exists(conn, t):
            out[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return out


def _objects(conn) -> set:
    return {(r[0], r[1]) for r in conn.execute("SELECT type, name FROM sqlite_master")}


def migrate(db_path: str, dry_run: bool = False, bootstrap: bool = True, count_rows: bool = True) -> dict:
    conn = sqlite3.connect(db_path, timeout=60, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")
    report = {"db": os.path.abspath(db_path), "dry_run": dry_run}
    try:
        if not model_registry.table_exists(conn, "model_params") or not model_registry.table_exists(conn, "asset_models"):
            raise SystemExit("banco sem model_params/asset_models — init_db não aplicado?")
        objs_before = _objects(conn)
        before = _counts(conn) if count_rows else {}
        conn.execute("BEGIN IMMEDIATE")
        changes = model_registry.ensure_schema(conn)
        boot = []
        if bootstrap:
            boot = model_registry.bootstrap_from_legacy(conn, git_sha=model_registry.code_git_sha())
        after = _counts(conn) if count_rows else {}
        objs_after = _objects(conn)
        missing = objs_before - objs_after
        if missing:
            raise RuntimeError(f"migração removeria objetos: {sorted(missing)}")
        for t, n in before.items():
            if after.get(t, 0) < n:
                raise RuntimeError(f"migração reduziria linhas de {t}: {n} -> {after.get(t)}")
        if dry_run:
            conn.execute("ROLLBACK")
        else:
            conn.execute("COMMIT")
        report.update({"schema_changes": changes, "bootstrap": boot,
                       "rows_before": before, "rows_after": after})
        return report
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description="Migração aditiva da fase 16 (versionamento de parâmetros)")
    ap.add_argument("--db", required=True, help="Caminho do banco SQLite")
    ap.add_argument("--dry-run", action="store_true", help="Executa tudo e faz ROLLBACK (não grava)")
    ap.add_argument("--no-bootstrap", action="store_true", help="Só schema, sem registrar a versão atual")
    ap.add_argument("--confirm-live", action="store_true",
                    help="Obrigatório para o banco de produção (data/irai_live.db) — só com aprovação do usuário")
    ap.add_argument("--no-count", action="store_true", help="Não contar linhas (evita varrer tabelas grandes)")
    args = ap.parse_args()

    if os.path.normcase(os.path.abspath(args.db)) == os.path.normcase(os.path.abspath(DB_PATH)) and not args.confirm_live:
        print("[ABORT] --db aponta para o banco de produção. Use --confirm-live (somente com aprovação explícita).")
        sys.exit(2)
    if not os.path.exists(args.db):
        print(f"[ABORT] banco não encontrado: {args.db}")
        sys.exit(2)
    rep = migrate(args.db, dry_run=args.dry_run, bootstrap=not args.no_bootstrap, count_rows=not args.no_count)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print("DRY-RUN: nada foi gravado (ROLLBACK)." if args.dry_run else "Migração aplicada (COMMIT).")


if __name__ == "__main__":
    main()
