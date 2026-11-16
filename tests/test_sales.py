import base64,copy,json,tempfile,unittest,gzip,time
from pathlib import Path
from datetime import date
from unittest.mock import patch
from stock_accounts import sales
from stock_accounts.store import Store,AccessDenied
from stock_accounts.planning_assistant import run_tool
S='General Wound Care';OTHER='Ostomy Care';PASSWORD='SalesTestPassword123!'
def document():return {'headers':['Material','Invoice Value in LC','Cancelled','Segment'],'rows':[['A',100,'',S],['B',-20,'X',OTHER]],'segmentIndex':3,'unmapped':0}
class Sheet:
    title='Sales';sheet_state='visible'
    def __init__(self,rows):self.rows=rows;self.max_row=len(rows);self.max_column=max(map(len,rows))
    def iter_rows(self,min_row=1,max_row=None,values_only=True):return iter(self.rows[min_row-1:max_row])
class Book:
    sheetnames=['Sales']
    def __init__(self,rows):self.sheet=Sheet(rows)
    def __iter__(self):return iter([self.sheet])
    def __getitem__(self,key):return self.sheet
    def close(self):pass
class ImportTests(unittest.TestCase):
    def test_dynamic_columns_dates_numeric_values_and_mapping(self):
        rows=[['Billing Doc.','Billing Date','Material','Invoice Value in LC','Source.Name'],[123,date(2026,4,1),'A',100,'October.xlsx'],[124,date(2026,5,1),'B',-20,'October.xlsx']]
        with patch('stock_accounts.sales.open_saved',return_value=Book(rows)):
            p=sales.preview(b'fake','Sales.xlsx');d=sales.parse(b'fake','Sales.xlsx','Sales',1,{'A':[S],'B':[S,OTHER]})
        self.assertEqual(len(p['sheets'][0]['headers']),5);self.assertEqual(d['headers'][-1],'Segment')
        self.assertEqual(d['rows'][0][:4],['123','2026-04-01','A',100]);self.assertEqual(d['rows'][0][-1],S);self.assertEqual(d['rows'][1][-1],'Unmapped')
    def test_explicit_segments_duplicate_columns_and_empty_rejected(self):
        with patch('stock_accounts.sales.open_saved',return_value=Book([['Segment','Value','Value'],['Advanced Wound Care',5,10]])):
            d=sales.parse(b'f','Sales.xlsx','Sales',1,{})
        self.assertEqual(d['headers'],['Segment','Value','Value (2)']);self.assertEqual(d['rows'][0][0],'Advance Wound Care')
        with patch('stock_accounts.sales.open_saved',return_value=Book([['Segment','Value']])):
            with self.assertRaises(ValueError):sales.parse(b'f','Sales.xlsx','Sales',1,{})
