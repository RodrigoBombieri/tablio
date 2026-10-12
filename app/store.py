"""Local single-operator persistence for the V0 proof of concept."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tablio.sqlite3"


@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS modules (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, schema_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS records (
          id TEXT PRIMARY KEY, module_id TEXT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
          values_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS records_module ON records(module_id);
        CREATE TABLE IF NOT EXISTS imports (
          id TEXT PRIMARY KEY, module_id TEXT NOT NULL REFERENCES modules(id),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)


def module_list():
    with connection() as db:
        return [{"id": row["id"], "name": row["name"], "count": row["count"]} for row in db.execute(
            "SELECT m.id,m.name,COUNT(r.id) AS count FROM modules m LEFT JOIN records r ON r.module_id=m.id GROUP BY m.id ORDER BY m.created_at DESC")]


def get_module(module_id):
    with connection() as db:
        row = db.execute("SELECT * FROM modules WHERE id=?", (module_id,)).fetchone()
        return {"id": row["id"], "schema": json.loads(row["schema_json"])} if row else None


def imported_module(import_id):
    with connection() as db:
        row = db.execute("SELECT module_id FROM imports WHERE id=?", (import_id,)).fetchone()
        return row["module_id"] if row else None


def import_records(import_id, schema, records):
    with connection() as db:
        existing = db.execute("SELECT module_id FROM imports WHERE id=?", (import_id,)).fetchone()
        if existing:
            return existing["module_id"]
        module_id = str(uuid.uuid4())
        db.execute("INSERT INTO modules(id,name,schema_json) VALUES(?,?,?)", (module_id, schema["name"], json.dumps(schema, ensure_ascii=False)))
        db.executemany("INSERT INTO records(id,module_id,values_json) VALUES(?,?,?)", [
            (str(uuid.uuid4()), module_id, json.dumps(values, ensure_ascii=False)) for values in records
        ])
        db.execute("INSERT INTO imports(id,module_id) VALUES(?,?)", (import_id, module_id))
        return module_id


def record_list(module_id):
    with connection() as db:
        return [{"id": row["id"], "values": json.loads(row["values_json"])} for row in db.execute(
            "SELECT id,values_json FROM records WHERE module_id=? ORDER BY rowid", (module_id,))]


def create_record(module_id, values):
    record_id = str(uuid.uuid4())
    with connection() as db:
        db.execute("INSERT INTO records(id,module_id,values_json) VALUES(?,?,?)", (record_id, module_id, json.dumps(values, ensure_ascii=False)))
    return record_id


def update_record(module_id, record_id, values):
    with connection() as db:
        cursor = db.execute("UPDATE records SET values_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND module_id=?", (json.dumps(values, ensure_ascii=False), record_id, module_id))
        return cursor.rowcount > 0


def delete_record(module_id, record_id):
    with connection() as db:
        cursor = db.execute("DELETE FROM records WHERE id=? AND module_id=?", (record_id, module_id))
        return cursor.rowcount > 0
