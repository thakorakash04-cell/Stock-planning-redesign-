import base64,copy,json,tempfile,unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from stock_accounts import pnl
from stock_accounts.pnl_import import read_master,read_salary
from stock_accounts.store import Store,AccessDenied

PASSWORD='PnlTestPassword123!'
S='General Wound Care';OTHER='Ostomy Care'
def master(amount=1000):
    return {'fy':2026,'start':'2026-04-01','end':'2026-05-31','warnings':[], 'controls':{'revenue':amount,'production':100,'rd':10},'revenue':[{'sku':'FG1','description':'Example','customer':'Example customer','quantity':-10,'uom':'EA','amount':amount}], 'production':[{'sku':'FG1','description':'Example','batch':'B1','month':'2026-04-01','quantity':10,'uom':'EA','amount':100}], 'rd':[{'segment':S,'center':'C1','description':'Example R&D','amount':10}]}
def salary():return {'fy':2026,'employees':[{'code':'E1','name':'Test Person','join':'2020-01-01','leave':None,'monthly':50,'segments':[S]}]}
def dataset():
    def t(name,headers,rows):return {'name':name,'headers':headers,'rows':rows}
    return {'sheets':[t('BOM Cost',['Material','Grand Total'],[['FG1',12]]),t('Sales Data',['Year','Month','Material','Quantity','UoM'],[[2026,'April','FG1',10,'EA'],[2026,'June','FG1',100,'EA']])], 'tables':[
        t('BOM',['Material','Component','Source.Name','Component(text)','Material Type'],[['FG1','RM1',S+'.xlsx','Example component','ZRAW']]),
        t('Prices',['Material','Std DP','UoM'],[['FG1',50,'EA']]),
        t('Order List',['Purchasing Document','Material','Document Date'],[['PO1','RM1','2026-03-31'],['PO2','RM1','2026-03-31']]),
        t('Material Document List',['Material','Batch','Posting Date','Movement Type','Purchase Order'],[['RM1','RB1','2026-04-10','101','PO1'],['RM1','RB1','2026-04-10','101','PO2'],['RM1','RB1','2026-05-10','261','PO1']])]}

