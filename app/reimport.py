"""Deterministic preview for incremental XLSX imports."""
import hashlib
from itertools import combinations
import json
import uuid


def _key(values, field_ids):
    parts = [values.get(field_id) for field_id in field_ids]
    if parts[0] is None or parts[0] == "":
        return None
    return json.dumps(parts[0] if len(parts) == 1 else parts, ensure_ascii=False, sort_keys=True)


def _label(values, field_ids):
    parts = [values.get(field_id) for field_id in field_ids]
    return parts[0] if len(parts) == 1 else " · ".join(str(part) if part not in (None, "") else "(vacío)" for part in parts)


def suggest_key_fields(records, incoming, primary_field_id, candidate_field_ids):
    """Find the smallest unique combination containing the selected main column."""
    others = [field_id for field_id in candidate_field_ids if field_id != primary_field_id]
    def unique(items, fields):
        seen = set()
        for item in items:
            value = _key(item["values"], fields)
            if value is None or value in seen:
                return False
            seen.add(value)
        return True
    for extra_count in (1, 2):
        for extras in combinations(others, extra_count):
            fields = [primary_field_id, *extras]
            if unique(records, fields) and unique(incoming, fields):
                return fields
    return None


def plan(records, incoming, key_field_id, import_id, imported_field_ids):
    field_ids = [key_field_id] if isinstance(key_field_id, str) else list(key_field_id)

    existing={}
    conflicts=[]
    for record in records:
        value=_key(record["values"], field_ids)
        if value is None: continue
        if value in existing:
            conflicts.append({"row":None,"key":_label(record["values"], field_ids),"message":"La clave aparece más de una vez en el módulo."})
        else: existing[value]=record
    seen=set()
    changes=[]
    unchanged=0
    for item in incoming:
        row,values=item["row"],item["values"]
        value=_key(values, field_ids)
        if value is None:
            conflicts.append({"row":row,"key":None,"message":"Falta la clave identificadora."})
            continue
        if value in seen:
            conflicts.append({"row":row,"key":_label(values, field_ids),"message":"La clave está duplicada en el archivo."})
            continue
        seen.add(value)
        old=existing.get(value)
        if old:
            merged=dict(old["values"])
            merged.update({fid:values[fid] for fid in imported_field_ids})
            if merged==old["values"]: unchanged+=1
            else: changes.append({"action":"update","id":old["id"],"row":row,"key":_label(values, field_ids),"old":old["values"],"new":merged})
        else:
            record_id=str(uuid.uuid5(uuid.UUID(import_id),value))
            changes.append({"action":"create","id":record_id,"row":row,"key":_label(values, field_ids),"old":None,"new":values})
    serialized=json.dumps({"key":field_ids,"changes":changes,"unchanged":unchanged,"conflicts":conflicts},ensure_ascii=False,sort_keys=True,separators=(",",":"))
    digest=hashlib.sha256(serialized.encode()).hexdigest()
    return {"changes":changes,"conflicts":conflicts,"unchanged":unchanged,"digest":digest,
            "created":sum(c["action"]=="create" for c in changes),
            "updated":sum(c["action"]=="update" for c in changes)}
