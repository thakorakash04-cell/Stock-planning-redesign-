import json,unittest
from unittest.mock import patch
import test_sales as fixture
from test_sales import S,document
from stock_accounts import preload,sales,pnl
from test_pnl import master,salary
class PreloadTests(unittest.TestCase):
    setUp=fixture.StorageAndRights.setUp
    tearDown=fixture.StorageAndRights.tearDown
    upload=fixture.StorageAndRights.upload
    grant=fixture.StorageAndRights.grant
    store_planning=fixture.StorageAndRights.store_planning
    def test_bootstrap_is_scoped_acknowledged_once_and_no_payload_resend(self):
        self.upload();self.upload('secondary');self.grant([S]);state={}
        prefs={'sales:selection':{'kind':'secondary'}}
        first=preload.bundle(self.s,self.v,prefs,state)
        self.assertEqual(first['sales']['primary']['rows'],[document()['rows'][0]+[S]])
        self.assertIsNone(first['pnl']);self.assertNotIn('Ostomy Care',json.dumps(first))
        self.assertEqual(preload.bundle(self.s,self.v,prefs,state)['id'],first['id'])
        preload.acknowledge(self.s,self.v,{'preloadId':first['id']},state)
        with patch('stock_accounts.sales.read',side_effect=AssertionError('Reloaded on an ordinary rerun')):
            self.assertIsNone(preload.bundle(self.s,self.v,prefs,state))
        self.assertNotIn('rows',json.dumps(state['_workspace_preload']['body']))
    def test_partial_preload_only_reads_changed_allowed_parts(self):
        self.upload();self.upload('secondary');self.grant([S]);state={}
        with patch('stock_accounts.sales.read',wraps=sales.read) as read,patch('stock_accounts.pnl.report',side_effect=AssertionError('Unrequested PnL read')):
            result=preload.bundle(self.s,self.v,{},state,['primary'])
        self.assertEqual([c.args[2]['kind'] for c in read.call_args_list],['primary']);self.assertEqual(set(result['sales']),{'primary'});self.assertIsNone(result['pnl'])
        with self.assertRaises(PermissionError):preload.bundle(self.s,self.v,{},state,['pnl'])
        for bad in [[],['bad'],['primary','primary']]:
            with self.assertRaises(ValueError):preload.bundle(self.s,self.v,{},state,bad)
    def test_sales_change_invalidates_dependent_pnl_metadata(self):
        self.upload();before=preload.versions(self.s,self.a)['pnl'];self.upload('secondary');after=preload.versions(self.s,self.a)['pnl'];self.assertNotEqual(before,after)
    def test_both_sales_change_signals_include_bom_mapping_revision(self):
        self.upload();self.upload('secondary');before=preload.versions(self.s,self.a)
        self.store_planning('New-BOM-version');after=preload.versions(self.s,self.a)
        self.assertNotEqual(before['primary'],after['primary']);self.assertNotEqual(before['secondary'],after['secondary'])
    def test_pnl_bootstrap_restores_saved_params_and_versions_are_metadata_only(self):
        pnl.save(self.s,self.a,'master',2026,'Master.xlsx',master(),None);pnl.save(self.s,self.a,'salary',2026,'Salary.xlsx',salary(),None)
        result=preload.bundle(self.s,self.a,{'pnl:filters':{'fy':2026,'basis':'revenue','segments':[S],'materialType':'all'}},{})
        self.assertEqual(result['pnl']['params']['fy'],2026);self.assertIsNotNone(result['pnl']['report'])
        queries=[];run=self.s.run
        def record(db,sql,args=()):queries.append(sql);return run(db,sql,args)
        with patch.object(self.s,'run',side_effect=record):preload.versions(self.s,self.a)
        self.assertFalse(any('SELECT payload' in q or 'SELECT *' in q for q in queries))
