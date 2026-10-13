"""Run the local Tablio PoC with: python -m app.server"""
from __future__ import annotations

import json
import hmac
import mimetypes
import os
import re
import sqlite3
import threading
import time
import uuid
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

from .core import convert_rows, infer_sheet, validate_record, validate_schema
from . import store
from .store import (create_record, delete_record, get_module, import_records,
                    initialize, module_list, record_list, update_record)
from .xlsx_io import SpreadsheetError, read_workbook, write_workbook

LOGIN_FAILURES = {}
LOGIN_LOCK = threading.Lock()

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
UPLOADS = Path(os.environ.get("TABLIO_UPLOADS_PATH", ROOT / "uploads"))
UPLOADS.mkdir(parents=True,exist_ok=True)
if os.name != "nt": os.chmod(UPLOADS,0o700)


def clean_expired():
    for token in store.expired_uploads():
        (UPLOADS / f"{token}.xlsx").unlink(missing_ok=True)
    for path in UPLOADS.glob("*.xlsx"):
        if time.time() - path.stat().st_mtime > 24 * 3600:
            path.unlink(missing_ok=True)


def _preview(token, sheet_name, org_id, user_id):
    if not store.pending_upload(token,org_id,user_id):
        raise ValueError("La importación no existe, venció o pertenece a otra organización.")
    path = UPLOADS / f"{token}.xlsx"
    if not path.exists():
        raise ValueError("La importación venció. Volvé a subir el archivo.")
    sheets = read_workbook(path.read_bytes())
    sheet = next((s for s in sheets if s["name"] == sheet_name), None)
    if not sheet:
        raise ValueError("Elegí una hoja válida del archivo.")
    result = infer_sheet(sheet)
    result["token"] = token
    result["sheets"] = [s["name"] for s in sheets]
    result["sample"] = [{"row": r["number"], "values": [r["cells"].get(f["sourceColumn"]) for f in result["fields"]]}
                        for r in sheet["rows"][1:6]]
    return result, sheet


