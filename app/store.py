"""SQLite persistence with organization-scoped access and V0 migration."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .security import hash_password, new_token, token_hash, verify_password

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("TABLIO_DB_PATH", ROOT / "data" / "tablio.sqlite3"))
ROLES = {"owner", "admin", "editor", "viewer"}
WRITE_ROLES = {"owner", "admin", "editor"}
MANAGE_ROLES = {"owner", "admin"}


@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt": os.chmod(DB_PATH.parent, 0o700)
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=30000")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        if DB_PATH.exists() and os.name != "nt": os.chmod(DB_PATH, 0o600)


def _has_column(db, table, column):
    return any(row["name"] == column for row in db.execute(f"PRAGMA table_info({table})"))


def initialize():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS organizations (id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,name TEXT NOT NULL,password_hash TEXT NOT NULL,disabled INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS memberships (user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,role TEXT NOT NULL CHECK(role IN ('owner','admin','editor','viewer')),PRIMARY KEY(user_id,organization_id));
        CREATE INDEX IF NOT EXISTS memberships_org ON memberships(organization_id);
        CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,csrf_token TEXT NOT NULL,expires_at INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS sessions_expires ON sessions(expires_at);
        CREATE TABLE IF NOT EXISTS modules (id TEXT PRIMARY KEY,name TEXT NOT NULL,schema_json TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY,module_id TEXT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,values_json TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS records_module ON records(module_id);
        CREATE TABLE IF NOT EXISTS imports (id TEXT PRIMARY KEY,module_id TEXT NOT NULL REFERENCES modules(id),created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS pending_uploads (token TEXT PRIMARY KEY,organization_id TEXT NOT NULL REFERENCES organizations(id),user_id TEXT NOT NULL REFERENCES users(id),expires_at INTEGER NOT NULL);
        """)
        if not _has_column(db,"modules","organization_id"):
            db.execute("ALTER TABLE modules ADD COLUMN organization_id TEXT REFERENCES organizations(id)")
        if not _has_column(db,"imports","organization_id"):
            db.execute("ALTER TABLE imports ADD COLUMN organization_id TEXT REFERENCES organizations(id)")
        if db.execute("SELECT 1 FROM modules WHERE organization_id IS NULL LIMIT 1").fetchone():
            existing = db.execute("SELECT id FROM organizations WHERE name='Legado V0' LIMIT 1").fetchone()
            org_id = existing["id"] if existing else str(uuid.uuid4())
            if not existing: db.execute("INSERT INTO organizations(id,name) VALUES(?,?)",(org_id,"Legado V0"))
            db.execute("UPDATE modules SET organization_id=? WHERE organization_id IS NULL",(org_id,))
            db.execute("UPDATE imports SET organization_id=? WHERE organization_id IS NULL",(org_id,))
        db.execute("CREATE INDEX IF NOT EXISTS modules_org ON modules(organization_id)")
        db.execute("CREATE INDEX IF NOT EXISTS imports_org ON imports(organization_id)")


def _email(value):
    value = str(value or "").strip().casefold()
    if not 3 <= len(value) <= 254 or "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValueError("Ingresá un email válido.")
    return value


def _name(value):
    value = str(value or "").strip()
    if not 1 <= len(value) <= 80: raise ValueError("Ingresá un nombre de 1 a 80 caracteres.")
    return value


def has_users():
    with connection() as db: return db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None


def bootstrap_owner(email,name,password,organization="Mi organización"):
    email,name,organization = _email(email),_name(name),_name(organization)
    hashed = hash_password(password)
    with connection() as db:
        if db.execute("SELECT 1 FROM users LIMIT 1").fetchone(): raise ValueError("Ya existe un usuario.")
        user_id = str(uuid.uuid4())
        org = db.execute("SELECT id FROM organizations WHERE name='Legado V0' LIMIT 1").fetchone()
        org_id = org["id"] if org else str(uuid.uuid4())
        if org: db.execute("UPDATE organizations SET name=? WHERE id=?",(organization,org_id))
        else: db.execute("INSERT INTO organizations(id,name) VALUES(?,?)",(org_id,organization))
        db.execute("INSERT INTO users(id,email,name,password_hash) VALUES(?,?,?,?)",(user_id,email,name,hashed))
        db.execute("INSERT INTO memberships(user_id,organization_id,role) VALUES(?,?,'owner')",(user_id,org_id))
        return user_id,org_id


