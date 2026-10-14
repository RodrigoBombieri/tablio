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
        CREATE TABLE IF NOT EXISTS stock_movements (id TEXT PRIMARY KEY,organization_id TEXT NOT NULL REFERENCES organizations(id),module_id TEXT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,user_id TEXT NOT NULL REFERENCES users(id),kind TEXT NOT NULL CHECK(kind IN ('sale','receipt')),quantity TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS stock_movements_recent ON stock_movements(organization_id,module_id,kind,created_at);
        CREATE INDEX IF NOT EXISTS records_module ON records(module_id);
        CREATE TABLE IF NOT EXISTS imports (id TEXT PRIMARY KEY,module_id TEXT NOT NULL REFERENCES modules(id),created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS pending_uploads (token TEXT PRIMARY KEY,organization_id TEXT NOT NULL REFERENCES organizations(id),user_id TEXT NOT NULL REFERENCES users(id),expires_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS reimports (id TEXT PRIMARY KEY,organization_id TEXT NOT NULL REFERENCES organizations(id),module_id TEXT NOT NULL REFERENCES modules(id),user_id TEXT NOT NULL REFERENCES users(id),key_field_id TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,undone_at TEXT);
        CREATE TABLE IF NOT EXISTS reimport_changes (run_id TEXT NOT NULL REFERENCES reimports(id) ON DELETE CASCADE,record_id TEXT NOT NULL,action TEXT NOT NULL,old_json TEXT,new_json TEXT,PRIMARY KEY(run_id,record_id));
        CREATE TABLE IF NOT EXISTS saved_views (id TEXT PRIMARY KEY,organization_id TEXT NOT NULL REFERENCES organizations(id),module_id TEXT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,query_json TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY,organization_id TEXT NOT NULL REFERENCES organizations(id),module_id TEXT,actor_user_id TEXT REFERENCES users(id),action TEXT NOT NULL,details_json TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS audit_org_time ON audit_events(organization_id,created_at DESC);
        CREATE TABLE IF NOT EXISTS access_tokens (token_hash TEXT PRIMARY KEY,organization_id TEXT REFERENCES organizations(id),user_id TEXT REFERENCES users(id),email TEXT NOT NULL,name TEXT,role TEXT,kind TEXT NOT NULL CHECK(kind IN ('invite','reset')),expires_at INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
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


def _audit(db,org_id,module_id,actor_id,action,details=None):
    db.execute("INSERT INTO audit_events(id,organization_id,module_id,actor_user_id,action,details_json) VALUES(?,?,?,?,?,?)",
               (str(uuid.uuid4()),org_id,module_id,actor_id,action,json.dumps(details or {},ensure_ascii=False)))


def activity(org_id,module_id=None,limit=50):
    limit=max(1,min(100,int(limit)))
    with connection() as db:
        sql="""SELECT a.id,a.module_id,a.action,a.details_json,a.created_at,u.name AS actor_name
            FROM audit_events a LEFT JOIN users u ON u.id=a.actor_user_id WHERE a.organization_id=?"""
        args=[org_id]
        if module_id: sql+=" AND a.module_id=?";args.append(module_id)
        sql+=" ORDER BY a.created_at DESC,a.rowid DESC LIMIT ?";args.append(limit)
        return [{"id":r["id"],"moduleId":r["module_id"],"action":r["action"],"details":json.loads(r["details_json"]),
                 "createdAt":r["created_at"],"actor":r["actor_name"] or "Sistema"} for r in db.execute(sql,args)]


def create_invitation(org_id,email,name,role,actor_id):
    if role not in {"admin","editor","viewer"}: raise ValueError("Rol inválido.")
    email,name=_email(email),_name(name)
    token=new_token()
    with connection() as db:
        user=db.execute("SELECT id FROM users WHERE email=? AND disabled=0",(email,)).fetchone()
        if user and db.execute("SELECT 1 FROM memberships WHERE user_id=? AND organization_id=?",(user["id"],org_id)).fetchone():
            raise ValueError("Esa persona ya tiene acceso a la organización.")
        db.execute("INSERT INTO access_tokens(token_hash,organization_id,email,name,role,kind,expires_at) VALUES(?,?,?,?,?,'invite',?)",
                   (token_hash(token),org_id,email,name,role,int(time.time())+7*86400))
        _audit(db,org_id,None,actor_id,"invitation_created",{"email":email,"role":role})
    return token


def create_reset_token(org_id,email,actor_id=None):
    email=_email(email);token=new_token()
    with connection() as db:
        row=db.execute("SELECT u.id FROM users u JOIN memberships m ON m.user_id=u.id WHERE u.email=? AND u.disabled=0 AND m.organization_id=?",(email,org_id)).fetchone()
        if not row: raise ValueError("No hay un usuario activo con ese email en la organización.")
        db.execute("DELETE FROM access_tokens WHERE kind='reset' AND user_id=?",(row["id"],))
        db.execute("INSERT INTO access_tokens(token_hash,organization_id,user_id,email,kind,expires_at) VALUES(?,?,?,?,'reset',?)",
                   (token_hash(token),org_id,row["id"],email,int(time.time())+3600))
        _audit(db,org_id,None,actor_id,"password_reset_issued",{"email":email})
    return token


def access_token_info(token):
    try: hashed=token_hash(token)
    except (ValueError,UnicodeEncodeError,AttributeError,TypeError): return None
    with connection() as db:
        row=db.execute("SELECT kind,email,expires_at FROM access_tokens WHERE token_hash=?",(hashed,)).fetchone()
        if not row or row["expires_at"]<=int(time.time()): return None
        existing=db.execute("SELECT 1 FROM users WHERE email=? AND disabled=0",(row["email"],)).fetchone() is not None
        return {"kind":row["kind"],"email":row["email"],"existing":existing}


def redeem_access_token(token,password):
    try: hashed=token_hash(token)
    except (ValueError,UnicodeEncodeError,AttributeError,TypeError) as exc: raise ValueError("El enlace no es válido.") from exc
    with connection() as db:
        row=db.execute("SELECT * FROM access_tokens WHERE token_hash=? AND expires_at>?",(hashed,int(time.time()))).fetchone()
        if not row: raise ValueError("El enlace venció o ya se usó. Pedí uno nuevo.")
        user=db.execute("SELECT id,password_hash,disabled FROM users WHERE email=?",(row["email"],)).fetchone()
        if row["kind"]=="invite":
            if user:
                if user["disabled"] or not verify_password(password,user["password_hash"]):
                    raise ValueError("Ingresá la contraseña actual de tu cuenta para aceptar la invitación.")
                user_id=user["id"]
            else:
                user_id=str(uuid.uuid4())
                db.execute("INSERT INTO users(id,email,name,password_hash) VALUES(?,?,?,?)",
                           (user_id,row["email"],row["name"],hash_password(password)))
            db.execute("INSERT INTO memberships(user_id,organization_id,role) VALUES(?,?,?)",(user_id,row["organization_id"],row["role"]))
            _audit(db,row["organization_id"],None,user_id,"invitation_accepted",{"email":row["email"]})
        else:
            if not user or user["disabled"]: raise ValueError("La cuenta ya no está disponible.")
            user_id=user["id"]
            db.execute("UPDATE users SET password_hash=? WHERE id=?",(hash_password(password),user_id))
            db.execute("DELETE FROM sessions WHERE user_id=?",(user_id,))
            _audit(db,row["organization_id"],None,user_id,"password_reset_completed",{"email":row["email"]})
        db.execute("DELETE FROM access_tokens WHERE token_hash=?",(hashed,))
        return row["kind"]


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


def create_user_in_org(org_id,email,name,password,role,actor_id=None):
    if role not in {"admin","editor","viewer"}: raise ValueError("Rol inválido.")
    email,name,hashed=_email(email),_name(name),hash_password(password)
    with connection() as db:
        if db.execute("SELECT 1 FROM users WHERE email=?",(email,)).fetchone(): raise ValueError("El email ya existe. Agregá una membresía.")
        user_id=str(uuid.uuid4())
        db.execute("INSERT INTO users(id,email,name,password_hash) VALUES(?,?,?,?)",(user_id,email,name,hashed))
        db.execute("INSERT INTO memberships(user_id,organization_id,role) VALUES(?,?,?)",(user_id,org_id,role))
        _audit(db,org_id,None,actor_id,"user_created",{"email":email,"role":role})
        return user_id


def add_membership(org_id,email,role,actor_id=None):
    if role not in {"admin","editor","viewer"}: raise ValueError("Rol inválido.")
    with connection() as db:
        row=db.execute("SELECT id FROM users WHERE email=? AND disabled=0",(_email(email),)).fetchone()
        if not row: raise ValueError("El usuario no existe.")
        db.execute("INSERT INTO memberships(user_id,organization_id,role) VALUES(?,?,?)",(row["id"],org_id,role))
        _audit(db,org_id,None,actor_id,"member_added",{"email":_email(email),"role":role})
        return row["id"]


def set_membership(org_id,user_id,role,actor_id=None):
    if role not in {"admin","editor","viewer"}: raise ValueError("Rol inválido.")
    with connection() as db:
        row=db.execute("SELECT role FROM memberships WHERE user_id=? AND organization_id=?",(user_id,org_id)).fetchone()
        if not row: return False
        if row["role"]=="owner": raise ValueError("El propietario no puede cambiar de rol.")
        db.execute("UPDATE memberships SET role=? WHERE user_id=? AND organization_id=?",(role,user_id,org_id))
        db.execute("DELETE FROM sessions WHERE user_id=?",(user_id,))
        _audit(db,org_id,None,actor_id,"member_role_changed",{"userId":user_id,"role":role})
        return True


def remove_membership(org_id,user_id,actor_id):
    with connection() as db:
        row=db.execute("SELECT role FROM memberships WHERE user_id=? AND organization_id=?",(user_id,org_id)).fetchone()
        if not row: return False
        if row["role"]=="owner" or user_id==actor_id: raise ValueError("No se puede quitar al propietario ni la membresía propia.")
        db.execute("DELETE FROM memberships WHERE user_id=? AND organization_id=?",(user_id,org_id))
        db.execute("DELETE FROM sessions WHERE user_id=?",(user_id,))
        _audit(db,org_id,None,actor_id,"member_removed",{"userId":user_id})
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
        return {"id":r["id"],"schema":json.loads(r["schema_json"]),
                "canUndoImport":_can_undo_import(db,org_id,module_id)} if r else None


def _can_undo_import(db,org_id,module_id):
    imported=db.execute("SELECT 1 FROM imports WHERE module_id=? AND organization_id=?",(module_id,org_id)).fetchone()
    changed=db.execute("""SELECT 1 FROM audit_events WHERE organization_id=? AND module_id=? AND action IN
        ('record_created','record_updated','record_deleted','module_configured','reimport_applied','reimport_undone','stock_movement') LIMIT 1""",
        (org_id,module_id)).fetchone()
    return bool(imported and not changed)


def undo_import(org_id,module_id,actor_id=None):
    with connection() as db:
        if not _can_undo_import(db,org_id,module_id):
            raise ValueError("Esta importación ya tiene cambios. Conservá el módulo y sus datos.")
        db.execute("DELETE FROM imports WHERE module_id=? AND organization_id=?",(module_id,org_id))
        db.execute("DELETE FROM modules WHERE id=? AND organization_id=?",(module_id,org_id))
        _audit(db,org_id,None,actor_id,"import_undone",{"moduleId":module_id})


def record_stock_movement(org_id,module_id,record_id,kind,quantity,actor_id):
    from decimal import Decimal, InvalidOperation
    from .core import validate_record
    from .insights import stock_field
    if kind not in {"sale","receipt"}: raise ValueError("Elegí venta o entrada de mercadería.")
    try: amount=Decimal(str(quantity))
    except (InvalidOperation,TypeError): raise ValueError("Ingresá una cantidad válida.")
    if not amount.is_finite() or amount<=0 or amount>1000000000:
        raise ValueError("Ingresá una cantidad positiva válida.")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        module=db.execute("SELECT schema_json FROM modules WHERE id=? AND organization_id=?",(module_id,org_id)).fetchone()
        record=db.execute("SELECT values_json FROM records WHERE id=? AND module_id=?",(record_id,module_id)).fetchone()
        if not module or not record: raise ValueError("Producto no encontrado.")
        schema=json.loads(module["schema_json"])
        field=stock_field(schema["fields"])
        if not field or field["type"] not in {"integer","decimal","currency"} or field.get("formula"):
            raise ValueError("Configurá un campo numérico llamado Stock actual.")
        values=json.loads(record["values_json"])
        try: current=Decimal(str(values[field["id"]]))
        except (InvalidOperation,KeyError,TypeError): raise ValueError("Completá el stock actual de este producto antes de registrar movimientos.")
        if kind=="sale" and amount>current: raise ValueError("La venta supera el stock disponible.")
        updated=current-amount if kind=="sale" else current+amount
        values[field["id"]]=str(updated)
        normalized=validate_record(values,schema)
        movement_id=str(uuid.uuid4())
        db.execute("UPDATE records SET values_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND module_id=?",(json.dumps(normalized,ensure_ascii=False),record_id,module_id))
        db.execute("INSERT INTO stock_movements(id,organization_id,module_id,record_id,user_id,kind,quantity) VALUES(?,?,?,?,?,?,?)",(movement_id,org_id,module_id,record_id,actor_id,kind,str(amount)))
        _audit(db,org_id,module_id,actor_id,"stock_movement",{"recordId":record_id,"kind":kind,"quantity":str(amount)})
        return {"id":movement_id,"stock":normalized[field["id"]]}


def recent_sales(org_id,module_id):
    from decimal import Decimal
    with connection() as db:
        rows=db.execute("""SELECT record_id,quantity FROM stock_movements WHERE organization_id=? AND module_id=?
            AND kind='sale' AND created_at>=datetime('now','-30 days')""",(org_id,module_id))
        result={}
        for row in rows:
            result[row["record_id"]]=result.get(row["record_id"],Decimal(0))+Decimal(row["quantity"])
        return {key:float(value) for key,value in result.items()}


def update_module_schema(org_id,module_id,candidate,actor_id=None):
    from .core import TYPES, validate_record
    if not isinstance(candidate,dict): raise ValueError("Configuración inválida.")
    with connection() as db:
        row=db.execute("SELECT schema_json FROM modules WHERE id=? AND organization_id=?",(module_id,org_id)).fetchone()
        if not row: return None
        old=json.loads(row["schema_json"])
        revision=old.get("revision",1)
        if candidate.get("revision")!=revision: raise ValueError("El módulo cambió. Volvé a abrir su configuración.")
        name=str(candidate.get("name","")).strip()
        if not 1<=len(name)<=80: raise ValueError("Ingresá un nombre de módulo de 1 a 80 caracteres.")
        supplied=candidate.get("fields")
        previous=old["fields"]
        if not isinstance(supplied,list) or not len(previous)<=len(supplied)<=30:
            raise ValueError("Debe haber entre 1 y 30 campos; no se pueden quitar campos con datos.")
        clean=[];labels=set();ids={f["id"] for f in previous}
        for index,field in enumerate(supplied):
            if not isinstance(field,dict): raise ValueError("Campo inválido.")
            label=str(field.get("label","")).strip()
            if not 1<=len(label)<=80 or label.casefold() in labels: raise ValueError("Cada campo necesita un nombre único de 1 a 80 caracteres.")
            labels.add(label.casefold())
            if type(field.get("required")) is not bool: raise ValueError(f"Indicá si {label} es obligatorio.")
            if index<len(previous):
                prior=previous[index]
                if field.get("id")!=prior["id"] or field.get("type")!=prior["type"]:
                    raise ValueError("No se puede cambiar el orden ni el tipo de los campos existentes.")
                item=dict(prior)
                item["sourceLabel"]=prior.get("sourceLabel",prior["label"])
                item["label"],item["required"]=label,field["required"]
            else:
                fid=field.get("id")
                if not isinstance(fid,str) or not fid.startswith("f") or not fid[1:].isdigit() or fid in ids:
                    raise ValueError("Identificador de campo inválido.")
                ids.add(fid)
                kind=field.get("type")
                if kind not in TYPES: raise ValueError(f"Tipo inválido en {label}.")
                if field["required"]: raise ValueError(f"Agregá {label} como opcional. Podés marcarlo obligatorio después de completar sus valores.")
                item={"id":fid,"label":label,"type":kind,"required":field["required"],"sourceColumn":None}
                if kind in ("decimal","currency"):
                    scale=field.get("scale")
                    if type(scale) is not int or not 0<=scale<=6: raise ValueError(f"Decimales inválidos en {label}.")
                    item["scale"]=scale
                    if kind=="currency": item["currency"]="ARS"
            if item["type"]=="enum":
                options=field.get("options",item.get("options",[]))
                if not isinstance(options,list) or not 1<=len(options)<=100 or any(not isinstance(v,str) or not 1<=len(v.strip())<=100 for v in options) or len({v.casefold() for v in options})!=len(options):
                    raise ValueError(f"Opciones inválidas en {label}.")
                item["options"]=options
            clean.append(item)
        primary=candidate.get("primaryFieldId",old["primaryFieldId"])
        if primary not in ids: raise ValueError("Elegí un campo principal válido.")
        template=candidate.get("template",old.get("template","general"))
        if template not in {"general","habilitaciones","minimercado","corralon"}:
            raise ValueError("Elegí una plantilla válida.")
        updated={**old,"revision":revision+1,"name":name,"template":template,"primaryFieldId":primary,"fields":clean}
        records=list(db.execute("SELECT id,values_json FROM records WHERE module_id=?",(module_id,)))
        for record in records:
            values=json.loads(record["values_json"])
            for field in clean:
                if field["id"] not in values: values[field["id"]]=None
            try: normalized=validate_record(values,updated)
            except ValueError as exc: raise ValueError(f"El registro {record['id'][:8]} no cumple la nueva configuración: {exc}") from exc
            db.execute("UPDATE records SET values_json=? WHERE id=?",(json.dumps(normalized,ensure_ascii=False),record["id"]))
        db.execute("UPDATE modules SET name=?,schema_json=? WHERE id=? AND organization_id=?",(name,json.dumps(updated,ensure_ascii=False),module_id,org_id))
        _audit(db,org_id,module_id,actor_id,"module_configured",{"name":name,"revision":revision+1})
        return updated


def imported_module(org_id,import_id):
    with connection() as db:
        r=db.execute("SELECT module_id FROM imports WHERE id=? AND organization_id=?",(import_id,org_id)).fetchone()
        return r["module_id"] if r else None


def import_records(org_id,import_id,schema,records,actor_id=None):
    with connection() as db:
        r=db.execute("SELECT module_id FROM imports WHERE id=? AND organization_id=?",(import_id,org_id)).fetchone()
        if r: return r["module_id"]
        module_id=str(uuid.uuid4())
        db.execute("INSERT INTO modules(id,name,schema_json,organization_id) VALUES(?,?,?,?)",(module_id,schema["name"],json.dumps(schema,ensure_ascii=False),org_id))
        db.executemany("INSERT INTO records(id,module_id,values_json) VALUES(?,?,?)",[(str(uuid.uuid4()),module_id,json.dumps(v,ensure_ascii=False)) for v in records])
        db.execute("INSERT INTO imports(id,module_id,organization_id) VALUES(?,?,?)",(import_id,module_id,org_id))
        _audit(db,org_id,module_id,actor_id,"module_imported",{"count":len(records),"name":schema["name"]})
        return module_id


def record_list(org_id,module_id):
    with connection() as db:
        return [{"id":r["id"],"values":json.loads(r["values_json"])} for r in db.execute("""SELECT r.id,r.values_json FROM records r
            JOIN modules m ON m.id=r.module_id WHERE r.module_id=? AND m.organization_id=? ORDER BY r.rowid""",(module_id,org_id))]


def query_records(org_id,module_id,schema,query):
    """Filter, order, count, and page inside SQLite instead of loading every record."""
    fields={f["id"]:f for f in schema["fields"]}
    where=["r.module_id=?","m.organization_id=?"]
    params=[module_id,org_id]
    def expression(fid): return "json_extract(r.values_json, '$."+fid+"')"
    search=str(query.get("q",[""])[0]).strip()
    if search:
        text_ids=[f["id"] for f in schema["fields"] if f["type"]=="text"]
        if text_ids:
            where.append("("+" OR ".join(f"casefold_contains({expression(fid)}, ?)" for fid in text_ids)+")")
            params.extend([search]*len(text_ids))
        else: where.append("0")
    fid=str(query.get("field",[""])[0]);op=str(query.get("op",[""])[0]);term=str(query.get("value",[""])[0])
    if fid:
        if fid not in fields: raise ValueError("Campo de filtro inválido.")
        kind=fields[fid]["type"]
        allowed={"text":{"contains","eq","empty","not_empty"},"enum":{"eq","empty","not_empty"},"boolean":{"eq","empty","not_empty"},"date":{"eq","lt","gt","empty","not_empty"},"integer":{"eq","lt","gt","empty","not_empty"},"decimal":{"eq","lt","gt","empty","not_empty"},"currency":{"eq","lt","gt","empty","not_empty"}}
        if op not in allowed[kind]: raise ValueError("Operador de filtro inválido.")
        expr=expression(fid)
        if op=="empty": where.append(f"{expr} IS NULL")
        elif op=="not_empty": where.append(f"{expr} IS NOT NULL")
        elif op=="contains": where.append(f"casefold_contains({expr}, ?)");params.append(term)
        elif kind in ("integer","decimal","currency"):
            from decimal import Decimal
            try: Decimal(term)
            except Exception as exc: raise ValueError("Ingresá un número válido para filtrar.") from exc
            where.append(f"decimal_compare({expr}, ?) { {'eq':'=','lt':'<','gt':'>'}[op] } 0");params.append(term)
        elif kind=="boolean":
            if term.casefold() not in ("true","false","si","sí","no"): raise ValueError("Elegí Sí o No.")
            where.append(f"{expr} {'=' if op=='eq' else '<' if op=='lt' else '>'} ?");params.append(1 if term.casefold() in ("true","si","sí") else 0)
        else: where.append(f"{expr} {'=' if op=='eq' else '<' if op=='lt' else '>'} ?");params.append(term)
    sort=str(query.get("sort",[""])[0]);direction=str(query.get("direction",["asc"])[0])
    if direction not in ("asc","desc"): raise ValueError("Orden inválido.")
    if sort and sort not in fields: raise ValueError("Campo de orden inválido.")
    try: page=max(1,int(query.get("page",["1"])[0]))
    except (ValueError,TypeError): page=1
    page=min(page,100000)
    order="r.rowid"
    if sort:
        order=expression(sort)
        if fields[sort]["type"] in ("integer","decimal","currency"): order+=" COLLATE DECIMAL_TEXT"
        elif fields[sort]["type"] in ("text","enum"): order+=" COLLATE NOCASE"
    sql=" FROM records r JOIN modules m ON m.id=r.module_id WHERE "+" AND ".join(where)
    with connection() as db:
        from decimal import Decimal
        db.create_function("casefold_contains",2,lambda value,needle: int(str(needle).casefold() in str(value or "").casefold()))
        db.create_function("decimal_compare",2,lambda a,b: (Decimal(str(a))>Decimal(str(b)))-(Decimal(str(a))<Decimal(str(b))))
        db.create_collation("DECIMAL_TEXT",lambda a,b: (Decimal(a)>Decimal(b))-(Decimal(a)<Decimal(b)))
        total=db.execute("SELECT COUNT(*)"+sql,params).fetchone()[0]
        rows=db.execute("SELECT r.id,r.values_json"+sql+f" ORDER BY {order} {direction.upper()},r.rowid LIMIT 25 OFFSET ?",params+[(page-1)*25]).fetchall()
        return {"total":total,"page":page,"items":[{"id":r["id"],"values":json.loads(r["values_json"])} for r in rows]}


def saved_views(org_id,module_id,user_id):
    with connection() as db:
        return [{"id":r["id"],"name":r["name"],"query":json.loads(r["query_json"])} for r in db.execute("SELECT * FROM saved_views WHERE organization_id=? AND module_id=? AND user_id=? ORDER BY created_at,id",(org_id,module_id,user_id))]


def save_view(org_id,module_id,user_id,name,query):
    name=str(name or "").strip()
    if not 1<=len(name)<=80: raise ValueError("Ingresá un nombre de vista de 1 a 80 caracteres.")
    if not isinstance(query,dict) or set(query)-{"q","field","op","value","sort","direction","columns"}:
        raise ValueError("Vista inválida.")
    if not db_module_exists(org_id,module_id): raise ValueError("Módulo no encontrado.")
    view_id=str(uuid.uuid4())
    with connection() as db:
        db.execute("INSERT INTO saved_views(id,organization_id,module_id,user_id,name,query_json) VALUES(?,?,?,?,?,?)",(view_id,org_id,module_id,user_id,name,json.dumps(query,ensure_ascii=False)))
    return view_id


def db_module_exists(org_id,module_id):
    with connection() as db: return db.execute("SELECT 1 FROM modules WHERE id=? AND organization_id=?",(module_id,org_id)).fetchone() is not None


def delete_view(org_id,module_id,user_id,view_id):
    with connection() as db:
        return db.execute("DELETE FROM saved_views WHERE id=? AND organization_id=? AND module_id=? AND user_id=?",(view_id,org_id,module_id,user_id)).rowcount>0


def create_record(org_id,module_id,values,actor_id=None):
    record_id=str(uuid.uuid4())
    with connection() as db:
        cur=db.execute("""INSERT INTO records(id,module_id,values_json) SELECT ?,m.id,? FROM modules m
            WHERE m.id=? AND m.organization_id=?""",(record_id,json.dumps(values,ensure_ascii=False),module_id,org_id))
        if cur.rowcount: _audit(db,org_id,module_id,actor_id,"record_created",{"recordId":record_id})
        return record_id if cur.rowcount else None


def update_record(org_id,module_id,record_id,values,actor_id=None):
    with connection() as db:
        cur=db.execute("""UPDATE records SET values_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND module_id=?
          AND EXISTS(SELECT 1 FROM modules WHERE id=? AND organization_id=?)""",(json.dumps(values,ensure_ascii=False),record_id,module_id,module_id,org_id))
        if cur.rowcount: _audit(db,org_id,module_id,actor_id,"record_updated",{"recordId":record_id})
        return cur.rowcount>0


def delete_record(org_id,module_id,record_id,actor_id=None):
    with connection() as db:
        cur=db.execute("""DELETE FROM records WHERE id=? AND module_id=? AND EXISTS(
            SELECT 1 FROM modules WHERE id=? AND organization_id=?)""",(record_id,module_id,module_id,org_id))
        if cur.rowcount: _audit(db,org_id,module_id,actor_id,"record_deleted",{"recordId":record_id})
        return cur.rowcount>0


def reimport_run(org_id, run_id):
    with connection() as db:
        row=db.execute("SELECT id,module_id,undone_at FROM reimports WHERE id=? AND organization_id=?",(run_id,org_id)).fetchone()
        return dict(row) if row else None


def apply_reimport(org_id,module_id,run_id,user_id,key_field_id,changes):
    """Apply a reviewed replacement set atomically, checking its prior values."""
    with connection() as db:
        existing=db.execute("SELECT module_id FROM reimports WHERE id=? AND organization_id=?",(run_id,org_id)).fetchone()
        if existing: return existing["module_id"],True
        if not db.execute("SELECT 1 FROM modules WHERE id=? AND organization_id=?",(module_id,org_id)).fetchone():
            raise ValueError("Módulo no encontrado.")
        for change in changes:
            if change["action"]=="update":
                current=db.execute("SELECT values_json FROM records WHERE id=? AND module_id=?",(change["id"],module_id)).fetchone()
                if not current or json.loads(current["values_json"])!=change["old"]:
                    raise ValueError("Los registros cambiaron desde la vista previa. Revisá la importación otra vez.")
            elif change["action"]=="create" and db.execute("SELECT 1 FROM records WHERE id=?",(change["id"],)).fetchone():
                raise ValueError("Los registros cambiaron desde la vista previa. Revisá la importación otra vez.")
        db.execute("INSERT INTO reimports(id,organization_id,module_id,user_id,key_field_id) VALUES(?,?,?,?,?)",(run_id,org_id,module_id,user_id,key_field_id))
        for change in changes:
            old=json.dumps(change["old"],ensure_ascii=False) if change["old"] is not None else None
            new=json.dumps(change["new"],ensure_ascii=False)
            if change["action"]=="create":
                db.execute("INSERT INTO records(id,module_id,values_json) VALUES(?,?,?)",(change["id"],module_id,new))
            else:
                db.execute("UPDATE records SET values_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND module_id=?",(new,change["id"],module_id))
            db.execute("INSERT INTO reimport_changes(run_id,record_id,action,old_json,new_json) VALUES(?,?,?,?,?)",(run_id,change["id"],change["action"],old,new))
        _audit(db,org_id,module_id,user_id,"reimport_applied",{"runId":run_id,"created":sum(c["action"]=="create" for c in changes),"updated":sum(c["action"]=="update" for c in changes)})
        return module_id,False


def undo_reimport(org_id,module_id,run_id,actor_id=None):
    with connection() as db:
        run=db.execute("SELECT undone_at FROM reimports WHERE id=? AND module_id=? AND organization_id=?",(run_id,module_id,org_id)).fetchone()
        if not run: return False
        if run["undone_at"]: raise ValueError("Esta reimportación ya fue deshecha.")
        changes=list(db.execute("SELECT * FROM reimport_changes WHERE run_id=?",(run_id,)))
        for change in changes:
            current=db.execute("SELECT values_json FROM records WHERE id=? AND module_id=?",(change["record_id"],module_id)).fetchone()
            if not current or json.loads(current["values_json"])!=json.loads(change["new_json"]):
                raise ValueError("Hay registros modificados después de importar. No se puede deshacer automáticamente.")
        for change in changes:
            if change["action"]=="create": db.execute("DELETE FROM records WHERE id=? AND module_id=?",(change["record_id"],module_id))
            else: db.execute("UPDATE records SET values_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND module_id=?",(change["old_json"],change["record_id"],module_id))
        db.execute("UPDATE reimports SET undone_at=CURRENT_TIMESTAMP WHERE id=?",(run_id,))
        _audit(db,org_id,module_id,actor_id,"reimport_undone",{"runId":run_id})
        return True


def reimport_history(org_id,module_id):
    with connection() as db:
        return [dict(r) for r in db.execute("""SELECT r.id,r.key_field_id,r.created_at,r.undone_at,
            SUM(CASE WHEN c.action='create' THEN 1 ELSE 0 END) AS created,
            SUM(CASE WHEN c.action='update' THEN 1 ELSE 0 END) AS updated
            FROM reimports r LEFT JOIN reimport_changes c ON c.run_id=r.id
            WHERE r.organization_id=? AND r.module_id=? GROUP BY r.id ORDER BY r.created_at DESC LIMIT 20""",(org_id,module_id))]
