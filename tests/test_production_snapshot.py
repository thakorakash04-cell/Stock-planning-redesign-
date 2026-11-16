import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from stock_accounts.store import Store,AccessDenied
from stock_accounts import production,production_snapshot as cache

def dataset():
    orders={'name':'Production Order Details','headers':['Order','Batch','Material Number','Material description','Order quantity (GMEIN)','Confirmed quantity (GMEIN)','Basic start date','Basic finish date'],'rows':[[1,'ABC','A','Product A',100,0,'2026-10-01','2026-10-20']]}
    moves={'name':'Material Document List','headers':['Material','Batch','Movement Type','Posting Date','Material Type'],'rows':[['B','QC',101,'2026-10-01','ZFGS']]}
    return {'productionSnapshotDate':'2026-10-10','tables':[orders,moves],'sheets':[]}

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store('sqlite:///'+str(Path(self.tmp.name)/'cache.db'))
        self.store.bootstrap_admin('admin','AdminPassword123!');self.actor=self.store.login('admin','AdminPassword123!')
        cache._cache.clear();cache._durable.clear()
    def tearDown(self):self.tmp.cleanup()
    def test_upload_builds_once_relogin_and_restart_reuse_snapshot(self):
        with patch.object(production,'build',wraps=production.build) as build:
            self.store.save_dataset(self.actor,'master.xlsx',dataset())
            first=production.read(self.store,self.actor)
            first['ongoing'][0]['row'][8]=999
            for _ in range(3):
                actor=self.store.login('admin','AdminPassword123!')
                result=production.read(self.store,actor)
                self.assertIsNone(result['ongoing'][0]['row'][8])
            self.assertEqual(build.call_count,1)
            cache._cache.clear();cache._durable.clear()
            production.read(Store(self.store.url),self.actor)
            self.assertEqual(build.call_count,1,'restart must load durable snapshot instead of recalculating')
            changed=dataset();changed['tables'][0]['rows'][0][4]=200
            self.store.save_dataset(self.actor,'new-master.xlsx',changed)
            self.assertEqual(production.read(self.store,self.actor)['ongoing'][0]['row'][5],200)
            self.assertEqual(build.call_count,2)
    def test_initial_workspace_includes_rows_only_for_authorized_users(self):
        from stock_accounts import workspace
        self.store.save_dataset(self.actor,'master.xlsx',dataset())
        state={}
        with patch.object(workspace.st,'session_state',state),patch.object(workspace,'ui_payload',return_value=({'filename':'master.xlsx'},[], 'v1')):
            initial,_,_=workspace.workspace_payload(self.store,self.actor)
            self.assertEqual(len(initial['production']['ongoing']),1)
            self.assertEqual(len(initial['production']['qc']['rows']),1)
            self.assertIn('productionRevision',initial)
            self.store.create_viewer(self.actor,'viewer','ViewerPassword123!')
            self.store.update_permissions(self.actor,'viewer',{'menu_3':False})
            viewer=self.store.login('viewer','ViewerPassword123!')
            restricted,_,_=workspace.workspace_payload(self.store,viewer)
            self.assertNotIn('production',restricted)

    def test_edits_overlay_snapshot_without_rebuilding_source(self):
        with patch.object(production,'build',wraps=production.build) as build:
            self.store.save_dataset(self.actor,'master.xlsx',dataset())
            report=production.read(self.store,self.actor);item=report['ongoing'][0]
            production.save(self.store,self.actor,{'kind':'ongoing','version':report['version'],'plan_id':item['id'],'revision':0,'value':{'quantity':80,'endDate':'2026-10-22'}})
            result=production.read(self.store,self.actor)
            self.assertEqual(result['ongoing'][0]['row'][8],80)
            self.assertEqual(build.call_count,1)
            self.assertIsNone(cache.cached_build(self.store.get_dataset(self.actor))['ongoing'][0]['row'][8])
    def test_concurrent_legacy_reads_build_only_once_and_recheck_access(self):
        self.store.save_dataset(self.actor,'master.xlsx',dataset())
        with self.store.transaction() as db:self.store.run(db,'DELETE FROM production_source_snapshot')
        cache._cache.clear();cache._durable.clear()
        with patch.object(production,'build',wraps=production.build) as build:
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _:production.read(self.store,self.actor),range(4)))
            self.assertEqual(build.call_count,1)
        self.store.create_viewer(self.actor,'viewer','ViewerPassword123!')
        viewer=self.store.login('viewer','ViewerPassword123!');production.read(self.store,viewer)
        self.store.update_permissions(self.actor,'viewer',{'menu_3':False})
        with self.assertRaises(AccessDenied):production.read(self.store,viewer)

if __name__=='__main__':unittest.main()


class SourceSegments(unittest.TestCase):
    def test_qc_and_ongoing_use_qualified_row_source(self):
        data=dataset()
        data['tables'][0]['headers'].append('Unique Material.Source.Name')
        data['tables'][0]['rows'][0].append('General Wound Care.xlsx')
        data['tables'][1]['headers'].append('Unique Material.Source.Name')
        data['tables'][1]['rows'][0].append('Ostomy Care.XLSX')
        data['tables'].append({'name':'Unique Material','headers':['Material','Source.Name'],'rows':[['A','Energy Devices.xlsx'],['B','Energy Devices.xlsx']]})
        value=cache.calculate({'data':data,'version':'row-source','updated_at':1792211998})
        self.assertEqual(value['qc']['segments'],[['Ostomy Care']])
        self.assertEqual(value['ongoing'][0]['segments'],['General Wound Care'])

