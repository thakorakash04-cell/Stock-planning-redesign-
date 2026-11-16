from copy import deepcopy
from stock_accounts.bom_prices import with_prices

def test_prices_follow_total_and_preserve_costs_and_input():
    sheet={'name':'BOM Cost','headers':['Material','Grand Total','Other'],'rows':[['FG1',42,'x'],['FG2',15,'y'],['MISSING',2,'z']]}
    dataset={'tables':[{'name':'DP MRP','headers':['Material','Std DP','MRP'],'rows':[['fg1 ',100,150],['FG2',0,20],['FG2',0,20]]}]}
    original=deepcopy(sheet)
    result=with_prices(sheet,dataset)
    assert result['headers']==['Material','Grand Total','Pack Size','Std DP','MRP','Other']
    assert result['rows']==[['FG1',42,None,100,150,'x'],['FG2',15,None,0,20,'y'],['MISSING',2,None,None,None,'z']]
    assert sheet==original

def test_conflicts_blank_and_new_master_prices_replace_old():
    sheet={'name':'BOM Cost','headers':['Material','Grand Total'],'rows':[['001',1]]}
    table={'name':'DP MRP','headers':['SKU Code','Std DP','MRP'],'rows':[['001',5,9],['001',6,9],['1',99,99]]}
    assert with_prices(sheet,{'tables':[table]})['rows']==[['001',1,None,None,9]]
    table['rows']=[['001',7,10]]
    assert with_prices(sheet,{'tables':[table]})['rows']==[['001',1,None,7,10]]

def test_missing_price_columns_and_other_views():
    sheet={'name':'BOM Cost','headers':['Material','Grand Total'],'rows':[['FG',2]]}
    assert with_prices(sheet,{'tables':[]})['rows']==[['FG',2,None,None,None]]
    other={**sheet,'name':'Summary'}
    assert with_prices(other,{}) is other

def test_pack_quantity_uses_sku_and_no_of_units_not_product_dimensions():
    sheet={'name':'BOM Cost','headers':['Material','Grand Total'],'rows':[['001',42],['FG2',10],['MISSING',5]]}
    table={'name':'DP MRP','headers':['SKU Code','Size','No. of  Units','Std  DP','MRP'],'rows':[[' 001.0 ','10cm x 10cm','5',100,150],['001','10cm x 10cm',5,100,150],['1','Other',99,999,999],['FG2','10 ml',1,20,30]]}
    assert with_prices(sheet,{'tables':[table]})['rows']==[['001',42,5,100,150],['FG2',10,1,20,30],['MISSING',5,None,None,None]]
    table['rows'].append(['001','10cm x 10cm',10,100,150])
    assert with_prices(sheet,{'tables':[table]})['rows'][0][2] is None
    table['rows']=[['001','10cm x 10cm',12,100,150]]
    assert with_prices(sheet,{'tables':[table]})['rows'][0][2]==12
