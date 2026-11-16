"""One cached, permission-scoped allocation of stock across all upcoming plans."""
import hashlib,json,time
from collections import defaultdict
from decimal import Decimal
from .production_materials import availability,dec

REVISION=2
def signature(items):
    values=sorted((i['id'],i['revision'],i.get('materialCode'),i['row'][3:6]) for i in items)
    return hashlib.sha256(json.dumps([REVISION,values],sort_keys=True).encode()).hexdigest()
def schema(s,db):
    s.run(db,'CREATE TABLE IF NOT EXISTS production_batch_availability (scope TEXT PRIMARY KEY,version TEXT NOT NULL,uploaded_at DOUBLE PRECISION NOT NULL,signature TEXT NOT NULL,checked_at DOUBLE PRECISION NOT NULL,summary TEXT NOT NULL,payload TEXT NOT NULL)')
def metadata(s,db,scope,version,uploaded_at):
    schema(s,db)
    return s.run(db,'SELECT signature,checked_at,summary FROM production_batch_availability WHERE scope=? AND version=? AND uploaded_at=?',(scope,version,uploaded_at)).fetchone()
def summary(s,actor,current,items):
    with s.transaction() as db:
        s.require(db,actor,permission='menu_3')
        row=metadata(s,db,current.get('_scope','all'),current['version'],current['updated_at'])
    return json.loads(row['summary']) if row and row['signature']==signature(items) else None

def calculate(data,items):
    ordered=sorted(items,key=lambda i:(str(i['row'][4] or '9999'),str(i['row'][5] or '9999'),i['id']))
    grouped=defaultdict(list)
    for item in ordered:grouped[item.get('materialCode') or ''].append(item)
    requirements={};errors={};components={};unitsets=defaultdict(set)
    for code,plans in grouped.items():
        total=sum((dec(i['row'][3]) or Decimal(0) for i in plans),Decimal(0))
        try:
            if not code:raise ValueError('Select the FG/SFG material for this plan.')
            result=availability(data,code,float(total))
        except ValueError as exc:
            for item in plans:errors[item['id']]=str(exc)
            continue
        for row in result['rows']:
            component,name,unit,required,stock,_,status=row
            key=(component,unit);unitsets[component].add(unit)
            g=components.setdefault(key,{'name':name,'required':Decimal(0),'stock':dec(stock),'valid':True})
            if dec(stock) is None:g['stock']=None
            elif g['stock'] is not None:g['stock']=min(g['stock'],dec(stock))
            if dec(required) is None or status=='Cannot verify':g['valid']=False
            else:g['required']+=dec(required)
            for item in plans:
                amount=dec(required)*dec(item['row'][3])/total if dec(required) is not None else None
                requirements.setdefault(item['id'],{})[key]=amount
    for (component,_),g in components.items():
        if len(unitsets[component])>1:g['valid']=False
    remaining={k:g['stock'] for k,g in components.items()}
    plan_rows=[];statuses={}
    for priority,item in enumerate(ordered,1):
        needed=requirements.get(item['id'],{});unknown=[];short=[]
        for k,amount in needed.items():
            g=components[k]
            if amount is None or not g['valid'] or remaining[k] is None:unknown.append(k[0])
            elif amount>remaining[k]:short.append(k[0]+': '+str(amount-remaining[k])+' '+str(k[1]))
        status='Cannot verify' if errors.get(item['id']) or unknown or not needed else 'Material shortage' if short else 'Ready'
        if status=='Ready':
            for k,amount in needed.items():remaining[k]-=amount
        statuses[item['id']]=status
        plan_rows.append([priority,item['materialCode'] if item.get('materialCode') else item['row'][0],item['row'][2],item['row'][3],item['row'][4],item['row'][5],status,errors.get(item['id']) or ', '.join(unknown+short) or 'All components allocated'])
    issue_rows=[]
    for item in ordered:
        needed=requirements.get(item['id'],{})
        prefix=[item['id'],None,item.get('materialCode') or item['row'][0],item['row'][1],item['row'][2],item['row'][3],item['row'][4]]
        if not needed:
            issue_rows.append(prefix+[None,None,None,None,statuses[item['id']],errors.get(item['id']) or 'No component requirements could be verified.'])
        for (component,unit),amount in sorted(needed.items()):
            g=components[(component,unit)]
            issue_rows.append(prefix+[component,g['name'],unit,float(amount) if amount is not None else None,statuses[item['id']],'Requirement verified' if amount is not None and g['valid'] else 'Cannot verify availability; review BOM, stock and unit details.'])
    rows=[]
    for (component,unit),g in sorted(components.items()):
        known=g['valid'] and g['stock'] is not None
        shortage=max(g['required']-g['stock'],Decimal(0)) if known else None
        rows.append([component,g['name'],unit,float(g['required']) if g['valid'] else None,float(g['stock']) if g['stock'] is not None else None,float(shortage) if shortage is not None else None,'Available' if known and shortage==0 else 'Shortage' if known else 'Cannot verify'])
    return {'available':bool(items) and all(v=='Ready' for v in statuses.values()),'planStatuses':statuses,
        'planHeaders':['Priority','Material','Batch','Planned Quantity','Start Date','End Date','Status','Shortage / verification details'],'planRows':plan_rows,
        'issueHeaders':['Plan Reference','SAP Order','Product Code','Product Description','Product Batch','Planned Product Quantity','Start Date','Component Code','Component Description','Unit','Required Quantity','Plan Readiness','Verification'], 'issueRows':issue_rows,
        'headers':['Component','Description','Unit','Combined Required Quantity','Current Stock','Need to Order','Status'],'rows':rows,
        'explanation':'All permitted upcoming plans are checked, regardless of table filters. Shared component requirements are combined. Stock is allocated by start date, end date, then plan ID. A blocked plan consumes no stock. Current stock includes unrestricted and quality-inspection stock; on-order and future production are excluded. This is a snapshot simulation, not a stock reservation or recursive SFG explosion. Plans with unverifiable BOMs have incomplete combined demand; see plan errors before ordering.'}

