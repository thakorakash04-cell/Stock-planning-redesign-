"""Read saved PnL reports and monthly fixed CTC. Never refresh Excel or retain originals."""
import calendar,io,math,re
from datetime import date,datetime,timedelta
from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel
from workbook import validate_zip

REVISION=3
def norm(value):return re.sub(r'[^a-z0-9]','',str(value or '').lower())
def segment(value):
    value=re.sub(r'\.xlsx?$','',str(value or '').strip(),flags=re.I)
    aliases={'advancedwoundcare':'Advance Wound Care','advancewoundcare':'Advance Wound Care','generalwoundcare':'General Wound Care','ostomy':'Ostomy Care','ostomycare':'Ostomy Care','endovascularsolutions':'Endovascular Solution','endovascularsolution':'Endovascular Solution','energydevices':'Energy Device','energydevice':'Energy Device','oncology':'Oncology'}
    return aliases.get(norm(value),value)
def code(value):return str(value or '').strip().removesuffix('.0')
def number(value,required=False):
    if value is None or str(value).strip()=='':
        if required:raise ValueError('A required amount or quantity is blank.')
        return None
    try:result=float(value)
    except (TypeError,ValueError):raise ValueError('Amounts and quantities must be numeric.') from None
    if not math.isfinite(result):raise ValueError('Amounts must be finite.')
    return result
def day(value):
    if isinstance(value,datetime):return value.date()
    if isinstance(value,date):return value
    if value is None or str(value).strip().upper() in ('','NA','N/A','NAT'):return None
    if isinstance(value,(float,int)):
        try:return from_excel(value).date()
        except (ValueError,AttributeError):return None
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y'):
        try:return datetime.strptime(str(value)[:10],fmt).date()
        except ValueError:pass
    return None
def fiscal(d):return d.year if d.month>=4 else d.year-1
def coverage(start,end):
    start,end=day(start),day(end)
    if not start or not end or start>end or start!=date(fiscal(start),4,1) or fiscal(end)!=fiscal(start):raise ValueError('Cumulative coverage must start on 1 April and end within the same financial year.')
    return start,end
def open_saved(raw,filename):
    if not str(filename).lower().endswith('.xlsx') or not 0<len(raw)<=25_000_000:raise ValueError('Choose an XLSX file under 25 MB.')
    validate_zip(raw)
    return load_workbook(io.BytesIO(raw),read_only=True,data_only=True,keep_links=False)
def find_sheet(wb,label):
    name=next((n for n in wb.sheetnames if norm(n)==norm(label)),None)
    if not name:raise ValueError('Missing worksheet: '+label)
    return wb[name]
def table(ws,required):
    if ws.max_row>100000 or ws.max_column>200:raise ValueError('The worksheet is too large.')
    iterator=ws.iter_rows(values_only=True)
    for row in iterator:
        headers=[norm(v) for v in row]
        if all(any(h in choices for h in headers) for choices in required.values()):
            indices={key:next(i for i,h in enumerate(headers) if h in choices) for key,choices in required.items()}
            return indices,iterator
    raise ValueError('Required worksheet columns were not found: '+', '.join(required))