class Calculations(unittest.TestCase):
    def values(self,result):return {r[0]:r[1] for r in result['statement']['rows']}
    def test_product_sku_matching_and_fixed_segment_salary_rd_shares(self):
        products=[{'id':'a','name':'First','division':S,'codes':['FG1']},{'id':'b','name':'Second','division':S,'codes':['FG2']}]
        m=master();m['revenue'].append({**m['revenue'][0],'sku':'FG2','amount':200});m['production'].append({**m['production'][0],'sku':'FG2','amount':40})
        first=pnl.calculate(m,salary(),dataset(),{},[],products=products,product_ids=['a']);v=self.values(first)
        self.assertEqual(v['Sales'],1000);self.assertEqual(v['Product cost'],100);self.assertEqual(v['Employee cost'],50);self.assertEqual(v['R&D cost'],5)
        self.assertEqual({r[2] for r in first['details']['production']},{'FG1'})
        self.assertEqual(sum(r[-1] for r in first['details']['salary']),50)
        adjusted=self.values(pnl.calculate(m,salary(),dataset(),{'adjustments':{S:{'manufacturing':20,'product_override':9999}}},[],products=products,product_ids=['a']))
        self.assertEqual(adjusted['Product cost'],100);self.assertEqual(adjusted['Manufacturing OHD'],10)
        both=self.values(pnl.calculate(m,salary(),dataset(),{},[],products=products,product_ids=['a','b']))
        self.assertEqual(both['Sales'],1200);self.assertEqual(both['Product cost'],140);self.assertEqual(both['Employee cost'],100);self.assertEqual(both['R&D cost'],10)
        dp=self.values(pnl.calculate(m,salary(),dataset(),{},[],basis='std_dp',products=products,product_ids=['a']))
        self.assertEqual(dp['Sales'],500);self.assertEqual(dp['Product cost'],120);self.assertEqual(dp['Employee cost'],50)
        products.append({'id':'c','name':'No SKU yet','division':S,'codes':[]})
        third=self.values(pnl.calculate(m,salary(),dataset(),{},[],products=products,product_ids=['a']))
        self.assertAlmostEqual(third['Employee cost'],100/3);self.assertAlmostEqual(third['R&D cost'],10/3)
        with self.assertRaises(ValueError):pnl.calculate(m,salary(),dataset(),{},[OTHER],products=products,product_ids=['a'])
        products[1]['codes']=['FG1']
        with self.assertRaisesRegex(ValueError,'multiple products'):pnl.calculate(m,salary(),dataset(),{},[],products=products,product_ids=['a'])
    def test_product_share_follows_employee_working_segments_and_join_leave_days(self):
        products=[{'id':'a','name':'First','division':S,'codes':['FG1']},{'id':'b','name':'Second','division':S,'codes':['FG2']},{'id':'o','name':'Other','division':OTHER,'codes':['FG3']}]
        sal=salary();sal['employees'][0].update(segments=[S,OTHER],monthly=600,join='2026-04-16',leave='2026-05-15')
        r=pnl.calculate(master(),sal,dataset(),{},[],products=products,product_ids=['a'])
        self.assertAlmostEqual(self.values(r)['Employee cost'],600*(15/30+15/31)/2/2)
        self.assertEqual({row[2] for row in r['details']['salary']},{S})
    def test_restricted_dp_business_segment_and_qualified_transfer_source(self):
        from stock_accounts.segment_access import scope_data
        d=dataset()
        d['tables'][1]={'name':'DP MRP','headers':['SKU Code','Segment','Std  DP','UOM'],'rows':[['FG1','GWC',50,'EA']]}
        d['tables'].append({'name':'Other source','headers':['Material','Unique Material.Source.Name'],'rows':[['FG1',S+'.xlsx']]})
        r=pnl.calculate(master(),salary(),scope_data(d,[S]),{},[S],restricted=True,basis='std_dp')
        self.assertEqual(self.values(r)['Sales'],500)
        self.assertEqual(self.values(r)['Product cost'],120)
        self.assertEqual(r['details']['bom'][0][6],120)
    def test_component_line_costs_sum_to_fg_total_when_saved_total_missing(self):
        d=dataset();d['sheets'][0]['rows']=[]
        d['tables'].append({'name':'BOM Cost','headers':['Source.Name','Material','Component','Item Number','Total BOM Cost'],'rows':[[S+'.xlsx','FG1','RM1',10,7],[S+'.xlsx','FG1','PK1',20,5]]})
        r=pnl.calculate(master(),salary(),d,{},[S],basis='std_dp')
        self.assertEqual(self.values(r)['Product cost'],120)
        self.assertEqual(self.values(r)['Sales'],500)
    def test_bom_total_alias_and_embedded_fallback(self):
        d=dataset();d['sheets'][0]={'name':'BOM Cost','headers':['FG Material Code','Total BOM Cost'],'rows':[[' fg1 ',12]]}
        values=self.values(pnl.calculate(master(),salary(),d,{},[],basis='std_dp'))
        self.assertEqual(values['Sales'],500);self.assertEqual(values['Product cost'],120)
        d['sheets'][0]['rows']=[]
        d['tables'].append({'name':'BOM Cost','headers':['Material Number','Grand Total'],'rows':[['FG1',12]]})
        self.assertEqual(self.values(pnl.calculate(master(),salary(),d,{},[],basis='std_dp'))['Product cost'],120)
        d['sheets'][0]['rows']=[['FG1',11],['FG1',12]]
        self.assertIsNone(self.values(pnl.calculate(master(),salary(),d,{},[],basis='std_dp'))['EBITDA'])
    def test_original_formulas_period_interest_and_no_po_duplication(self):
        result=pnl.calculate(master(),salary(),dataset(),{},[]);v=self.values(result)
        self.assertTrue(result['complete']);self.assertAlmostEqual(v['Employee cost'],100)
        self.assertAlmostEqual(v['Inventory days'],30);self.assertAlmostEqual(v['Creditor days'],10)
        self.assertAlmostEqual(v['Working capital'],1000/60*110);self.assertAlmostEqual(v['Interest'],1000/60*110*.085/6)
        self.assertAlmostEqual(v['EBITDA'],790);self.assertAlmostEqual(v['PAT'],(790-v['Interest'])*.82)
        self.assertAlmostEqual(v['Net cash profit'],v['PAT']-v['Working capital'])
    def test_ctc_proration_leave_and_shared_segments(self):
        sal={'employees':[{'code':'E','name':'Example','join':'2026-04-16','leave':'2026-05-15','monthly':600,'segments':[S,OTHER]}]}
        totals,monthly,details=pnl.salary_rows(sal,date(2026,4,1),date(2026,6,30),{S})
        self.assertAlmostEqual(totals[S],600*(15/30+15/31)/2);self.assertNotIn(OTHER,totals);self.assertEqual(len(details),2)
    def test_std_dp_period_sign_and_missing_rates(self):
        v=self.values(pnl.calculate(master(),salary(),dataset(),{},[],basis='std_dp'))
        self.assertEqual(v['Sales'],500)
        source=dataset();source['tables'][1]['rows']=[['FG1',50,'EA'],['FG1',60,'EA']]
        result=pnl.calculate(master(),salary(),source,{},[],basis='std_dp')
        self.assertFalse(result['complete']);self.assertIsNone(self.values(result)['PAT'])
        source=dataset();source['sheets'][1]['rows']=[[2026,'April','FG1',-2,'EA']]
        self.assertEqual(self.values(pnl.calculate(master(),salary(),source,{},[],basis='std_dp'))['Sales'],-100)
    def test_each_segment_sales_uses_dp_and_cost_uses_bom(self):
        segments=['Ostomy Care','General Wound Care','Advance Wound Care','Endovascular Solution','Energy Device','Oncology']
        for segment in segments:
            with self.subTest(segment=segment):
                d=dataset();d['tables'][0]['rows'][0][2]=segment+'.xlsx'
                # BOM must never become a fallback selling price, even if it has a mislabeled DP column.
                d['tables'].append({'name':'BOM Cost','headers':['Material','Std DP','Grand Total'],'rows':[['FG1',12,12]]})
                d['tables'][1]['rows'][0][0]=' fg1 '
                m=master();m['rd'][0]['segment']=segment
                sal=salary();sal['employees'][0]['segments']=[segment]
                r=pnl.calculate(m,sal,d,{},[segment],basis='std_dp');v=self.values(r)
                self.assertEqual(v['Sales'],500);self.assertEqual(v['Product cost'],120)
                self.assertEqual(r['details']['transfers'][0][5],50)
                self.assertEqual(r['details']['bom'][0][5],12)
                self.assertEqual(r['formulaDrivers']['taxRate'],.18)
                d['tables'][1]['rows']=[]
                missing=pnl.calculate(m,sal,d,{},[segment],basis='std_dp')
                self.assertIsNone(self.values(missing)['EBITDA'])
    def test_bom_missing_conflicting_zero_and_returns(self):
        d=dataset();d['sheets'][0]['rows']=[['FG1',12],['FG1',15]]
        r=pnl.calculate(master(),salary(),d,{},[],basis='std_dp')
        self.assertIsNone(self.values(r)['EBITDA']);self.assertTrue(any('BOM Grand Total' in w for w in r['warnings']))
        d['sheets'][0]['rows']=[['FG1',0]]
        self.assertEqual(self.values(pnl.calculate(master(),salary(),d,{},[],basis='std_dp'))['Product cost'],0)
        d['sheets'][0]['rows']=[['FG1',12]];d['sheets'][1]['rows']=[[2026,'April','FG1',-2,'EA']]
        self.assertEqual(self.values(pnl.calculate(master(),salary(),d,{},[],basis='std_dp'))['Product cost'],-24)
    def test_corrected_august_period_controls_transfers_and_salary(self):
        m=master();m['end']='2026-08-31';d=dataset()
        d['sheets'][1]['rows']=[[2026,'August','FG1',2,'EA'],[2026,'September','FG1',100,'EA']]
        v=self.values(pnl.calculate(m,salary(),d,{},[],basis='std_dp'))
        self.assertEqual(v['Sales'],100);self.assertEqual(v['Product cost'],24);self.assertEqual(v['Employee cost'],250)
    def test_missing_cost_salary_history_and_zero_overrides(self):
        m=master();m['production'][0]['amount']=None
        provisional=pnl.calculate(m,salary(),dataset(),{},[])
        self.assertEqual(self.values(provisional)['EBITDA'],890)
        self.assertFalse(provisional['complete'])
        self.assertTrue(any('Provisional' in w for w in provisional['warnings']))
        r=pnl.calculate(m,salary(),dataset(),{'adjustments':{S:{'product_override':0}},'inventory_override':0,'creditor_override':0},[])
        self.assertTrue(r['complete']);self.assertEqual(self.values(r)['Product cost'],0);self.assertEqual(self.values(r)['Inventory days'],0)
        self.assertIsNone(self.values(pnl.calculate(master(),None,dataset(),{},[]))['Employee cost'])
        d=dataset();d['tables'][-1]['rows'][0][2]='2025-04-10';d['tables'][-1]['rows'][1][2]='2025-04-10'
        self.assertIsNone(self.values(pnl.calculate(master(),salary(),d,{},[]))['Working capital'])
    def test_sales_mode_changes_sales_and_bom_cogs_retains_other_costs_days(self):
        revenue=self.values(pnl.calculate(master(),salary(),dataset(),{},[]))
        dp=self.values(pnl.calculate(master(),salary(),dataset(),{},[],basis='std_dp'))
        for key in ('R&D cost','Employee cost','Manufacturing OHD','SG&A','Depreciation','Capex','Inventory days','Creditor days','Debtor days'):
            self.assertEqual(revenue[key],dp[key],key)
        self.assertEqual(dp['Product cost'],120)
        self.assertEqual(dp['EBITDA']-revenue['EBITDA'],dp['Sales']-revenue['Sales']-20)
        self.assertEqual(dp['Product cost %'],24)
        self.assertEqual(dp['Employee cost %'],20)
        rows=pnl.calculate(master(),salary(),dataset(),{},[],basis='std_dp')['statement']['rows']
        self.assertEqual([r[0] for r in rows][2],'Product cost %')
    def test_batch_summary_uses_dated_ledger_original_transfer_rule(self):
        d=dataset();d['sheets'][1]={'name':'Sales Data','headers':['Batch','Material','FG Transfer Quantity (MMI-MLSIPL/MEP)'],'rows':[['B','FG1',9999]]}
        d['tables'].append({'name':'Material Document List','headers':['Material','Posting Date','Qty in Un. of Entry','Unit of Entry','Movement Type','Material Type'], 'rows':[
            ['FG1','2026-04-01',-12,'EA',601,'ZFGS'],['FG1','2026-05-31',2,'EA',602,'ZFGS'],
            ['FG1','2026-06-01',-99,'EA',601,'ZFGS'],['FG1','2026-04-02',300,'EA',101,'ZFGS'],['FG1','2026-04-02',-500,'EA',601,'ZRAW']]})
        # Select the ledger carrying complete dated transfer fields.
        d['tables']=[t for t in d['tables'] if t['name']!='Material Document List' or 'Qty in Un. of Entry' in t['headers']]
        r=pnl.calculate(master(),salary(),d,{},[S],basis='std_dp')
        self.assertEqual(self.values(r)['Sales'],500)
        self.assertEqual(len(r['details']['transfers']),2)
        self.assertEqual([row[3] for row in r['details']['transfers']],[12,-2])
        self.assertTrue(any('601, 602' in w for w in r['warnings']))
        for row in d['tables'][-1]['rows']:row[3]='BOX'
        original=pnl.calculate(master(),salary(),d,{},[S],basis='std_dp')
        self.assertEqual(self.values(original)['Sales'],500)
        self.assertTrue(any('unit labels differ' in w for w in original['warnings']))
        strict=pnl.calculate(master(),salary(),d,{'transfer_sku_price':False},[S],basis='std_dp')
        self.assertIsNone(self.values(strict)['EBITDA'])
    def test_secondary_sales_and_invalid_dates_are_rejected(self):
        with self.assertRaises(ValueError):pnl.calculate(master(),salary(),dataset(),{},[],basis='secondary')
        m=master();m['start']='2026-05-01'
        with self.assertRaises(ValueError):pnl.calculate(m,salary(),dataset(),{},[])