def authenticate(email,password):
    try: email = _email(email)
    except ValueError: return None
    with connection() as db:
        row = db.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if not row or row["disabled"] or not verify_password(password,row["password_hash"]): return None
        token,csrf = new_token(),new_token()
        db.execute("INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at) VALUES(?,?,?,?)",(token_hash(token),row["id"],csrf,int(time.time())+12*3600))
        return token,csrf,row["id"]


def session_user(token):
    if not token: return None
    try: hashed = token_hash(token)
    except (ValueError,UnicodeEncodeError): return None
    with connection() as db:
        row = db.execute("""SELECT s.csrf_token,s.expires_at,u.id,u.email,u.name,u.disabled FROM sessions s
            JOIN users u ON u.id=s.user_id WHERE s.token_hash=?""",(hashed,)).fetchone()
        return dict(row) if row and not row["disabled"] and row["expires_at"]>int(time.time()) else None


def logout(token):
    if token:
        with connection() as db: db.execute("DELETE FROM sessions WHERE token_hash=?",(token_hash(token),))


def change_password(user_id,current_password,new_password):
    hashed=hash_password(new_password)
    with connection() as db:
        row=db.execute("SELECT password_hash FROM users WHERE id=? AND disabled=0",(user_id,)).fetchone()
        if not row or not verify_password(current_password,row["password_hash"]):
            raise ValueError("La contraseña actual es incorrecta.")
        db.execute("UPDATE users SET password_hash=? WHERE id=?",(hashed,user_id))
        db.execute("DELETE FROM sessions WHERE user_id=?",(user_id,))


def memberships(user_id):
    with connection() as db:
        return [dict(row) for row in db.execute("""SELECT o.id,o.name,m.role FROM memberships m JOIN organizations o
            ON o.id=m.organization_id WHERE m.user_id=? ORDER BY o.created_at,o.id""",(user_id,))]


def role_for(user_id,org_id):
    with connection() as db:
        row=db.execute("SELECT role FROM memberships WHERE user_id=? AND organization_id=?",(user_id,org_id)).fetchone()
        return row["role"] if row else None


def create_organization(user_id,name):
    org_id=str(uuid.uuid4())
    with connection() as db:
        db.execute("INSERT INTO organizations(id,name) VALUES(?,?)",(org_id,_name(name)))
        db.execute("INSERT INTO memberships(user_id,organization_id,role) VALUES(?,?,'owner')",(user_id,org_id))
    return org_id


def users_for_org(org_id):
    with connection() as db:
        return [dict(row) for row in db.execute("""SELECT u.id,u.email,u.name,u.disabled,m.role FROM memberships m
            JOIN users u ON u.id=m.user_id WHERE m.organization_id=? ORDER BY u.email""",(org_id,))]


def create_user_in_org(org_id,email,name,password,role):
    if role not in {"admin","editor","viewer"}: raise ValueError("Rol inválido.")
    email,name,hashed=_email(email),_name(name),hash_password(password)
    with connection() as db:
        if db.execute("SELECT 1 FROM users WHERE email=?",(email,)).fetchone(): raise ValueError("El email ya existe. Agregá una membresía.")
        user_id=str(uuid.uuid4())
        db.execute("INSERT INTO users(id,email,name,password_hash) VALUES(?,?,?,?)",(user_id,email,name,hashed))
        db.execute("INSERT INTO memberships(user_id,organization_id,role) VALUES(?,?,?)",(user_id,org_id,role))
        return user_id


def add_membership(org_id,email,role):
    if role not in {"admin","editor","viewer"}: raise ValueError("Rol inválido.")
    with connection() as db:
        row=db.execute("SELECT id FROM users WHERE email=? AND disabled=0",(_email(email),)).fetchone()
        if not row: raise ValueError("El usuario no existe.")
        db.execute("INSERT INTO memberships(user_id,organization_id,role) VALUES(?,?,?)",(row["id"],org_id,role))
        return row["id"]


def set_membership(org_id,user_id,role):
    if role not in {"admin","editor","viewer"}: raise ValueError("Rol inválido.")
    with connection() as db:
        row=db.execute("SELECT role FROM memberships WHERE user_id=? AND organization_id=?",(user_id,org_id)).fetchone()
        if not row: return False
        if row["role"]=="owner": raise ValueError("El propietario no puede cambiar de rol.")
        db.execute("UPDATE memberships SET role=? WHERE user_id=? AND organization_id=?",(role,user_id,org_id))
        db.execute("DELETE FROM sessions WHERE user_id=?",(user_id,))
        return True


