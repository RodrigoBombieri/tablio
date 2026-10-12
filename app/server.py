"""Run the local Tablio PoC with: python -m app.server"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import time
import uuid
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .core import convert_rows, infer_sheet, validate_record, validate_schema
from .store import (create_record, delete_record, get_module, import_records,
                    initialize, module_list, record_list, update_record)
from .xlsx_io import SpreadsheetError, read_workbook, write_workbook

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)


def clean_expired():
    for path in UPLOADS.glob("*.xlsx"):
        if time.time() - path.stat().st_mtime > 24 * 3600:
            path.unlink(missing_ok=True)


def _preview(token, sheet_name):
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
    def _json(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
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

    def _route(self):
        clean_expired()
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if self.command == "GET" and path == "/api/modules":
            return self._json(module_list())
        if self.command == "POST" and path == "/api/analyze":
            raw = self._body()
            sheets = read_workbook(raw)
            token = str(uuid.uuid4())
            (UPLOADS / f"{token}.xlsx").write_bytes(raw)
            result, _ = _preview(token, sheets[0]["name"])
            return self._json(result)
        if self.command == "GET" and path == "/api/preview":
            token = query.get("token", [""])[0]
            if not re.fullmatch(r"[a-f0-9-]{36}", token): raise ValueError("Importación inválida.")
            result, _ = _preview(token, query.get("sheet", [""])[0])
            return self._json(result)
        if self.command == "POST" and path == "/api/import":
            body = self._request_json()
            token = body.get("token", "")
            if not re.fullmatch(r"[a-f0-9-]{36}", token): raise ValueError("Importación inválida.")
            # The import ID is the upload token, making repeated confirmations idempotent.
            try:
                preview, sheet = _preview(token, body.get("sheet"))
            except ValueError:
                # Completed imports can be retried after the temporary file was removed.
                from .store import imported_module
                module_id = imported_module(token)
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
            module_id = import_records(token, schema, records)
            (UPLOADS / f"{token}.xlsx").unlink(missing_ok=True)
            return self._json({"moduleId": module_id, "count": len(records)})
        match = re.fullmatch(r"/api/modules/([a-f0-9-]{36})(?:/(records|export)(?:/([a-f0-9-]{36}))?)?", path)
        if match:
            mid, action, rid = match.groups()
            module = get_module(mid)
            if not module: return self._json({"error": "Módulo no encontrado."}, 404)
            schema = module["schema"]
            if self.command == "GET" and not action: return self._json(module)
            if self.command == "GET" and action == "records":
                records = filter_records(record_list(mid), schema, query)
                try: page = max(1, int(query.get("page", ["1"])[0]))
                except ValueError: page = 1
                return self._json({"total": len(records), "page": page, "items": records[(page-1)*25:page*25]})
            if self.command == "GET" and action == "export":
                records = record_list(mid)
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
                values = validate_record(self._request_json().get("values"), schema)
                if self.command == "POST" and not rid: return self._json({"id": create_record(mid, values)}, 201)
                if self.command == "PUT" and rid:
                    if not update_record(mid, rid, values): return self._json({"error": "Registro no encontrado."}, 404)
                    return self._json({"id": rid})
            if action == "records" and self.command == "DELETE" and rid:
                if not delete_record(mid, rid): return self._json({"error": "Registro no encontrado."}, 404)
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
        self.end_headers(); self.wfile.write(raw)

    def do_GET(self): self._safe()
    def do_POST(self): self._safe()
    def do_PUT(self): self._safe()
    def do_DELETE(self): self._safe()

    def _safe(self):
        try: self._route()
        except (ValueError, SpreadsheetError) as exc: self._json({"error": str(exc)}, 400)
        except Exception:
            self.log_error("Error interno al procesar %s", self.path)
            self._json({"error": "Ocurrió un error interno."}, 500)


def main():
    initialize(); clean_expired()
    port = int(os.environ.get("TABLIO_PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Tablio disponible en http://127.0.0.1:{port}")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__": main()
