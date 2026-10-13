"""Online SQLite backups with integrity checks and retention."""
import argparse
import os
import shutil
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from . import store

BACKUP_DIR=Path(os.environ.get("TABLIO_BACKUP_PATH",store.ROOT / "backups"))


def create_backup():
    if not store.DB_PATH.is_file(): raise FileNotFoundError("La base de Tablio todavía no existe.")
    BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    if os.name!="nt": os.chmod(BACKUP_DIR,0o700)
    name="tablio-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]+".sqlite3"
    target=BACKUP_DIR/name
    temporary=BACKUP_DIR/(name+".tmp")
    try:
        source_uri=f"file:{store.DB_PATH.resolve().as_posix()}?mode=ro"
        with closing(sqlite3.connect(source_uri,uri=True)) as source, closing(sqlite3.connect(temporary)) as destination:
            source.backup(destination)
            if destination.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise RuntimeError("La copia no superó integrity_check.")
        if os.name!="nt": os.chmod(temporary,0o600)
        temporary.replace(target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def verify_backup(path):
    path=Path(path).resolve()
    if not path.is_file() or path.suffix!=".sqlite3": raise ValueError("Elegí un archivo de backup SQLite.")
    uri=f"file:{path.as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri,uri=True)) as db:
        return db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"


def prune(days):
    cutoff=time.time()-days*86400
    for path in BACKUP_DIR.glob("tablio-*.sqlite3"):
        if path.stat().st_mtime<cutoff: path.unlink()


def backup_status(max_age_hours=36):
    files=sorted(BACKUP_DIR.glob("tablio-*.sqlite3"),key=lambda p:p.stat().st_mtime,reverse=True) if BACKUP_DIR.exists() else []
    if not files: return {"ok":False,"message":"No hay copias de seguridad."}
    latest=files[0]
    age_hours=(time.time()-latest.stat().st_mtime)/3600
    if age_hours>max_age_hours: return {"ok":False,"message":"La última copia es demasiado antigua.","path":str(latest),"ageHours":round(age_hours,1)}
    if not verify_backup(latest): return {"ok":False,"message":"La última copia no es íntegra.","path":str(latest)}
    return {"ok":True,"message":"La última copia es reciente e íntegra.","path":str(latest),"ageHours":round(age_hours,1)}


def restore_backup(path):
    if not verify_backup(path): raise ValueError("Backup inválido; no se restauró la base.")
    store.DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    if store.DB_PATH.exists():
        safety=create_backup()
        print(f"Copia previa a la restauración: {safety}",flush=True)
    temporary=store.DB_PATH.with_name(store.DB_PATH.name+".restore.tmp")
    try:
        shutil.copy2(path,temporary)
        with closing(sqlite3.connect(f"file:{temporary.resolve().as_posix()}?mode=ro",uri=True)) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok": raise ValueError("La copia temporal no es íntegra.")
        if os.name!="nt": os.chmod(temporary,0o600)
        temporary.replace(store.DB_PATH)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description="Copias de seguridad de Tablio")
    parser.add_argument("command",choices=("create","verify","loop","restore","status"))
    parser.add_argument("path",nargs="?")
    parser.add_argument("--retention-days",type=int,default=30)
    parser.add_argument("--interval-hours",type=float,default=24)
    parser.add_argument("--max-age-hours",type=float,default=36)
    parser.add_argument("--force",action="store_true")
    args=parser.parse_args()
    if args.command=="status":
        import json
        result=backup_status(args.max_age_hours)
        print(json.dumps(result,ensure_ascii=False))
        if not result["ok"]: raise SystemExit(1)
    elif args.command=="verify":
        if not args.path: parser.error("verify requiere una ruta")
        if not verify_backup(args.path): raise SystemExit("Backup inválido.")
        print("Backup íntegro.")
    elif args.command=="create":
        print(create_backup())
        prune(args.retention_days)
    elif args.command=="restore":
        if not args.path or not args.force: parser.error("restore requiere ruta y --force; detené primero la aplicación")
        restore_backup(args.path)
        print("Backup restaurado.")
    else:
        if args.interval_hours<=0: parser.error("El intervalo debe ser positivo")
        while True:
            print(create_backup(),flush=True)
            prune(args.retention_days)
            time.sleep(args.interval_hours*3600)


if __name__=="__main__": main()
