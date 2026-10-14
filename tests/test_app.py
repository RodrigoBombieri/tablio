import io
import http.client
import json
import os
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from app import store
from app import backup
from app.core import convert_rows, infer_sheet
from app.formulas import parse_formula, evaluate
from app.server import Handler, TablioHTTPServer
from app.xlsx_io import SpreadsheetError, read_workbook, write_workbook
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / 'outputs' / '01a06e97-c8d6-7c20-aebd-4c816513d8af'


class AppTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows port binding')
    def test_second_server_cannot_bind_to_same_port(self):
        first=TablioHTTPServer(('127.0.0.1',0),Handler)
        try:
            with self.assertRaises(OSError):
                second=TablioHTTPServer(('127.0.0.1',first.server_port),Handler)
                second.server_close()
        finally:
            first.server_close()

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
        cls.owner_id,cls.org_id=store.bootstrap_owner('owner@tablio.test','Dueño','contraseña-segura-123','Pruebas')
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        conn=http.client.HTTPConnection('127.0.0.1',cls.server.server_port)
        conn.request('POST','/api/login',body=json.dumps({'email':'owner@tablio.test','password':'contraseña-segura-123'}),headers={'Content-Type':'application/json'})
        response=conn.getresponse(); cls.cookie=response.getheader('Set-Cookie').split(';')[0];cls.csrf=json.loads(response.read())['csrfToken'];conn.close()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()
        store.DB_PATH = cls.previous_db
        cls.temp.cleanup()

    def request(self, path, method='GET', payload=None, content_type='application/json', org=None, cookie=None, csrf=None):
        if isinstance(payload, dict): payload=json.dumps(payload).encode()
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        headers={'X-Organization-Id':org or self.org_id,'Cookie':self.cookie if cookie is None else cookie,
                 'X-CSRF-Token':self.csrf if csrf is None else csrf}
        if payload: headers['Content-Type']=content_type
        conn.request(method,path,body=payload,headers=headers)
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
        before=len(store.module_list(self.org_id))
        status,result=self.request('/api/import','POST',{'token':preview['token'],'sheet':'Fallos','schema':schema})
        self.assertEqual(status,422)
        self.assertEqual(result['errors'][0]['row'],2)
        self.assertEqual(len(store.module_list(self.org_id)),before)

    def test_auth_roles_and_organization_isolation(self):
        second=store.create_organization(self.owner_id,'Otra organización')
        viewer=store.create_user_in_org(second,'viewer@tablio.test','Lector','contraseña-segura-456','viewer')
        token,csrf,_=store.authenticate('viewer@tablio.test','contraseña-segura-456')
        cookie='tablio_session='+token
        status,_=self.request('/api/modules',org=self.org_id,cookie=cookie,csrf=csrf)
        self.assertEqual(status,403)
        status,modules=self.request('/api/modules',org=second,cookie=cookie,csrf=csrf)
        self.assertEqual((status,modules),(200,[]))
        raw=write_workbook('Solo lectura',['Dato'],[['x']])
        status,_=self.request('/api/analyze','POST',raw,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',org=second,cookie=cookie,csrf=csrf)
        self.assertEqual(status,403)
        status,_=self.request('/api/modules','GET',org=second,cookie='',csrf='')
        self.assertEqual(status,401)
        status,_=self.request('/api/organizations','POST',{'name':'Sin CSRF'},cookie=self.cookie,csrf='')
        self.assertEqual(status,403)
        schema={'schemaVersion':1,'name':'Privado','primaryFieldId':'f1','fields':[{'id':'f1','label':'Dato','type':'text','required':False,'sourceColumn':0}]}
        mid=store.import_records(self.org_id,'private-test',schema,[{'f1':'secreto'}])
        status,_=self.request(f'/api/modules/{mid}',org=second,cookie=cookie,csrf=csrf)
        self.assertEqual(status,404)
        self.assertEqual(store.role_for(viewer,second),'viewer')

    def test_user_management_revokes_sessions_and_private_uploads(self):
        status,created=self.request('/api/users','POST',{'name':'Editor','email':'editor@tablio.test','password':'contraseña-segura-789','role':'viewer'})
        self.assertEqual(status,201,created)
        token,csrf,_=store.authenticate('editor@tablio.test','contraseña-segura-789')
        cookie='tablio_session='+token
        status,_=self.request('/api/users','GET',cookie=cookie,csrf=csrf)
        self.assertEqual(status,403)
        status,_=self.request(f"/api/users/{created['id']}",'PUT',{'role':'editor'})
        self.assertEqual(status,200)
        status,_=self.request('/api/modules',cookie=cookie,csrf=csrf)
        self.assertEqual(status,401)
        token,csrf,_=store.authenticate('editor@tablio.test','contraseña-segura-789')
        cookie='tablio_session='+token
        raw=write_workbook('Pendiente',['Dato'],[['x']])
        status,preview=self.request('/api/analyze','POST',raw,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',cookie=cookie,csrf=csrf)
        self.assertEqual(status,200,preview)
        other=store.create_organization(self.owner_id,'Aislada')
        status,_=self.request(f"/api/preview?token={preview['token']}&sheet=Pendiente",org=other)
        self.assertEqual(status,400)
        status,_=self.request(f"/api/users/{created['id']}",'DELETE')
        self.assertEqual(status,200)
        status,_=self.request('/api/modules',cookie=cookie,csrf=csrf)
        self.assertEqual(status,401)

    def test_online_backup_is_consistent(self):
        previous=backup.BACKUP_DIR
        backup.BACKUP_DIR=Path(self.temp.name)/'backups'
        try:
            path=backup.create_backup()
            self.assertTrue(backup.verify_backup(path))
            self.assertGreater(path.stat().st_size,0)
            self.assertTrue(backup.backup_status()['ok'])
        finally:
            backup.BACKUP_DIR=previous

    def test_restore_backup_recovers_previous_state(self):
        previous_db,previous_backups=store.DB_PATH,backup.BACKUP_DIR
        store.DB_PATH=Path(self.temp.name)/'restore-test.sqlite3'
        backup.BACKUP_DIR=Path(self.temp.name)/'restore-backups'
        try:
            store.initialize()
            user_id,_=store.bootstrap_owner('restore@tablio.test','Restaurar','contraseña-segura-333')
            saved=backup.create_backup()
            store.create_organization(user_id,'Después del backup')
            self.assertEqual(len(store.memberships(user_id)),2)
            backup.restore_backup(saved)
            self.assertEqual(len(store.memberships(user_id)),1)
            self.assertTrue(any(backup.BACKUP_DIR.glob('tablio-*.sqlite3')))
        finally:
            store.DB_PATH,backup.BACKUP_DIR=previous_db,previous_backups

    def test_password_change_revokes_sessions(self):
        store.create_user_in_org(self.org_id,'password@tablio.test','Cambio','contraseña-segura-111','editor')
        token,csrf,_=store.authenticate('password@tablio.test','contraseña-segura-111')
        status,result=self.request('/api/change-password','POST',{'currentPassword':'contraseña-segura-111','newPassword':'contraseña-nueva-222'},cookie='tablio_session='+token,csrf=csrf)
        self.assertEqual(status,200,result)
        status,_=self.request('/api/modules',cookie='tablio_session='+token,csrf=csrf)
        self.assertEqual(status,401)
        self.assertIsNone(store.authenticate('password@tablio.test','contraseña-segura-111'))
        self.assertIsNotNone(store.authenticate('password@tablio.test','contraseña-nueva-222'))

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
        modules=store.module_list(self.org_id)
        # Previous tests may run in a different order; create a small independent module.
        schema={'schemaVersion':1,'name':'Persistencia','primaryFieldId':'f1','fields':[
            {'id':'f1','label':'Codigo','type':'text','required':True,'sourceColumn':0}]}
        mid=store.import_records(self.org_id,'test-persist-'+str(len(modules)),schema,[{'f1':'0009'}])
        self.assertEqual(store.get_module(self.org_id,mid)['schema']['name'],'Persistencia')
        self.assertEqual(store.record_list(self.org_id,mid)[0]['values']['f1'],'0009')

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

    def test_merged_cells_and_formula_row_exclusion(self):
        source=write_workbook('Datos',['CODIGO','VALOR','OTRO'],[['A',10,'uno'],['B',20,'dos'],['C',30,'tres']])
        with zipfile.ZipFile(io.BytesIO(source)) as archive:
            contents={name:archive.read(name) for name in archive.namelist()}
        xml=contents['xl/worksheets/sheet1.xml'].decode()
        xml=xml.replace('<c r="B3"><v>20</v></c>','<c r="B3" t="e"><f>#REF!*2</f><v>#REF!</v></c>')
        xml=xml.replace('</worksheet>','<mergeCells count="1"><mergeCell ref="E5:F5"/></mergeCells></worksheet>')
        contents['xl/worksheets/sheet1.xml']=xml.encode()
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            for name, content in contents.items(): archive.writestr(name,content)
        status,preview=self.request('/api/analyze','POST',buffer.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(status,200,preview)
        self.assertEqual(len(preview['formulaIssues']),1)
        schema={'schemaVersion':1,'name':'Datos','primaryFieldId':'f1','fields':[
            {'id':'f1','label':'CODIGO','type':'text','required':False,'sourceColumn':0},
            {'id':'f2','label':'VALOR','type':'integer','required':False,'sourceColumn':1},
            {'id':'f3','label':'OTRO','type':'text','required':False,'sourceColumn':2}]}
        body={'token':preview['token'],'sheet':'Datos','schema':schema,'excludedRows':[3]}
        status,checked=self.request('/api/import/validate','POST',body)
        self.assertEqual(status,200,checked)
        self.assertEqual((checked['rowCount'],checked['errorCount']),(2,0))
        status,created=self.request('/api/import','POST',body)
        self.assertEqual(status,200,created)
        self.assertEqual(created['count'],2)
        _,records=self.request(f"/api/modules/{created['moduleId']}/records")
        self.assertEqual([r['values']['f1'] for r in records['items']],['A','C'])
        self.assertTrue(all('f3' in r['values'] for r in records['items']))

    def test_reimport_preview_commit_undo_and_duplicate_guard(self):
        schema={'schemaVersion':1,'revision':1,'name':'Actualizable','primaryFieldId':'f1','fields':[
            {'id':'f1','label':'Codigo','type':'text','required':True,'sourceColumn':0},
            {'id':'f2','label':'Nombre','type':'text','required':False,'sourceColumn':1}]}
        mid=store.import_records(self.org_id,str(__import__('uuid').uuid4()),schema,[{'f1':'A','f2':'Antes'},{'f1':'B','f2':'Queda'}])
        raw=write_workbook('Actualizable',['Codigo','Nombre'],[['A','Después'],['C','Nuevo']])
        status,upload=self.request('/api/analyze','POST',raw,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(status,200,upload)
        body={'token':upload['token'],'sheet':upload['sheet'],'moduleId':mid,'keyFieldId':'f1'}
        status,preview=self.request('/api/reimport/preview','POST',body)
        self.assertEqual(status,200,preview)
        self.assertEqual((preview['created'],preview['updated'],preview['unchanged']),(1,1,0))
        body['digest']=preview['digest']
        status,done=self.request('/api/reimport/confirm','POST',body)
        self.assertEqual(status,200,done)
        status,retry=self.request('/api/reimport/confirm','POST',body)
        self.assertEqual(status,200,retry)
        self.assertTrue(retry['alreadyImported'])
        values={r['values']['f1']:r['values']['f2'] for r in store.record_list(self.org_id,mid)}
        self.assertEqual(values,{'A':'Después','B':'Queda','C':'Nuevo'})
        status,history=self.request(f'/api/modules/{mid}/reimports')
        self.assertEqual((status,history[0]['created'],history[0]['updated']),(200,1,1))
        status,undone=self.request(f"/api/modules/{mid}/reimports/{done['runId']}",'POST',{})
        self.assertEqual(status,200,undone)
        values={r['values']['f1']:r['values']['f2'] for r in store.record_list(self.org_id,mid)}
        self.assertEqual(values,{'A':'Antes','B':'Queda'})
        raw=write_workbook('Actualizable',['Codigo','Nombre'],[['A','Uno'],['A','Dos']])
        _,upload=self.request('/api/analyze','POST',raw,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        status,conflict=self.request('/api/reimport/preview','POST',{'token':upload['token'],'sheet':upload['sheet'],'moduleId':mid,'keyFieldId':'f1'})
        self.assertEqual(status,422)
        self.assertEqual(conflict['conflictCount'],1)

    def test_reimport_rechecks_preview_and_denies_other_organization(self):
        schema={'schemaVersion':1,'revision':1,'name':'Control','primaryFieldId':'f1','fields':[
            {'id':'f1','label':'Codigo','type':'text','required':True,'sourceColumn':0},
            {'id':'f2','label':'Nombre','type':'text','required':False,'sourceColumn':1}]}
        mid=store.import_records(self.org_id,str(__import__('uuid').uuid4()),schema,[{'f1':'A','f2':'Original'}])
        raw=write_workbook('Control',['Codigo','Nombre'],[['A','Nuevo']])
        _,upload=self.request('/api/analyze','POST',raw,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        body={'token':upload['token'],'sheet':'Control','moduleId':mid,'keyFieldId':'f1'}
        status,preview=self.request('/api/reimport/preview','POST',body)
        self.assertEqual(status,200,preview)
        other=store.create_organization(self.owner_id,'Separada para importar')
        status,_=self.request('/api/reimport/preview','POST',body,org=other)
        self.assertEqual(status,404)
        record=store.record_list(self.org_id,mid)[0]
        store.update_record(self.org_id,mid,record['id'],{'f1':'A','f2':'Editado'})
        status,_=self.request('/api/reimport/confirm','POST',{**body,'digest':preview['digest']})
        self.assertEqual(status,400)
        self.assertEqual(store.record_list(self.org_id,mid)[0]['values']['f2'],'Editado')

    def test_import_data_correction_before_saving(self):
        raw=write_workbook('Corregible',['Codigo','Saldo'],[['A','invalido']])
        _,upload=self.request('/api/analyze','POST',raw,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        schema={'schemaVersion':1,'name':'Corregible','primaryFieldId':'f1','fields':[
            {'id':'f1','label':'Codigo','type':'text','required':True,'sourceColumn':0},
            {'id':'f2','label':'Saldo','type':'currency','required':True,'scale':2,'sourceColumn':1}]}
        body={'token':upload['token'],'sheet':upload['sheet'],'schema':schema}
        status,review=self.request('/api/import/validate','POST',body)
        self.assertEqual((status,review['errorCount']),(200,1))
        body['dataCorrections']={'2:2':'12.50'}
        status,review=self.request('/api/import/validate','POST',body)
        self.assertEqual((status,review['errorCount'],review['sample'][0]['values']['f2']),(200,0,'12.50'))
        status,done=self.request('/api/import','POST',body)
        self.assertEqual(status,200,done)
        self.assertEqual(store.record_list(self.org_id,done['moduleId'])[0]['values']['f2'],'12.50')

    def test_configure_fields_saved_views_and_sql_pagination(self):
        schema={'schemaVersion':1,'revision':1,'name':'Consulta','primaryFieldId':'f1','fields':[
            {'id':'f1','label':'Codigo','type':'text','required':True,'sourceColumn':0},
            {'id':'f2','label':'Precio','type':'currency','required':False,'scale':2,'sourceColumn':1}]}
        mid=store.import_records(self.org_id,str(__import__('uuid').uuid4()),schema,[
            {'f1':'A','f2':'10.00'},{'f1':'B','f2':'2.00'},{'f1':'C','f2':'100.00'}])
        candidate={**schema,'name':'Productos','fields':[
            {**schema['fields'][0],'label':'Código'},schema['fields'][1],
            {'id':'f3','label':'Notas','type':'text','required':False,'sourceColumn':None}]}
        status,updated=self.request(f'/api/modules/{mid}','PUT',candidate)
        self.assertEqual(status,200,updated)
        self.assertEqual(updated['schema']['revision'],2)
        self.assertEqual(updated['schema']['fields'][0]['sourceLabel'],'Codigo')
        self.assertIsNone(store.record_list(self.org_id,mid)[0]['values']['f3'])
        status,sorted_rows=self.request(f'/api/modules/{mid}/records?sort=f2&direction=asc')
        self.assertEqual((status,[r['values']['f1'] for r in sorted_rows['items']]),(200,['B','A','C']))
        status,filtered=self.request(f'/api/modules/{mid}/records?field=f2&op=gt&value=9')
        self.assertEqual((status,filtered['total']),(200,2))
        status,saved=self.request(f'/api/modules/{mid}/views','POST',{'name':'Precios altos','query':{'field':'f2','op':'gt','value':'9','sort':'f2','direction':'desc','columns':['f1','f2']}})
        self.assertEqual(status,201,saved)
        status,views=self.request(f'/api/modules/{mid}/views')
        self.assertEqual((status,len(views)),(200,1))
        status,_=self.request(f"/api/modules/{mid}/views/{saved['id']}",'DELETE')
        self.assertEqual(status,200)
        status,bad=self.request(f'/api/modules/{mid}','PUT',candidate)
        self.assertEqual(status,400)

    def test_invitation_reset_and_activity_are_organization_scoped(self):
        other=store.create_organization(self.owner_id,'Otra para accesos')
        status,invite=self.request('/api/invitations','POST',{'email':'nuevo@tablio.test','name':'Nueva persona','role':'viewer'})
        self.assertEqual(status,201,invite)
        status,info=self.request('/api/access-token','POST',{'token':invite['token']},org=other,cookie='',csrf='')
        self.assertEqual((status,info['kind'],info['existing']),(200,'invite',False))
        status,redeemed=self.request('/api/redeem-token','POST',{'token':invite['token'],'password':'contraseña-segura-999'},org=other,cookie='',csrf='')
        self.assertEqual((status,redeemed['kind']),(200,'invite'))
        status,_=self.request('/api/redeem-token','POST',{'token':invite['token'],'password':'contraseña-segura-999'},org=other,cookie='',csrf='')
        self.assertEqual(status,400)
        token,csrf,user_id=store.authenticate('nuevo@tablio.test','contraseña-segura-999')
        self.assertEqual(store.role_for(user_id,self.org_id),'viewer')
        self.assertIsNone(store.role_for(user_id,other))
        status,_=self.request('/api/activity',cookie='tablio_session='+token,csrf=csrf)
        self.assertEqual(status,403)
        status,events=self.request('/api/activity')
        self.assertEqual(status,200)
        self.assertIn('invitation_accepted',[event['action'] for event in events])
        status,reset=self.request('/api/password-resets','POST',{'email':'nuevo@tablio.test'})
        self.assertEqual(status,201,reset)
        status,_=self.request('/api/redeem-token','POST',{'token':reset['token'],'password':'contraseña-cambiada-999'},cookie='',csrf='')
        self.assertEqual(status,200)
        self.assertIsNone(store.authenticate('nuevo@tablio.test','contraseña-segura-999'))
        self.assertIsNotNone(store.authenticate('nuevo@tablio.test','contraseña-cambiada-999'))
        status,_=self.request('/api/modules',cookie='tablio_session='+token,csrf=csrf)
        self.assertEqual(status,401)


if __name__=='__main__': unittest.main()