def filter_records(records, schema, query):
    fields = {f["id"]: f for f in schema["fields"]}
    search = query.get("q", [""])[0].casefold()
    if search:
        text_ids = [f["id"] for f in schema["fields"] if f["type"] == "text"]
        records = [r for r in records if any(search in str(r["values"].get(fid) or "").casefold() for fid in text_ids)]
    fid = query.get("field", [""])[0]
    op = query.get("op", [""])[0]
    term = query.get("value", [""])[0]
    if fid and op and fid in fields:
        kind = fields[fid]["type"]
        allowed = {"text": {"contains", "eq", "empty", "not_empty"}, "enum": {"eq", "empty", "not_empty"},
                   "boolean": {"eq", "empty", "not_empty"}, "date": {"eq", "lt", "gt", "empty", "not_empty"},
                   "integer": {"eq", "lt", "gt", "empty", "not_empty"}, "decimal": {"eq", "lt", "gt", "empty", "not_empty"},
                   "currency": {"eq", "lt", "gt", "empty", "not_empty"}}
        if op not in allowed[kind]: raise ValueError("Operador de filtro inválido.")
        def matches(record):
            raw = record["values"].get(fid)
            if op == "empty": return raw is None
            if op == "not_empty": return raw is not None
            if raw is None: return False
            if op == "contains": return term.casefold() in str(raw).casefold()
            try:
                if kind in ("integer", "decimal", "currency"):
                    left, right = Decimal(str(raw)), Decimal(term)
                elif kind == "boolean":
                    left, right = raw, term.lower() in ("true", "si", "sí")
                else:
                    left, right = str(raw), term
                return {"eq": lambda: left == right, "lt": lambda: left < right, "gt": lambda: left > right}[op]()
            except Exception:
                return False
        records = [r for r in records if matches(r)]
    return records


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload, status=200, headers=None):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key,value in (headers or {}).items(): self.send_header(key,value)
        self.end_headers()
        self.wfile.write(raw)

    def _body(self, limit=6 * 1024 * 1024):
        length = int(self.headers.get("Content-Length", "0"))
        if length > limit or length <= 0:
            raise ValueError("El archivo o pedido supera el tamaño permitido.")
        return self.rfile.read(length)

    def _request_json(self):
        try: return json.loads(self._body(1024 * 1024))
        except json.JSONDecodeError: raise ValueError("El pedido contiene JSON inválido.")

    def _session_token(self):
        jar=SimpleCookie()
        try: jar.load(self.headers.get("Cookie", ""))
        except Exception: return None
        morsel=jar.get("tablio_session")
        return morsel.value if morsel else None

    def _cookie(self, token, max_age=12*3600):
        secure="; Secure" if os.environ.get("TABLIO_SECURE_COOKIES")=="1" else ""
        return f"tablio_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={max_age}{secure}"

    def _principal(self):
        user=store.session_user(self._session_token())
        if not user: raise PermissionError("Iniciá sesión para continuar.")
        if self.command in ("POST","PUT","PATCH","DELETE"):
            origin=self.headers.get("Origin")
            allowed=os.environ.get("TABLIO_ORIGIN")
            if allowed and origin and origin!=allowed: raise PermissionError("Origen no permitido.")
            if not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""),user["csrf_token"]):
                raise PermissionError("Sesión inválida. Recargá la página.")
        return user

    def _organization(self, user):
        org_id=self.headers.get("X-Organization-Id", "")
        role=store.role_for(user["id"],org_id)
        if not role: raise PermissionError("No tenés acceso a esa organización.")
        return org_id,role

    def _require_write(self, role):
        if role not in store.WRITE_ROLES: raise PermissionError("No tenés permiso para modificar datos.")

    def _require_owner(self, role):
        if role!="owner": raise PermissionError("Solo el propietario puede administrar usuarios.")

    def _route(self):
        clean_expired()
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if path.startswith("/api/"):
            if self.command == "POST" and path == "/api/login":
                body=self._request_json()
                key=(self.client_address[0],str(body.get("email","")).strip().casefold())
                with LOGIN_LOCK:
                    recent=[stamp for stamp in LOGIN_FAILURES.get(key,[]) if stamp>time.time()-900]
                    if len(recent)>=5: return self._json({"error":"Demasiados intentos. Esperá 15 minutos."},429)
                result=store.authenticate(body.get("email"),body.get("password"))
                if not result:
                    with LOGIN_LOCK: LOGIN_FAILURES[key]=recent+[time.time()]
                    return self._json({"error":"Email o contraseña incorrectos."},401)
                with LOGIN_LOCK: LOGIN_FAILURES.pop(key,None)
                token,csrf,user_id=result
                return self._json({"csrfToken":csrf,"user":{"id":user_id},"organizations":store.memberships(user_id)},
                                  headers={"Set-Cookie":self._cookie(token)})
            user=self._principal()
            if self.command == "GET" and path == "/api/me":
                return self._json({"user":{"id":user["id"],"email":user["email"],"name":user["name"]},
                                   "csrfToken":user["csrf_token"],"organizations":store.memberships(user["id"])})
            if self.command == "POST" and path == "/api/logout":
                store.logout(self._session_token())
                return self._json({"loggedOut":True},headers={"Set-Cookie":self._cookie("",0)})
            if self.command == "POST" and path == "/api/change-password":
                body=self._request_json()
                store.change_password(user["id"],body.get("currentPassword"),body.get("newPassword"))
                return self._json({"changed":True},headers={"Set-Cookie":self._cookie("",0)})
            if self.command == "POST" and path == "/api/organizations":
                org_id=store.create_organization(user["id"],self._request_json().get("name"))
                return self._json({"id":org_id},201)
            org_id,role=self._organization(user)
            if path == "/api/users" and self.command == "GET":
                self._require_owner(role)
                return self._json(store.users_for_org(org_id))
            if path == "/api/users" and self.command == "POST":
                self._require_owner(role)
                body=self._request_json()
                user_id=store.create_user_in_org(org_id,body.get("email"),body.get("name"),body.get("password"),body.get("role"))
                return self._json({"id":user_id},201)
            if path == "/api/memberships" and self.command == "POST":
                self._require_owner(role)
                body=self._request_json()
                user_id=store.add_membership(org_id,body.get("email"),body.get("role"))
                return self._json({"id":user_id},201)
            member=re.fullmatch(r"/api/users/([a-f0-9-]{36})",path)
            if member and self.command == "PUT":
                self._require_owner(role)
                changed=store.set_membership(org_id,member.group(1),self._request_json().get("role"))
                return self._json({"updated":changed},200 if changed else 404)
            if member and self.command == "DELETE":
                self._require_owner(role)
                removed=store.remove_membership(org_id,member.group(1),user["id"])
                return self._json({"removed":removed},200 if removed else 404)
        if self.command == "GET" and path == "/api/modules":
            return self._json(module_list(org_id))
        if self.command == "POST" and path == "/api/analyze":
            self._require_write(role)
            raw = self._body()
            sheets = read_workbook(raw)
            token = str(uuid.uuid4())
            (UPLOADS / f"{token}.xlsx").write_bytes(raw)
            if os.name != "nt": os.chmod(UPLOADS / f"{token}.xlsx",0o600)
            store.register_upload(token,org_id,user["id"])
            result, _ = _preview(token, sheets[0]["name"],org_id,user["id"])
            return self._json(result)
        if self.command == "GET" and path == "/api/preview":
            self._require_write(role)
            token = query.get("token", [""])[0]
            if not re.fullmatch(r"[a-f0-9-]{36}", token): raise ValueError("Importación inválida.")
            result, _ = _preview(token, query.get("sheet", [""])[0],org_id,user["id"])
            return self._json(result)
        if self.command == "POST" and path == "/api/import":
            self._require_write(role)
            body = self._request_json()
            token = body.get("token", "")
            if not re.fullmatch(r"[a-f0-9-]{36}", token): raise ValueError("Importación inválida.")
            # The import ID is the upload token, making repeated confirmations idempotent.
            try:
                preview, sheet = _preview(token, body.get("sheet"),org_id,user["id"])
            except ValueError:
                # Completed imports can be retried after the temporary file was removed.
                from .store import imported_module
                module_id = store.imported_module(org_id,token)
                if module_id: return self._json({"moduleId": module_id, "alreadyImported": True})
                raise
            corrections = body.get("formulaCorrections", {})
            if not isinstance(corrections, dict) or len(corrections) > 1000:
                raise ValueError("Correcciones de fórmulas inválidas.")
            issue_keys = {f"{issue['row']}:{issue['column']}" for issue in preview["formulaIssues"]}
            for key, formula in corrections.items():
                if key not in issue_keys or not isinstance(formula, str) or not formula.startswith("=") or len(formula) > 500:
                    raise ValueError("Corrección de fórmula inválida.")
                row_number, column = map(int, key.split(":"))
                row = next(r for r in sheet["rows"] if r["number"] == row_number)
                row["cells"][column-1] = {"formula": formula, "cached": None}
            schema = validate_schema(body.get("schema", {}), infer_sheet(sheet))
            records, errors = convert_rows(sheet, schema)
            if errors: return self._json({"errors": errors[:100], "errorCount": len(errors)}, 422)
            module_id = import_records(org_id,token, schema, records)
            (UPLOADS / f"{token}.xlsx").unlink(missing_ok=True)
            store.finish_upload(token,org_id,user["id"])
            return self._json({"moduleId": module_id, "count": len(records)})
        match = re.fullmatch(r"/api/modules/([a-f0-9-]{36})(?:/(records|export)(?:/([a-f0-9-]{36}))?)?", path)
        if match:
            mid, action, rid = match.groups()
            module = get_module(org_id,mid)
            if not module: return self._json({"error": "Módulo no encontrado."}, 404)
            schema = module["schema"]
            if self.command == "GET" and not action: return self._json(module)
            if self.command == "GET" and action == "records":
                records = filter_records(record_list(org_id,mid), schema, query)
                try: page = max(1, int(query.get("page", ["1"])[0]))
                except ValueError: page = 1
                return self._json({"total": len(records), "page": page, "items": records[(page-1)*25:page*25]})
            if self.command == "GET" and action == "export":
                records = record_list(org_id,mid)
                headers = [f["label"] for f in schema["fields"]]
                rows = [[record["values"].get(f["id"]) for f in schema["fields"]] for record in records]
                blob = write_workbook(schema["name"], headers, rows, [f["type"] for f in schema["fields"]],
                                      {i: f["formula"] for i, f in enumerate(schema["fields"]) if f.get("formula")},
                                      {f["id"]: i for i, f in enumerate(schema["fields"])})
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                self.send_header("Content-Disposition", f'attachment; filename="tablio-{mid[:8]}.xlsx"')
                self.send_header("Content-Length", str(len(blob)))
                self.end_headers(); self.wfile.write(blob); return
            if action == "records" and self.command in ("POST", "PUT"):
                self._require_write(role)
                values = validate_record(self._request_json().get("values"), schema)
                if self.command == "POST" and not rid: return self._json({"id": create_record(org_id,mid, values)}, 201)
                if self.command == "PUT" and rid:
                    if not update_record(org_id,mid, rid, values): return self._json({"error": "Registro no encontrado."}, 404)
                    return self._json({"id": rid})
            if action == "records" and self.command == "DELETE" and rid:
                self._require_write(role)
                if not delete_record(org_id,mid, rid): return self._json({"error": "Registro no encontrado."}, 404)
                return self._json({"deleted": True})
        if path.startswith("/api/"):
            return self._json({"error": "Ruta no encontrada."}, 404)
        file = WEB / (path.lstrip("/") or "index.html")
        if not file.is_file() or WEB not in file.resolve().parents:
            return self._json({"error": "Archivo no encontrado."}, 404)
        raw = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers(); self.wfile.write(raw)

    def do_GET(self): self._safe()
    def do_POST(self): self._safe()
    def do_PUT(self): self._safe()
    def do_DELETE(self): self._safe()

    def _safe(self):
        try: self._route()
        except PermissionError as exc: self._json({"error":str(exc)},401 if "Iniciá sesión" in str(exc) else 403)
        except sqlite3.IntegrityError: self._json({"error":"El dato ya existe o no cumple una restricción."},409)
        except (ValueError, SpreadsheetError) as exc: self._json({"error": str(exc)}, 400)
        except Exception:
            self.log_error("Error interno al procesar %s", self.path)
            self._json({"error": "Ocurrió un error interno."}, 500)


def main():
    initialize(); clean_expired()
    port = int(os.environ.get("TABLIO_PORT", "8000"))
    host = os.environ.get("TABLIO_BIND_HOST", "127.0.0.1")
    if host != "127.0.0.1" and os.environ.get("TABLIO_SECURE_COOKIES")!="1":
        raise SystemExit("La exposición de red requiere HTTPS y TABLIO_SECURE_COOKIES=1.")
    if host != "127.0.0.1" and not os.environ.get("TABLIO_ORIGIN", "").startswith("https://"):
        raise SystemExit("Configurá TABLIO_ORIGIN con la URL HTTPS pública.")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Tablio disponible en {host}:{port}",flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__": main()
