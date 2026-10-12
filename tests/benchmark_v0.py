"""Measure the V0 design limit with synthetic, non-sensitive records."""
import json
import tempfile
import time
from pathlib import Path

from app import store
from app.core import convert_rows, infer_sheet, validate_schema
from app.xlsx_io import read_workbook, write_workbook

headers = [f'Campo {i}' for i in range(1, 31)]
rows = [[f'valor-{r:04d}-{c:02d}' for c in range(30)] for r in range(5000)]
start=time.perf_counter()
xlsx=write_workbook('Carga',headers,rows)
sheet=read_workbook(xlsx)[0]
proposal=infer_sheet(sheet)
parse_seconds=time.perf_counter()-start
schema=validate_schema({'schemaVersion':1,'name':'Carga','primaryFieldId':'f1','fields':[
    {'id':f['id'],'label':f['label'],'type':'text','required':True,'sourceColumn':f['sourceColumn']}
    for f in proposal['fields']]},proposal)
start=time.perf_counter()
records,errors=convert_rows(sheet,schema)
convert_seconds=time.perf_counter()-start
assert len(records)==5000 and not errors
(Path(__file__).resolve().parent.parent/'tmp').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent/'tmp') as directory:
    old_path=store.DB_PATH
    store.DB_PATH=Path(directory)/'bench.sqlite3'
    try:
        store.initialize()
        start=time.perf_counter()
        module_id=store.import_records('benchmark',schema,records)
        import_seconds=time.perf_counter()-start
        start=time.perf_counter()
        found=store.record_list(module_id)
        query_seconds=time.perf_counter()-start
        assert len(found)==5000
    finally:
        store.DB_PATH=old_path
print(json.dumps({'records':5000,'columns':30,'xlsx_mib':round(len(xlsx)/1048576,2),
                  'parse_and_infer_s':round(parse_seconds,2),'convert_s':round(convert_seconds,2),
                  'import_s':round(import_seconds,2),'read_all_s':round(query_seconds,2)},indent=2))