def remove_membership(org_id,user_id,actor_id):
    with connection() as db:
        row=db.execute("SELECT role FROM memberships WHERE user_id=? AND organization_id=?",(user_id,org_id)).fetchone()
        if not row: return False
        if row["role"]=="owner" or user_id==actor_id: raise ValueError("No se puede quitar al propietario ni la membresía propia.")
        db.execute("DELETE FROM memberships WHERE user_id=? AND organization_id=?",(user_id,org_id))
        db.execute("DELETE FROM sessions WHERE user_id=?",(user_id,))
        return True


def register_upload(token,org_id,user_id):
    with connection() as db:
        db.execute("INSERT INTO pending_uploads(token,organization_id,user_id,expires_at) VALUES(?,?,?,?)",(token,org_id,user_id,int(time.time())+24*3600))


def pending_upload(token,org_id,user_id):
    with connection() as db:
        return db.execute("SELECT 1 FROM pending_uploads WHERE token=? AND organization_id=? AND user_id=? AND expires_at>?",(token,org_id,user_id,int(time.time()))).fetchone() is not None


def finish_upload(token,org_id,user_id):
    with connection() as db: db.execute("DELETE FROM pending_uploads WHERE token=? AND organization_id=? AND user_id=?",(token,org_id,user_id))


def expired_uploads():
    with connection() as db:
        tokens=[r["token"] for r in db.execute("SELECT token FROM pending_uploads WHERE expires_at<=?",(int(time.time()),))]
        db.execute("DELETE FROM pending_uploads WHERE expires_at<=?",(int(time.time()),))
        return tokens


def module_list(org_id):
    with connection() as db:
        return [{"id":r["id"],"name":r["name"],"count":r["count"]} for r in db.execute("""SELECT m.id,m.name,COUNT(r.id) AS count FROM modules m
            LEFT JOIN records r ON r.module_id=m.id WHERE m.organization_id=? GROUP BY m.id ORDER BY m.created_at DESC""",(org_id,))]


def get_module(org_id,module_id):
    with connection() as db:
        r=db.execute("SELECT * FROM modules WHERE id=? AND organization_id=?",(module_id,org_id)).fetchone()
        return {"id":r["id"],"schema":json.loads(r["schema_json"])} if r else None


def imported_module(org_id,import_id):
    with connection() as db:
        r=db.execute("SELECT module_id FROM imports WHERE id=? AND organization_id=?",(import_id,org_id)).fetchone()
        return r["module_id"] if r else None


def import_records(org_id,import_id,schema,records):
    with connection() as db:
        r=db.execute("SELECT module_id FROM imports WHERE id=? AND organization_id=?",(import_id,org_id)).fetchone()
        if r: return r["module_id"]
        module_id=str(uuid.uuid4())
        db.execute("INSERT INTO modules(id,name,schema_json,organization_id) VALUES(?,?,?,?)",(module_id,schema["name"],json.dumps(schema,ensure_ascii=False),org_id))
        db.executemany("INSERT INTO records(id,module_id,values_json) VALUES(?,?,?)",[(str(uuid.uuid4()),module_id,json.dumps(v,ensure_ascii=False)) for v in records])
        db.execute("INSERT INTO imports(id,module_id,organization_id) VALUES(?,?,?)",(import_id,module_id,org_id))
        return module_id


def record_list(org_id,module_id):
    with connection() as db:
        return [{"id":r["id"],"values":json.loads(r["values_json"])} for r in db.execute("""SELECT r.id,r.values_json FROM records r
            JOIN modules m ON m.id=r.module_id WHERE r.module_id=? AND m.organization_id=? ORDER BY r.rowid""",(module_id,org_id))]


def create_record(org_id,module_id,values):
    record_id=str(uuid.uuid4())
    with connection() as db:
        cur=db.execute("""INSERT INTO records(id,module_id,values_json) SELECT ?,m.id,? FROM modules m
            WHERE m.id=? AND m.organization_id=?""",(record_id,json.dumps(values,ensure_ascii=False),module_id,org_id))
        return record_id if cur.rowcount else None


def update_record(org_id,module_id,record_id,values):
    with connection() as db:
        cur=db.execute("""UPDATE records SET values_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND module_id=?
          AND EXISTS(SELECT 1 FROM modules WHERE id=? AND organization_id=?)""",(json.dumps(values,ensure_ascii=False),record_id,module_id,module_id,org_id))
        return cur.rowcount>0


def delete_record(org_id,module_id,record_id):
    with connection() as db:
        cur=db.execute("""DELETE FROM records WHERE id=? AND module_id=? AND EXISTS(
            SELECT 1 FROM modules WHERE id=? AND organization_id=?)""",(record_id,module_id,module_id,org_id))
        return cur.rowcount>0
