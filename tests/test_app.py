import io
import http.client
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from app import store
from app.core import convert_rows, infer_sheet
from app.formulas import parse_formula, evaluate
from app.server import Handler
from app.xlsx_io import SpreadsheetError, read_workbook, write_workbook
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / 'outputs' / '01a06e97-c8d6-7c20-aebd-4c816513d8af'


class AppTests(unittest.TestCase):
    def test_a1_and_structured_references_are_equivalent(self):
        labels=['COSTO','% DE GTOS','BOLSA']
        formulas=['=(A2*B2)+C2','=([@COSTO]*[@[% DE GTOS]])+[@BOLSA]',
                  '=(Tabla1[[#This Row],[COSTO]]*Tabla1[[#This Row],[% DE GTOS]])+Tabla1[[#This Row],[BOLSA]]']
        parsed=[parse_formula(value,2,labels)[0] for value in formulas]
        self.assertEqual(parsed,['f1 * f2 + f3']*3)
        self.assertEqual(evaluate(parsed[0],{'f1':'100','f2':'0.2','f3':'5'}),'25.0')
        with self.assertRaises(ValueError): parse_formula('=A3+B2',2,labels)

    @classmethod
    def setUpClass(cls):
        (ROOT / 'tmp').mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / 'tmp')
        cls.previous_db = store.DB_PATH
        store.DB_PATH = Path(cls.temp.name) / 'test.sqlite3'
        store.initialize()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()
        store.DB_PATH = cls.previous_db
        cls.temp.cleanup()

    def request(self, path, method='GET', payload=None, content_type='application/json'):
        if isinstance(payload, dict): payload=json.dumps(payload).encode()
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        conn.request(method,path,body=payload,headers={'Content-Type':content_type} if payload else {})
        response=conn.getresponse(); body=response.read(); status=response.status; conn.close()
        return status, body if path.endswith('/export') and status==200 else json.loads(body)

    def schema_for(self, preview):
        fields=[]
        for field in preview['fields']:
            kind=field['type']
            if field['label'] in ('Categoria','Unidad','Rubro','UnidadVenta','Estado'):
                kind='enum'
            item={'id':field['id'],'label':field['label'],'sourceColumn':field['sourceColumn'],
                  'type':kind,'required':False}
            if kind in ('currency','decimal'): item['scale']=field['scale']
            if kind=='enum':
                source=read_workbook((FIXTURES/('minimercado.xlsx' if preview['sheet'].startswith('Productos') else 'corralon_materiales.xlsx')).read_bytes())[0]
                item['options']=list(dict.fromkeys(str(row['cells'].get(field['sourceColumn'])) for row in source['rows'][1:]))
            fields.append(item)
        return {'schemaVersion':1,'name':preview['sheet'],'primaryFieldId':fields[1]['id'],'fields':fields}

    def test_two_sector_workbooks_end_to_end(self):
        for file_name in ('minimercado.xlsx','corralon_materiales.xlsx'):
            with self.subTest(file=file_name):
                raw=(FIXTURES/file_name).read_bytes()
                status, preview=self.request('/api/analyze','POST',raw,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                self.assertEqual(status,200)
                self.assertEqual(preview['rowCount'],30)
                schema=self.schema_for(preview)
                body={'token':preview['token'],'sheet':preview['sheet'],'schema':schema}
                status,result=self.request('/api/import','POST',body)
                self.assertEqual(status,200,result)
                self.assertEqual(result['count'],30)
                mid=result['moduleId']
                status,retry=self.request('/api/import','POST',body)
                self.assertEqual(status,200)
                self.assertEqual(retry['moduleId'],mid)
                status,first_page=self.request(f'/api/modules/{mid}/records?page=1')
                self.assertEqual((status,first_page['total'],len(first_page['items'])),(200,30,25))
                status,second_page=self.request(f'/api/modules/{mid}/records?page=2')
                self.assertEqual(len(second_page['items']),5)
                field=schema['fields'][0]
                self.assertEqual(first_page['items'][0]['values'][field['id']], '00001' if file_name.startswith('mini') else 'CM-0001')
                status,filtered=self.request(f'/api/modules/{mid}/records?field={field["id"]}&op=eq&value={first_page["items"][0]["values"][field["id"]]}')
                self.assertEqual(filtered['total'],1)
                record=first_page['items'][0]
                updated=dict(record['values']); price_field=next(f for f in schema['fields'] if f['type']=='currency')
                updated[price_field['id']]='1234.50'
                status,_=self.request(f'/api/modules/{mid}/records/{record["id"]}','PUT',{'values':updated})
                self.assertEqual(status,200)
                status,created=self.request(f'/api/modules/{mid}/records','POST',{'values':updated})
                self.assertEqual(status,201)
                status,_=self.request(f'/api/modules/{mid}/records/{created["id"]}','DELETE')
                self.assertEqual(status,200)
                status,exported=self.request(f'/api/modules/{mid}/export')
                self.assertEqual(status,200)
                self.assertEqual(len(read_workbook(exported)[0]['rows']),31)

    def test_invalid_record_does_not_publish_import(self):
        raw=write_workbook('Fallos',['Codigo','Saldo'],[['0001','12.345']])
        status,preview=self.request('/api/analyze','POST',raw,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(status,200)
        schema={'schemaVersion':1,'name':'Fallos','primaryFieldId':'f1','fields':[
            {'id':'f1','label':'Codigo','type':'text','required':True,'sourceColumn':0},
            {'id':'f2','label':'Saldo','type':'currency','required':True,'scale':2,'sourceColumn':1}]}
        before=len(store.module_list())
        status,result=self.request('/api/import','POST',{'token':preview['token'],'sheet':'Fallos','schema':schema})
        self.assertEqual(status,422)
        self.assertEqual(result['errors'][0]['row'],2)
        self.assertEqual(len(store.module_list()),before)

    def test_date_required_and_identifier_errors(self):
        raw=write_workbook('Validacion',['Codigo','Fecha','Cantidad'],[['0001','31/02/2026',2],['','2026-08-01',1.5]])
        sheet=read_workbook(raw)[0]
        proposal=infer_sheet(sheet)
        schema={'fields':[
            {'id':'f1','label':'Codigo','type':'text','required':True,'sourceColumn':0},
            {'id':'f2','label':'Fecha','type':'date','required':True,'sourceColumn':1},
            {'id':'f3','label':'Cantidad','type':'integer','required':True,'sourceColumn':2}]}
        records,errors=convert_rows(sheet,schema)
        self.assertEqual(len(records),2)
        self.assertEqual({e['code'] for e in errors},{'INVALID_DATE','REQUIRED_VALUE','INVALID_NUMBER'})
        self.assertEqual({e['row'] for e in errors},{2,3})

    def test_sqlite_survives_reopening_connection(self):
        modules=store.module_list()
        # Previous tests may run in a different order; create a small independent module.
        schema={'schemaVersion':1,'name':'Persistencia','primaryFieldId':'f1','fields':[
            {'id':'f1','label':'Codigo','type':'text','required':True,'sourceColumn':0}]}
        mid=store.import_records('test-persist-'+str(len(modules)),schema,[{'f1':'0009'}])
        self.assertEqual(store.get_module(mid)['schema']['name'],'Persistencia')
        self.assertEqual(store.record_list(mid)[0]['values']['f1'],'0009')

    def test_formula_import_correction_recalculation_and_export(self):
        source=write_workbook('Precios',['COSTO','% DE GTOS','BOLSA','TOTAL'],[[100,0.2,5,25]],['integer','decimal','integer','decimal'])
        with zipfile.ZipFile(io.BytesIO(source)) as archive:
            contents={name:archive.read(name) for name in archive.namelist()}
        xml=contents['xl/worksheets/sheet1.xml'].decode()
        xml=xml.replace('<c r="D2"><v>25</v></c>','<c r="D2"><f>(A2*B2)+C2</f><v>25</v></c>')
        contents['xl/worksheets/sheet1.xml']=xml.encode()
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            for name, content in contents.items(): archive.writestr(name,content)
        status,preview=self.request('/api/analyze','POST',buffer.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(status,200,preview)
        self.assertEqual(preview['fields'][3]['formula'],'f1 * f2 + f3')
        fields=[]
        for f in preview['fields']:
            item={k:f[k] for k in ('id','label','type','required','sourceColumn')}
            if f['type'] in ('decimal','currency'): item['scale']=f['scale']
            fields.append(item)
        schema={'schemaVersion':1,'name':'Precios','primaryFieldId':'f1','fields':fields}
        status,imported=self.request('/api/import','POST',{'token':preview['token'],'sheet':'Precios','schema':schema})
        self.assertEqual(status,200,imported)
        mid=imported['moduleId']
        _,data=self.request(f'/api/modules/{mid}/records')
        self.assertEqual(data['items'][0]['values']['f4'],'25.000000')
        values={'f1':200,'f2':'0.2','f3':5,'f4':'999'}
        status,created=self.request(f'/api/modules/{mid}/records','POST',{'values':values})
        self.assertEqual(status,201,created)
        _,data=self.request(f'/api/modules/{mid}/records')
        self.assertEqual(data['items'][-1]['values']['f4'],'45.000000')
        _,exported=self.request(f'/api/modules/{mid}/export')
        self.assertEqual(read_workbook(exported)[0]['rows'][2]['cells'][3]['formula'],'=((A3*B3)+C3)')

    def test_formula_issue_can_be_corrected_during_import(self):
        source=write_workbook('Errores',['COSTO','TOTAL'],[[100,200],[200,400]],['integer','integer'])
        with zipfile.ZipFile(io.BytesIO(source)) as archive:
            contents={name:archive.read(name) for name in archive.namelist()}
        xml=contents['xl/worksheets/sheet1.xml'].decode()
        xml=xml.replace('<c r="B2"><v>200</v></c>','<c r="B2"><f>A2*2</f><v>200</v></c>')
        xml=xml.replace('<c r="B3"><v>400</v></c>','<c r="B3" t="e"><f>#REF!*2</f><v>#REF!</v></c>')
        contents['xl/worksheets/sheet1.xml']=xml.encode()
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            for name, content in contents.items(): archive.writestr(name,content)
        status,preview=self.request('/api/analyze','POST',buffer.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(status,200,preview)
        self.assertEqual(len(preview['formulaIssues']),1)
        f=preview['fields']
        schema={'schemaVersion':1,'name':'Errores','primaryFieldId':'f1','fields':[
            {'id':'f1','label':'COSTO','type':'integer','required':False,'sourceColumn':0},
            {'id':'f2','label':'TOTAL','type':'decimal','required':False,'sourceColumn':1,'scale':f[1]['scale']}]}
        body={'token':preview['token'],'sheet':'Errores','schema':schema}
        status,result=self.request('/api/import','POST',body)
        self.assertEqual(status,422,result)
        self.assertEqual(result['errors'][0]['code'],'INVALID_FORMULA')
        body['formulaCorrections']={'3:2':'=A3*2'}
        status,result=self.request('/api/import','POST',body)
        self.assertEqual(status,200,result)
        _,data=self.request(f"/api/modules/{result['moduleId']}/records")
        self.assertEqual(data['items'][1]['values']['f2'],'400.000000')


if __name__=='__main__': unittest.main()
