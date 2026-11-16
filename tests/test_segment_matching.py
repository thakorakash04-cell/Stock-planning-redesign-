import copy,json,unittest
from workbook import segment_map
from stock_accounts.segment_access import scope_data

class SegmentMatching(unittest.TestCase):
    def test_normalized_codes_and_component_inheritance(self):
        tables=[{'name':'BOM','headers':['FG Material Code','Component Code','Source.Name'],'rows':[[' 00123.0 ',' rm1 ',' Ostomy Care.XLSX '],['FG2','RM2','Energy Device.xlsx']]}]
        mapping=segment_map(tables)
        self.assertEqual(mapping.get('00123'),{'Ostomy Care'})
        self.assertEqual(mapping.get('RM1'),{'Ostomy Care'})
        self.assertIsNone(mapping.get('123'))
        self.assertEqual(copy.deepcopy(mapping).get(' RM1 '),{'Ostomy Care'})
        self.assertEqual(len(json.loads(json.dumps({k:sorted(v) for k,v in mapping.items()}))),4)
    def test_scoped_stock_rows_use_same_code_normalization(self):
        data={'tables':[{'name':'BOM','headers':['Material','Source.Name'],'rows':[['1001','Ostomy Care.xlsx'],['FG2','Energy Device.xlsx']]},{'name':'Production','headers':['Material Number'],'rows':[[' 1001.0 '],[' fg2 ']]}],'sheets':[]}
        scoped=scope_data(data,['Ostomy Care'])
        self.assertEqual(scoped['tables'][1]['rows'],[[' 1001.0 ']])
        self.assertEqual(scope_data(data,['Energy Device'])['tables'][1]['rows'],[[' fg2 ']])
    def test_mixed_segment_aggregate_stays_restricted(self):
        data={'tables':[{'name':'BOM','headers':['Material','Source.Name'],'rows':[['A','Ostomy Care.xlsx'],['A','Energy Device.xlsx']]}],'sheets':[{'name':'Stock','headers':['Material'],'rows':[[' a ']]}]}
        self.assertEqual(scope_data(data,['Ostomy Care'])['sheets'][0]['rows'],[])

    def test_qualified_source_and_price_business_segment(self):
        data={'tables':[
            {'name':'Unique Material','headers':['Material','Source.Name'],'rows':[['A','Ostomy Care.XLSX']]},
            {'name':'Material Document List','headers':['Material','Unique Material.Source.Name'],'rows':[['A','Ostomy Care.XLSX'],['A','Energy Devices.xlsx']]},
            {'name':'DP MRP','headers':['SKU Code','Segment','Std  DP'],'rows':[['A','Ostomy',50]]},
            {'name':'Stock Data','headers':['Material','Current Stock'],'rows':[['A',100]]}
        ],'sheets':[]}
        scoped=scope_data(data,['ostomy care'])
        self.assertEqual(scoped['tables'][1]['rows'],[['A','Ostomy Care.XLSX']])
        self.assertEqual(scoped['tables'][2]['rows'],[['A','Ostomy',50]])
        self.assertEqual(segment_map(data['tables']).get('A'),{'Ostomy Care'})
        from stock_accounts.segment_access import available
        self.assertNotIn('Ostomy',available(data))
    def test_qualified_blank_source_uses_material_fallback(self):
        data={'tables':[{'name':'Unique Material','headers':['Material','Source.Name'],'rows':[['A','Ostomy Care.xlsx']]},{'name':'Material Document List','headers':['Material','Unique Material.Source.Name'],'rows':[['A',None],['B',None]]}],'sheets':[]}
        self.assertEqual(scope_data(data,['Ostomy Care'])['tables'][1]['rows'],[['A',None]])
