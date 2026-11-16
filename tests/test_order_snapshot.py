import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from stock_accounts.store import Store
from stock_accounts import order_snapshot as cache,planning
from test_production_snapshot import dataset

def planning_dataset():
    data=dataset()
    headers=planning.REQUIRED+['Source.Name','Base unit of measure']
    data['tables'] += [
        {'name':'BOM','headers':headers,'rows':[
            ['A','Finished product','S','Intermediate','ZSFG',2,10,0,'Wound','EA'],
            ['S','Intermediate','R','Raw material','ZRM',3,20,5,'Wound','EA']]},
        {'name':'Planning Quantity','headers':['Material Code','Material Name','Material Type','Unit'],'rows':[['A','Finished product','ZFGS','EA'],['S','Intermediate','ZSFG','EA']]}
    ]
    return data

class OrderSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store('sqlite:///'+str(Path(self.tmp.name)/'orders.db'))
        self.store.bootstrap_admin('admin','AdminPassword123!');self.actor=self.store.login('admin','AdminPassword123!');cache._cache.clear()
    def tearDown(self):self.tmp.cleanup()
    def test_master_summary_and_options_reused_across_logins_and_restart(self):
        with patch.object(cache,'build',wraps=cache.build) as build:
            self.store.save_dataset(self.actor,'master.xlsx',planning_dataset())
            for _ in range(3):
                actor=self.store.login('admin','AdminPassword123!')
                status=planning.handle_planning(self.store,actor,{'action':'planning_status'})
                self.assertEqual([v['code'] for v in status['options']],['A','S'])
                rows={r[0]:r for r in status['summary']['rows']}
                self.assertEqual(rows['A'][2],'ZFGS');self.assertEqual(rows['S'][2],'ZSFG')
                self.assertEqual(rows['B'][5],'Not in master BOM')
                status['options'].clear()
            self.assertEqual(build.call_count,1)
            cache._cache.clear()
            self.assertEqual(len(planning.handle_planning(Store(self.store.url),actor,{'action':'planning_status'})['options']),2)
            self.assertEqual(build.call_count,1)
            changed=planning_dataset();changed['tables'][-2]['rows'][0][1]='New master product'
            self.store.save_dataset(actor,'new-master.xlsx',changed)
            status=planning.handle_planning(self.store,actor,{'action':'planning_status'})
            self.assertEqual(status['options'][0]['description'],'New master product')
            self.assertEqual(build.call_count,2)

if __name__=='__main__':unittest.main()
