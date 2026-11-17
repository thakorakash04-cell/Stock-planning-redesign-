from stock_accounts.meril_stock import apply

def report(rows,stamp=0):
 return {'available':True,'headers':['FG Code','Billed Qty','Segment'],'segmentIndex':2,'rows':rows,'source':{'updated_at':stamp}}

def test_fg_aggregation_signed_values_energy_exclusion_and_ist_date():
 table={'headers':['Material','Stock'],'rows':[['001',8],['FG2',1],['ED',2]]}
 p=report([['001',10,'Care'],['001',-2,'Care'],['FG2',1,'Care'],['ED',40,'Energy Device']])
 s=report([['001',3,'Care'],['FG2',5,'Care'],['ED',4,'Energy Device']],1767205800)
 r=apply(table,p,s,{'ED':['Energy Device']})
 assert r['rows'][0][-2:]==[5,'2026-01-01']
 assert r['rows'][1][-2]==-4
 assert r['rows'][2][-2:]==[None,None]
 assert table['rows'][0]==['001',8]

def test_missing_sources_columns_and_invalid_values_stay_unknown():
 t={'headers':['Material'],'rows':[['A'],['B']]}
 assert apply(t,{},report([]),{})['rows'][0][-2] is None
 p=report([['A',None,'Care']]);s=report([])
 assert apply(t,p,s,{})['rows'][0][-2] is None
 assert apply(t,p,s,{})['rows'][1][-2]==0
 p['headers'][1]='Billed Value'
 assert apply(t,p,s,{})['rows'][1][-2] is None