def read_master(raw,filename,start,end):
    start,end=coverage(start,end);wb=open_saved(raw,filename)
    result={'start':start.isoformat(),'end':end.isoformat(),'fy':fiscal(start),'revenue':[],'production':[],'rd':[],'controls':{},'warnings':[]}
    try:
        ws=find_sheet(wb,'R&D Cost');ix,it=table(ws,{'segment':{'segment'},'center':{'costcenter','costcentre'},'description':{'costcenterlongdescription','costcentrelongdescription'},'amount':{'total','amount'}})
        previous=''
        for row in it:
            r={k:row[i] for k,i in ix.items()}
            if norm(r['segment'])=='grandtotal':result['controls']['rd']=number(r['amount'],True);continue
            if all(v is None for v in r.values()):continue
            if not r['center']:raise ValueError('R&D rows need a cost center.')
            previous=segment(r['segment']) if r['segment'] else previous
            if not previous:raise ValueError('An R&D segment is missing.')
            result['rd'].append({'segment':previous,'center':code(r['center']),'description':str(r['description'] or ''),'amount':number(r['amount'],True)})
        ws=find_sheet(wb,'Revenue');ix,it=table(ws,{'sku':{'materialcode','material','sku','skucode'},'description':{'materialdescription','description'},'customer':{'customername','customer'},'quantity':{'quantity'},'uom':{'uom','unit','baseunitofmeasure'},'amount':{'total','sales','amount','revenue'}})
        previous={}
        for row in it:
            r={k:row[i] for k,i in ix.items()}
            if norm(r['sku'])=='grandtotal':result['controls']['revenue']=number(r['amount'],True);continue
            if all(v is None for v in r.values()):continue
            for k in ('sku','description','customer'):
                if r[k] is not None:previous[k]=r[k]
                else:r[k]=previous.get(k)
            if not r['sku']:raise ValueError('A revenue SKU is missing.')
            result['revenue'].append({'sku':code(r['sku']),'description':str(r['description'] or ''),'customer':str(r['customer'] or ''),'quantity':number(r['quantity'],True),'uom':str(r['uom'] or ''),'amount':number(r['amount'],True)})
        ws=find_sheet(wb,'Production Cost');ix,it=table(ws,{'year':{'year'},'month':{'month'},'sku':{'materialnumber','materialcode','material','sku'},'description':{'materialdescription','description'},'batch':{'batch'},'uom':{'uom','unit'},'quantity':{'producedquantity','quantity'},'amount':{'cogs','productioncost','amount'}})
        previous={}
        for row in it:
            r={k:row[i] for k,i in ix.items()}
            if norm(r['year'])=='grandtotal':result['controls']['production']=number(r['amount'],True);continue
            if all(v is None for v in r.values()):continue
            for k in ('year','month','sku','description'):
                if r[k] is not None:previous[k]=r[k]
                else:r[k]=previous.get(k)
            try:
                month=int(r['month']) if str(r['month']).isdigit() else next(i for i in range(1,13) if norm(r['month']) in (norm(calendar.month_name[i]),norm(calendar.month_abbr[i])))
                d=date(int(r['year']),month,1)
            except (ValueError,TypeError,StopIteration):raise ValueError('Production needs valid Year and Month values.') from None
            result['production'].append({'month':d.isoformat(),'sku':code(r['sku']),'description':str(r['description'] or ''),'batch':str(r['batch'] or ''),'quantity':number(r['quantity'],True),'uom':str(r['uom'] or ''),'amount':number(r['amount'])})
        for kind in ('revenue','production','rd'):
            if not result[kind]:raise ValueError('No saved '+kind+' detail records were found.')
            total=sum(r['amount'] or 0 for r in result[kind])
            if kind not in result['controls'] or abs(total-result['controls'][kind])>.05:raise ValueError(kind+' detail does not reconcile to the saved Grand Total. Refresh and save Excel before uploading.')
        excluded=[r for r in result['production'] if not start<=day(r['month'])<=end]
        result['production']=[r for r in result['production'] if start<=day(r['month'])<=end]
        if excluded:result['warnings'].append(f'{len(excluded)} production rows outside {start} to {end} excluded after validating the full workbook Grand Total.')
        result['warnings'].append('Revenue and R&D are cumulative statement totals without row dates; they cannot be represented as monthly profit.')
        return result
    finally:wb.close()
def read_salary(raw,filename,fy):
    try:fy=int(fy)
    except (TypeError,ValueError):raise ValueError('Choose a valid financial year.') from None
    if not 2000<=fy<=2100:raise ValueError('Choose a valid financial year.')
    wb=open_saved(raw,filename)
    try:
        if len(wb.sheetnames)!=1:raise ValueError('Use one salary worksheet.')
        ix,it=table(wb.active,{'code':{'empcode','employeecode','employeeid'},'name':{'empname','employeename'},'join':{'joingdate','joiningdate','dateofjoining'},'leave':{'leavingdate','dateofleaving'},'segments':{'segment','segments'},'monthly':{'salary','monthlyfixedctc','monthlyctc','fixedctc'}})
        rows=[];seen=set()
        for row in it:
            r={k:row[i] for k,i in ix.items()}
            if all(v is None for v in r.values()):continue
            c=code(r['code']);join=day(r['join']);leave=day(r['leave']);amount=number(r['monthly'],True)
            segments=sorted(set(segment(x) for x in re.split(r'[,;\n]+',str(r['segments'] or '')) if x.strip()))
            if not c or c in seen or not join or not segments or amount<0:raise ValueError('Salary rows need unique employee codes, joining dates, non-negative monthly CTC and segments.')
            if r['leave'] is not None and str(r['leave']).strip().upper() not in ('','NA','N/A') and leave is None:raise ValueError('Invalid leaving date.')
            if leave and leave<join:raise ValueError('Leaving date cannot precede joining date.')
            seen.add(c);rows.append({'code':c,'name':str(r['name'] or ''),'join':join.isoformat(),'leave':leave.isoformat() if leave else None,'segments':segments,'monthly':amount})
        if not rows or len(rows)>20000:raise ValueError('Use 1–20,000 employee records.')
        return {'fy':fy,'employees':rows}
    finally:wb.close()