def check(s,actor,event,archive=True):
    from .production import read,schema as production_schema
    with s.transaction() as db:
        s.require(db,actor,permission='menu_3')
        production_schema(s,db)
        initial_revisions=[dict(r) for r in s.run(db,"SELECT id,revision FROM production_shared WHERE kind='upcoming' ORDER BY id").fetchall()]
    report=read(s,actor,archive=archive)
    if event.get('version')!=report['version']:raise ValueError('The workbook changed. Refresh Production.')
    current=s.get_dataset(actor);items=report['upcoming'];sig=signature(items);scope=current.get('_scope','all')
    if current['version']!=report['version'] or current['updated_at']!=report['sourceStamp']:raise ValueError('The workbook changed. Refresh Production.')
    with s.transaction() as db:
        s.require(db,actor,permission='menu_3');schema(s,db)
        revisions=[dict(r) for r in s.run(db,"SELECT id,revision FROM production_shared WHERE kind='upcoming' ORDER BY id").fetchall()]
        if revisions!=initial_revisions:
            # Reading can archive plans that already have a matching SAP order.
            # Refuse a result for a set that changed while sources were read.
            raise ValueError('The upcoming plan list changed. Refresh Production and check again.')
        row=s.run(db,'SELECT payload FROM production_batch_availability WHERE scope=? AND version=? AND uploaded_at=? AND signature=?',(scope,current['version'],current['updated_at'],sig)).fetchone()
        if row:return json.loads(row['payload'])
    result=calculate(current['data'],items)
    result.update(version=current['version'],sourceStamp=current['updated_at'],signature=sig,checkedAt=time.time())
    compact={k:result[k] for k in ('available','planStatuses','version','sourceStamp','signature','checkedAt')}
    with s.transaction() as db:
        s.require(db,actor,permission='menu_3')
        master=s.run(db,"SELECT version,updated_at FROM datasets WHERE id='current'").fetchone()
        latest=[dict(r) for r in s.run(db,"SELECT id,revision FROM production_shared WHERE kind='upcoming' ORDER BY id").fetchall()]
        if (master['version'],master['updated_at'])!=(current['version'],current['updated_at']) or revisions!=latest:raise ValueError('The workbook or plans changed. Refresh Production and check again.')
        s.run(db,'INSERT INTO production_batch_availability VALUES(?,?,?,?,?,?,?) ON CONFLICT(scope) DO UPDATE SET version=excluded.version,uploaded_at=excluded.uploaded_at,signature=excluded.signature,checked_at=excluded.checked_at,summary=excluded.summary,payload=excluded.payload',(scope,current['version'],current['updated_at'],sig,result['checkedAt'],json.dumps(compact),json.dumps(result,allow_nan=False)))
    return result
