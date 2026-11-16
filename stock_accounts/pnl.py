"""Permission-scoped cumulative PnL, monthly fixed CTC and version-cached source documents."""
import base64,calendar,copy,gzip,hashlib,json,math,threading,time
from collections import OrderedDict,defaultdict
from datetime import date,timedelta
from .store import AccessDenied
from .pnl_import import code,coverage,day,fiscal,norm,number,read_master,read_salary,segment

REVISION=9
_lock=threading.RLock()
DEFAULTS={'interest_rate':.085,'tax_rate':.18,'debtor_days':90.,'year_days':360,'transfer_multiplier':1,'transfer_movements':['601','602'],'transfer_sku_price':True,'inventory_override':None,'creditor_override':None,'mapping':{},'adjustments':{}}
def authorize(store,actor,admin=False):
    with store.transaction() as db:
        identity=store.require(db,actor,admin=admin)
        if identity['role']!='admin' and not identity['permissions'].get('menu_10',False):raise AccessDenied('Your administrator has not granted PnL access.')
        return identity
def schema(store):
    with _lock:
        if getattr(store,'_pnl_schema',False)==REVISION:return
        with store.transaction() as db:
            store.run(db,'CREATE TABLE IF NOT EXISTS stock_pnl_documents (id TEXT PRIMARY KEY,kind TEXT NOT NULL,fy INTEGER NOT NULL,filename TEXT NOT NULL,version TEXT NOT NULL,updated_at DOUBLE PRECISION NOT NULL,updated_by TEXT NOT NULL,segments TEXT NOT NULL,payload TEXT NOT NULL)')
            store.run(db,'CREATE TABLE IF NOT EXISTS stock_pnl_summaries (cache_key TEXT PRIMARY KEY,fy INTEGER NOT NULL,payload TEXT NOT NULL,created_at DOUBLE PRECISION NOT NULL)')
        store._pnl_schema=REVISION;store._pnl_cache=OrderedDict();store._pnl_cache_bytes=0;store._pnl_results=OrderedDict();store._pnl_summaries=OrderedDict()
def metadata(store,actor):
    authorize(store,actor);schema(store)
    with store.transaction() as db:
        store.require(db,actor)
        return [dict(r) for r in store.run(db,'SELECT id,kind,fy,filename,version,updated_at,updated_by,segments FROM stock_pnl_documents ORDER BY fy DESC,kind').fetchall()]
def read(store,actor,key):
    authorize(store,actor);schema(store)
    with store.transaction() as db:
        store.require(db,actor)
        row=store.run(db,'SELECT version FROM stock_pnl_documents WHERE id=?',(key,)).fetchone()
        if not row:return None
        cachekey=(key,row['version'])
        with _lock:cached=store._pnl_cache.get(cachekey)
        if cached is not None:return copy.deepcopy(cached[0])
        row=store.run(db,'SELECT payload FROM stock_pnl_documents WHERE id=? AND version=?',(key,row['version'])).fetchone()
        if not row:raise ValueError('PnL source changed. Reload and retry.')
        raw=gzip.decompress(base64.b64decode(row['payload']));value=json.loads(raw)
    with _lock:
        if len(raw)<=16_000_000:
            if cachekey in store._pnl_cache:store._pnl_cache_bytes-=store._pnl_cache[cachekey][1]
            store._pnl_cache[cachekey]=(value,len(raw));store._pnl_cache_bytes+=len(raw)
            while len(store._pnl_cache)>16 or store._pnl_cache_bytes>32_000_000:
                _,old=store._pnl_cache.popitem(last=False);store._pnl_cache_bytes-=old[1]
    return copy.deepcopy(value)
def save(store,actor,kind,fy,filename,value,expected):
    authorize(store,actor,True);schema(store);key=f'{kind}:{fy}'
    raw=json.dumps(value,allow_nan=False,separators=(',',':')).encode()
    if len(raw)>16_000_000:raise ValueError('Prepared PnL data exceeds 16 MB. Reduce the workbook scope.')
    version=hashlib.sha256(raw).hexdigest();payload=base64.b64encode(gzip.compress(raw)).decode()
    names=sorted({r['segment'] for r in value.get('rd',[])}|{s for r in value.get('employees',[]) for s in r['segments']})
    with store.transaction() as db:
        store.require(db,actor,admin=True)
        row=store.run(db,'SELECT version FROM stock_pnl_documents WHERE id=?'+('' if store.sqlite else ' FOR UPDATE'),(key,)).fetchone()
        if (row['version'] if row else None)!=expected:raise ValueError('This PnL source changed. Reload before replacing it.')
        store.run(db,'INSERT INTO stock_pnl_documents VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET filename=excluded.filename,version=excluded.version,updated_at=excluded.updated_at,updated_by=excluded.updated_by,segments=excluded.segments,payload=excluded.payload',(key,kind,fy,str(filename)[:255],version,time.time(),actor.username,json.dumps(names),payload))
        store._log(db,actor.username,'pnl_'+kind+'_updated',str(fy),actor.session_id,{'version':version})
        store.history_write(db,actor,'PnL '+kind,{'version':expected},{'version':version,'fy':fy})
    return {'ok':True,'version':version}
