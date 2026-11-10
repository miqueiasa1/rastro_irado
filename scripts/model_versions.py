"""
Operação explícita e auditável das versões de modelo (fase 16, REQ-P06).

    python scripts/model_versions.py --db <banco> list [--target WIN$N]
    python scripts/model_versions.py --db <banco> show <version_id>
    python scripts/model_versions.py --db <banco> events [<version_id>]
    python scripts/model_versions.py --db <banco> promote <version_id> --effective-from AAAA-MM-DD --actor danh
    python scripts/model_versions.py --db <banco> reject <version_id> --actor danh

promote: shadow → active a partir de uma sessão FUTURA; a active anterior vira 'retired' com
effective_to = effective_from. Nunca é automático. Gravar no banco de produção exige --confirm-live.
"""
import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import DB_PATH, get_connection
from backend.irai import model_registry


def main():
    ap = argparse.ArgumentParser(description="Versões de modelo (fase 16)")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--confirm-live", action="store_true", help="Necessário para gravar no banco de produção")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("--target")
    p = sub.add_parser("show"); p.add_argument("version_id")
    p = sub.add_parser("events"); p.add_argument("version_id", nargs="?")
    p = sub.add_parser("promote"); p.add_argument("version_id"); p.add_argument("--effective-from", required=True)
    p.add_argument("--actor", required=True); p.add_argument("--notes"); p.add_argument("--allow-today", action="store_true")
    p = sub.add_parser("reject"); p.add_argument("version_id"); p.add_argument("--actor", required=True); p.add_argument("--notes")
    args = ap.parse_args()

    writes = args.cmd in ("promote", "reject")
    is_live = os.path.normcase(os.path.abspath(args.db)) == os.path.normcase(os.path.abspath(DB_PATH))
    if writes and is_live and not args.confirm_live:
        print("[ABORT] escrita no banco de produção exige --confirm-live (somente com aprovação explícita).")
        sys.exit(2)
    conn = get_connection(args.db)
    try:
        if not model_registry.has_registry(conn):
            print("[ABORT] migração da fase 16 não aplicada neste banco.")
            sys.exit(2)
        if args.cmd == "list":
            slug = None
            if args.target:
                row = conn.execute("SELECT slug FROM asset_models WHERE target=?", (args.target,)).fetchone()
                slug = row["slug"] if row else args.target.lower()
            out = model_registry.list_versions(conn, slug=slug)
        elif args.cmd == "show":
            out = model_registry.get_version(conn, args.version_id, with_artifact=True)
        elif args.cmd == "events":
            out = model_registry.list_events(conn, args.version_id)
        elif args.cmd == "promote":
            out = model_registry.promote(conn, args.version_id, args.effective_from, actor=args.actor,
                                         notes=args.notes, allow_today=args.allow_today)
            conn.commit()
        elif args.cmd == "reject":
            model_registry.reject(conn, args.version_id, actor=args.actor, notes=args.notes)
            conn.commit()
            out = {"rejected": args.version_id}
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