class StorageAndRights(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Store('sqlite:///'+str(Path(self.tmp.name)/'sales.db'));self.s.bootstrap_admin('admin',PASSWORD);self.a=self.s.login('admin',PASSWORD)
        self.s.create_viewer(self.a,'viewer',PASSWORD);self.v=self.s.login('viewer',PASSWORD)
        self.dataset={'tables':[{'name':'BOM','headers':['Material','Component','Source.Name'],'rows':[['A','COMPONENT',S+'.xlsx'],['B','COMPONENT',OTHER+'.xlsx'],['SFG','RM',S+'.xlsx']]},{'name':'Planning Quantity','headers':['Material Code','Material Type'],'rows':[['A','ZFGS'],['B','ZFGS'],['SFG','ZSFG']]}]}
        self.store_planning('BOM1')
        self.event={'action':'sales_upload','kind':'primary','filename':'Monthly.xlsx','sheet':'Sales','content':base64.b64encode(b'fake').decode(),'expected':None}
    def store_planning(self,version):
        raw=base64.b64encode(gzip.compress(json.dumps(self.dataset).encode())).decode()
        with self.s.transaction() as db:self.s.run(db,"INSERT INTO datasets VALUES('current',?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,version=excluded.version,updated_at=excluded.updated_at",(raw,'Planning.xlsx',version,'admin',time.time()))
    def tearDown(self):self.tmp.cleanup()
    def upload(self,kind='primary',value=None,expected=None):
        with patch('stock_accounts.sales.parse',return_value=value or document()):return sales.save(self.s,self.a,{**self.event,'kind':kind,'expected':expected})
    def grant(self,segments=None):
        self.s.update_permissions(self.a,'viewer',{'menu_11':True})
        with self.s.transaction() as db:self.s.run(db,'UPDATE accounts SET allowed_segments=? WHERE username=?',(json.dumps(segments) if segments is not None else None,'viewer'))
        self.v=self.s.login('viewer',PASSWORD)
    def test_permission_and_segment_checks_apply_even_to_conditional_reads(self):
        self.upload()
        with self.assertRaises(AccessDenied):sales.read(self.s,self.v,{'kind':'primary'})
        full=sales.read(self.s,self.a,{'kind':'primary'});self.grant([S]);scoped=sales.read(self.s,self.v,{'kind':'primary','knownVersion':full['version']})
        self.assertEqual(scoped['rows'],[document()['rows'][0]+[S]]);self.assertNotIn(OTHER,json.dumps(scoped));self.assertNotIn('uploadInfo',scoped)
        self.assertNotEqual(scoped['version'],full['version'])
        with self.assertRaises(AccessDenied):sales.save(self.s,self.v,self.event)
        with self.assertRaises(AccessDenied):sales.handle(self.s,self.v,{**self.event,'action':'sales_preview'})
        self.s.update_permissions(self.a,'viewer',{'menu_11':False})
        with self.assertRaises(AccessDenied):sales.read(self.s,self.v,{'kind':'primary','knownVersion':scoped['version']})
    def test_independent_replacements_restart_and_conflict(self):
        first=self.upload();self.upload('secondary');new=document();new['rows'][0][1]=999
        self.upload(value=new,expected=first['version'])
        with self.assertRaisesRegex(ValueError,'changed'):self.upload(expected=first['version'])
        reopened=Store(self.s.url)
        self.assertEqual(sales.read(reopened,self.a,{'kind':'primary'})['rows'][0][1],999)
        self.assertEqual(sales.read(reopened,self.a,{'kind':'secondary'})['rows'][0][1],100)
    def test_warm_logins_do_not_fetch_payload_again_and_conditional_reads_are_small(self):
        self.upload();first=sales.read(self.s,self.a,{'kind':'primary'});queries=[];run=self.s.run
        def record(db,sql,args=()):queries.append(sql);return run(db,sql,args)
        actor=self.s.login('admin',PASSWORD)
        with patch.object(self.s,'run',side_effect=record):
            warm=sales.read(self.s,actor,{'kind':'primary'});small=sales.read(self.s,actor,{'kind':'primary','knownVersion':first['version']})
        self.assertEqual(warm['rows'],first['rows']);self.assertTrue(small['notModified']);self.assertNotIn('rows',small)
        self.assertFalse(any('SELECT payload FROM stock_sales_documents' in q for q in queries))
    def test_primary_only_bom_parent_membership_and_bom_change_invalidates_cached_rows(self):
        value=document();value['rows'] += [['UNKNOWN',500,'',S],['COMPONENT',500,'',S],['SFG',500,'',S]]
        self.upload(value=value);self.upload('secondary',value=value)
        primary=sales.read(self.s,self.a,{'kind':'primary'})
        self.assertEqual([r[0] for r in primary['rows']],['A','B','SFG'])
        self.assertEqual(len(sales.read(self.s,self.a,{'kind':'secondary'})['rows']),5)
        self.dataset['tables'][0]['rows']=[['B','COMPONENT',OTHER+'.xlsx']];self.store_planning('BOM2')
        changed=sales.read(self.s,self.a,{'kind':'primary','knownVersion':primary['version']})
        self.assertNotEqual(changed['version'],primary['version']);self.assertEqual([r[0] for r in changed['rows']],['B'])
    def test_saved_bom_cost_fallback_case_normalization_and_zero_preservation(self):
        self.dataset={'sheets':[{'name':'BOM Cost','headers':['FG Code','Description'],'rows':[[' a ','Example'],['00123','Number code']]}],'tables':[]}
        self.store_planning('Saved-only')
        value=document();value['rows']=[['A',100,'',S],['  a  ',10,'',S],['00123',5,'',S],['123',99,'',S],['UNKNOWN',99,'',S]]
        self.upload(value=value)
        data=sales.read(self.s,self.a,{'kind':'primary'})
        self.assertEqual([r[0] for r in data['rows']],['A','  a  ','00123'])
    def test_bom_source_segments_are_current_scoped_and_do_not_duplicate_transactions(self):
        self.dataset['tables'][0]['rows'].append(['A','OTHER_COMPONENT',OTHER+'.xlsx'])
        self.store_planning('Shared-BOM');self.upload();self.upload('secondary')
        full=sales.read(self.s,self.a,{'kind':'primary'})
        self.assertEqual(full['headers'][-1],'BOM Segment')
        self.assertEqual(full['rows'][0][-1],S+' / '+OTHER)
        self.assertEqual([r[:4] for r in full['rows']],document()['rows'])
        self.grant([S]);scoped=sales.read(self.s,self.v,{'kind':'primary'})
        self.assertEqual(scoped['rows'],[document()['rows'][0]+[S]])
        self.assertNotIn(OTHER,json.dumps(scoped))
        secondary=sales.read(self.s,self.a,{'kind':'secondary'})
        self.dataset['tables'][0]['rows']=[['A','COMPONENT','Oncology.xlsx'],['B','COMPONENT',OTHER+'.xlsx']]
        self.store_planning('Changed-BOM')
        fresh=sales.read(self.s,self.a,{'kind':'secondary','knownVersion':secondary['version']})
        self.assertNotEqual(fresh['version'],secondary['version']);self.assertEqual(fresh['rows'][0][-1],'Oncology')
        self.assertEqual(fresh['rows'][0][3],S,'Uploaded Sales Segment is preserved')
        restricted=sales.read(self.s,self.v,{'kind':'primary'})
        self.assertEqual(restricted['rows'][0][-1],'Unmapped segment')
        self.assertNotIn('Oncology',json.dumps(restricted))
    def test_bom_grouping_handles_missing_mapping_name_collisions_and_cached_reads(self):
        value=document();value['headers'].append('BOM Segment');value['rows']=[r+['Imported note'] for r in value['rows']]
        self.upload('secondary',value=value)
        self.dataset['tables'][0]['rows']=[['A','COMPONENT',S+'.xlsx']];self.store_planning('Only-A')
        first=sales.read(self.s,self.a,{'kind':'secondary'});second=sales.read(self.s,self.a,{'kind':'secondary'})
        self.assertEqual(first,second);self.assertEqual(first['headers'][-1],'BOM Segment (Source.Name)')
        self.assertEqual(first['rows'][0][-2:]==['Imported note',S],True)
        self.assertEqual(first['rows'][1][-1],'Unmapped segment')
        self.assertEqual(sales.summarize(self.s,self.a,{'kind':'secondary','group':first['bomSegmentColumn'],'statistic':'sum','value':'Invoice Value in LC'})['rows'],[[S,100,1],['Unmapped segment',-20,1]])
    def test_shared_read_only_assistant_tool_is_scoped(self):
        self.upload();self.grant([S]);before=sales.metadata(self.s,self.a)
        result=sales.summarize(self.s,self.v,{'kind':'primary','value':'Invoice Value in LC','statistic':'sum'})
        self.assertEqual(result['rows'],[[S,100,1]])
        out=run_tool(self.s,self.v,{'operation':'sales','kind':'primary','statistic':'count'},{'data':{}})
        self.assertTrue(out);self.assertEqual(before,sales.metadata(self.s,self.a))
if __name__=='__main__':unittest.main()