class StorageAndRights(unittest.TestCase):
    def test_product_scope_permissions_and_catalogue_version_invalidate_cache(self):
        from stock_accounts.product_catalog import publish
        products=[{'id':'a','name':'First','division':S,'sections':[{'kind':'variants','rows':[{'code':'FG1'}]}]},{'id':'b','name':'Second','division':S,'sections':[]},{'id':'o','name':'Other','division':OTHER,'sections':[{'kind':'variants','rows':[{'code':'FG3'}]}]}]
        publish(self.s,self.a,products,'')
        first=pnl.report(self.s,self.a,{'fy':2026,'products':['a']})
        self.assertEqual(next(r[1] for r in first['statement']['rows'] if r[0]=='Employee cost'),50)
        self.grant([S]);viewer=self.s.login('viewer',PASSWORD)
        with self.assertRaises(AccessDenied):pnl.report(self.s,viewer,{'fy':2026,'products':['o']})
        self.assertEqual({p['id'] for p in pnl.catalogue(self.s,viewer)['products']},{'a','b'})
        products.pop(1);publish(self.s,self.a,products,'')
        second=pnl.report(self.s,self.a,{'fy':2026,'products':['a']})
        self.assertNotEqual(first['snapshotVersion'],second['snapshotVersion'])
        self.assertEqual(next(r[1] for r in second['statement']['rows'] if r[0]=='Employee cost'),100)
        with self.assertRaisesRegex(ValueError,'changed'):pnl.report(self.s,self.a,{'fy':2026,'products':['a'],'snapshotVersion':first['snapshotVersion'],'kind':'salary'},True)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Store('sqlite:///'+str(Path(self.tmp.name)/'pnl.db'));self.s.bootstrap_admin('admin',PASSWORD);self.a=self.s.login('admin',PASSWORD)
        self.s.create_viewer(self.a,'viewer',PASSWORD);self.v=self.s.login('viewer',PASSWORD)
        with self.s.transaction() as db:
            import gzip,hashlib,time
            payload=base64.b64encode(gzip.compress(json.dumps(dataset()).encode())).decode()
            self.s.run(db,"INSERT INTO datasets VALUES('current',?,?,?,?,?)",(payload,'Source.xlsx',hashlib.sha256(payload.encode()).hexdigest(),'admin',time.time()))
        pnl.save(self.s,self.a,'master',2026,'Master.xlsx',master(),None);pnl.save(self.s,self.a,'salary',2026,'Salary.xlsx',salary(),None)
    def tearDown(self):self.tmp.cleanup()
    def grant(self,segments=None):
        self.s.update_permissions(self.a,'viewer',{'menu_10':True})
        with self.s.transaction() as db:self.s.run(db,'UPDATE accounts SET allowed_segments=? WHERE username=?',(json.dumps(segments) if segments is not None else None,'viewer'))
        self.v=self.s.login('viewer',PASSWORD)
    def test_pnl_defaults_deny_then_admin_grants_and_salary_stays_private(self):
        with self.assertRaises(AccessDenied):pnl.catalogue(self.s,self.v)
        self.grant([S]);result=pnl.report(self.s,self.v,{'fy':2026})
        self.assertNotIn('Test Person',json.dumps(result));self.assertNotIn('employees',result)
        with self.assertRaises(AccessDenied):pnl.report(self.s,self.v,{'fy':2026,'kind':'salary'},True)
        with self.assertRaises(AccessDenied):pnl.report(self.s,self.v,{'fy':2026,'segments':[OTHER]})
        with self.assertRaises(AccessDenied):pnl.handle(self.s,self.v,{'action':'pnl_settings','fy':2026,'settings':{}})
        self.s.update_permissions(self.a,'viewer',{'menu_10':False})
        with self.assertRaises(AccessDenied):pnl.report(self.s,self.v,{'fy':2026})
    def test_unrelated_segment_financials_never_enter_viewer_response(self):
        m=master();m['revenue'].append({'sku':'OTHER','description':'PRIVATE PRODUCT','customer':'PRIVATE CUSTOMER','quantity':1,'uom':'EA','amount':900000})
        old=next(r['version'] for r in pnl.metadata(self.s,self.a) if r['kind']=='master')
        pnl.save(self.s,self.a,'master',2026,'Master.xlsx',m,old)
        pnl.save(self.s,self.a,'settings',2026,'Assumptions',pnl.validate_settings({'mapping':{'OTHER':OTHER}}),None)
        self.grant([S]);report=pnl.report(self.s,self.v,{'fy':2026})
        self.assertNotIn('PRIVATE',json.dumps(report));self.assertNotIn(OTHER,json.dumps(report))
        d=pnl.report(self.s,self.v,{'fy':2026,'kind':'revenue'},True)
        self.assertTrue(all(row[0]==S for row in d['rows']));self.assertEqual(d['rows'][0][-1],1000)
    def test_summary_scope_includes_full_live_segment_entitlement(self):
        m=master();m['rd'].append({'segment':OTHER,'center':'OTHER','description':'Private division','amount':20})
        old=next(r['version'] for r in pnl.metadata(self.s,self.a) if r['kind']=='master')
        pnl.save(self.s,self.a,'master',2026,'Master.xlsx',m,old)
        self.grant([S,OTHER]);wide=pnl.report(self.s,self.v,{'fy':2026,'segments':[S]})
        self.assertIn(OTHER,wide['segments'])
        self.grant([S]);narrow=pnl.report(self.s,self.v,{'fy':2026,'segments':[S]})
        self.assertNotIn(OTHER,json.dumps(narrow))
        self.assertNotEqual(wide['snapshotVersion'],narrow['snapshotVersion'])
    def test_cumulative_replacement_independent_uploads_and_restart(self):
        old=next(r['version'] for r in pnl.metadata(self.s,self.a) if r['kind']=='master')
        pnl.save(self.s,self.a,'master',2026,'New.xlsx',master(2000),old)
        self.assertEqual(pnl.report(self.s,self.a,{'fy':2026})['statement']['rows'][0][1],2000)
        self.assertEqual(len(pnl.read(self.s,self.a,'salary:2026')['employees']),1)
        with self.assertRaises(ValueError):pnl.save(self.s,self.a,'master',2026,'Stale.xlsx',master(),old)
        reopened=Store(self.s.url);self.assertEqual(pnl.read(reopened,self.a,'master:2026')['revenue'][0]['amount'],2000)
    def test_warm_reads_do_not_download_payload_and_details_are_paged(self):
        pnl.read(self.s,self.a,'master:2026');queries=[];run=self.s.run
        def record(db,sql,args=()):queries.append(sql);return run(db,sql,args)
        with patch.object(self.s,'run',side_effect=record):pnl.read(self.s,self.a,'master:2026')
        self.assertFalse(any('SELECT payload FROM stock_pnl_documents' in q for q in queries))
        pnl.report(self.s,self.a,{'fy':2026})
        with patch('stock_accounts.pnl.calculate',side_effect=AssertionError('Warm result recalculated')):pnl.report(self.s,self.a,{'fy':2026})
        detail=pnl.report(self.s,self.a,{'fy':2026,'kind':'salary'},True)
        self.assertEqual(detail['total'],2);self.assertEqual(len(detail['rows']),2)

    def test_persistent_summary_reused_after_restart_without_source_payload(self):
        first=pnl.report(self.s,self.a,{'fy':2026})
        reopened=Store(self.s.url);queries=[];run=reopened.run
        def record(db,sql,args=()):queries.append(sql);return run(db,sql,args)
        with patch.object(reopened,'run',side_effect=record),patch('stock_accounts.pnl.calculate',side_effect=AssertionError('Recalculated')),patch('stock_accounts.pnl.planning_data',side_effect=AssertionError('Downloaded planning source')):
            restored=pnl.report(reopened,self.a,{'fy':2026})
        self.assertEqual(first['statement'],restored['statement'])
        self.assertFalse(any('SELECT payload FROM stock_pnl_documents' in q for q in queries))
        self.assertNotIn('Test Person',json.dumps(restored))
        with patch('stock_accounts.pnl.calculate',wraps=pnl.calculate) as calc:pnl.report(reopened,self.a,{'fy':2026,'force':True});self.assertEqual(calc.call_count,1)
        old=next(r['version'] for r in pnl.metadata(self.s,self.a) if r['kind']=='master')
        pnl.save(self.s,self.a,'master',2026,'New.xlsx',master(2000),old)
        with self.assertRaisesRegex(ValueError,'changed'):pnl.report(self.s,self.a,{'fy':2026,'snapshotVersion':first['snapshotVersion'],'kind':'revenue'},True)
        self.assertEqual(pnl.report(self.s,self.a,{'fy':2026})['statement']['rows'][0][1],2000)

