"""
Manutenção diária do IRAI (auditoria 28/10/2026 — itens A16, A17 e M2).

1. Backup consistente do SQLite (API de backup, segura com WAL e com os serviços rodando)
   → D:\\irai_backups (ou data\\backups se não houver D:), mantendo as últimas N cópias.
2. Retenção de logs: apaga arquivos em logs\\ com mais de N dias (havia 1,27 GB / 2.017 arquivos).
3. Retenção do Firebase RTDB: remove nós por data mais antigos que N dias
   (series/{data}, summaries/{data}, history/{data}, garch/{data}, overview/{data}, summaries/gex/{data}).

Uso:
    python scripts/daily_maintenance.py               # executa tudo
    python scripts/daily_maintenance.py --dry-run     # só mostra o que faria
Agendado via Agendador de Tarefas: "IRAI Daily Maintenance" (19:15, seg–sex).
"""
import argparse
import os
import re
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, ROOT)

DB_PATH = os.path.join(ROOT, "data", "irai_live.db")
BACKUP_DIR = r"D:\irai_backups" if os.path.exists("D:\\") else os.path.join(ROOT, "data", "backups")
LOG_DIR = os.path.join(ROOT, "logs")

KEEP_BACKUPS = 7
LOG_RETENTION_DAYS = 14
RTDB_RETENTION_DAYS = 60  # o seletor de datas do site lista até 60 sessões
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def backup_db(dry):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dst = os.path.join(BACKUP_DIR, f"irai_live_{datetime.now().strftime('%Y%m%d_%H%M')}.db")
    if dry:
        log(f"[dry] backup → {dst}")
    else:
        t = time.time()
        src = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=60)
        out = sqlite3.connect(dst)
        src.backup(out)
        ok = out.execute("PRAGMA quick_check").fetchone()[0]
        out.close(); src.close()
        log(f"Backup OK ({os.path.getsize(dst) / 1e9:.2f} GB, {time.time() - t:.0f}s, quick_check={ok}) → {dst}")
        if ok != "ok":
            log("ATENÇÃO: quick_check do backup falhou — mantendo backups antigos intactos.")
            return
    backups = sorted(f for f in os.listdir(BACKUP_DIR) if re.match(r"irai_live_\d{8}_\d{4}\.db$", f))
    for old in backups[:-KEEP_BACKUPS]:
        p = os.path.join(BACKUP_DIR, old)
        log(f"{'[dry] ' if dry else ''}removendo backup antigo {old}")
        if not dry:
            os.remove(p)


def prune_logs(dry):
    if not os.path.isdir(LOG_DIR):
        return
    cutoff = time.time() - LOG_RETENTION_DAYS * 86400
    n, size = 0, 0
    for dirpath, _, files in os.walk(LOG_DIR):
        for f in files:
            p = os.path.join(dirpath, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if st.st_mtime < cutoff:
                n += 1; size += st.st_size
                if not dry:
                    try:
                        os.remove(p)
                    except OSError:
                        pass  # arquivo em uso pelo serviço
    log(f"{'[dry] ' if dry else ''}Logs > {LOG_RETENTION_DAYS} dias: {n} arquivos, {size / 1e6:.0f} MB")


def prune_rtdb(dry):
    env_path = os.path.join(ROOT, ".env")
    fb_url = os.environ.get("FIREBASE_URL")
    if not fb_url and os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            if line.startswith("FIREBASE_URL="):
                fb_url = line.split("=", 1)[1].strip()
    sa = os.path.join(ROOT, "serviceAccountKey.json")
    if not fb_url or not os.path.exists(sa):
        log("Firebase não configurado — pulando retenção do RTDB.")
        return
    import firebase_admin
    from firebase_admin import credentials, db
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(sa), {"databaseURL": fb_url})
    cutoff = (date.today() - timedelta(days=RTDB_RETENTION_DAYS)).isoformat()
    total = 0
    for parent in ["series", "summaries", "history", "garch", "overview", "summaries/gex"]:
        keys = db.reference(parent).get(shallow=True) or {}
        old = sorted(k for k in keys if DATE_RE.match(k) and k < cutoff)
        if not old:
            continue
        total += len(old)
        log(f"{'[dry] ' if dry else ''}RTDB {parent}: removendo {len(old)} datas ({old[0]} … {old[-1]})")
        if not dry:
            for k in old:
                db.reference(f"{parent}/{k}").delete()
    log(f"RTDB: {total} nós por data anteriores a {cutoff} {'seriam ' if dry else ''}removidos")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for step in (backup_db, prune_logs, prune_rtdb):
        try:
            step(args.dry_run)
        except Exception as e:
            log(f"ERRO em {step.__name__}: {e}")


if __name__ == "__main__":
    main()