def all_segments(store,actor):
    authorize(store,actor,True)
    return sorted({s for r in metadata(store,actor) for s in json.loads(r['segments'])})
def catalogue(store,actor):
    identity=authorize(store,actor);docs=metadata(store,actor)
    allowed=identity.get('allowedSegments');permitted=None if allowed is None else {segment(s) for s in allowed}
    names={s for r in docs for s in json.loads(r['segments'])}
    from .product_catalog import read as products_read
    products=products_read(store,actor)
    names.update(segment(p['division']) for p in products['products'])
    return {'documents':[{k:v for k,v in r.items() if k!='segments'} for r in docs], 'segments':sorted(s for s in names if permitted is None or s in permitted),'admin':identity['role']=='admin','products':[{'id':p['id'],'name':p['name'],'segment':segment(p['division']),'codes':p['codes']} for p in products['products']],'productVersion':products['version']}
def validate_settings(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Invalid PnL assumptions.')
    out={**copy.deepcopy(DEFAULTS),**value}
    for key,lo,hi in [('interest_rate',0,1),('tax_rate',0,1),('debtor_days',0,2000),('year_days',360,366)]:
        out[key]=number(out[key],True)
        if not lo<=out[key]<=hi:raise ValueError('PnL assumption outside the allowed range: '+key)
    if out['year_days'] not in (360,365,366) or out['transfer_multiplier'] not in (-1,1):raise ValueError('Use 360/365/366 days and transfer sign 1 or -1.')
    if not isinstance(out['transfer_sku_price'],bool):raise ValueError('Choose the original SKU price convention or strict unit matching.')
    movements=out['transfer_movements']
    if not isinstance(movements,list) or not 1<=len(movements)<=30 or any(not isinstance(v,str) or not v.isdigit() or len(v)>4 for v in movements):raise ValueError('Enter 1–30 numeric transfer movement codes.')
    out['transfer_movements']=sorted(set(movements))
    for key in ('inventory_override','creditor_override'):
        out[key]=number(out[key])
        if out[key] is not None and not 0<=out[key]<=2000:raise ValueError('Day overrides must be 0–2000 or blank.')
    if not isinstance(out['mapping'],dict) or len(out['mapping'])>10000:raise ValueError('Use at most 10,000 SKU mappings.')
    out['mapping']={code(k):segment(v) for k,v in out['mapping'].items()}
    if any(not k or len(k)>100 or not v or len(v)>100 for k,v in out['mapping'].items()):raise ValueError('Enter valid SKU and segment mappings.')
    if not isinstance(out['adjustments'],dict) or len(out['adjustments'])>200:raise ValueError('Invalid segment adjustments.')
    for s,values in out['adjustments'].items():
        if not s or len(s)>100 or not isinstance(values,dict) or set(values)-{'manufacturing','sga','depreciation','capex','product_override'}:raise ValueError('Invalid adjustment fields.')
        for k,v in values.items():
            values[k]=number(v)
            if values[k] is not None and values[k]<0:raise ValueError('Adjustment amounts cannot be negative.')
    return out
def months(start,end):
    d=start.replace(day=1)
    while d<=end:
        last=date(d.year,d.month,calendar.monthrange(d.year,d.month)[1]);a,b=max(d,start),min(last,end)
        yield d,a,b,(b-a).days+1,calendar.monthrange(d.year,d.month)[1]
        d=last+timedelta(days=1)
def salary_rows(salary,start,end,wanted):
    totals=defaultdict(float);monthly=defaultdict(float);details=[]
    for emp in salary['employees']:
        join,leave=day(emp['join']),day(emp.get('leave')) or end
        for d,a,b,_,days_in_month in months(start,end):
            days=max(0,(min(b,leave)-max(a,join)).days+1)
            for s in emp['segments']:
                if s not in wanted or not days:continue
                cost=emp['monthly']*days/days_in_month/len(emp['segments'])
                totals[s]+=cost;monthly[(d.isoformat(),s)]+=cost
                details.append([emp['code'],emp['name'],s,d.isoformat(),emp['monthly'],emp['join'],emp.get('leave'),days,len(emp['segments']),cost])
    return totals,monthly,details
def source_mapping(dataset,settings):
    from workbook import segment_map
    result={code(k):sorted({segment(s) for s in v}) for k,v in segment_map(dataset.get('tables',[])).items()}
    result.update({k:[v] for k,v in settings['mapping'].items()})
    return result
def material_selection(value):
    """Accept legacy single types and explicit checkbox selections without changing calculations."""
    if value=='all' or value is None:return 'all'
    if isinstance(value,str):return [value]
    if not isinstance(value,list) or len(value)>200 or any(not isinstance(v,str) or len(v)>150 for v in value):raise ValueError('Choose valid lead-time material types.')
    return sorted(set(value))

def lead_observations(dataset,start,end,wanted,material_type='all'):
    from .lead_time import build
    material_type=material_selection(material_type)
    table,_=build(dataset);values=defaultdict(lambda:[defaultdict(set),defaultdict(set)]);details=[]
    for r in table['rows']:
        inward=day(r[5])
        if not inward or not start<=inward<=end or (material_type!='all' and str(r[11]) not in material_type):continue
        tags={segment(x) for x in str(r[12] or '').split(',')}
        for s in tags.intersection(wanted):
            details.append([s,*r])
            for i,col in enumerate((10,8)):
                if isinstance(r[col],(float,int)) and r[col]>=0:values[s][i][(str(r[0]),str(r[2]))].add(r[col])
    avg={s:[sum(sum(v)/len(v) for v in groups.values())/len(groups) if groups else None for groups in pairs] for s,pairs in values.items()}
    return avg,details,table['headers'],sorted({str(r[11]) for r in table['rows'] if r[11]})
def transfers(dataset,start,end,settings):
    """Saved Sales Data is the authoritative movement-filtered view; no invented movement allowlist."""
    sheet=next((s for s in dataset.get('sheets',[]) if norm(s['name']) in {'salesdata','salestransfers','salesandtransfers'}),None)
    def columns(source):
        h=[norm(x) for x in source['headers']]
        def ix(names):return next((i for i,x in enumerate(h) if x in names),None)
        return (ix({'material','materialcode','materialnumber','sku','skucode'}),ix({'totaltransferquantity','transferquantity','totalsalesquantity','salesquantity','quantity','sumofquantity','totalquantity','sumoftotaltransferquantity','fgtransferquantitymmimlsiplmep','transferqty'}),ix({'year','years','postingdateyear'}),ix({'month','months','postingdatemonth','postingdatemonthindex'}),ix({'postingdate','date','documentdate'}),ix({'uom','unit','baseunitofmeasure','unitofentry'}),ix({'movementtype'}))
    ledger=False
    if sheet:
        ki,qi,yi,mi,di,ui,move=columns(sheet)
    if not sheet or ki is None or qi is None or (di is None and (yi is None or mi is None)):
        sheet=next((t for t in dataset.get('tables',[]) if norm(t['name'])=='materialdocumentlist'),None)
        if not sheet:raise ValueError('Dated transfer records are missing. Upload the full planning workbook with its Material Document List model.')
        ki,qi,yi,mi,di,ui,move=columns(sheet);h=[norm(x) for x in sheet['headers']]
        # Verified source measure Mvm 601 = -SUM(Qty in Un. of Entry), 601/602.
        qi=next((i for i,x in enumerate(h) if x in {'qtyinunofentry','quantityinunitofentry'}),qi)
        ui=next((i for i,x in enumerate(h) if x=='unitofentry'),ui)
        ledger=True
        if move is None:raise ValueError('Material Document List needs Movement Type to identify eligible transfers.')
    if ki is None or qi is None or (di is None and (yi is None or mi is None)):raise ValueError('Dated transfer source needs Material, Quantity and Posting Date or Year/Month columns.')
    hs=[norm(x) for x in sheet['headers']]
    material_type=next((i for i,x in enumerate(hs) if x=='materialtype'),None)
    material_description=next((i for i,x in enumerate(hs) if x=='materialtypedescription'),None)
    from .sales import material_key
    rates=defaultdict(set);units=defaultdict(set)
    rate_tables=[t for t in dataset.get('tables',[]) if norm(t['name']) in {'dpmrp','dpmrpdata'}] or [t for t in dataset.get('tables',[]) if norm(t['name']) not in {'bom','bomcost'}]
    for t in rate_tables:
        hs=[norm(x) for x in t['headers']];key=next((i for i,x in enumerate(hs) if x in {'material','materialcode','materialnumber','sku','skucode'}),None);price=next((i for i,x in enumerate(hs) if x in {'stddp','standarddp','stddpvalue','stddpprice','stddpinr','dpmrpstddp'}),None);unit=next((i for i,x in enumerate(hs) if x in {'uom','unit','baseunitofmeasure'}),None)
        if key is not None and unit is not None:
            for r in t['rows']:
                if r[unit]:units[material_key(r[key])].add(str(r[unit]))
        if key is None or price is None:continue
        for r in t['rows']:
            try:value=number(r[price])
            except ValueError:continue
            if value is not None and value>=0:rates[material_key(r[key])].add((value,str(r[unit] or '') if unit is not None else ''))
    from workbook import row_source
    out=[];warnings=['Dated Material Document List: finished-goods transfer movements '+', '.join(settings['transfer_movements'])+'; quantity = minus Qty in Un. of Entry (reversals retained).'] if ledger else []
    unit_notes=set()
    for r in sheet['rows']:
        if ledger:
            if code(r[move]) not in settings['transfer_movements']:continue
            if material_type is not None and norm(r[material_type]) not in {'zfgs','zfert','fert','fg','finishedgoods'}:continue
            if material_type is None and material_description is not None and norm(r[material_description])!='finishedgoods':continue
        if di is not None:d=day(r[di])
        else:
            try:
                month=int(r[mi]) if str(r[mi]).isdigit() else next(i for i in range(1,13) if norm(r[mi]) in (norm(calendar.month_name[i]),norm(calendar.month_abbr[i])))
                d=date(int(r[yi]),month,1)
            except (ValueError,TypeError,StopIteration):raise ValueError('Sales Data contains an invalid Year/Month. Refresh the planning workbook.') from None
        if not d:raise ValueError('Sales Data contains a missing posting date.')
        if not start<=d<=end:continue
        if di is None and end<date(d.year,d.month,calendar.monthrange(d.year,d.month)[1]):raise ValueError('A partial statement month cannot be valued from a monthly Sales Data total.')
        sku=code(r[ki]);qty=number(r[qi],True)*settings['transfer_multiplier']*(-1 if ledger else 1);unit=str(r[ui] or '') if ui is not None else (next(iter(units[material_key(sku)])) if len(units[material_key(sku)])==1 else '');options=rates.get(material_key(sku),set());prices={v for v,u in options if unit and (not u or norm(u)==norm(unit))}
        if ledger and not prices and settings['transfer_sku_price']:
            # Preserve the source Transferred DP Value SKU-price convention.
            # No pack conversion is implied by this multiplication.
            prices={v for v,_ in options}
            if len(prices)==1:unit_notes.add(sku)
        price=next(iter(prices)) if len(prices)==1 else None
        out.append({'sku':sku,'date':d.isoformat(),'quantity':qty,'uom':unit,'rate':price,'amount':qty*price if price is not None else (0 if qty==0 else None),'segment':row_source(sheet['headers'],r) if ledger else '', 'movement':('Ledger transfer · ' if ledger else '')+str(r[move]) if move is not None else 'Saved worksheet filters'})
    if unit_notes:warnings.append('Original workbook SKU-price convention: some transfer unit labels differ from DP UOM. Qty in Un. of Entry × SKU Std DP is retained without a pack conversion. Admin can require strict unit matching.')
    return out,warnings
def bom_costs(dataset):
    """Prefer saved FG totals; model totals fill only missing SKUs, never conflicts."""
    from .sales import material_key
    key_names={'material','materialcode','materialnumber','fgcode','fgmaterial','fgmaterialcode','fgmaterialnumber','sku','skucode','rowlabels'}
    def collect(sources,model=False):
        rates=defaultdict(set)
        for sheet in sources:
            if norm(sheet.get('name'))!='bomcost':continue
            headers=[norm(h) for h in sheet['headers']]
            ki=next((i for i,h in enumerate(headers) if h in key_names),None)
            totals=('grandtotal','totalbomcost','bomcosttotal','totalcost') if model else ('grandtotal','totalbomcost','bomcosttotal','totalcost','total')
            ci=next((headers.index(h) for h in totals if h in headers),None)
            if ki is None or ci is None:continue
            line_cost=model and 'component' in headers and headers[ci]=='totalbomcost'
            line_totals=defaultdict(float);invalid=set();seen=set()
            for row in sheet['rows']:
                if max(ki,ci)>=len(row):continue
                sku=material_key(row[ki])
                if not sku:continue
                try:value=number(row[ci])
                except ValueError:
                    if line_cost:invalid.add(sku)
                    continue
                if line_cost:
                    identity=json.dumps(row,sort_keys=True)
                    if identity in seen:continue
                    seen.add(identity)
                    if value is None:invalid.add(sku)
                    else:line_totals[sku]+=value
                elif value is not None:rates[sku].add(value)
            for sku,total in line_totals.items():
                if sku not in invalid:rates[sku].add(total)
        return {k:next(iter(v)) if len(v)==1 else None for k,v in rates.items()}
    from .model_views import bom_sheet
    saved=[bom_sheet(dataset,sheet) if norm(sheet.get('name'))=='bomcost' else sheet for sheet in dataset.get('sheets',[])]
    rates=collect(saved)
    for sku,value in collect(dataset.get('tables',[]),True).items():rates.setdefault(sku,value)
    return rates

def calculate(master,salary,dataset,settings,selected,restricted=False,basis='revenue',material_type='all',products=None,product_ids=None):
    start,end=coverage(master['start'],master['end']);settings=validate_settings(settings);mapping=source_mapping(dataset,settings)
    from .sales import material_key
    mapping={material_key(k):v for k,v in mapping.items()};factors={};selected_skus=None;allocations=[]
    if product_ids:
        products=products or [];by_id={p['id']:p for p in products};ids=set(product_ids)
        if not ids.issubset(by_id):raise ValueError('A selected product is unavailable. Refresh the product list.')
        population=defaultdict(set);owners=defaultdict(set)
        for p in products:
            s=segment(p.get('segment',p.get('division')));population[s].add(p['id'])
            for sku in p['codes']:owners[material_key(sku)].add(p['id'])
        counts=defaultdict(int);selected_skus=set()
        for pid in sorted(ids):
            p=by_id[pid];s=segment(p.get('segment',p.get('division')))
            if selected and s not in selected:raise ValueError('Selected products must belong to the selected working segments.')
            counts[s]+=1
            for sku in p['codes']:
                key=material_key(sku)
                if len(owners[key])!=1:raise ValueError('A selected SKU belongs to multiple products. Correct the product mapping before calculating PnL.')
                selected_skus.add(key);mapping[key]=[s]
            allocations.append([p['id'],p['name'],s,len(population[s]),1/len(population[s])])
        factors={s:n/len(population[s]) for s,n in counts.items()}
    resolve=lambda sku: mapping.get(material_key(sku),['Unmapped'])[0] if len(mapping.get(material_key(sku),['Unmapped']))==1 else 'Unmapped'
    names={r['segment'] for r in master['rd']}|{resolve(r['sku']) for kind in ('production','revenue') for r in master[kind]}|{s for e in (salary or {}).get('employees',[]) for s in e['segments']}
    wanted=set(selected) if selected else names
    if product_ids:wanted=set(factors)
    if restricted:wanted.discard('Unmapped')
    details={'revenue':[],'production':[],'rd':[],'salary':[],'lead':[],'transfers':[],'bom':[]};totals={s:defaultdict(float) for s in wanted};issues={s:[] for s in wanted};warnings=list(master['warnings']);monthly=defaultdict(lambda:[0.,0.])
    if basis not in ('revenue','std_dp'):raise ValueError('Secondary sales is reserved for a future release.')
    for kind in ('revenue','production','rd'):
        for r in master[kind]:
            s=r['segment'] if kind=='rd' else resolve(r['sku'])
            if s not in wanted or (kind!='rd' and selected_skus is not None and material_key(r['sku']) not in selected_skus):continue
            amount=(r['amount'] or 0)*(factors.get(s,1) if kind=='rd' else 1)
            totals[s][kind]+=amount
            if kind=='production':
                details[kind].append([s,r['month'],r['sku'],r['description'],r['batch'],r['quantity'],r['uom'],r['amount']]);monthly[(r['month'],s)][0]+=r['amount'] or 0
                if basis=='revenue' and r['amount'] is None and r['quantity']!=0:issues[s].append('Missing production cost')
            elif kind=='revenue':details[kind].append([s,r['sku'],r['description'],r['customer'],r['quantity'],r['uom'],r['amount']])
            else:details[kind].append([s,r['center'],r['description'],amount])
    if salary:
        sal,salmonths,saldetail=salary_rows(salary,start,end,wanted);details['salary']=saldetail
        for s in wanted:totals[s]['salary']=sal[s]*factors.get(s,1)
        for row in details['salary']:row[-1]*=factors.get(row[2],1)
        for key,value in salmonths.items():monthly[key][1]=value*factors.get(key[1],1)
    else:
        for s in wanted:issues[s].append('Annual salary file not uploaded')
    if basis=='std_dp':
        warnings.append('Product cost = cached BOM Cost Grand Total × eligible net transfer quantity within the statement period; no pack conversion is inferred. Other costs retain the uploaded statement assumptions.')
        tx,notes=transfers(dataset,start,end,settings);warnings+=notes
        from .sales import material_key
        costs=bom_costs(dataset)
        for s in wanted:totals[s]['revenue']=0;totals[s]['production']=0
        for r in tx:
            s=resolve(r['sku']) if product_ids or not r.get('segment') else segment(r['segment'])
            if s not in wanted or (selected_skus is not None and material_key(r['sku']) not in selected_skus):continue
            cost=costs.get(material_key(r['sku']));value=r['quantity']*cost if cost is not None else (0 if r['quantity']==0 else None)
            totals[s]['production']+=value or 0
            details['bom'].append([s,r['date'],r['sku'],r['quantity'],r['uom'],cost,value,r['movement']])
            if value is None:issues[s].append('Missing or conflicting BOM Grand Total')
            totals[s]['revenue']+=r['amount'] or 0;details['transfers'].append([s,r['date'],r['sku'],r['quantity'],r['uom'],r['rate'],r['amount'],r['movement']])
            if r['amount'] is None:issues[s].append('Missing or conflicting Std DP / unit')
        if not tx:
            for s in wanted:issues[s].append('No eligible dated Sales Data rows in the statement period')
        warnings.append('Std DP uses the current planning workbook version. Dated Sales Data is used when available; a batch-only sheet uses the dated Material Document List with the verified 601/602 transfer profile (admin configurable). No historical price or unit conversion is invented.')
    lead,details['lead'],lead_headers,material_types=lead_observations(dataset,start,end,wanted,material_type)
    fraction=sum(days/full for _,_,_,days,full in months(start,end))/12;denominator=settings['year_days']*fraction;statements={}
    for s,t in totals.items():
        adj={k:(v*factors.get(s,1) if v is not None else None) for k,v in settings['adjustments'].get(s,{}).items()};inventory,creditor=lead.get(s,[None,None]);inventory=settings['inventory_override'] if settings['inventory_override'] is not None else inventory;creditor=settings['creditor_override'] if settings['creditor_override'] is not None else creditor
        product=t['production']
        if basis!='std_dp' and adj.get('product_override') is not None and not product_ids:
            product=adj['product_override'];issues[s]=[x for x in issues[s] if x not in ('Missing production cost','Missing or conflicting BOM Grand Total')]
        manufacturing=adj.get('manufacturing') or 0;sga=adj.get('sga') or 0;depreciation=adj.get('depreciation') or 0;capex=adj.get('capex') or 0
        if s=='Unmapped':issues[s].append('Unmapped or ambiguous SKU segments')
        missing_bom=basis=='std_dp' and 'Missing or conflicting BOM Grand Total' in issues[s]
        if missing_bom:product=None
        operating=(product if product is not None else 0)+t['rd']+(t['salary'] if salary else 0)+manufacturing+sga
        # A recorded-cost subtotal is useful even when a COGS cell is blank.
        # Keep the incompleteness warning; never pretend missing COGS was confirmed zero.
        blocking=[x for x in issues[s] if x not in ('Missing production cost','Unmapped or ambiguous SKU segments')]
        ebitda=t['revenue']-operating if not blocking else None
        wc=0 if t['revenue']==0 else None if inventory is None or creditor is None else t['revenue']/denominator*(settings['debtor_days']+inventory-creditor)
        if t['revenue']!=0 and (inventory is None or creditor is None):issues[s].append('Missing inward-period lead time; admin override or source history required')
        interest=(wc+capex)*settings['interest_rate']*fraction if wc is not None else None
        pbt=ebitda-interest-depreciation if ebitda is not None and interest is not None else None;tax=pbt*settings['tax_rate'] if pbt is not None else None;pat=pbt-tax if pbt is not None else None;cash=pat+depreciation if pat is not None else None
        invested=wc+capex+t['rd'] if wc is not None else None
        statements[s]={'Sales':t['revenue'],'Product cost':product,'Manufacturing OHD':manufacturing,'Employee cost':t['salary'] if salary else None,'SG&A':sga,'R&D cost':t['rd'],'Total cost':operating if salary and not missing_bom else None,'EBITDA':ebitda,'EBITDA %':ebitda/t['revenue']*100 if ebitda is not None and t['revenue'] else None,'Interest':interest,'Depreciation':depreciation,'Profit before tax':pbt,'Profit before tax %':pbt/t['revenue']*100 if pbt is not None and t['revenue'] else None,'Income tax':tax,'PAT':pat,'PAT %':pat/t['revenue']*100 if pat is not None and t['revenue'] else None,'Cash profit':cash,'Working capital':wc,'Net cash profit':cash-wc if cash is not None and wc is not None else None,'Capex':capex,'ROI %':pat/invested*100 if pat is not None and invested else (0 if pat is not None and invested==0 else None),'Inventory days':inventory,'Creditor days':creditor,'Debtor days':settings['debtor_days']}
    cost_labels=('Product cost','Manufacturing OHD','Employee cost','SG&A','R&D cost','Total cost')
    for s,values in statements.items():
        expanded={}
        for label,value in values.items():
            expanded[label]=value
            if label in cost_labels:expanded[label+' %']=value/values['Sales']*100 if value is not None and values['Sales'] else None
        statements[s]=expanded
    aggregate={}
    for key in next(iter(statements.values()),{}):
        values=[v[key] for v in statements.values()]
        aggregate[key]=sum(values) if all(v is not None for v in values) and not key.endswith('days') and not key.endswith('%') else None
    aggregate['Debtor days']=settings['debtor_days']
    for key in ('Inventory days','Creditor days'):
        # Lead-time assumptions retain the master Revenue weights across sales modes.
        weights=defaultdict(float)
        for r in master['revenue']:
            if resolve(r['sku']) in statements and (selected_skus is None or material_key(r['sku']) in selected_skus):weights[resolve(r['sku'])]+=r['amount'] or 0
        active=[(statements[s][key],weights[s]) for s in statements if weights[s]!=0]
        aggregate[key]=sum(v*w for v,w in active)/sum(w for _,w in active) if active and all(v is not None for v,_ in active) and sum(w for _,w in active)!=0 else (next(iter(statements.values()))[key] if len(statements)==1 else None)
    for key,numerator in [(label+' %',label) for label in (*cost_labels,'EBITDA','Profit before tax','PAT')]:
        aggregate[key]=aggregate.get(numerator)/aggregate['Sales']*100 if aggregate.get(numerator) is not None and aggregate.get('Sales') else None
    investment=(aggregate.get('Working capital') or 0)+(aggregate.get('Capex') or 0)+(aggregate.get('R&D cost') or 0)
    aggregate['ROI %']=aggregate['PAT']/investment*100 if aggregate.get('PAT') is not None and investment else (0 if aggregate.get('PAT') is not None and investment==0 else None)
    if product_ids:
        warnings.append('Product PnL matches selected product SKU codes only. Salary and R&D are allocated by selected product count ÷ all catalogue products in the working segment, after normal salary proration and multi-segment allocation. Shared admin OHD/SG&A/depreciation/capex use the same share. Segment product-cost overrides do not replace SKU costs in product mode. Lead-time days retain the segment assumptions.')
        if any(not next(p for p in products if p['id']==pid)['codes'] for pid in product_ids):warnings.append('A selected product has no mapped SKU: it receives its shared costs but has no matched sales or production records.')
    details['allocation']=allocations
    if any(issues.values()):warnings+=sorted({s+': '+x for s,v in issues.items() for x in set(v)})
    if any('Missing production cost' in v for v in issues.values()):warnings.append('Provisional: product cost is the sum of recorded COGS. EBITDA and downstream profit use that displayed subtotal; blank COGS is not a confirmed zero. Complete the source costs or set an admin product-cost override.')
    return {'statement':{'headers':['Particulars','Selected total',*sorted(statements)],'rows':[[key,aggregate[key],*[statements[s][key] for s in sorted(statements)]] for key in aggregate]},'monthly':{'headers':['Month','Segment','Recorded production cost','Allocated employee cost'],'rows':[[m,s,*v] for (m,s),v in sorted(monthly.items())]},'warnings':warnings,'details':details,'leadHeaders':['Segment',*lead_headers],'segments':sorted(names),'unmapped':sorted({r['sku'] for kind in ('production','revenue') for r in master[kind] if resolve(r['sku'])=='Unmapped'}),'period':{'start':start.isoformat(),'end':end.isoformat(),'yearFraction':fraction},'complete':not any(issues.values()),'materialTypes':material_types,'formulaDrivers':{'interestRate':settings['interest_rate'],'taxRate':settings['tax_rate'],'yearFraction':fraction}}
def planning_data(store,actor):
    """Internal full source read. PnL applies canonical segment boundaries before any response."""
    authorize(store,actor)
    with store.transaction() as db:
        store.require(db,actor)
        meta=store.run(db,"SELECT version,updated_at,filename FROM datasets WHERE id='current'").fetchone()
        if not meta:return None
        key=(meta['version'],meta['updated_at'],meta['filename']);cached=getattr(store,'_dataset_payload_cache',None)
        if cached and cached[0]==key:row=cached[1]
        else:
            row=store.run(db,"SELECT * FROM datasets WHERE id='current' AND version=?",(meta['version'],)).fetchone()
            if not row:raise ValueError('Planning source changed. Retry the PnL request.')
            row=dict(row);store._dataset_payload_cache=(key,row)
    result=dict(row);result['data']=json.loads(gzip.decompress(base64.b64decode(result.pop('payload'))));return result

def report(store,actor,event,detail=False):
    identity=authorize(store,actor)
    try:fy=int(event.get('fy'))
    except (TypeError,ValueError):raise ValueError('Select a financial year.') from None
    choices=event.get('segments',[])
    product_ids=event.get('products',[])
    if not isinstance(product_ids,list) or len(product_ids)>2000 or any(not isinstance(p,str) or len(p)>200 for p in product_ids):raise ValueError('Choose valid products.')
    product_ids=sorted(set(product_ids))
    if not isinstance(choices,list) or any(not isinstance(s,str) or len(s)>100 for s in choices):raise ValueError('Choose valid segments.')
    allowed=identity.get('allowedSegments');restricted=allowed is not None
    if restricted:
        permitted={segment(s) for s in allowed}
        if choices and not set(choices).issubset(permitted):raise AccessDenied('PnL segment access denied.')
        choices=choices or sorted(permitted)
        if not choices:raise AccessDenied('No PnL segments have been granted.')
    from .product_catalog import read as products_read
    product_catalogue=products_read(store,actor)
    products=product_catalogue['products']
    if not set(product_ids).issubset({p['id'] for p in products}):raise AccessDenied('A selected product is unavailable for your segment access. Refresh the product list.')
    schema(store)
    with store.transaction() as db:
        store.require(db,actor)
        versions=[tuple(r) if store.sqlite else (r['id'],r['version']) for r in store.run(db,'SELECT id,version FROM stock_pnl_documents WHERE fy=? ORDER BY id',(fy,)).fetchall()]
        plan=store.run(db,"SELECT version,updated_at FROM datasets WHERE id='current'").fetchone()
        plan_version=(plan['version'],plan['updated_at']) if plan else None
    source_version=hashlib.sha256(json.dumps([REVISION,fy,versions,plan_version,product_catalogue['version']],sort_keys=True).encode()).hexdigest()
    if event.get('sourceVersion') and event['sourceVersion']!=source_version:raise ValueError('PnL sources changed. Load PnL before opening supporting records.')
    basis=event.get('basis','revenue');material_type=material_selection(event.get('materialType','all'))
    scope=sorted(set(choices))
    signature=hashlib.sha256(json.dumps([REVISION,fy,versions,plan_version,scope,restricted,sorted(permitted) if restricted else None,identity['role']=='admin',basis,material_type,product_ids,product_catalogue['version']],sort_keys=True).encode()).hexdigest()
    if event.get('snapshotVersion') and event['snapshotVersion']!=signature:raise ValueError('PnL sources changed since this statement was loaded. Load PnL before opening supporting records.')
    if not detail and not event.get('force'):
        with _lock:summary=copy.deepcopy(store._pnl_summaries.get(signature))
        if summary is None:
            with store.transaction() as db:
                store.require(db,actor)
                row=store.run(db,'SELECT payload FROM stock_pnl_summaries WHERE cache_key=?',(signature,)).fetchone()
            if row:
                summary=json.loads(gzip.decompress(base64.b64decode(row['payload'])))
                with _lock:
                    store._pnl_summaries[signature]=copy.deepcopy(summary)
                    while len(store._pnl_summaries)>16:store._pnl_summaries.popitem(last=False)
        if summary is not None:
            authorize(store,actor)
            if identity['role']=='admin':
                saved=read(store,actor,f'settings:{fy}')
                summary['settings']=saved if saved is not None else copy.deepcopy(DEFAULTS)
                summary['settingsVersion']=hashlib.sha256(json.dumps(saved,allow_nan=False,separators=(',',':')).encode()).hexdigest() if saved is not None else None
            return summary
    master=read(store,actor,f'master:{fy}')
    if not master:raise ValueError('Upload a cumulative PnL master for this financial year first.')
    salary=read(store,actor,f'salary:{fy}');stored_settings=read(store,actor,f'settings:{fy}');settings=stored_settings if stored_settings is not None else copy.deepcopy(DEFAULTS)
    current=planning_data(store,actor);dataset=(current or {}).get('data',{'sheets':[],'tables':[]})
    key=signature
    with _lock:cached=None if event.get('force') else store._pnl_results.get(key)
    if cached is None:
        result=calculate(master,salary,dataset,settings,choices,restricted,event.get('basis','revenue'),material_type,products,product_ids)
        if len(json.dumps(result))<4_000_000:
            with _lock:
                store._pnl_results[key]=copy.deepcopy(result)
                while len(store._pnl_results)>8:store._pnl_results.popitem(last=False)
    else:result=copy.deepcopy(cached)
    result['planningSource']={k:current.get(k) for k in ('filename','version','updated_at')} if current else None
    if detail:
        kind=event.get('kind')
        if kind=='salary' and identity['role']!='admin':raise AccessDenied('Individual employee compensation is administrator-only.')
        if kind not in result['details']:raise ValueError('Choose a valid PnL supporting table.')
        headers={'allocation':['Product ID','Product','Working segment','Total segment products','Allocated share'],'revenue':['Segment','SKU','Description','Customer','Quantity','UoM','Revenue'],'production':['Segment','Month','SKU','Description','Batch','Quantity','UoM','Recorded cost'],'rd':['Segment','Cost center','Description','R&D cost'],'salary':['Employee code','Employee name','Segment','Month','Monthly fixed CTC','Joining date','Leaving date','Eligible days','Assigned segments','Allocated cost'],'lead':result['leadHeaders'],'bom':['Segment','Period/date','SKU','Net transfer quantity','UoM','BOM Grand Total','BOM transfer cost','Movement scope'],'transfers':['Segment','Period/date','SKU','Net quantity','UoM','Std DP','Value','Movement scope']}[kind]
        authorize(store,actor)
        rows=result['details'][kind];offset=max(0,int(event.get('offset',0)));return {'headers':headers,'rows':rows[offset:offset+200],'total':len(rows),'offset':offset,'name':kind}
    result['productAllocation']={'headers':['Product ID','Product','Working segment','Total segment products','Allocated share'],'rows':result['details']['allocation']}
    result['selectedProducts']=[{'id':p['id'],'name':p['name']} for p in products if p['id'] in product_ids]
    result.pop('details');result.pop('leadHeaders')
    if restricted:result['segments']=[s for s in result['segments'] if s in permitted];result.pop('unmapped',None)
    elif identity['role']!='admin':result.pop('unmapped',None)
    result['sourceVersion']=source_version
    result['snapshotVersion']=signature
    result['calculatedAt']=time.time()
    # Persist compact, permission-scoped summaries only: never source or salary rows.
    raw=json.dumps(result,allow_nan=False,separators=(',',':')).encode()
    if len(raw)<=500_000:
        with store.transaction() as db:
            store.require(db,actor)
            store.run(db,'INSERT INTO stock_pnl_summaries VALUES(?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload,created_at=excluded.created_at',(signature,fy,base64.b64encode(gzip.compress(raw)).decode(),time.time()))
            store.run(db,'DELETE FROM stock_pnl_summaries WHERE cache_key NOT IN (SELECT cache_key FROM stock_pnl_summaries ORDER BY created_at DESC LIMIT 64)')
        with _lock:
            store._pnl_summaries[signature]=copy.deepcopy(result)
            while len(store._pnl_summaries)>16:store._pnl_summaries.popitem(last=False)
    if identity['role']=='admin':
        result['settings']=settings
        result['settingsVersion']=hashlib.sha256(json.dumps(stored_settings,allow_nan=False,separators=(',',':')).encode()).hexdigest() if stored_settings is not None else None
    authorize(store,actor)
    return result
def handle(store,actor,event):
    op=event['action'];authorize(store,actor)
    if op=='pnl_catalogue':return catalogue(store,actor)
    if op in ('pnl_report','pnl_detail'):return report(store,actor,event,op=='pnl_detail')
    authorize(store,actor,True)
    if op=='pnl_settings':
        fy=int(event.get('fy'));value=validate_settings(event.get('settings'));return save(store,actor,'settings',fy,'PnL assumptions',value,event.get('expected'))
    if op not in ('pnl_master_upload','pnl_salary_upload'):raise ValueError('Unknown PnL operation.')
    content=event.get('content','')
    if not isinstance(content,str) or len(content)>34_000_000:raise ValueError('Choose a workbook under 25 MB.')
    raw=base64.b64decode(content,validate=True);filename=str(event.get('filename','upload.xlsx'))
    value=read_master(raw,filename,event.get('start'),event.get('end')) if op=='pnl_master_upload' else read_salary(raw,filename,event.get('fy'))
    if value['fy']!=int(event.get('fy')):raise ValueError('Statement dates must match the selected financial year.')
    return save(store,actor,'master' if op=='pnl_master_upload' else 'salary',value['fy'],filename,value,event.get('expected'))