class FakeSheet:
    def __init__(self,rows):self.rows=rows;self.max_row=len(rows);self.max_column=max(map(len,rows))
    def iter_rows(self,values_only=True):return iter(self.rows)
class FakeBook:
    def __init__(self,sheets):self.sheets={k:FakeSheet(v) for k,v in sheets.items()};self.sheetnames=list(sheets);self.active=self.sheets[self.sheetnames[0]]
    def __getitem__(self,key):return self.sheets[key]
    def close(self):pass
class Imports(unittest.TestCase):
    def test_saved_pivot_continuations_and_controls(self):
        sheets={'Revenue':[['Material Code','Material Description','Customer Name','Quantity','UoM','Total'],['FG1','Example','Customer',-1,'EA',100],[None,None,None,-1,'EA',100],['Grand Total',None,None,None,None,200]],'R&D Cost':[['Segment','Cost Center','Cost Center Long Description','Total'],[S,'C1','Research',10],['Grand Total',None,None,10]],'Production Cost':[['Year','Month','Material Number','Material description','Batch','UoM','Produced Quantity','COGS'],[2026,'April','FG1','Example','B1','EA',1,50],[None,None,None,None,'B2','EA',1,50],['Grand Total',None,None,None,None,None,2,100]]}
        with patch('stock_accounts.pnl_import.open_saved',return_value=FakeBook(sheets)):m=read_master(b'fake','sample.xlsx','2026-04-01','2026-04-30')
        self.assertEqual(len(m['production']),2);self.assertEqual(m['production'][1]['sku'],'FG1');self.assertEqual(sum(r['amount'] for r in m['revenue']),200)
        sheets['Production Cost'].insert(-1,[2026,'September','FG1','Example','B3','EA',1,25])
        sheets['Production Cost'][-1][-1]=125
        with patch('stock_accounts.pnl_import.open_saved',return_value=FakeBook(sheets)):corrected=read_master(b'fake','august.xlsx','2026-04-01','2026-08-31')
        self.assertEqual(len(corrected['production']),2);self.assertEqual(corrected['end'],'2026-08-31')
        self.assertTrue(any('excluded' in w for w in corrected['warnings']))
        sheets['Revenue'][-1][-1]=999
        with patch('stock_accounts.pnl_import.open_saved',return_value=FakeBook(sheets)):
            with self.assertRaises(ValueError):read_master(b'fake','sample.xlsx','2026-04-01','2026-04-30')
    def test_salary_monthly_not_divided_by_twelve_and_duplicate_codes_rejected(self):
        rows=[['Emp Code','Emp Name','Joing Date','Leaving Date','Segment','Salary'],['E1','Test Person',date(2026,4,1),'NA',S+','+OTHER,600]]
        with patch('stock_accounts.pnl_import.open_saved',return_value=FakeBook({'Sheet1':rows})):s=read_salary(b'fake','salary.xlsx',2026)
        self.assertEqual(s['employees'][0]['monthly'],600);self.assertEqual(len(s['employees'][0]['segments']),2)
        rows.append(rows[-1])
        with patch('stock_accounts.pnl_import.open_saved',return_value=FakeBook({'Sheet1':rows})):
            with self.assertRaises(ValueError):read_salary(b'fake','salary.xlsx',2026)

if __name__=='__main__':unittest.main()
