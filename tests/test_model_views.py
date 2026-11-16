import copy,unittest
from stock_accounts.model_views import apply
from stock_accounts.segment_access import scope_data
from stock_accounts import pnl
from test_pnl import dataset,master,salary,S

def source():
    d=dataset()
    d['sheets']=[{'name':'Summary','headers':['Material','Qty'],'rows':[['ENERGY',2]]}, {'name':'BOM Cost','headers':['Material','Grand Total'],'rows':[['ENERGY',99]]}, {'name':'Sales Data','headers':d['sheets'][1]['headers'],'rows':d['sheets'][1]['rows']}, {'name':'Production Data','headers':['Year','Batch','Material(text)','Material','UoM','Order Quantity','Rejection Quantity','QC Quantity','FG Quantity'],'rows':[[2026,'ENERGY-B','Energy','ENERGY','EA',2,0,0,2]]}]
    def table(name,headers,rows):return {'name':name,'headers':headers,'rows':rows}
    d['tables'] += [
        table('BOM Cost',['Source.Name','Material','Material(text)','Base unit of measure','Component','Component quantity','Material Type','Price List.Price','Total BOM Cost'],[[S+'.xlsx','FG1','Product','EA','RM1',2,'ZRAW',3,6],[S+'.xlsx','FG1','Product','EA','PK1',3,'ZPKG',2,6]]),
        table('Unique Material',['Material','Source.Name'],[['FG1',S+'.xlsx']]),
        table('Production Order Details',['Order','Material Number','Batch','Order quantity (GMEIN)','Confirmed quantity (GMEIN)'],[[1,'FG1','BATCH',10,9]]),
        table('Stock Data',['Material','Current Stock'],[['FG1',7]]),
    ]
    moves=next(t for t in d['tables'] if t['name']=='Material Document List')
    moves['headers']=['Material','Batch','Movement Type','Posting Date','Material Type','Quantity','Unique Material.Source.Name','Material Description','Base Unit of Measure']
    moves['rows']=[['FG1','BATCH',m,'2026-04-02','ZFGS',q,S+'.xlsx','Product','EA'] for m,q in [(101,9),(331,-1),(321,8),(321,-8)]]
    return d

class FullModelViews(unittest.TestCase):
    def test_energy_only_saved_pivots_do_not_hide_other_segment(self):
        d=source();before=copy.deepcopy(d);result=apply(d)
        self.assertEqual(result['sheets'][1]['rows'][0][0],'FG1')
        self.assertEqual(result['sheets'][1]['rows'][0][7],12)
        self.assertEqual(result['sheets'][3]['rows'][0][:9],[2026,'BATCH','Product','FG1','EA',10,-1,-1,8])
        self.assertEqual(d,before)
        scoped=apply(scope_data(d,[S]))
        self.assertEqual(scoped['sheets'][1]['rows'][0][7],12)
        self.assertEqual(len(scoped['sheets'][3]['rows']),1)
        self.assertEqual(apply(scope_data(d,['Energy Devices']))['sheets'][1]['rows'],[])
    def test_missing_line_cost_uses_known_extended_price_but_not_zero(self):
        d=source();t=next(t for t in d['tables'] if t['name']=='BOM Cost')
        t['rows'][0][-1]=None
        self.assertEqual(apply(d)['sheets'][1]['rows'][0][7],12)
        t['rows'][0][-2]=None
        self.assertIsNone(apply(d)['sheets'][1]['rows'][0][7])
        r=pnl.calculate(master(),salary(),d,{},[S],basis='std_dp')
        values={row[0]:row[1] for row in r['statement']['rows']}
        self.assertIsNone(values['Product cost']);self.assertIsNone(values['Product cost %'])
        self.assertIsNone(values['EBITDA'])
    def test_std_dp_ignores_primary_sales_zero_override(self):
        d=source();r=pnl.calculate(master(),salary(),d,{'adjustments':{S:{'product_override':0}}},[S],basis='std_dp')
        values={row[0]:row[1] for row in r['statement']['rows']}
        self.assertEqual(values['Product cost'],120)
        self.assertEqual(values['Sales'],500)
    def test_stock_capacity_uses_original_component_minimum(self):
        d=source();bom=next(t for t in d['tables'] if t['name']=='BOM')
        bom['headers']+=['Max Quantity to be produced from current stock','MAX QUANTITY CAN BE PRODUCED AFTER RECEIVING STOCK']
        bom['rows'][0]+=[5,20]
        r=apply(d)['sheets'][0]['rows'][0]
        self.assertEqual(r[:5],['FG1',None,7,5,20])

    def test_both_workspace_entrypoints_serve_full_model_views(self):
        from stock_accounts.workspace import ui_payload as base
        from stock_accounts.workspace_insights import ui_payload as insights
        d=source();current={'data':d,'version':'sliced','filename':'Master.xlsx','updated_at':1792211998}
        for build in (base,insights):
            payload,_,_=build(current)
            self.assertEqual(payload['sheets'][1]['rows'][0][0],'FG1')
            self.assertEqual(payload['sheets'][3]['rows'][0][3],'FG1')
