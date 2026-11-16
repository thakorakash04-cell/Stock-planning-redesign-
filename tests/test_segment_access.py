import base64,io,json,tempfile,unittest
from pathlib import Path
import pandas as pd
from stock_accounts.store import Store,AccessDenied
from stock_accounts import production,planning
from stock_accounts.portal_console import handle
from stock_accounts.portal_alerts import preview
from test_production_snapshot import dataset

def master():
    data=dataset();data['tables'][0]['rows'].append([2,'XYZ','B','Blue product',200,0,'2026-10-01','2026-10-20'])
    data['tables'][1]['rows']=[['A','QC-A',101,'2026-10-01','ZFGS'],['B','QC-B',101,'2026-10-01','ZFGS']]
    data['tables'] += [
        {'name':'Unique Material','headers':['Material','Source.Name'],'rows':[['A','Red.xlsx'],['B','Blue.xlsx']]},
        {'name':'BOM','headers':planning.REQUIRED+['Source.Name'],'rows':[['A','Red product','R','Shared component','ZRM',2,10,0,'Red.xlsx'],['B','Blue product','R','Shared component','ZRM',3,10,0,'Blue.xlsx']]},
        {'name':'Planning Quantity','headers':['Material Code','Material Name','Material Type'],'rows':[['A','Red product','ZFGS'],['B','Blue product','ZFGS']]},
        {'name':'Unknown private table','headers':['Secret'],'rows':[['BLUE-PRIVATE']]}
    ]
    data['sheets']=[{'name':'Summary','headers':['Material','Description','Qty'],'rows':[['A','Red product',100],['B','Blue product',200],['R','Shared mixed-segment demand',999]]}]
    return data

class SegmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store('sqlite:///'+str(Path(self.tmp.name)/'scope.db'))
        self.store.bootstrap_admin('admin','AdminPassword123!');self.admin=self.store.login('admin','AdminPassword123!')
        self.store.save_dataset(self.admin,'master.xlsx',master());self.store.create_viewer(self.admin,'viewer','ViewerPassword123!',email='viewer@example.invalid')
        self.old=self.store.login('viewer','ViewerPassword123!');self.store.update_segments(self.admin,'viewer',['Red'])
        self.viewer=self.store.login('viewer','ViewerPassword123!')
    def tearDown(self):self.tmp.cleanup()
    def test_raw_rows_caches_planning_and_production_stay_in_scope(self):
        with self.assertRaises(AccessDenied):self.store.get_dataset(self.old)
        current=self.store.get_dataset(self.viewer)
        self.assertEqual(current['data']['sheets'][0]['rows'],[['A','Red product',100]])
        tables={t['name']:t for t in current['data']['tables']}
        self.assertEqual(tables['Unknown private table']['rows'],[])
        self.assertEqual([r[0] for r in tables['BOM']['rows']],['A'])
        status=planning.handle_planning(self.store,self.viewer,{'action':'planning_status'})
        self.assertEqual([r['code'] for r in status['options']],['A'])
        self.assertNotIn('Blue',json.dumps(status))
        report=production.read(self.store,self.viewer)
        self.assertEqual([i['row'][2] for i in report['ongoing']],['A'])
        self.assertEqual([r[0] for r in report['qc']['rows']],['A'])
        self.assertEqual(len(production.read(self.store,self.admin)['ongoing']),2,'restricted cache must not poison full cache')
        self.store.update_permissions(self.admin,'viewer',{'download':True,'update_data':True});viewer=self.store.login('viewer','ViewerPassword123!')
        with self.assertRaises(AccessDenied):self.store.save_dataset(viewer,'scoped-master',master())
    def test_ai_context_and_matched_exports_cannot_reveal_other_segments(self):
        from stock_accounts.assistant_insights import stock_tables
        from stock_accounts.matched_export import export_matched
        from unittest.mock import patch
        import streamlit as st
        with patch.object(st,'session_state',{}):
            tables,version,_=stock_tables(self.store,self.viewer)
            self.assertNotIn('Blue product',json.dumps(tables))
            self.assertNotIn('BLUE-PRIVATE',json.dumps(tables))
        current=self.store.get_dataset(self.viewer)
        denied={'scope':'related','version':current['version'],'tab':0,'row':['B','Blue product',200],'col':0,'table':'BOM','headers':['Material'],'rows':[['B']]}
        with self.assertRaises(ValueError):export_matched(self.store,self.viewer,denied)
        permitted={**denied,'row':['A','Red product',100],'rows':[['A']]}
        file=export_matched(self.store,self.viewer,permitted)
        frame=pd.read_excel(io.BytesIO(base64.b64decode(file['content'])))
        self.assertEqual(frame['Material'].tolist(),['A'])

    def test_manage_user_save_changes_scope_and_revokes_session(self):
        handle(self.store,self.admin,{'operation':'memberSave','username':'viewer','email':'viewer@example.invalid','permissions':{'menu_3':True},'allowedSegments':['Blue'],'active':True},{})
        with self.assertRaises(AccessDenied):self.store.identity(self.viewer)
        viewer=self.store.login('viewer','ViewerPassword123!')
        self.assertEqual(self.store.identity(viewer)['allowedSegments'],['Blue'])
        self.assertEqual(self.store.get_dataset(viewer)['data']['sheets'][0]['rows'],[['B','Blue product',200]])

    def test_scope_changes_and_empty_selection(self):
        with self.assertRaises(AccessDenied):self.store.update_segments(self.viewer,'viewer',['Blue'])
        with self.assertRaises(ValueError):self.store.update_segments(self.admin,'viewer',['Invented'])
        self.store.update_segments(self.admin,'viewer',[]);viewer=self.store.login('viewer','ViewerPassword123!')
        self.assertFalse(any(t['rows'] for t in self.store.get_dataset(viewer)['data']['tables']))
        self.store.update_segments(self.admin,'viewer',None);viewer=self.store.login('viewer','ViewerPassword123!')
        self.assertEqual(len(self.store.get_dataset(viewer)['data']['sheets'][0]['rows']),3)
    def test_user_management_and_emails_respect_segments(self):
        init=handle(self.store,self.admin,{'operation':'consoleInit'},{});self.assertEqual(init['segments'],['Blue','Red'])
        user=next(u for u in init['users'] if u['username']=='viewer');self.assertEqual(user['allowedSegments'],['Red'])
        self.store.portal_save(self.admin,{'email_rules':[{'enabled':True,'recipient':'viewer@example.invalid','section':'Summary','column':'Qty','operator':'>','value':'0','message':'Stock'}]})
        message=preview(self.store,self.admin)['viewer@example.invalid']
        self.assertIn('Red product',message);self.assertNotIn('Blue product',message)
    def test_other_segment_plans_cannot_be_read_or_modified(self):
        current=self.store.get_dataset(self.admin)
        for code,segment in [('A','Red'),('B','Blue')]:
            production.save(self.store,self.admin,{'kind':'upcoming','version':current['version'],'value':{'product':code,'materialCode':code,'description':segment+' plan','batch':'NEW-'+code,'quantity':10,'startDate':'2026-10-12','endDate':'2026-10-20','segment':segment}})
        report=production.read(self.store,self.viewer)
        self.assertEqual(len(report['upcoming']),1);self.assertEqual(report['upcoming'][0]['row'][0],'A')
        denied=next(r for r in production.read(self.store,self.admin)['upcoming'] if r['row'][0]=='B')
        self.store.update_permissions(self.admin,'viewer',{'edit_upcoming':True});viewer=self.store.login('viewer','ViewerPassword123!')
        with self.assertRaises(AccessDenied):production.delete(self.store,viewer,{'plan_id':denied['id'],'revision':denied['revision'],'version':current['version']})

if __name__=='__main__':unittest.main()
