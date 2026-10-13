"""Deterministic preview for incremental XLSX imports."""
import hashlib
import json
import uuid


def plan(records, incoming, key_field_id, import_id, imported_field_ids):
    def key(value):
        return None if value is None or value == "" else json.dumps(value,ensure_ascii=False,sort_keys=True)

    existing={}
    conflicts=[]
    for record in records:
        value=key(record["values"].get(key_field_id))
        if value is None: continue
        if value in existing:
            conflicts.append({"row":None,"key":record["values"].get(key_field_id),"message":"La clave aparece más de una vez en el módulo."})
        else: existing[value]=record
    seen=set()
    changes=[]
    unchanged=0
    for item in incoming:
        row,values=item["row"],item["values"]
        value=key(values.get(key_field_id))
        if value is None:
            conflicts.append({"row":row,"key":None,"message":"Falta la clave identificadora."})
            continue
        if value in seen:
            conflicts.append({"row":row,"key":values[key_field_id],"message":"La clave está duplicada en el archivo."})
            continue
        seen.add(value)
        old=existing.get(value)
        if old:
            merged=dict(old["values"])
            merged.update({fid:values[fid] for fid in imported_field_ids})
            if merged==old["values"]: unchanged+=1
            else: changes.append({"action":"update","id":old["id"],"row":row,"key":values[key_field_id],"old":old["values"],"new":merged})
        else:
            record_id=str(uuid.uuid5(uuid.UUID(import_id),value))
            changes.append({"action":"create","id":record_id,"row":row,"key":values[key_field_id],"old":None,"new":values})
    serialized=json.dumps({"key":key_field_id,"changes":changes,"unchanged":unchanged,"conflicts":conflicts},ensure_ascii=False,sort_keys=True,separators=(",",":"))
    digest=hashlib.sha256(serialized.encode()).hexdigest()
    return {"changes":changes,"conflicts":conflicts,"unchanged":unchanged,"digest":digest,
            "created":sum(c["action"]=="create" for c in changes),
            "updated":sum(c["action"]=="update" for c in changes)}
